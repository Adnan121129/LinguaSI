"""SI Tutor chat and English Lab role-play conversations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Pagination, ai_rate_limit, get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import Message, Page
from app.schemas.tutor import (
    ConversationOut,
    ConversationSummary,
    CreateConversationRequest,
    SendMessageRequest,
    SendMessageResponse,
    TutorMessageOut,
)
from app.services import tutor_service

router = APIRouter(prefix="/tutor", tags=["tutor"])


def _message_out(m) -> TutorMessageOut:
    return TutorMessageOut(id=m.id, role=m.role, content=m.content, meta=m.meta or {}, created_at=m.created_at)


@router.get("/conversations", response_model=Page[ConversationSummary], summary="Your SI Tutor chats and role-play conversations")
def list_conversations(
    mode: str | None = Query(None, pattern="^(tutor|conversation)$"),
    pagination: Pagination = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[ConversationSummary]:
    items, total = tutor_service.list_conversations(db, user, mode, pagination.page, pagination.page_size)
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.post(
    "/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Start a tutor chat, or a role-play conversation from a Lab scenario",
)
def create_conversation(payload: CreateConversationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ConversationOut:
    conv = tutor_service.create_conversation(db, user, payload.mode, payload.scenario_id, payload.title)
    return ConversationOut(**tutor_service.conversation_out(tutor_service.get_conversation(db, user, conv.id)))


@router.get("/conversations/{conv_id}", response_model=ConversationOut)
def get_conversation(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ConversationOut:
    return ConversationOut(**tutor_service.conversation_out(tutor_service.get_conversation(db, user, conv_id)))


@router.post(
    "/conversations/{conv_id}/messages", response_model=SendMessageResponse, summary="Send a message; the SI Tutor replies using your learner profile as memory"
)
def send_message(conv_id: int, payload: SendMessageRequest, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)) -> SendMessageResponse:
    user_msg, reply, outcome = tutor_service.send_message(db, user, conv_id, payload.content)
    return SendMessageResponse(user_message=_message_out(user_msg), reply=_message_out(reply), outcome=outcome)


@router.delete("/conversations/{conv_id}", response_model=Message)
def delete_conversation(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Message:
    tutor_service.delete_conversation(db, user, conv_id)
    return Message(message="Conversation deleted.")
