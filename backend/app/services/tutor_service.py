"""SI Tutor conversations (teaching chat) and English Lab role-play conversations."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.agents import si_core, tutor
from app.ai.providers.base import AIError
from app.core.clock import ensure_aware, utcnow
from app.core.errors import AIUnavailableError, NotFoundError, ValidationAppError
from app.models import TutorConversation, TutorMessage, User
from app.schemas.common import ActivityOutcome
from app.services.content import scenario

# A role-play counts as one English Lab session once the learner has taken this many turns.
CONVERSATION_SESSION_TURNS = 4


def conversation_out(conv: TutorConversation, with_messages: bool = True) -> dict:
    data = {
        "id": conv.id,
        "title": conv.title,
        "mode": conv.mode,
        "scenario": conv.scenario,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }
    if conv.mode == "conversation" and conv.scenario:
        scen = scenario(conv.scenario) or {}
        data["scenario_info"] = {k: scen.get(k) for k in ("id", "title", "level", "ai_role", "goal", "phrases")}
    if with_messages:
        data["messages"] = [{"id": m.id, "role": m.role, "content": m.content, "meta": m.meta, "created_at": m.created_at} for m in conv.messages]
    return data


def list_conversations(db: Session, user: User, mode: str | None, page: int, page_size: int):
    q = select(TutorConversation).where(TutorConversation.user_id == user.id)
    if mode:
        q = q.where(TutorConversation.mode == mode)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(TutorConversation.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return [conversation_out(c, with_messages=False) for c in rows], total


def create_conversation(db: Session, user: User, mode: str, scenario_id: str | None, title: str | None) -> TutorConversation:
    conv = TutorConversation(user_id=user.id, mode=mode, title=(title or "New conversation")[:200])
    if mode == "conversation":
        scen = scenario(scenario_id or "")
        if not scen:
            raise ValidationAppError("Choose a valid conversation scenario.")
        conv.scenario = scen["id"]
        conv.title = scen["title"]
        conv.messages.append(TutorMessage(role="assistant", content=scen["opening"], meta={"intent": "scenario_opening"}))
    else:
        first = user.name.split(" ")[0] if user.name else "there"
        conv.messages.append(
            TutorMessage(
                role="assistant",
                content=(
                    f'Hi {first}! I\'m your SI Tutor. Ask me about grammar or vocabulary, paste a sentence and write "check: ...", '
                    "or ask what to focus on - I know your recent mistakes and goals."
                ),
                meta={"intent": "welcome"},
            )
        )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_conversation(db: Session, user: User, conv_id: int) -> TutorConversation:
    conv = db.scalar(
        select(TutorConversation)
        .options(selectinload(TutorConversation.messages))
        .where(TutorConversation.id == conv_id)
        .execution_options(populate_existing=True)
    )
    if conv is None or conv.user_id != user.id:
        raise NotFoundError("Conversation not found.")
    return conv


def send_message(db: Session, user: User, conv_id: int, content: str) -> tuple[TutorMessage, TutorMessage, ActivityOutcome | None]:
    conv = get_conversation(db, user, conv_id)
    text = content.strip()
    if not text:
        raise ValidationAppError("Message cannot be empty.")
    try:
        if conv.mode == "conversation":
            reply, meta = tutor.conversation_reply(db, user, conv, text), {"intent": "role_play"}
        else:
            reply, meta = tutor.chat(db, user, conv, text)
    except AIError as exc:
        raise AIUnavailableError("The SI Tutor is temporarily unavailable. Please try again in a moment.") from exc
    user_msg = TutorMessage(role="user", content=text[:4000], meta={})
    assistant_msg = TutorMessage(role="assistant", content=reply[:8000], meta=meta)
    conv.messages.append(user_msg)
    conv.messages.append(assistant_msg)
    if conv.mode == "tutor" and conv.title == "New conversation":
        conv.title = (" ".join(text.split()[:7]) + ("..." if len(text.split()) > 7 else ""))[:200]
    conv.updated_at = utcnow()
    db.flush()

    outcome = None
    learner_turns = [m.content for m in conv.messages if m.role == "user"]
    if conv.mode == "conversation" and len(learner_turns) >= CONVERSATION_SESSION_TURNS and not (conv.context or {}).get("session_recorded"):
        conv.context = {**(conv.context or {}), "session_recorded": True}
        started = ensure_aware(conv.created_at)
        elapsed = int((utcnow() - started).total_seconds()) if started else 300
        outcome = si_core.process_activity(
            db,
            user,
            si_core.ActivityEvent(
                activity="lab",
                title=f"Conversation: {conv.title}",
                ref_type="tutor_conversation",
                ref_id=conv.id,
                duration_seconds=min(1800, max(60, elapsed)),
                usage_text=" ".join(learner_turns),
                usage_source="conversation",
                xp=[(10, "lab_activity", f"Conversation practice: {conv.title}")],
                mission_metrics={"lab_sessions": 1},
                completes_kinds={"lab"},
                meta={"scenario": conv.scenario, "turns": len(learner_turns)},
            ),
        )
    else:
        db.commit()
    return user_msg, assistant_msg, outcome


def delete_conversation(db: Session, user: User, conv_id: int) -> None:
    conv = get_conversation(db, user, conv_id)
    db.delete(conv)
    db.commit()
