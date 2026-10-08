"""A deliberately simple spaced-repetition scheduler (SM-2 inspired) with five learner-facing states."""

from __future__ import annotations

from datetime import datetime, timedelta

STATES = ("new", "learning", "familiar", "strong", "mastered")


def quality_from(correct: bool, response_ms: int | None, *, hinted: bool = False) -> int:
    """Map an answer to an SM-2 quality score (0-5)."""
    if not correct:
        return 1
    if hinted:
        return 3
    if response_ms is not None and response_ms < 4000:
        return 5
    if response_ms is not None and response_ms > 15000:
        return 3
    return 4


def derive_state(correct_count: int, incorrect_count: int, interval_days: float, streak: int) -> str:
    if correct_count == 0 and incorrect_count == 0:
        return "new"
    if streak < 2 or interval_days < 2:
        return "learning"
    if interval_days < 7:
        return "familiar"
    if interval_days < 21 or correct_count < 4:
        return "strong"
    return "mastered"


def schedule(uv, quality: int, now: datetime) -> str:
    """Update a UserVocabulary-like object in place and return its new state."""
    if quality < 3:
        if uv.state in ("familiar", "strong", "mastered"):
            uv.lapses = (uv.lapses or 0) + 1
        uv.streak = 0
        uv.incorrect_count = (uv.incorrect_count or 0) + 1
        uv.interval_days = 0.0
        uv.ease = max(1.3, round((uv.ease or 2.5) - 0.2, 2))
        uv.due_at = now + timedelta(minutes=10)
    else:
        uv.streak = (uv.streak or 0) + 1
        uv.correct_count = (uv.correct_count or 0) + 1
        if uv.streak == 1:
            interval = 1.0
        elif uv.streak == 2:
            interval = 3.0
        else:
            interval = round(max(uv.interval_days or 1.0, 1.0) * (uv.ease or 2.5), 1)
        ease = (uv.ease or 2.5) + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        uv.ease = round(min(3.0, max(1.3, ease)), 2)
        uv.interval_days = min(interval, 180.0)
        uv.due_at = now + timedelta(days=uv.interval_days)
    uv.last_reviewed_at = now
    uv.state = derive_state(uv.correct_count or 0, uv.incorrect_count or 0, uv.interval_days or 0.0, uv.streak or 0)
    return uv.state


def mark_known(uv, now: datetime) -> str:
    """'I already know this word' - fast-track a too-easy word so it is rarely shown."""
    uv.correct_count = max(uv.correct_count or 0, 4)
    uv.streak = max(uv.streak or 0, 3)
    uv.interval_days = 30.0
    uv.ease = max(uv.ease or 2.5, 2.7)
    uv.due_at = now + timedelta(days=30)
    uv.last_reviewed_at = now
    uv.state = "mastered"
    return uv.state


def classify(uv) -> str:
    """Learner-facing classification used by the vocabulary insights view."""
    total = (uv.correct_count or 0) + (uv.incorrect_count or 0)
    acc = (uv.correct_count or 0) / total if total else None
    if total >= 3 and acc is not None and acc < 0.5 and (uv.incorrect_count or 0) >= 3:
        return "repeatedly_misunderstood"
    if (uv.lapses or 0) >= 1 and uv.state == "learning":
        return "forgotten"
    if uv.state == "mastered" and (uv.incorrect_count or 0) == 0:
        return "too_easy"
    if acc is not None and 0.6 <= acc <= 0.85:
        return "challenging"
    return "in_progress"
