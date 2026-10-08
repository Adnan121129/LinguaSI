"""Shared test fixtures.

Tests run against a real PostgreSQL database (default: linguasi_test on localhost; override with
TEST_DATABASE_URL). The schema is built with the Alembic migrations, curated content is seeded
once per session, and learner data is removed after every test. AI runs in Mock AI Mode unless a
test swaps in a failing provider.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://linguasi:linguasi@localhost:5432/linguasi_test")
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "AI_PROVIDER": "mock",
        "AI_MOCK_MODE": "true",
        "STT_PROVIDER": "mock",
        "TTS_PROVIDER": "mock",
        "AUTO_SEED": "false",
        "REDIS_URL": "",
        "RATE_LIMIT_ENABLED": "true",
        "ADMIN_EMAILS": "admin@example.com",
        "STORAGE_BACKEND": "local",
        "STORAGE_LOCAL_DIR": tempfile.mkdtemp(prefix="linguasi-test-storage-"),
        "LOG_LEVEL": "WARNING",
    }
)
for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
    os.environ.pop(key, None)

import pytest  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.ai.client import ai_client  # noqa: E402
from app.ai.providers.base import AIProviderError, AIRequest, AIResult  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.seed.loader import load_all  # noqa: E402
from app.services import vocabulary_service  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONTENT_TABLES = ("vocabulary_items", "grammar_exercises", "reading_passages", "listening_scripts", "writing_tasks", "speaking_topics")


def _ensure_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = sa.create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.scalar(sa.text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}):
            conn.execute(sa.text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    _ensure_database()
    with engine.begin() as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    with SessionLocal() as db:
        load_all(db)
    yield
    engine.dispose()


def _reset_state() -> None:
    ai_client.set_provider(None)
    limiter.reset()
    vocabulary_service._EXPLAIN_CACHE.clear()
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM users"))
        conn.execute(sa.text("DELETE FROM ai_interaction_logs"))
        conn.execute(sa.text("DELETE FROM system_logs"))
        for table in ("reading_passages", "listening_scripts", "writing_tasks"):
            conn.execute(sa.text(f"DELETE FROM {table} WHERE seed_key IS NULL"))
        conn.execute(sa.text("DELETE FROM vocabulary_items WHERE source = 'admin'"))
        edited = 0
        for table in CONTENT_TABLES:
            conn.execute(sa.text(f"UPDATE {table} SET is_active = true WHERE NOT is_active"))
            if table != "speaking_topics":
                edited += conn.execute(sa.text(f"UPDATE {table} SET source = 'seed' WHERE source = 'edited'")).rowcount
    if edited:
        with SessionLocal() as db:
            load_all(db)


@pytest.fixture(autouse=True)
def clean_state() -> Iterator[None]:
    yield
    _reset_state()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@dataclass
class Learner:
    """A registered user plus a thin authenticated wrapper around the test client."""

    client: TestClient
    email: str
    password: str
    tokens: dict
    user: dict

    @property
    def id(self) -> int:
        return self.user["id"]

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def get(self, url: str, **kwargs):
        return self.client.get(url, headers=self.headers, **kwargs)

    def post(self, url: str, **kwargs):
        return self.client.post(url, headers=self.headers, **kwargs)

    def put(self, url: str, **kwargs):
        return self.client.put(url, headers=self.headers, **kwargs)

    def patch(self, url: str, **kwargs):
        return self.client.patch(url, headers=self.headers, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.client.delete(url, headers=self.headers, **kwargs)


ONBOARDING = {
    "goal": "ielts",
    "ielts_module": "academic",
    "self_reported_level": "intermediate",
    "target_band": 7.0,
    "daily_minutes": 30,
    "preferred_mode": "balanced",
    "confidence": 3,
    "preferred_topics": ["technology", "education"],
    "timezone": "Asia/Dhaka",
}


@pytest.fixture
def make_learner(client: TestClient):
    def factory(*, name: str = "Test Learner", email: str | None = None, password: str = "secret-pass-1", onboard: bool = False) -> Learner:
        email = email or f"learner-{uuid.uuid4().hex[:10]}@example.com"
        response = client.post("/auth/register", json={"email": email, "password": password, "name": name})
        assert response.status_code == 201, response.text
        body = response.json()
        learner = Learner(client=client, email=email, password=password, tokens=body, user=body["user"])
        if onboard:
            r = learner.post("/onboarding", json=ONBOARDING)
            assert r.status_code == 200, r.text
            learner.user = r.json()
        return learner

    return factory


@pytest.fixture
def learner(make_learner) -> Learner:
    return make_learner()


@pytest.fixture
def onboarded(make_learner) -> Learner:
    return make_learner(onboard=True)


class FailingProvider:
    """Simulates an AI outage: every request fails like a provider error would."""

    name = "failing"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, request: AIRequest) -> AIResult:
        self.calls.append(request.task)
        raise AIProviderError("Simulated provider outage")


@pytest.fixture
def ai_outage() -> Iterator[FailingProvider]:
    provider = FailingProvider()
    ai_client.set_provider(provider)
    yield provider
    ai_client.set_provider(None)
