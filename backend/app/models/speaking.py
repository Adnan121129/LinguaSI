"""Speaking mock tests: topic bank, sessions, per-turn transcripts and evaluations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin


class SpeakingTopic(CreatedAtMixin, Base):
    """Seed bank of original IELTS-style speaking material (Part 1 frames or Part 2 cue cards + Part 3)."""

    __tablename__ = "speaking_topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    seed_key: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(10))  # part1 | cue_card
    topic: Mapped[str] = mapped_column(String(80))
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    questions: Mapped[list] = mapped_column(JSONB, default=list)  # part 1 questions
    cue_card: Mapped[dict | None] = mapped_column(JSONB)  # {title, prompt, bullets, rounding_off}
    part3_questions: Mapped[list] = mapped_column(JSONB, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)


class SpeakingSession(TimestampMixin, Base):
    __tablename__ = "speaking_sessions"
    __table_args__ = (Index("ix_speaking_sessions_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(10), default="full")  # full | part1 | part2 | part3
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    topic: Mapped[str] = mapped_column(String(120), default="")
    plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    current_part: Mapped[int] = mapped_column(Integer, default=1)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    followups_asked: Mapped[int] = mapped_column(Integer, default=0)
    current_question: Mapped[dict] = mapped_column(JSONB, default=dict)
    target_expressions: Mapped[list] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    total_speaking_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    failure_reason: Mapped[str | None] = mapped_column(String(300))

    transcripts: Mapped[list[SpeakingTranscript]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="SpeakingTranscript.id")
    evaluation: Mapped[SpeakingEvaluation | None] = relationship(back_populates="session", uselist=False, cascade="all, delete-orphan")


class SpeakingTranscript(CreatedAtMixin, Base):
    __tablename__ = "speaking_transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("speaking_sessions.id", ondelete="CASCADE"), index=True)
    part: Mapped[int] = mapped_column(Integer)
    turn_index: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    is_followup: Mapped[bool] = mapped_column(Boolean, default=False)
    transcript: Mapped[str] = mapped_column(Text, default="")
    transcript_source: Mapped[str] = mapped_column(String(10), default="typed")  # stt | browser | typed
    audio_key: Mapped[str | None] = mapped_column(String(255))
    audio_mime: Mapped[str | None] = mapped_column(String(60))
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    stt_confidence: Mapped[float | None] = mapped_column(Float)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)

    session: Mapped[SpeakingSession] = relationship(back_populates="transcripts")


class SpeakingEvaluation(CreatedAtMixin, Base):
    __tablename__ = "speaking_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("speaking_sessions.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    overall_band: Mapped[float] = mapped_column(Float)
    fluency_coherence: Mapped[float] = mapped_column(Float)
    lexical_resource: Mapped[float] = mapped_column(Float)
    grammatical_range_accuracy: Mapped[float] = mapped_column(Float)
    pronunciation: Mapped[float | None] = mapped_column(Float)
    pronunciation_note: Mapped[str] = mapped_column(Text, default="")
    criteria_feedback: Mapped[dict] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    hesitation: Mapped[dict] = mapped_column(JSONB, default=dict)
    repeated_words: Mapped[list] = mapped_column(JSONB, default=list)
    fillers: Mapped[dict] = mapped_column(JSONB, default=dict)
    grammar_patterns: Mapped[list] = mapped_column(JSONB, default=list)
    errors: Mapped[list] = mapped_column(JSONB, default=list)
    strengths: Mapped[list] = mapped_column(JSONB, default=list)
    weaknesses: Mapped[list] = mapped_column(JSONB, default=list)
    recommendations: Mapped[list] = mapped_column(JSONB, default=list)
    expressions_used: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(60))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped[SpeakingSession] = relationship(back_populates="evaluation")
