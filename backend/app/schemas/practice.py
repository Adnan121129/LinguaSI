from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ActivityOutcome


class MistakeOut(BaseModel):
    id: int
    source: str
    category: str
    category_label: str
    subcategory: str
    label: str
    original: str
    corrected: str
    explanation: str
    context: str | None
    severity: str
    occurrences: int
    repeated: bool
    status: str
    practice_attempts: int
    practice_correct: int
    revisit_at: datetime | None
    mastered_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime


class MistakeDetail(MistakeOut):
    guide: dict | None
    related: list[MistakeOut]


class MistakeStatusRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(mastered|unresolved)$")
    revisit_in_days: int | None = Field(default=None, ge=1, le=60)


class PracticeItemOut(BaseModel):
    id: str
    qtype: str
    prompt: str
    options: list[str] | None
    source: str
    mistake_id: int | None = None


class PracticeResultItem(BaseModel):
    id: str
    correct: bool
    your_answer: str
    answer: str
    explanation: str


class PracticeSetOut(BaseModel):
    id: int
    kind: str
    title: str
    description: str
    why: str
    focus: str | None
    status: str
    items: list[PracticeItemOut]
    total: int
    score: int
    accuracy: float | None
    estimated_minutes: int
    results: list[PracticeResultItem] = []
    created_at: datetime
    completed_at: datetime | None


class CreatePracticeRequest(BaseModel):
    focus: str = Field(min_length=2, max_length=40)
    kind: str = Field(default="grammar_drill", pattern="^(grammar_drill|mistake_repair|revision|collocation_drill|argument_builder)$")
    mistake_ids: list[int] | None = Field(default=None, max_length=10)
    item_count: int = Field(default=8, ge=3, le=15)


class SubmitPracticeRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)
    duration_seconds: int = Field(default=0, ge=0, le=7200)


class SubmitPracticeResponse(BaseModel):
    practice: PracticeSetOut
    mastered_mistakes: list[int]
    outcome: ActivityOutcome
