from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ActivityOutcome


class LabSection(BaseModel):
    key: str
    title: str
    description: str
    route: str
    count: int | None = None


class DailyPhrase(BaseModel):
    phrase: str
    meaning: str
    example: str
    day: str


class LabOverview(BaseModel):
    goal: str
    sections: list[LabSection]
    daily_phrase: DailyPhrase


class PronunciationSet(BaseModel):
    focus: str
    title: str
    sentences: list[str]


class Scenario(BaseModel):
    id: str
    title: str
    level: str
    ai_role: str
    goal: str
    phrases: list[str]


class PronunciationCheckRequest(BaseModel):
    sentence: str = Field(min_length=2, max_length=300)
    transcript: str = Field(min_length=1, max_length=600)
    duration_seconds: float | None = Field(default=None, ge=0, le=300)


class PronunciationCheckResult(BaseModel):
    match: float
    matched_words: int
    total_words: int
    missing_words: list[str]
    unexpected_words: list[str]
    tip: str
    note: str
    outcome: ActivityOutcome
