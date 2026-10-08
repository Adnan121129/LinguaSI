"""SI Tutor - teaches rather than simply answering.

* writing hints during tutor-mode writing (diagnosis, hints, guiding questions - never a model answer)
* free conversation with the learner, using LearnerContext as memory
* sentence checking that first gives hints and reveals corrections only when asked
* English Lab role-play conversations
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.context import build_context
from app.ai.client import ai_client
from app.ai.providers.base import AIMessage
from app.ai.schemas import WritingHintAI
from app.analytics.grammar_rules import detect_errors
from app.analytics.text import word_count
from app.core.clock import ensure_aware, utcnow
from app.models import TutorConversation, User, VocabularyItem, WritingSubmission
from app.services.content import scenario

CHECK_TRIGGER = re.compile(
    r"^\s*(?:please\s+)?(?:check|correct|proofread|is this (?:sentence )?(?:correct|right)|can you (?:check|correct))\b[\s:,-]*(.*)$", re.I | re.S
)
QUOTED = re.compile(r"[\"“](.{6,400}?)[\"”]")
REVEAL = re.compile(
    r"\b(tell me the answer|show me|what is the correct|what's the correct|i don't know|i dont know|give me the answer|correct version|just correct it|show the answer)\b",
    re.I,
)
MEANING = re.compile(
    r"(?:what does|what's the meaning of|what is the meaning of|meaning of|define|definition of)\s+['\"“]?([a-zA-Z][a-zA-Z\-' ]{1,40}?)['\"”]?(?:\s+mean)?\s*\??$",
    re.I,
)


def writing_hint(db: Session, user: User, submission: WritingSubmission, question: str | None) -> WritingHintAI:
    task = submission.task
    ctx = build_context(db, user)
    topic_words = list(db.scalars(select(VocabularyItem.word).where(VocabularyItem.topics.contains([task.topic])).order_by(func.random()).limit(6)))
    created = ensure_aware(submission.created_at)
    elapsed = int((utcnow() - created).total_seconds() // 60) if created else 0
    label = {"task1": "Task 1", "task2": "Task 2", "general": "General writing"}[task.task_type]
    variables = {
        "task_label": f"{label} ({task.module.replace('_', ' ')})",
        "prompt": task.prompt,
        "key_points": task.key_points or ["(not specified)"],
        "learner_context": ctx.for_prompt("writing"),
        "question": question or "(no question - give general guidance on the draft)",
        "word_count": word_count(submission.content),
        "elapsed_minutes": elapsed,
        "time_limit": f"{task.time_limit_minutes} minutes",
        "draft": submission.content or "(empty)",
    }
    mock_context = {
        "draft": submission.content,
        "question": question,
        "task": {
            "task_type": task.task_type,
            "module": task.module,
            "category": task.category,
            "prompt": task.prompt,
            "key_points": task.key_points,
            "min_words": task.min_words,
            "topic": task.topic,
        },
        "recurring": ctx.recurring_subcategories,
        "topic_vocab": topic_words,
    }
    parsed, _ = ai_client.generate_model("writing_hint", variables, WritingHintAI, user_id=user.id, mock_context=mock_context)
    return parsed


def _extract_check(message: str) -> str | None:
    m = CHECK_TRIGGER.match(message)
    if m and m.group(1).strip():
        candidate = m.group(1).strip()
        quoted = QUOTED.search(candidate)
        return (quoted.group(1) if quoted else candidate).strip()
    quoted = QUOTED.search(message)
    if quoted and re.search(r"\b(correct|right|check|wrong|mistake|grammar)\b", message, re.I):
        return quoted.group(1).strip()
    return None


def chat(db: Session, user: User, conversation: TutorConversation, message: str) -> tuple[str, dict]:
    ctx = build_context(db, user)
    history_rows = conversation.messages[-8:]
    history = [AIMessage("user" if m.role == "user" else "assistant", m.content) for m in history_rows]
    last_assistant = next((m for m in reversed(history_rows) if m.role == "assistant"), None)
    meta: dict = {"intent": "chat"}
    check = None
    vocab_item = None
    vocab_query = None

    sentence = _extract_check(message)
    if sentence:
        errors = detect_errors(sentence, mode="writing", academic=False)
        check = {
            "sentence": sentence,
            "reveal": False,
            "errors": [{"original": e.original, "corrected": e.corrected, "explanation": e.explanation, "subcategory": e.subcategory} for e in errors],
        }
        meta = {"intent": "sentence_check", "check": check}
    elif REVEAL.search(message) and last_assistant and (last_assistant.meta or {}).get("intent") == "sentence_check":
        check = dict(last_assistant.meta["check"]) | {"reveal": True}
        meta = {"intent": "reveal", "check": check}
    else:
        m = MEANING.search(message.strip())
        if m:
            vocab_query = m.group(1).strip().lower()
            item = db.scalar(select(VocabularyItem).where(func.lower(VocabularyItem.word) == vocab_query).limit(1))
            vocab_item = (
                {
                    "word": item.word,
                    "part_of_speech": item.part_of_speech,
                    "definition": item.definition,
                    "example": item.example,
                    "collocations": item.collocations,
                    "synonyms": item.synonyms,
                }
                if item
                else {}
            )
            meta = {"intent": "vocabulary", "word": vocab_query, "found": bool(item)}

    prompt_message = message
    if check:
        detected = "; ".join(f"'{e['original']}' -> '{e['corrected']}' ({e['subcategory']})" for e in check["errors"]) or "no rule-based errors found"
        mode = "The learner asked for the corrections now; give them." if check["reveal"] else "Give hints first; do not reveal the full correction yet."
        prompt_message = f'{message}\n\n[LinguaSI rule-based check of "{check["sentence"]}": {detected}. {mode}]'
    elif vocab_item:
        prompt_message = f"{message}\n\n[LinguaSI word bank entry: {vocab_item['word']} ({vocab_item['part_of_speech']}): {vocab_item['definition']}. Example: {vocab_item['example']}]"

    result = ai_client.generate(
        "tutor_chat",
        {"learner_context": ctx.for_prompt("tutor"), "message": prompt_message},
        user_id=user.id,
        history=history,
        mock_context={"message": message, "learner": ctx.as_mock(), "check": check, "vocab_item": vocab_item, "vocab_query": vocab_query},
    )
    return result.text.strip(), meta


def conversation_reply(db: Session, user: User, conversation: TutorConversation, message: str) -> str:
    scen = scenario(conversation.scenario or "") or {}
    history = [AIMessage("user" if m.role == "user" else "assistant", m.content) for m in conversation.messages[-12:]]
    turn_index = sum(1 for m in conversation.messages if m.role == "assistant") - 1
    level = user.profile.estimated_cefr or user.profile.self_reported_level
    result = ai_client.generate(
        "conversation_chat",
        {
            "ai_role": scen.get("ai_role", "a friendly conversation partner"),
            "scenario_title": scen.get("title", "Conversation"),
            "goal": scen.get("goal", "practise speaking"),
            "level": level,
            "message": message,
        },
        user_id=user.id,
        history=history,
        mock_context={"scenario_id": conversation.scenario, "turn_index": max(0, turn_index)},
    )
    return result.text.strip()
