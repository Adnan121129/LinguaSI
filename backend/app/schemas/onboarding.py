from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.core.clock import get_zone
from app.schemas.common import ActivityOutcome


class OnboardingRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    goal: str = Field(pattern="^(ielts|general)$")
    ielts_module: str = Field(default="academic", pattern="^(academic|general_training)$")
    self_reported_level: str = Field(pattern="^(beginner|elementary|intermediate|upper_intermediate|advanced)$")
    target_band: float = Field(default=6.5, ge=4.0, le=9.0)
    test_date: date | None = None
    daily_minutes: int = Field(default=30, ge=5, le=240)
    preferred_mode: str = Field(default="balanced", pattern="^(guided|balanced|exam)$")
    confidence: int = Field(default=3, ge=1, le=5)
    preferred_topics: list[str] = Field(default_factory=list, max_length=12)
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("target_band")
    @classmethod
    def _half(cls, v: float) -> float:
        if (v * 2) != int(v * 2):
            raise ValueError("Target band must be a whole or half band")
        return v

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        if v is not None and get_zone(v).key != v:
            raise ValueError("Unknown timezone")
        return v


class DiagnosticItemOut(BaseModel):
    id: str
    level: str | None = None
    qtype: str | None = None
    prompt: str
    options: list[str] | None = None


class DiagnosticStartResponse(BaseModel):
    attempt_id: int
    vocabulary: list[DiagnosticItemOut]
    grammar: list[DiagnosticItemOut]
    reading: dict
    listening: dict
    writing: dict
    speaking: list[dict]
    started_at: datetime


class SpeakingSample(BaseModel):
    id: str = Field(max_length=10)
    transcript: str = Field(max_length=4000)
    duration_seconds: float | None = Field(default=None, ge=0, le=600)
    source: str = Field(default="typed", pattern="^(browser|typed|device)$")


class DiagnosticSubmitRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)
    writing: str = Field(default="", max_length=8000)
    speaking: list[SpeakingSample] = Field(default_factory=list, max_length=4)


class DiagnosticSection(BaseModel):
    key: str
    label: str
    score: float | None
    band: float | None
    correct: int | None = None
    total: int | None = None
    note: str | None = None


class DiagnosticResult(BaseModel):
    attempt_id: int
    label: str = "Estimated IELTS Readiness"
    estimated_cefr: str | None
    estimated_band: float | None
    confidence: str
    sections: list[DiagnosticSection]
    strengths: list[str]
    focus_areas: list[str]
    writing_feedback: dict | None
    next_steps: list[dict]
    disclaimer: str = (
        "This is an AI estimated level from a short practice diagnostic. It is not an official IELTS result and it will become more accurate as you practise."
    )
    completed_at: datetime | None
    outcome: ActivityOutcome | None = None
