from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ActivityOutcome


class StartSpeakingRequest(BaseModel):
    mode: str = Field(default="full", pattern="^(full|part1|part2|part3)$")


class TurnOut(BaseModel):
    part: int
    kind: str
    question: str
    examiner_text: str
    is_followup: bool
    cue_card: dict | None = None
    prep_seconds: int = 0
    max_seconds: int = 60
    index: int
    total: int


class TranscriptOut(BaseModel):
    id: int
    part: int
    turn_index: int
    question: str
    is_followup: bool
    transcript: str
    transcript_source: str
    duration_seconds: float
    word_count: int
    stt_confidence: float | None
    has_audio: bool
    audio_url: str | None
    metrics: dict
    created_at: datetime


class SpeakingEvaluationOut(BaseModel):
    id: int
    label: str = "AI Estimated Band"
    overall_band: float
    fluency_coherence: float
    lexical_resource: float
    grammatical_range_accuracy: float
    pronunciation: float | None
    pronunciation_note: str
    criteria_feedback: dict
    metrics: dict
    hesitation: dict
    repeated_words: list[dict]
    fillers: dict
    grammar_patterns: list[str]
    errors: list[dict]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    expressions_used: list[str]
    summary: str
    provider: str
    model: str
    is_mock: bool
    created_at: datetime
    disclaimer: str = "AI practice evaluation - not an official IELTS score."


class SpeakingSessionOut(BaseModel):
    id: int
    mode: str
    status: str
    topic: str
    current_part: int
    current_index: int
    total_turns: int
    target_expressions: list[str]
    started_at: datetime | None
    finished_at: datetime | None
    total_speaking_seconds: float
    failure_reason: str | None
    current_turn: TurnOut | None
    transcripts: list[TranscriptOut]
    evaluation: SpeakingEvaluationOut | None


class StartSpeakingResponse(BaseModel):
    session: SpeakingSessionOut
    turn: TurnOut
    speech: dict


class RespondResponse(BaseModel):
    transcript: TranscriptOut
    next: TurnOut | None
    done: bool


class FinishRequest(BaseModel):
    session_id: int


class FinishResponse(BaseModel):
    session: SpeakingSessionOut
    outcome: ActivityOutcome


class SpeakingSummary(BaseModel):
    id: int
    mode: str
    status: str
    topic: str
    overall_band: float | None
    responses: int
    total_speaking_seconds: float
    created_at: datetime
    finished_at: datetime | None
