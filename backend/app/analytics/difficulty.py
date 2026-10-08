"""Adaptive difficulty and skill-profile updates.

Every practice result updates the learner's skill profile:
  * score      - exponentially weighted average (fast to adapt early, stable later)
  * band       - recency-weighted average of recent AI estimated bands
  * confidence - grows with the number of attempts, shrinks with inconsistency
  * trend      - slope of the recent scores
  * difficulty - changes by at most one step, and only after several attempts at the current
                 difficulty agree (>= 85% -> harder, < 55% -> easier). A single answer never
                 causes a dramatic change.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime

from app.core.levels import snap_half

RECENT_LIMIT = 12
PROMOTE_THRESHOLD = 85.0
DEMOTE_THRESHOLD = 55.0


@dataclass
class SkillUpdate:
    skill: str
    score_before: float
    score_after: float
    band_after: float | None
    difficulty_before: int
    difficulty_after: int
    trend: str
    reason: str | None


def _trend(scores: list[float]) -> str:
    if len(scores) < 3:
        return "new"
    pts = scores[-6:]
    n = len(pts)
    mean_x = (n - 1) / 2
    mean_y = sum(pts) / n
    denom = sum((i - mean_x) ** 2 for i in range(n)) or 1
    slope = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(pts)) / denom
    if slope > 1.5:
        return "improving"
    if slope < -1.5:
        return "declining"
    return "stable"


def apply_result(profile, *, score: float, band: float | None, difficulty: int | None, at: datetime) -> SkillUpdate:
    """Mutates a LearnerSkillProfile-like object with a new normalised result (0-100)."""
    score = max(0.0, min(100.0, float(score)))
    before_score = profile.score or 0.0
    before_diff = profile.difficulty or 2
    entry = {"score": round(score, 1), "band": band, "difficulty": difficulty, "at": at.isoformat()}
    recent = list(profile.recent or []) + [entry]
    recent = recent[-RECENT_LIMIT:]
    profile.recent = recent
    profile.attempts = (profile.attempts or 0) + 1

    alpha = 0.6 if profile.attempts <= 3 else 0.35
    profile.score = round(score if profile.attempts == 1 else alpha * score + (1 - alpha) * before_score, 1)

    bands = [r["band"] for r in recent if r.get("band") is not None][-5:]
    if bands:
        weights = list(range(1, len(bands) + 1))
        profile.band = snap_half(sum(b * w for b, w in zip(bands, weights, strict=True)) / sum(weights))

    scores = [r["score"] for r in recent]
    spread = statistics.pstdev(scores[-5:]) if len(scores) >= 2 else 0.0
    profile.confidence = round(min(1.0, profile.attempts / 8) * (1 - min(0.5, spread / 50)), 2)
    profile.trend = _trend(scores)
    profile.last_practiced_at = at

    reason = None
    if difficulty is not None:
        current = before_diff
        same = [r for r in recent[-5:] if r.get("difficulty") == current]
        last3 = [r["score"] for r in same[-3:]]
        last2 = [r["score"] for r in same[-2:]]
        if len(last3) >= 3 and sum(last3) / 3 >= PROMOTE_THRESHOLD and current < 5:
            profile.difficulty = current + 1
            reason = f"Average {sum(last3) / 3:.0f}% over your last 3 sessions at level {current} - moving up to level {current + 1}."
        elif len(last2) >= 2 and sum(last2) / 2 < DEMOTE_THRESHOLD and current > 1:
            profile.difficulty = current - 1
            reason = f"Average {sum(last2) / 2:.0f}% over your last 2 sessions at level {current} - easing to level {current - 1} with targeted support."
    return SkillUpdate(
        skill=profile.skill,
        score_before=before_score,
        score_after=profile.score,
        band_after=profile.band,
        difficulty_before=before_diff,
        difficulty_after=profile.difficulty,
        trend=profile.trend,
        reason=reason,
    )
