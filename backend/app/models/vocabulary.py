"""Vocabulary bank, per-learner word states (spaced repetition) and review history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.models.base import Base, CreatedAtMixin

VOCAB_STATES = ("new", "learning", "familiar", "strong", "mastered")


class VocabularyItem(CreatedAtMixin, Base):
    __tablename__ = "vocabulary_items"
    __table_args__ = (UniqueConstraint("word", "part_of_speech"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(80), index=True)
    part_of_speech: Mapped[str] = mapped_column(String(20))
    definition: Mapped[str] = mapped_column(Text)
    example: Mapped[str] = mapped_column(Text)
    extra_examples: Mapped[list] = mapped_column(JSONB, default=list)
    synonyms: Mapped[list] = mapped_column(JSONB, default=list)
    antonyms: Mapped[list] = mapped_column(JSONB, default=list)
    collocations: Mapped[list] = mapped_column(JSONB, default=list)
    word_family: Mapped[dict] = mapped_column(JSONB, default=dict)  # {noun, verb, adjective, adverb}
    topics: Mapped[list] = mapped_column(JSONB, default=list)
    cefr: Mapped[str] = mapped_column(String(4), default="B2")
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    is_academic: Mapped[bool] = mapped_column(Boolean, default=False)
    is_phrase: Mapped[bool] = mapped_column(Boolean, default=False)  # multi-word collocation / expression
    source: Mapped[str] = mapped_column(String(20), default="seed")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")  # hidden from learners when False


class UserVocabulary(Base):
    __tablename__ = "user_vocabulary"
    __table_args__ = (
        UniqueConstraint("user_id", "item_id"),
        Index("ix_user_vocabulary_due", "user_id", "due_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("vocabulary_items.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(10), default="new")
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    due_at: Mapped[datetime] = mapped_column(default=utcnow)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_ms: Mapped[int | None] = mapped_column(Integer)
    used_in_writing: Mapped[int] = mapped_column(Integer, default=0)
    used_in_speaking: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[float] = mapped_column(Float, default=1.0)
    reason: Mapped[str] = mapped_column(String(30), default="level")  # level | weak_area | writing_error | ...
    reason_detail: Mapped[str | None] = mapped_column(String(300))
    last_reviewed_at: Mapped[datetime | None]
    added_at: Mapped[datetime] = mapped_column(default=utcnow)

    item: Mapped[VocabularyItem] = relationship(lazy="joined")


class VocabularyReview(CreatedAtMixin, Base):
    __tablename__ = "vocabulary_reviews"
    __table_args__ = (Index("ix_vocabulary_reviews_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("vocabulary_items.id", ondelete="CASCADE"))
    user_vocab_id: Mapped[int] = mapped_column(ForeignKey("user_vocabulary.id", ondelete="CASCADE"), index=True)
    exercise_type: Mapped[str] = mapped_column(String(30))
    correct: Mapped[bool] = mapped_column(Boolean)
    answer: Mapped[str] = mapped_column(String(300), default="")
    response_ms: Mapped[int | None] = mapped_column(Integer)
    quality: Mapped[int] = mapped_column(Integer, default=0)
    state_before: Mapped[str] = mapped_column(String(10))
    state_after: Mapped[str] = mapped_column(String(10))
