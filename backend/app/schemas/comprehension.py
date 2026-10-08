"""Schemas shared by the Reading and Listening modules."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ActivityOutcome


class QuestionOut(BaseModel):
    id: int
    position: int
    qtype: str
    prompt: str
    options: list[str] | None
    word_limit: int | None


class QuestionResult(BaseModel):
    question_id: int
    qtype: str
    correct: bool
    your_answer: str
    answer: str
    explanation: str
    evidence: str
    evidence_paragraph: str | None = None
    note: str | None = None


class ReadingGenerateRequest(BaseModel):
    difficulty: int | None = Field(default=None, ge=1, le=5)
    topic: str | None = Field(default=None, max_length=60)
    question_count: int = Field(default=8, ge=3, le=14)
    time_limit_minutes: int = Field(default=20, ge=5, le=60)
    module: str | None = Field(default=None, pattern="^(academic|general_training)$")
    question_types: list[str] | None = Field(default=None, max_length=8)


class PassageOut(BaseModel):
    id: int
    title: str
    topic: str
    module: str
    difficulty: int
    paragraphs: list[dict]
    headings: list[str]
    word_count: int
    source: str


class ReadingAttemptOut(BaseModel):
    id: int
    status: str
    passage: PassageOut
    questions: list[QuestionOut]
    time_limit_minutes: int
    difficulty: int
    started_at: datetime
    submitted_at: datetime | None
    correct: int
    total: int
    accuracy: float | None
    band: float | None
    results: list[QuestionResult] = []
    answers: dict = {}
    notice: str | None = None
    spotlight: list[str] = []


class SubmitAnswersRequest(BaseModel):
    attempt_id: int
    answers: dict[str, str] = Field(default_factory=dict)
    time_spent_seconds: int = Field(default=0, ge=0, le=14400)
    replays: int | None = Field(default=None, ge=0, le=50)


class ReadingSubmitResponse(BaseModel):
    attempt: ReadingAttemptOut
    outcome: ActivityOutcome


class ListeningGenerateRequest(BaseModel):
    difficulty: int | None = Field(default=None, ge=1, le=5)
    topic: str | None = Field(default=None, max_length=60)
    scenario: str | None = Field(default=None, pattern="^(conversation|monologue|discussion|lecture)$")
    question_count: int = Field(default=6, ge=3, le=12)
    time_limit_minutes: int = Field(default=15, ge=5, le=45)
    accent: str | None = Field(default=None, pattern="^(british|american|australian)$")
    question_types: list[str] | None = Field(default=None, max_length=6)


class SegmentOut(BaseModel):
    index: int
    speaker: str
    text: str | None
    audio_url: str | None


class ScriptOut(BaseModel):
    id: int
    title: str
    topic: str
    scenario: str
    difficulty: int
    context: str
    speakers: list[dict]
    segments: list[SegmentOut]
    speech_rate: float
    accent: str
    audio_mode: str  # server | device
    transcript_hidden: bool
    source: str


class ListeningAttemptOut(BaseModel):
    id: int
    status: str
    script: ScriptOut
    questions: list[QuestionOut]
    time_limit_minutes: int
    difficulty: int
    started_at: datetime
    submitted_at: datetime | None
    correct: int
    total: int
    accuracy: float | None
    band: float | None
    replays: int
    results: list[QuestionResult] = []
    answers: dict = {}
    notice: str | None = None


class ListeningSubmitResponse(BaseModel):
    attempt: ListeningAttemptOut
    outcome: ActivityOutcome


class AttemptSummary(BaseModel):
    id: int
    title: str
    topic: str
    difficulty: int
    status: str
    correct: int
    total: int
    accuracy: float | None
    band: float | None
    started_at: datetime
    submitted_at: datetime | None
