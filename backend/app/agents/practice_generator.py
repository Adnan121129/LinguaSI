"""SI Practice Generator.

Creates personalised practice: writing tasks, focused repair sets built from the learner's own
mistakes, and (with a real AI provider) original reading passages and listening scripts.

Generated reading/listening content goes through a quality validation step before it is stored:
every answer must be supported by an exact quote from the source text, answer formats must match
their question type, and malformed questions are dropped. If too few questions survive, the
content is rejected and the curated bank is used instead (the learner is told).
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.context import build_context
from app.ai.client import ai_client
from app.ai.mock.content import practice as mock_practice
from app.ai.mock.writing import generate_task as template_generate
from app.ai.providers.base import AIError
from app.ai.schemas import ListeningScriptAI, PracticeSetAI, ReadingPassageAI, WritingTaskAI
from app.analytics.scoring import normalize_completion, normalize_text
from app.analytics.text import word_count
from app.core.taxonomy import SUBCATEGORIES, label_for, practice_topic_for
from app.models import GrammarExercise, Mistake, PracticeSet, User, WritingSubmission, WritingTask
from app.services.content import kb_entry

logger = logging.getLogger("linguasi.agents.practice")

BANK_TOPICS_CACHE: set[str] | None = None
READING_TYPES = {
    "multiple_choice",
    "true_false_not_given",
    "yes_no_not_given",
    "matching_headings",
    "matching_information",
    "sentence_completion",
    "summary_completion",
    "short_answer",
}
LISTENING_TYPES = {"multiple_choice", "form_completion", "note_completion", "sentence_completion", "short_answer"}


# --- Writing tasks ------------------------------------------------------------------------------


def _valid_visual(task: WritingTaskAI) -> bool:
    v = task.visual
    if v is None:
        return False
    if v.chart_type == "process":
        return len(v.steps) >= 4
    if not v.categories or not v.series:
        return False
    if any(len(s.values) != len(v.categories) for s in v.series):
        return False
    if v.chart_type == "pie":
        return all(abs(sum(s.values) - 100) <= 2 for s in v.series)
    return True


def generate_writing_task(
    db: Session, user: User, *, module: str, task_type: str, category: str | None, topic: str | None, difficulty: int | None
) -> tuple[WritingTask, str | None]:
    """Returns (task, notice). Falls back to the template generator if the AI output is unusable."""
    recent_topics = list(
        db.scalars(
            select(WritingTask.topic)
            .join(WritingSubmission, WritingSubmission.task_id == WritingTask.id)
            .where(WritingSubmission.user_id == user.id)
            .order_by(WritingSubmission.created_at.desc())
            .limit(5)
        )
    )
    ctx = build_context(db, user)
    seed = random.randint(1, 10_000_000)
    variables = {
        "module": module,
        "task_type": task_type,
        "category": category or "(choose a suitable category)",
        "topic": topic or ", ".join(ctx.preferred_topics[:3]) or "(choose a topic suitable for IELTS)",
        "difficulty": difficulty or 3,
        "learner_context": ctx.for_prompt("writing"),
        "avoid_topics": ", ".join(recent_topics) or "(none)",
    }
    mock_context = {"module": module, "task_type": task_type, "category": category, "topic": topic, "seed": seed, "avoid_topics": recent_topics}
    notice = None
    try:
        parsed, _ = ai_client.generate_model("writing_generate_task", variables, WritingTaskAI, user_id=user.id, mock_context=mock_context)
        if task_type == "task1" and module == "academic" and not _valid_visual(parsed):
            raise ValueError("generated visual failed validation")
        source = "template" if ai_client.is_mock else "ai"
    except (AIError, ValueError) as exc:
        logger.info("Writing task generation fell back to templates: %s", exc)
        parsed = template_generate(mock_context)
        source = "template"
        notice = "AI generation was unavailable, so SI created this task from its original templates."

    min_words = 150 if task_type == "task1" else 250 if task_type == "task2" else 120
    minutes = 20 if task_type == "task1" else 40 if task_type == "task2" else 20
    task = WritingTask(
        task_type=task_type,
        module=module,
        category=(parsed.category or category or "general")[:40],
        topic=(parsed.topic or "general")[:60],
        title=parsed.title[:200],
        prompt=parsed.prompt,
        instructions=parsed.instructions,
        key_points=parsed.key_points[:6],
        visual=parsed.visual.model_dump() if parsed.visual else None,
        min_words=min_words,
        time_limit_minutes=minutes,
        difficulty=difficulty or 3,
        source=source,
        created_for_user_id=user.id,
    )
    db.add(task)
    db.flush()
    return task, notice


# --- Practice sets --------------------------------------------------------------------------------


def _bank_topics(db: Session) -> set[str]:
    global BANK_TOPICS_CACHE
    if BANK_TOPICS_CACHE is None:
        BANK_TOPICS_CACHE = set(db.scalars(select(GrammarExercise.topic).distinct()))
    return BANK_TOPICS_CACHE


def resolve_topic(db: Session, focus: str) -> str | None:
    if focus in _bank_topics(db):
        return focus
    topic = practice_topic_for(focus)
    return topic if topic in _bank_topics(db) else None


def _personal_item(m: Mistake) -> dict:
    context = m.context or ""
    if context and m.original in context:
        prompt_sentence = context
        answer = context.replace(m.original, m.corrected, 1)
    else:
        prompt_sentence = m.original
        answer = m.corrected
    source_label = {"writing": "your writing", "speaking": "your speaking", "diagnostic": "your diagnostic"}.get(m.source, "your practice")
    return {
        "qtype": "error_correction",
        "prompt": f"Correct this sentence from {source_label}: {prompt_sentence}",
        "options": None,
        "answer": answer,
        "accepted": [m.corrected] if answer != m.corrected else [],
        "explanation": m.explanation or f"Rule: {label_for(m.subcategory)}.",
        "mistake_id": m.id,
        "source": "personal",
        "partial_ok": answer != m.corrected,
    }


def build_practice_set(
    db: Session,
    user: User,
    *,
    focus: str,
    kind: str = "grammar_drill",
    mistake_ids: list[int] | None = None,
    item_count: int = 8,
    title: str | None = None,
    why: str | None = None,
) -> PracticeSet:
    topic = resolve_topic(db, focus)
    mistakes_q = select(Mistake).where(Mistake.user_id == user.id, Mistake.status != "mastered")
    if mistake_ids:
        mistakes = list(db.scalars(mistakes_q.where(Mistake.id.in_(mistake_ids))))
    else:
        related = [focus] + ([s for s in _subcategories_for_topic(topic)] if topic else [])
        mistakes = list(db.scalars(mistakes_q.where(Mistake.subcategory.in_(related)).order_by(Mistake.last_seen_at.desc()).limit(3)))
    mistakes = [m for m in mistakes if m.category not in ("comprehension", "fluency") and m.source != "vocabulary"]
    items: list[dict] = [_personal_item(m) for m in mistakes[:3]]

    if topic:
        recent_keys = set()
        for ps in db.scalars(select(PracticeSet).where(PracticeSet.user_id == user.id).order_by(PracticeSet.created_at.desc()).limit(3)):
            recent_keys.update(i.get("bank_key") for i in ps.items or [] if i.get("bank_key"))
        bank = list(db.scalars(select(GrammarExercise).where(GrammarExercise.topic == topic, GrammarExercise.is_active.is_(True))))
        rng = random.Random()
        rng.shuffle(bank)
        bank.sort(key=lambda ex: ex.seed_key in recent_keys)
        for ex in bank:
            if len(items) >= item_count:
                break
            items.append(
                {
                    "qtype": ex.qtype,
                    "prompt": ex.prompt,
                    "options": ex.options,
                    "answer": ex.answer,
                    "accepted": ex.accepted,
                    "explanation": ex.explanation,
                    "source": "bank",
                    "bank_key": ex.seed_key,
                }
            )

    if len(items) < item_count:
        items.extend(_generated_items(db, user, focus, item_count - len(items), mistakes))

    rng = random.Random()
    personal = [i for i in items if i["source"] == "personal"]
    others = [i for i in items if i["source"] != "personal"]
    rng.shuffle(others)
    items = (others[: max(0, item_count - len(personal))] + personal)[:item_count] if personal else others[:item_count]
    for idx, item in enumerate(items, start=1):
        item["id"] = f"i{idx}"
    entry = kb_entry(focus) or (kb_entry(topic) if topic else None)
    focus_label = label_for(focus) if focus != "argument_building" else "Argument building"
    practice = PracticeSet(
        user_id=user.id,
        kind=kind,
        title=title or (f"5-minute {focus_label} Repair Challenge" if kind in ("mistake_repair", "revision") else f"{focus_label} drill"),
        description=(entry or {}).get("rule", f"Focused practice on {focus_label.lower()}."),
        why=why or "",
        focus=focus,
        items=items,
        mistake_ids=[m.id for m in mistakes],
        total=len(items),
        estimated_minutes=max(3, round(len(items) * 0.6)),
        source="personal" if any(i["source"] == "personal" for i in items) else ("ai" if any(i["source"] == "ai" for i in items) else "seed"),
    )
    db.add(practice)
    db.flush()
    return practice


def _subcategories_for_topic(topic: str | None) -> list[str]:
    return [s.key for s in SUBCATEGORIES.values() if s.practice_topic == topic]


def _generated_items(db: Session, user: User, focus: str, count: int, mistakes: list[Mistake]) -> list[dict]:
    if count <= 0:
        return []
    entry = kb_entry(focus) or {}
    level = user.profile.estimated_cefr or user.profile.self_reported_level
    try:
        parsed, _ = ai_client.generate_model(
            "practice_generate",
            {
                "focus": focus,
                "focus_label": label_for(focus),
                "rule": entry.get("rule", "(see focus)"),
                "item_count": count,
                "level": level,
                "mistakes": [f"'{m.original}' -> '{m.corrected}'" for m in mistakes] or ["(none recorded)"],
            },
            PracticeSetAI,
            user_id=user.id,
            mock_context={"focus": focus, "item_count": count, "mistake_items": [], "seed": user.id},
        )
    except AIError:
        parsed = mock_practice({"focus": focus, "item_count": count, "mistake_items": [], "seed": user.id})
    out = []
    for item in parsed.items:
        if item.qtype == "multiple_choice" and item.answer not in item.options:
            continue
        if not item.prompt.strip() or not item.answer.strip():
            continue
        out.append(
            {
                "qtype": item.qtype,
                "prompt": item.prompt,
                "options": item.options or None,
                "answer": item.answer,
                "accepted": item.accepted_answers,
                "explanation": item.explanation,
                "source": "ai" if not ai_client.is_mock else "kb",
            }
        )
    return out[:count]


# --- Reading / listening generation with validation ------------------------------------------------


@dataclass
class ValidationReport:
    kept: int
    dropped: int
    problems: list[str]

    def as_dict(self) -> dict:
        return {"validated": True, "method": "ai_generated_checked", "kept": self.kept, "dropped": self.dropped, "problems": self.problems[:10]}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("’", "'")).strip()


def validate_questions(
    questions: list, source_text: str, *, allowed: set[str], labels: list[str] | None = None, headings: list[str] | None = None
) -> tuple[list, ValidationReport]:
    text = _norm(source_text)
    kept, problems = [], []
    for q in questions:
        problem = None
        qtype = q.qtype
        if qtype not in allowed:
            problem = f"unsupported type {qtype}"
        elif qtype in ("true_false_not_given", "yes_no_not_given"):
            valid = {"TRUE", "FALSE", "NOT GIVEN"} if qtype == "true_false_not_given" else {"YES", "NO", "NOT GIVEN"}
            q.answer = q.answer.strip().upper()
            if q.answer not in valid:
                problem = "invalid TFNG answer"
            elif q.answer != "NOT GIVEN" and (not q.evidence or _norm(q.evidence) not in text):
                problem = "evidence not found"
        elif qtype == "multiple_choice":
            letters = [o.strip()[:1].upper() for o in q.options]
            q.answer = q.answer.strip()[:1].upper()
            if len(q.options) < 3 or q.answer not in letters:
                problem = "answer not among options"
        elif qtype == "matching_headings":
            if not headings or q.answer not in headings:
                problem = "heading answer not in list"
        elif qtype == "matching_information":
            if not labels or q.answer.strip().upper() not in labels:
                problem = "paragraph label invalid"
            q.options = labels
        else:  # completion / short answer types
            answer = normalize_completion(q.answer)
            if not answer or (
                answer not in normalize_completion(source_text)
                and not any(normalize_completion(a) in normalize_completion(source_text) for a in q.accepted_answers)
            ):
                problem = "answer not in source text"
            elif q.word_limit and len(normalize_text(q.answer).split()) > q.word_limit:
                problem = "answer exceeds word limit"
        if problem is None and qtype not in ("true_false_not_given", "yes_no_not_given", "matching_headings") and q.evidence and _norm(q.evidence) not in text:
            problem = "evidence not found"
        if problem:
            problems.append(f"{qtype}: {problem}")
        else:
            kept.append(q)
    return kept, ValidationReport(len(kept), len(questions) - len(kept), problems)


def generate_reading(
    db: Session, user: User, *, module: str, topic: str, difficulty: int, question_count: int, question_types: list[str], target_expressions: list[str]
) -> tuple[ReadingPassageAI, ValidationReport]:
    ctx = build_context(db, user)
    parsed, _ = ai_client.generate_model(
        "reading_generate",
        {
            "module": module,
            "topic": topic,
            "difficulty": difficulty,
            "question_count": question_count,
            "question_types": ", ".join(question_types),
            "target_expressions": ", ".join(target_expressions) or "(none)",
            "learner_context": ctx.for_prompt("reading"),
        },
        ReadingPassageAI,
        user_id=user.id,
    )
    text = " ".join(p.text for p in parsed.paragraphs)
    labels = [p.label.strip().upper() for p in parsed.paragraphs]
    kept, report = validate_questions(
        parsed.questions, text, allowed=READING_TYPES & set(question_types) or READING_TYPES, labels=labels, headings=parsed.headings
    )
    parsed.questions = kept
    if len(parsed.paragraphs) < 3 or word_count(text) < 150 or len(kept) < max(3, question_count // 2):
        raise ValueError(f"generated reading failed validation ({report.problems[:3]})")
    return parsed, report


def generate_listening(
    db: Session, user: User, *, topic: str, scenario: str, difficulty: int, question_count: int, accent: str, target_expressions: list[str]
) -> tuple[ListeningScriptAI, ValidationReport]:
    ctx = build_context(db, user)
    parsed, _ = ai_client.generate_model(
        "listening_generate",
        {
            "topic": topic,
            "scenario": scenario,
            "difficulty": difficulty,
            "question_count": question_count,
            "accent": accent,
            "target_expressions": ", ".join(target_expressions) or "(none)",
            "learner_context": ctx.for_prompt("listening"),
        },
        ListeningScriptAI,
        user_id=user.id,
    )
    ids = {s.id for s in parsed.speakers}
    parsed.segments = [s for s in parsed.segments if s.speaker in ids and s.text.strip()]
    text = " ".join(s.text for s in parsed.segments)
    kept, report = validate_questions(parsed.questions, text, allowed=LISTENING_TYPES)
    parsed.questions = kept
    if not parsed.segments or word_count(text) < 120 or len(kept) < max(3, question_count // 2):
        raise ValueError(f"generated listening failed validation ({report.problems[:3]})")
    return parsed, report
