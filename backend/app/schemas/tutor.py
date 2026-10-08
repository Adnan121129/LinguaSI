from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ActivityOutcome


class ScenarioInfo(BaseModel):
    id: str | None = None
    title: str | None = None
    level: str | None = None
    ai_role: str | None = None
    goal: str | None = None
    phrases: list[str] | None = None


class TutorMessageOut(BaseModel):
    id: int
    role: str
    content: str
    meta: dict
    created_at: datetime


class ConversationSummary(BaseModel):
    id: int
    title: str
    mode: str
    scenario: str | None
    scenario_info: ScenarioInfo | None = None
    created_at: datetime
    updated_at: datetime


class ConversationOut(ConversationSummary):
    messages: list[TutorMessageOut]


class CreateConversationRequest(BaseModel):
    mode: str = Field(default="tutor", pattern="^(tutor|conversation)$")
    scenario_id: str | None = Field(default=None, max_length=60)
    title: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _scenario_required(self) -> CreateConversationRequest:
        if self.mode == "conversation" and not self.scenario_id:
            raise ValueError("scenario_id is required for conversation practice")
        return self


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class SendMessageResponse(BaseModel):
    user_message: TutorMessageOut
    reply: TutorMessageOut
    outcome: ActivityOutcome | None = None
