"""SI Error Analyst.

Normalises errors from every module onto one taxonomy, stores them in the learner's mistake
tracker (deduplicated and flagged when repeated), and turns recurring patterns into *signals*
that the other agents act on (vocabulary queue, practice sets, recommendations, speaking
targets...). This is the hub of LinguaSI's cross-skill intelligence.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.client import ai_client
from app.ai.providers.base import AIError
from app.ai.schemas import ErrorClassificationAI
from app.core.clock import utcnow
from app.core.taxonomy import SUBCATEGORIES, category_for, label_for, normalize_subcategory
from app.models import Mistake, User

logger = logging.getLogger("linguasi.agents.error_analyst")


@dataclass
class ErrorRecord:
    source: str
    category: str
    subcategory: str
    original: str
    corrected: str
    explanation: str = ""
    context: str | None = None
    severity: str = "medium"
    ref_type: str | None = None
    ref_id: int | None = None
    signature_hint: str | None = None


@dataclass
class Signal:
    key: str
    source: str
    subcategory: str | None
    strength: float
    title: str
    detail: str
    data: dict = field(default_factory=dict)


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", "", (value or "").lower())).strip()


def signature_for(record: ErrorRecord) -> str:
    base = record.signature_hint or _normalise_text(record.original)[:150]
    return f"{record.subcategory}:{base}"[:200]


def normalise_records(records: list[ErrorRecord], *, user_id: int | None = None) -> list[ErrorRecord]:
    """Map every record onto the taxonomy. Unknown labels go to the cheap classification model."""
    unknown = [r for r in records if r.subcategory not in SUBCATEGORIES]
    if unknown and not ai_client.is_mock:
        try:
            parsed, _ = ai_client.generate_model(
                "error_classify",
                {"errors": "\n".join(f"{i}. [{r.category}/{r.subcategory}] '{r.original}' -> '{r.corrected}'" for i, r in enumerate(unknown))},
                ErrorClassificationAI,
                user_id=user_id,
                mock_context={"errors": [{"category": r.category, "subcategory": r.subcategory} for r in unknown]},
            )
            for item in parsed.items:
                if 0 <= item.index < len(unknown):
                    unknown[item.index].subcategory = item.subcategory
        except AIError:
            logger.info("Error classification unavailable; using local alias mapping")
    for r in records:
        r.subcategory = normalize_subcategory(r.subcategory, r.category)
        r.category = category_for(r.subcategory)
        if r.severity not in ("low", "medium", "high"):
            r.severity = "medium"
    return records


def record_errors(db: Session, user: User, records: list[ErrorRecord]) -> tuple[list[Mistake], list[Signal]]:
    """Persist errors as mistakes. Returns (mistakes, signals). Caller commits."""
    if not records:
        return [], []
    now = utcnow()
    history_window = now - timedelta(days=60)
    prior_subcats = set(db.scalars(select(Mistake.subcategory).where(Mistake.user_id == user.id, Mistake.last_seen_at >= history_window)))
    mistakes: list[Mistake] = []
    batch_counts: dict[str, int] = {}
    seen_signatures: dict[str, Mistake] = {}
    for record in records:
        batch_counts[record.subcategory] = batch_counts.get(record.subcategory, 0) + 1
        signature = signature_for(record)
        existing = seen_signatures.get(signature) or db.scalar(select(Mistake).where(Mistake.user_id == user.id, Mistake.signature == signature).limit(1))
        if existing is not None:
            existing.occurrences += 1
            existing.last_seen_at = now
            existing.repeated = True
            if existing.status in ("corrected", "mastered"):
                existing.status = "unresolved"
                existing.mastered_at = None
                existing.practice_streak = 0
            if record.context:
                existing.context = record.context
            mistake = existing
        else:
            mistake = Mistake(
                user_id=user.id,
                source=record.source,
                category=record.category,
                subcategory=record.subcategory,
                original=record.original[:2000],
                corrected=record.corrected[:2000],
                explanation=record.explanation,
                context=(record.context or "")[:1000] or None,
                severity=record.severity,
                signature=signature,
                occurrences=1,
                repeated=record.subcategory in prior_subcats,
                status="unresolved",
                ref_type=record.ref_type,
                ref_id=record.ref_id,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(mistake)
        seen_signatures[signature] = mistake
        mistakes.append(mistake)
    db.flush()
    return mistakes, detect_signals(db, user, batch_counts, source=records[0].source)


SIGNAL_RULES = {
    "collocation": "collocation_weakness",
    "word_choice": "collocation_weakness",
    "word_formation": "lexical_range",
    "repetition": "lexical_range",
    "spelling": "spelling_weakness",
    "informal_register": "academic_style",
    "contractions": "academic_style",
    "linking_words": "cohesion_weakness",
    "referencing": "cohesion_weakness",
    "idea_development": "task_response_weakness",
    "position_clarity": "task_response_weakness",
    "relevance": "task_response_weakness",
    "filler_words": "fluency_weakness",
    "hesitation": "fluency_weakness",
    "short_answers": "fluency_weakness",
}


def detect_signals(db: Session, user: User, batch_counts: dict[str, int], *, source: str) -> list[Signal]:
    """Turn recurring patterns (this batch + the last 30 days) into signals for other agents."""
    since = utcnow() - timedelta(days=30)
    signals: list[Signal] = []
    for sub, in_batch in batch_counts.items():
        total = int(
            db.scalar(
                select(func.coalesce(func.sum(Mistake.occurrences), 0)).where(
                    Mistake.user_id == user.id, Mistake.subcategory == sub, Mistake.last_seen_at >= since
                )
            )
            or 0
        )
        if total < 3 and in_batch < 2:
            continue
        key = SIGNAL_RULES.get(sub)
        if key is None:
            category = category_for(sub)
            key = "grammar_pattern" if category == "grammar" else "comprehension_pattern" if category == "comprehension" else None
        if key is None:
            continue
        label = label_for(sub)
        signals.append(
            Signal(
                key=key,
                source=source,
                subcategory=sub,
                strength=min(1.0, total / 8),
                title=f"Recurring {label.lower()} mistakes",
                detail=f"{in_batch} in this {source} activity and {total} in the last 30 days.",
                data={"in_batch": in_batch, "last_30_days": total},
            )
        )
    return signals


def record_practice_result(mistake: Mistake, correct: bool) -> bool:
    """Update mastery after a practice item about this mistake. Returns True if newly mastered."""
    now = utcnow()
    mistake.practice_attempts += 1
    mistake.last_practiced_at = now
    if correct:
        mistake.practice_correct += 1
        mistake.practice_streak += 1
        if mistake.practice_streak >= 2 and mistake.status != "mastered":
            mistake.status = "mastered"
            mistake.mastered_at = now
            return True
        if mistake.status == "unresolved":
            mistake.status = "corrected"
    else:
        mistake.practice_streak = 0
        if mistake.status != "unresolved":
            mistake.status = "unresolved"
            mistake.mastered_at = None
    return False
