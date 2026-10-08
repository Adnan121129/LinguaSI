"""Recommendations, diagnostic attempts, tutor conversations, AI interaction logs and system logs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.models.base import Base, CreatedAtMixin, TimestampMixin


class Recommendation(CreatedAtMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_user_status", "user_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rule: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(30))  # writing | speaking | reading | listening | vocabulary | grammar | mistakes
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    why: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[float] = mapped_column(Float, default=0.5)
    signals: Mapped[dict] = mapped_column(JSONB, default=dict)
    action: Mapped[dict] = mapped_column(JSONB, default=dict)  # {route, params}
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | completed | dismissed | expired
    source: Mapped[str] = mapped_column(String(10), default="rules")
    expires_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]


class DiagnosticAttempt(Base):
    __tablename__ = "diagnostic_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    items: Mapped[dict] = mapped_column(JSONB, default=dict)  # served sections incl. answer keys (server side only)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    section_scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    writing_sample: Mapped[str] = mapped_column(Text, default="")
    writing_band: Mapped[float | None] = mapped_column(Float)
    speaking_sample: Mapped[str | None] = mapped_column(Text)
    speaking_band: Mapped[float | None] = mapped_column(Float)
    estimated_cefr: Mapped[str | None] = mapped_column(String(4))
    estimated_band: Mapped[float | None] = mapped_column(Float)
    skill_estimates: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    completed_at: Mapped[datetime | None]


class TutorConversation(TimestampMixin, Base):
    __tablename__ = "tutor_conversations"
    __table_args__ = (Index("ix_tutor_conversations_user_updated", "user_id", "updated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    mode: Mapped[str] = mapped_column(String(20), default="tutor")  # tutor | conversation
    scenario: Mapped[str | None] = mapped_column(String(60))
    context: Mapped[dict] = mapped_column(JSONB, default=dict)

    messages: Mapped[list[TutorMessage]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="TutorMessage.id")


class TutorMessage(CreatedAtMixin, Base):
    __tablename__ = "tutor_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("tutor_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    conversation: Mapped[TutorConversation] = relationship(back_populates="messages")


class AIInteractionLog(Base):
    """Observability for every AI call. Stores metadata only, never prompts or learner text by default."""

    __tablename__ = "ai_interaction_logs"
    __table_args__ = (Index("ix_ai_interaction_logs_created", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    agent: Mapped[str] = mapped_column(String(40))
    task: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(60))
    tier: Mapped[str] = mapped_column(String(10))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_category: Mapped[str | None] = mapped_column(String(30))
    error_message: Mapped[str | None] = mapped_column(String(300))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    debug_payload: Mapped[dict | None] = mapped_column(JSONB)  # only when AI_LOG_CONTENT=true
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class SystemLog(Base):
    __tablename__ = "system_logs"
    __table_args__ = (Index("ix_system_logs_created", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
