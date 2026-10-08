"""Learner intelligence: per-skill profiles, daily progress snapshots, study sessions and the SI activity feed."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.models.base import Base, CreatedAtMixin

SKILLS = ("reading", "listening", "writing", "speaking", "vocabulary", "grammar")
IELTS_SKILLS = ("reading", "listening", "writing", "speaking")


class LearnerSkillProfile(Base):
    __tablename__ = "learner_skill_profiles"
    __table_args__ = (UniqueConstraint("user_id", "skill"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(20))
    score: Mapped[float] = mapped_column(Float, default=0.0)  # normalised 0-100
    band: Mapped[float | None] = mapped_column(Float)  # AI estimated IELTS band (R/L/W/S)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    trend: Mapped[str] = mapped_column(String(12), default="new")  # new | improving | stable | declining
    difficulty: Mapped[int] = mapped_column(Integer, default=2)  # recommended difficulty 1..5
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    recent: Mapped[list] = mapped_column(JSONB, default=list)  # last results [{score, band, difficulty, at}]
    last_practiced_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class ProgressSnapshot(CreatedAtMixin, Base):
    __tablename__ = "progress_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    overall_band: Mapped[float | None] = mapped_column(Float)
    cefr: Mapped[str | None] = mapped_column(String(4))
    skills: Mapped[dict] = mapped_column(JSONB, default=dict)  # {skill: {score, band}}
    vocab_known: Mapped[int] = mapped_column(Integer, default=0)
    vocab_mastered: Mapped[int] = mapped_column(Integer, default=0)
    mistakes_open: Mapped[int] = mapped_column(Integer, default=0)
    xp_total: Mapped[int] = mapped_column(Integer, default=0)
    insights: Mapped[dict] = mapped_column(JSONB, default=dict)  # cached Progress Analyst narrative for the day


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (Index("ix_study_sessions_user_started", "user_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    activity: Mapped[str] = mapped_column(String(30))
    ref_type: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[datetime | None]
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float | None] = mapped_column(Float)  # normalised 0-100 when applicable
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)


class SIEvent(CreatedAtMixin, Base):
    """A transparent record of what SI Core inferred and which cross-skill actions it took."""

    __tablename__ = "si_events"
    __table_args__ = (Index("ix_si_events_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(30))
    signal: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[list] = mapped_column(JSONB, default=list)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
