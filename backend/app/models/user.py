"""Users, learner profile/preferences, auth sessions and learning goals."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.gamification import Streak


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="learner")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    last_active_at: Mapped[datetime | None]

    profile: Mapped[Profile] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="joined")
    streak: Mapped[Streak | None] = relationship(uselist=False, cascade="all, delete-orphan", viewonly=False)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Profile(TimestampMixin, Base):
    """Learner preferences plus the SI-derived summary of the learner (the persistent learner profile)."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    goal: Mapped[str] = mapped_column(String(20), default="ielts")  # ielts | general
    ielts_module: Mapped[str] = mapped_column(String(20), default="academic")  # academic | general_training
    self_reported_level: Mapped[str] = mapped_column(String(20), default="intermediate")
    target_band: Mapped[float] = mapped_column(Float, default=6.5)
    test_date: Mapped[date | None] = mapped_column(Date)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=30)
    preferred_mode: Mapped[str] = mapped_column(String(20), default="balanced")  # guided | balanced | exam
    confidence: Mapped[int] = mapped_column(Integer, default=3)  # 1..5
    preferred_topics: Mapped[list] = mapped_column(JSONB, default=list)
    theme: Mapped[str] = mapped_column(String(10), default="system")  # light | dark | system
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    keep_recordings: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    diagnostic_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # SI-derived learner intelligence (maintained by the Progress Analyst)
    estimated_cefr: Mapped[str | None] = mapped_column(String(4))
    estimated_band: Mapped[float | None] = mapped_column(Float)
    band_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    weak_areas: Mapped[list] = mapped_column(JSONB, default=list)
    strong_areas: Mapped[list] = mapped_column(JSONB, default=list)
    insights_updated_at: Mapped[datetime | None]

    user: Mapped[User] = relationship(back_populates="profile")


class AuthSession(CreatedAtMixin, Base):
    """A refresh-token session. Only a SHA-256 hash of the token is stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    last_used_at: Mapped[datetime | None]
    replaced_by_id: Mapped[int | None] = mapped_column(Integer)
    user_agent: Mapped[str | None] = mapped_column(String(255))


class LearningGoal(TimestampMixin, Base):
    __tablename__ = "learning_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal_type: Mapped[str] = mapped_column(String(30))  # overall_band | skill_band | cefr | daily_minutes
    skill: Mapped[str | None] = mapped_column(String(20))
    target_value: Mapped[float | None] = mapped_column(Float)
    target_label: Mapped[str | None] = mapped_column(String(100))
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | achieved | archived
    achieved_at: Mapped[datetime | None]
