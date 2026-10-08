"""Reading practice: generated/seeded passages, questions with answer keys, and learner attempts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.models.base import Base, CreatedAtMixin


class ReadingPassage(CreatedAtMixin, Base):
    __tablename__ = "reading_passages"

    id: Mapped[int] = mapped_column(primary_key=True)
    seed_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(60), index=True)
    module: Mapped[str] = mapped_column(String(20), default="academic")  # academic | general_training
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    paragraphs: Mapped[list] = mapped_column(JSONB, default=list)  # [{label, text}]
    headings: Mapped[list] = mapped_column(JSONB, default=list)  # options for matching-headings questions
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=15)
    target_vocabulary: Mapped[list] = mapped_column(JSONB, default=list)
    quality: Mapped[dict] = mapped_column(JSONB, default=dict)  # validation report
    source: Mapped[str] = mapped_column(String(20), default="seed")  # seed | ai
    created_for_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    questions: Mapped[list[ReadingQuestion]] = relationship(back_populates="passage", cascade="all, delete-orphan", order_by="ReadingQuestion.position")


class ReadingQuestion(Base):
    __tablename__ = "reading_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    passage_id: Mapped[int] = mapped_column(ForeignKey("reading_passages.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    qtype: Mapped[str] = mapped_column(String(30))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSONB)
    answer: Mapped[str] = mapped_column(String(300))
    accepted: Mapped[list] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    evidence_paragraph: Mapped[str | None] = mapped_column(String(4))
    word_limit: Mapped[int | None] = mapped_column(Integer)

    passage: Mapped[ReadingPassage] = relationship(back_populates="questions")


class ReadingAttempt(Base):
    __tablename__ = "reading_attempts"
    __table_args__ = (Index("ix_reading_attempts_user_started", "user_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    passage_id: Mapped[int] = mapped_column(ForeignKey("reading_passages.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress | submitted
    question_ids: Mapped[list] = mapped_column(JSONB, default=list)
    time_limit_minutes: Mapped[int] = mapped_column(Integer, default=20)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    results: Mapped[list] = mapped_column(JSONB, default=list)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float | None] = mapped_column(Float)
    band: Mapped[float | None] = mapped_column(Float)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    submitted_at: Mapped[datetime | None]

    passage: Mapped[ReadingPassage] = relationship(lazy="joined")
