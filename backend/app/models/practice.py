"""Practice content: the grammar exercise bank and generated/personalised practice sets."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin


class GrammarExercise(CreatedAtMixin, Base):
    __tablename__ = "grammar_exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    seed_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    topic: Mapped[str] = mapped_column(String(40), index=True)  # matches mistake subcategories
    qtype: Mapped[str] = mapped_column(String(30))  # multiple_choice | gap_fill | error_correction | sentence_order | transformation
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSONB)
    answer: Mapped[str] = mapped_column(Text)
    accepted: Mapped[list] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    cefr: Mapped[str] = mapped_column(String(4), default="B1")
    source: Mapped[str] = mapped_column(String(20), default="seed")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class PracticeSet(TimestampMixin, Base):
    """A short, focused exercise set (grammar drill, mistake repair challenge, revision session...).

    `items` stores the full items including answers; API responses strip answers until submission.
    """

    __tablename__ = "practice_sets"
    __table_args__ = (Index("ix_practice_sets_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    why: Mapped[str] = mapped_column(Text, default="")
    focus: Mapped[str | None] = mapped_column(String(40))
    items: Mapped[list] = mapped_column(JSONB, default=list)
    mistake_ids: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | completed
    score: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float | None] = mapped_column(Float)
    results: Mapped[list] = mapped_column(JSONB, default=list)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=5)
    source: Mapped[str] = mapped_column(String(20), default="seed")
    completed_at: Mapped[datetime | None]
