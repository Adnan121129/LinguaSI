"""Application settings loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-insecure-secret-change-me-0123456789abcdef"

# Default model names per provider and tier. Every value can be overridden with
# AI_MODEL_FAST / AI_MODEL_STRONG so the application never needs code changes when
# a provider renames or releases models.
PROVIDER_DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "anthropic": {"fast": "claude-haiku-5-5", "strong": "claude-opus-5-5"},
    "openai": {"fast": "gpt-5-mini", "strong": "gpt-5"},
    "gemini": {"fast": "gemini-2.5-flash", "strong": "gemini-2.5-pro"},
    "mock": {"fast": "mock-fast", "strong": "mock-strong"},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # The repository's root .env, then backend/.env (which wins). Real environment variables beat both.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        # An empty value (KEY=) means "use the default", so the .env templates can list every key.
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -------------------------------------------------------
    app_name: str = "LinguaSI"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- Database ----------------------------------------------------------
    database_url: str = "postgresql+psycopg://linguasi:linguasi@localhost:5432/linguasi"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # --- Auth --------------------------------------------------------------
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    # Comma-separated in the environment (ADMIN_EMAILS=a@x.com,b@y.com); a JSON list also works.
    admin_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- HTTP --------------------------------------------------------------
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8081",
            "http://localhost:19006",
        ]
    )
    rate_limit_enabled: bool = True
    redis_url: str | None = None

    # --- AI ----------------------------------------------------------------
    ai_provider: Literal["mock", "anthropic", "openai", "gemini"] = "mock"
    ai_mock_mode: bool = True
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    ai_model_fast: str | None = None
    ai_model_strong: str | None = None
    ai_effort_fast: Literal["low", "medium", "high"] = "low"
    ai_effort_strong: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    ai_timeout_seconds: float = 90.0
    ai_max_retries: int = 2
    ai_repair_attempts: int = 1
    anthropic_server_fallback: bool = True
    ai_log_content: bool = False
    ai_user_hourly_limit: int = 80

    # --- Speech ------------------------------------------------------------
    stt_provider: Literal["mock", "openai"] = "mock"
    tts_provider: Literal["mock", "openai"] = "mock"
    openai_stt_model: str = "whisper-1"
    openai_tts_model: str = "gpt-4o-mini-tts"
    max_audio_upload_mb: int = 15

    # --- Storage -----------------------------------------------------------
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: str = "./storage"
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # --- Content -----------------------------------------------------------
    seed_dir: str | None = None  # defaults to <repo>/database/seed
    auto_seed: bool = True  # load seed content on startup when the content tables are empty

    @field_validator("cors_origins", "admin_emails", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        if self.environment == "production" and (self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32):
            raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters in production")
        return self

    # --- Derived helpers ---------------------------------------------------
    def provider_key(self, provider: str) -> str | None:
        return {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
        }.get(provider)

    @property
    def effective_ai_provider(self) -> str:
        """The provider actually used. Falls back to the mock provider when mock mode is on or no key exists."""
        if self.ai_mock_mode or self.ai_provider == "mock":
            return "mock"
        if not self.provider_key(self.ai_provider):
            return "mock"
        return self.ai_provider

    @property
    def ai_is_mock(self) -> bool:
        return self.effective_ai_provider == "mock"

    def model_for_tier(self, tier: str) -> str:
        provider = self.effective_ai_provider
        if tier == "fast" and self.ai_model_fast and provider != "mock":
            return self.ai_model_fast
        if tier == "strong" and self.ai_model_strong and provider != "mock":
            return self.ai_model_strong
        return PROVIDER_DEFAULT_MODELS[provider][tier]

    @property
    def effective_stt_provider(self) -> str:
        if self.stt_provider == "openai" and self.openai_api_key:
            return "openai"
        return "mock"

    @property
    def effective_tts_provider(self) -> str:
        if self.tts_provider == "openai" and self.openai_api_key:
            return "openai"
        return "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
