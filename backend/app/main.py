"""FastAPI application factory for the LinguaSI API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.seed.loader import ensure_seed_content

logger = logging.getLogger("linguasi")

DESCRIPTION = """
**LinguaSI — Super Intelligent English & IELTS Learning Platform.**

A shared REST API used by the web and mobile apps. All learner-facing scores are
*AI Estimated* practice indicators — never official IELTS results.

Authenticate with `POST /auth/login` (or `/auth/register`) and send the returned
`access_token` as `Authorization: Bearer <token>`. Rotate it with `POST /auth/refresh`.

Errors always use the shape `{"error": {"code", "message", "details?", "request_id"}}`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info(
        "Starting LinguaSI API (env=%s, ai_provider=%s, mock=%s, stt=%s, tts=%s)",
        settings.environment,
        settings.effective_ai_provider,
        settings.ai_is_mock,
        settings.effective_stt_provider,
        settings.effective_tts_provider,
    )
    if not settings.ai_mock_mode and settings.ai_provider != "mock" and settings.ai_is_mock:
        logger.warning("AI_PROVIDER=%s but no API key is configured; using the mock AI provider", settings.ai_provider)
    if settings.auto_seed and settings.environment != "test":
        try:
            ensure_seed_content()
        except Exception:
            logger.exception("Automatic seed loading failed; run `python -m app.cli seed` manually")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="LinguaSI API",
        version="1.0.0",
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "auth", "description": "Registration, login and token rotation"},
            {"name": "me", "description": "Current user, preferences and account"},
            {"name": "onboarding", "description": "Onboarding and diagnostic assessment"},
            {"name": "dashboard", "description": "Personalised dashboard"},
            {"name": "writing", "description": "IELTS-style writing tutor and examiner"},
            {"name": "speaking", "description": "Speaking mock tests"},
            {"name": "vocabulary", "description": "Adaptive vocabulary engine"},
            {"name": "reading", "description": "Reading practice generator"},
            {"name": "listening", "description": "Listening practice generator"},
            {"name": "mistakes", "description": "Personal mistake tracker"},
            {"name": "practice", "description": "Focused practice sets (grammar drills, repair challenges)"},
            {"name": "progress", "description": "Progress analytics"},
            {"name": "gamification", "description": "Achievements, missions and challenges"},
            {"name": "recommendations", "description": "SI recommendations with explanations"},
            {"name": "tutor", "description": "SI Tutor conversations"},
            {"name": "lab", "description": "English Lab content"},
            {"name": "admin", "description": "Development/admin panel"},
            {"name": "system", "description": "Health and runtime metadata"},
        ],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
