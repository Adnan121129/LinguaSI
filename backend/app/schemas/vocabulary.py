from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ActivityOutcome, ORMModel


class VocabularyItemOut(ORMModel):
    id: int
    word: str
    part_of_speech: str
    definition: str
    example: str
    extra_examples: list[str]
    synonyms: list[str]
    antonyms: list[str]
    collocations: list[str]
    word_family: dict
    topics: list[str]
    cefr: str
    is_academic: bool
    is_phrase: bool


class ExerciseOut(BaseModel):
    id: str
    user_vocab_id: int
    item_id: int
    word: str | None
    state: str
    type: str
    prompt: str
    options: list[str] | None
    hint: str | None
    input: str
    reason: str | None = None
    reason_detail: str | None = None
    is_new: bool = False


class TodayResponse(BaseModel):
    exercises: list[ExerciseOut]
    due_count: int
    new_count: int
    counts: dict[str, int]
    retention: dict
    started_at: datetime


class ReviewRequest(BaseModel):
    exercise_id: str = Field(max_length=60)
    answer: str = Field(default="", max_length=500)
    response_ms: int | None = Field(default=None, ge=0, le=600000)
    hinted: bool = False


class ReviewResponse(BaseModel):
    correct: bool
    correct_answer: str
    feedback: str | None
    state_before: str
    state_after: str
    next_review_at: datetime
    item: VocabularyItemOut
    xp_gained: int
    mission_progress: list[str]


class CompleteSessionRequest(BaseModel):
    started_at: datetime
    duration_seconds: int = Field(default=0, ge=0, le=14400)


class CompleteSessionResponse(BaseModel):
    reviews: int
    correct: int
    accuracy: float | None
    outcome: ActivityOutcome | None


class UserWordOut(BaseModel):
    user_vocab_id: int
    item: VocabularyItemOut
    state: str
    correct_count: int
    incorrect_count: int
    due_at: datetime
    last_reviewed_at: datetime | None
    used_in_writing: int
    used_in_speaking: int
    reason: str
    reason_detail: str | None
    classification: str


class AddWordRequest(BaseModel):
    item_id: int


class ExplainResponse(BaseModel):
    explanation: str
    examples: list[str]
    common_mistake: str
    usage_tip: str
    is_mock: bool
