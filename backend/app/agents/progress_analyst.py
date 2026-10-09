"""SI Progress Analyst.

Maintains the learner intelligence profile: per-skill scores (via the adaptive difficulty
engine), weak and strong areas (skills, rubric criteria and recurring mistakes), the AI
estimated band / CEFR level, and daily progress snapshots used by the charts.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.difficulty import SkillUpdate, apply_result
from app.core.clock import local_today, utcnow
from app.core.database import insert_or_existing
from app.core.levels import band_to_cefr, band_to_score, round_band, score_to_cefr
from app.models import (
    IELTS_SKILLS,
    SKILLS,
    LearnerSkillProfile,
    ProgressSnapshot,
    SpeakingEvaluation,
    User,
    WritingEvaluation,
)
from app.repositories import stats

LEVEL_START_DIFFICULTY = {"beginner": 1, "elementary": 1, "intermediate": 2, "upper_intermediate": 3, "advanced": 4}
SKILL_LABELS = {
    "reading": "Reading",
    "listening": "Listening",
    "writing": "Writing",
    "speaking": "Speaking",
    "vocabulary": "Vocabulary",
    "grammar": "Grammar",
}
WRITING_CRITERIA = {
    "task_response": "Task Response (Writing)",
    "coherence_cohesion": "Coherence & Cohesion (Writing)",
    "lexical_resource": "Lexical Resource (Writing)",
    "grammatical_range_accuracy": "Grammatical Range & Accuracy",
}
SPEAKING_CRITERIA = {
    "fluency_coherence": "Fluency & Coherence (Speaking)",
    "lexical_resource": "Lexical Resource (Speaking)",
    "grammatical_range_accuracy": "Grammar in Speaking",
}


@dataclass
class SkillResult:
    skill: str
    score: float  # normalised 0-100
    band: float | None = None
    difficulty: int | None = None


def get_skill_profile(db: Session, user: User, skill: str) -> LearnerSkillProfile:
    query = select(LearnerSkillProfile).where(LearnerSkillProfile.user_id == user.id, LearnerSkillProfile.skill == skill)
    profile = db.scalar(query)
    if profile is None:
        profile = insert_or_existing(
            db,
            LearnerSkillProfile(
                user_id=user.id,
                skill=skill,
                score=0.0,
                confidence=0.0,
                trend="new",
                difficulty=LEVEL_START_DIFFICULTY.get(user.profile.self_reported_level, 2),
                attempts=0,
                recent=[],
            ),
            query,
        )
    return profile


def all_skill_profiles(db: Session, user: User) -> dict[str, LearnerSkillProfile]:
    return {skill: get_skill_profile(db, user, skill) for skill in SKILLS}


def apply_skill_results(db: Session, user: User, results: list[SkillResult]) -> list[SkillUpdate]:
    updates = []
    now = utcnow()
    for result in results:
        profile = get_skill_profile(db, user, result.skill)
        updates.append(apply_result(profile, score=result.score, band=result.band, difficulty=result.difficulty, at=now))
    return updates


def initialise_from_diagnostic(db: Session, user: User, estimates: dict[str, dict]) -> None:
    """Seed skill profiles from the diagnostic (counts as one attempt with modest confidence)."""
    now = utcnow()
    for skill, est in estimates.items():
        profile = get_skill_profile(db, user, skill)
        profile.score = round(est["score"], 1)
        profile.band = est.get("band")
        profile.difficulty = est.get("difficulty", profile.difficulty)
        profile.attempts = 1
        profile.confidence = 0.2
        profile.trend = "new"
        profile.recent = [{"score": round(est["score"], 1), "band": est.get("band"), "difficulty": None, "at": now.isoformat(), "diagnostic": True}]
        profile.last_practiced_at = now


def _criteria_averages(db: Session, user: User, model, criteria: dict[str, str], limit: int = 3) -> dict[str, float]:
    rows = db.scalars(select(model).where(model.user_id == user.id).order_by(model.created_at.desc()).limit(limit)).all()
    if not rows:
        return {}
    return {key: round(statistics.mean(getattr(r, key) for r in rows), 2) for key in criteria}


def refresh_insights(db: Session, user: User) -> None:
    profile = user.profile
    skills = all_skill_profiles(db, user)
    target = profile.target_band or 6.5
    target_score = band_to_score(target)
    candidates: list[dict] = []
    strengths: list[dict] = []

    for skill, sp in skills.items():
        if not sp.attempts:
            continue
        goal_score = target_score if skill in IELTS_SKILLS else max(70.0, target_score - 5)
        gap = goal_score - sp.score
        label = SKILL_LABELS[skill]
        if gap > 3:
            reason = f"{label} is at {sp.score:.0f}/100" + (f" (AI estimated band {sp.band:g})" if sp.band is not None else "") + ", below your target level."
            candidates.append({"key": f"skill:{skill}", "label": label, "skill": skill, "score": sp.score, "gap": gap, "reason": reason})
        elif sp.attempts >= 2:
            strengths.append(
                {
                    "key": f"skill:{skill}",
                    "label": label,
                    "skill": skill,
                    "score": sp.score,
                    "reason": f"{label} is at {sp.score:.0f}/100 - on track for your target.",
                }
            )

    for model, criteria, skill in ((WritingEvaluation, WRITING_CRITERIA, "writing"), (SpeakingEvaluation, SPEAKING_CRITERIA, "speaking")):
        averages = _criteria_averages(db, user, model, criteria)
        if not averages:
            continue
        lowest_key = min(averages, key=averages.get)
        others = [v for k, v in averages.items() if k != lowest_key]
        avg_low = averages[lowest_key]
        if avg_low < target or (others and avg_low <= min(others) - 0.5):
            candidates.append(
                {
                    "key": f"criterion:{skill}:{lowest_key}",
                    "label": criteria[lowest_key],
                    "skill": skill,
                    "score": band_to_score(avg_low),
                    "gap": (target - avg_low) * 11 + 4,
                    "reason": f"Averaging band {avg_low:g} in your recent {skill} evaluations (target {target:g}).",
                }
            )
        best_key = max(averages, key=averages.get)
        if averages[best_key] >= target:
            strengths.append(
                {
                    "key": f"criterion:{skill}:{best_key}",
                    "label": criteria[best_key],
                    "skill": skill,
                    "score": band_to_score(averages[best_key]),
                    "reason": f"Averaging band {averages[best_key]:g} - at or above your target.",
                }
            )

    for rec in stats.recurring_mistakes(db, user.id, days=30, limit=3, min_count=3):
        candidates.append(
            {
                "key": f"mistake:{rec['subcategory']}",
                "label": rec["label"],
                "skill": "grammar" if rec["category"] == "grammar" else rec["category"],
                "score": None,
                "gap": rec["count"] * 3,
                "reason": f"{rec['count']} {rec['label'].lower()} mistakes in the last 30 days.",
            }
        )

    candidates.sort(key=lambda c: c["gap"], reverse=True)
    strengths.sort(key=lambda s: s.get("score") or 0, reverse=True)
    profile.weak_areas = [{k: v for k, v in c.items() if k != "gap"} for c in candidates[:3]]
    profile.strong_areas = strengths[:3]

    # AI estimated overall band: needs at least two IELTS skills with data.
    bands = [(skills[s].band, skills[s].confidence) for s in IELTS_SKILLS if skills[s].band is not None and skills[s].attempts]
    if len(bands) >= 2:
        profile.estimated_band = round_band(sum(b for b, _ in bands) / len(bands))
        profile.band_confidence = round(min(1.0, sum(c for _, c in bands) / 4 + 0.05 * len(bands)), 2)
    if profile.estimated_band is not None:
        profile.estimated_cefr = band_to_cefr(profile.estimated_band)
    else:
        scores = [sp.score for sp in skills.values() if sp.attempts]
        if scores:
            profile.estimated_cefr = score_to_cefr(sum(scores) / len(scores))
    profile.insights_updated_at = utcnow()


def snapshot(db: Session, user: User) -> ProgressSnapshot:
    today = local_today(user.profile.timezone)
    query = select(ProgressSnapshot).where(ProgressSnapshot.user_id == user.id, ProgressSnapshot.day == today)
    snap = db.scalar(query)
    if snap is None:
        snap = insert_or_existing(db, ProgressSnapshot(user_id=user.id, day=today), query)
    skills = all_skill_profiles(db, user)
    snap.skills = {s: {"score": sp.score, "band": sp.band} for s, sp in skills.items() if sp.attempts}
    snap.overall_band = user.profile.estimated_band
    snap.cefr = user.profile.estimated_cefr
    counts = stats.vocab_counts(db, user.id)
    snap.vocab_known = counts["known"]
    snap.vocab_mastered = counts["mastered"]
    snap.mistakes_open = stats.mistake_counts(db, user.id)["unresolved"]
    snap.xp_total = stats.total_xp(db, user.id)
    return snap


def skill_snapshot_delta(db: Session, user: User, days: int = 14) -> dict[str, float]:
    """Score of each skill `days` ago (from snapshots), for trend narratives."""
    cutoff = local_today(user.profile.timezone) - timedelta(days=days)
    snap = db.scalar(
        select(ProgressSnapshot).where(ProgressSnapshot.user_id == user.id, ProgressSnapshot.day <= cutoff).order_by(ProgressSnapshot.day.desc()).limit(1)
    )
    if snap is None:
        snap = db.scalar(select(ProgressSnapshot).where(ProgressSnapshot.user_id == user.id).order_by(ProgressSnapshot.day.asc()).limit(1))
    if snap is None:
        return {}
    return {skill: data.get("score") for skill, data in (snap.skills or {}).items()}
