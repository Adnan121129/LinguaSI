from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.clock import get_zone
from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("Password must contain at least one letter and one number")
        return value

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=200)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=200)


class ProfileOut(ORMModel):
    goal: str
    ielts_module: str
    self_reported_level: str
    target_band: float
    test_date: date | None
    daily_minutes: int
    preferred_mode: str
    confidence: int
    preferred_topics: list[str]
    theme: str
    timezone: str
    keep_recordings: bool
    onboarding_completed: bool
    diagnostic_completed: bool
    estimated_cefr: str | None
    estimated_band: float | None
    band_confidence: float


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    role: str
    is_demo: bool
    created_at: datetime
    profile: ProfileOut


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    goal: str | None = Field(default=None, pattern="^(ielts|general)$")
    ielts_module: str | None = Field(default=None, pattern="^(academic|general_training)$")
    self_reported_level: str | None = Field(default=None, pattern="^(beginner|elementary|intermediate|upper_intermediate|advanced)$")
    target_band: float | None = Field(default=None, ge=4.0, le=9.0)
    test_date: date | None = None
    clear_test_date: bool = False
    daily_minutes: int | None = Field(default=None, ge=5, le=240)
    preferred_mode: str | None = Field(default=None, pattern="^(guided|balanced|exam)$")
    confidence: int | None = Field(default=None, ge=1, le=5)
    preferred_topics: list[str] | None = Field(default=None, max_length=12)
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")
    timezone: str | None = Field(default=None, max_length=64)
    keep_recordings: bool | None = None

    @field_validator("target_band")
    @classmethod
    def _half_band(cls, value: float | None) -> float | None:
        if value is not None and (value * 2) != int(value * 2):
            raise ValueError("Target band must be a whole or half band (e.g. 6.5)")
        return value

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, value: str | None) -> str | None:
        if value is not None and get_zone(value).key != value:
            raise ValueError("Unknown timezone")
        return value

    @field_validator("preferred_topics")
    @classmethod
    def _topics(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [t.strip().lower()[:40] for t in value if t and t.strip()]


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _strength(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("Password must contain at least one letter and one number")
        return value


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
