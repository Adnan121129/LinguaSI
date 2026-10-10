import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import Settings, settings
from app.core.rate_limit import client_ip

SECRET = "a-long-random-shared-secret-0123456789"


def _request(headers: dict[str, str], peer: str = "10.0.0.5") -> Request:
    return Request({"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()], "client": (peer, 4321)})


def test_hosting_provider_database_urls_use_the_psycopg_driver():
    assert Settings(database_url="postgres://u:p@db.example.com:5432/app?sslmode=require").database_url == (
        "postgresql+psycopg://u:p@db.example.com:5432/app?sslmode=require"
    )
    assert Settings(database_url="postgresql://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(database_url="postgresql+psycopg://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"


def test_the_session_secret_can_come_from_a_file(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    secret_file = tmp_path / "jwt-secret"
    secret_file.write_text("f" * 64 + "\n")
    monkeypatch.setenv("JWT_SECRET_FILE", str(secret_file))
    assert Settings(_env_file=None, environment="production").jwt_secret == "f" * 64
    # JWT_SECRET wins over the file.
    assert Settings(_env_file=None, jwt_secret="j" * 40).jwt_secret == "j" * 40
    # A missing or empty file is no secret: production refuses to start without one.
    secret_file.write_text("")
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, environment="production")
    monkeypatch.setenv("JWT_SECRET_FILE", str(tmp_path / "missing"))
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, environment="production")


def test_production_requires_a_long_proxy_secret():
    with pytest.raises(ValidationError, match="PROXY_SHARED_SECRET"):
        Settings(environment="production", jwt_secret="j" * 40, proxy_shared_secret="short")
    assert Settings(environment="production", jwt_secret="j" * 40, proxy_shared_secret=SECRET).proxy_shared_secret == SECRET


def test_only_the_web_server_holding_the_secret_can_report_a_learner_address(monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", SECRET)
    vouched = {"X-LinguaSI-Proxy-Secret": SECRET, "X-LinguaSI-Client-IP": "203.0.113.7"}
    assert client_ip(_request(vouched)) == "203.0.113.7"
    assert client_ip(_request({**vouched, "X-LinguaSI-Proxy-Secret": SECRET[:-1]})) == "10.0.0.5"
    assert client_ip(_request({"X-LinguaSI-Client-IP": "203.0.113.7"})) == "10.0.0.5"
    assert client_ip(_request({**vouched, "X-LinguaSI-Client-IP": "203.0.113.7; DROP"})) == "10.0.0.5"
    assert client_ip(_request({"X-Forwarded-For": "203.0.113.7"})) == "10.0.0.5"


def test_reported_addresses_are_ignored_when_no_secret_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", None)
    assert client_ip(_request({"X-LinguaSI-Proxy-Secret": "", "X-LinguaSI-Client-IP": "203.0.113.7"})) == "10.0.0.5"
