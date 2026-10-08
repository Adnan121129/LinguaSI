"""IELTS-style and general writing: tasks, submissions, evaluations and error annotations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin


class WritingTask(CreatedAtMixin, Base):
    __tablename__ = "writing_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_type: Mapped[str] = mapped_column(String(10))  # task1 | task2 | general
    module: Mapped[str] = mapped_column(String(20))  # academic | general_training | general_english
    category: Mapped[str] = mapped_column(String(40))  # line_graph, opinion, formal_letter, ...
    topic: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text, default="")
    visual: Mapped[dict | None] = mapped_column(JSONB)  # chart / table / process data for Task 1
    key_points: Mapped[list] = mapped_column(JSONB, default=list)  # what a strong answer should cover
    min_words: Mapped[int] = mapped_column(Integer, default=250)
    time_limit_minutes: Mapped[int] = mapped_column(Integer, default=40)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    source: Mapped[str] = mapped_column(String(20), default="seed")  # seed | ai | template
    seed_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    created_for_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class WritingSubmission(TimestampMixin, Base):
    __tablename__ = "writing_submissions"
    __table_args__ = (Index("ix_writing_submissions_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    task_id: Mapped[int] = mapped_column(ForeignKey("writing_tasks.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(10), default="tutor")  # tutor | exam
    content: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | submitted | evaluated | evaluation_failed
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    tutor_notes: Mapped[list] = mapped_column(JSONB, default=list)  # hint exchanges during tutor mode
    failure_reason: Mapped[str | None] = mapped_column(String(300))
    autosaved_at: Mapped[datetime | None]
    submitted_at: Mapped[datetime | None]
    evaluated_at: Mapped[datetime | None]

    task: Mapped[WritingTask] = relationship(lazy="joined")
    evaluation: Mapped[WritingEvaluation | None] = relationship(back_populates="submission", uselist=False, cascade="all, delete-orphan")


class WritingEvaluation(CreatedAtMixin, Base):
    __tablename__ = "writing_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("writing_submissions.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    overall_band: Mapped[float] = mapped_column(Float)
    task_response: Mapped[float] = mapped_column(Float)  # Task Achievement for Task 1
    coherence_cohesion: Mapped[float] = mapped_column(Float)
    lexical_resource: Mapped[float] = mapped_column(Float)
    grammatical_range_accuracy: Mapped[float] = mapped_column(Float)
    criteria_feedback: Mapped[dict] = mapped_column(JSONB, default=dict)
    strengths: Mapped[list] = mapped_column(JSONB, default=list)
    weaknesses: Mapped[list] = mapped_column(JSONB, default=list)
    task_response_issues: Mapped[list] = mapped_column(JSONB, default=list)
    cohesion_issues: Mapped[list] = mapped_column(JSONB, default=list)
    vocabulary_issues: Mapped[list] = mapped_column(JSONB, default=list)
    advice: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    recommended_exercise: Mapped[dict] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(60))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)

    submission: Mapped[WritingSubmission] = relationship(back_populates="evaluation")
    errors: Mapped[list[WritingError]] = relationship(back_populates="evaluation", cascade="all, delete-orphan", order_by="WritingError.start_offset")


class WritingError(Base):
    __tablename__ = "writing_errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("writing_evaluations.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("writing_submissions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mistake_id: Mapped[int | None] = mapped_column(ForeignKey("mistakes.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(30))
    subcategory: Mapped[str] = mapped_column(String(40))
    original: Mapped[str] = mapped_column(Text)
    corrected: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    repeated: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(10), default="ai")  # ai | rules

    evaluation: Mapped[WritingEvaluation] = relationship(back_populates="errors")
