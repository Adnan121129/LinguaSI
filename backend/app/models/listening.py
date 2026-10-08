"""Listening practice: multi-speaker scripts (with optional synthesized audio), questions and attempts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.models.base import Base, CreatedAtMixin


class ListeningScript(CreatedAtMixin, Base):
    __tablename__ = "listening_scripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    seed_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(60), index=True)
    scenario: Mapped[str] = mapped_column(String(20), default="conversation")  # conversation | monologue | discussion | lecture
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    speakers: Mapped[list] = mapped_column(JSONB, default=list)  # [{id, name, role, voice, accent}]
    segments: Mapped[list] = mapped_column(JSONB, default=list)  # [{speaker, text}]
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    speech_rate: Mapped[float] = mapped_column(Float, default=1.0)
    accent: Mapped[str] = mapped_column(String(20), default="british")
    context: Mapped[str] = mapped_column(Text, default="")  # short scene-setting shown before listening
    audio_status: Mapped[str] = mapped_column(String(10), default="none")  # none | ready | failed
    audio: Mapped[list] = mapped_column(JSONB, default=list)  # [{segment, key, mime}]
    quality: Mapped[dict] = mapped_column(JSONB, default=dict)
    target_vocabulary: Mapped[list] = mapped_column(JSONB, default=list)
    source: Mapped[str] = mapped_column(String(20), default="seed")
    created_for_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    questions: Mapped[list[ListeningQuestion]] = relationship(back_populates="script", cascade="all, delete-orphan", order_by="ListeningQuestion.position")


class ListeningQuestion(Base):
    __tablename__ = "listening_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("listening_scripts.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    qtype: Mapped[str] = mapped_column(String(30))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSONB)
    answer: Mapped[str] = mapped_column(String(300))
    accepted: Mapped[list] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    word_limit: Mapped[int | None] = mapped_column(Integer)

    script: Mapped[ListeningScript] = relationship(back_populates="questions")


class ListeningAttempt(Base):
    __tablename__ = "listening_attempts"
    __table_args__ = (Index("ix_listening_attempts_user_started", "user_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    script_id: Mapped[int] = mapped_column(ForeignKey("listening_scripts.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    question_ids: Mapped[list] = mapped_column(JSONB, default=list)
    time_limit_minutes: Mapped[int] = mapped_column(Integer, default=15)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    results: Mapped[list] = mapped_column(JSONB, default=list)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float | None] = mapped_column(Float)
    band: Mapped[float | None] = mapped_column(Float)
    replays: Mapped[int] = mapped_column(Integer, default=0)
    transcript_viewed: Mapped[bool] = mapped_column(Boolean, default=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    submitted_at: Mapped[datetime | None]

    script: Mapped[ListeningScript] = relationship(lazy="joined")
