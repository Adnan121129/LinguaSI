"""Cross-skill mistake tracker. Every skill module feeds this table; SI Core reads it everywhere."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.models.base import Base, TimestampMixin

MISTAKE_STATUSES = ("unresolved", "corrected", "mastered")


class Mistake(TimestampMixin, Base):
    __tablename__ = "mistakes"
    __table_args__ = (
        Index("ix_mistakes_user_status", "user_id", "status"),
        Index("ix_mistakes_user_subcategory", "user_id", "subcategory"),
        Index("ix_mistakes_user_last_seen", "user_id", "last_seen_at"),
        Index("ix_mistakes_user_signature", "user_id", "signature"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(20))  # writing | speaking | vocabulary | reading | listening | grammar | diagnostic
    category: Mapped[str] = mapped_column(String(30))
    subcategory: Mapped[str] = mapped_column(String(40))
    original: Mapped[str] = mapped_column(Text)
    corrected: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    signature: Mapped[str] = mapped_column(String(200))
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    repeated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(12), default="unresolved")
    ref_type: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    practice_attempts: Mapped[int] = mapped_column(Integer, default=0)
    practice_correct: Mapped[int] = mapped_column(Integer, default=0)
    practice_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_practiced_at: Mapped[datetime | None]
    revisit_at: Mapped[datetime | None]
    mastered_at: Mapped[datetime | None]
    first_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
