"""Dashboard, progress analytics, recommendations, missions and achievements views."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents import learning_planner, progress_analyst
from app.agents.context import build_context
from app.agents.progress_analyst import SKILL_LABELS
from app.ai.client import ai_client
from app.ai.providers.base import AIError
from app.ai.schemas import ProgressInsightsAI
from app.core.clock import ensure_aware, get_zone, iso_week_key, local_now, local_today, utcnow
from app.core.config import settings
from app.core.levels import band_to_score
from app.core.taxonomy import label_for
from app.models import (
    SKILLS,
    DailyMission,
    Mistake,
    ProgressSnapshot,
    Recommendation,
    SIEvent,
    StudySession,
    User,
    UserChallenge,
    WritingError,
    WritingEvaluation,
    XPTransaction,
)
from app.repositories import stats
from app.services import gamification
from app.services.practice_service import mistake_out

logger = logging.getLogger("linguasi.dashboard")


def _greeting(user: User) -> str:
    hour = local_now(user.profile.timezone).hour
    part = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 18 else "Good evening"
    return f"{part}, {(user.name or 'there').split(' ')[0]}."


def rec_out(r: Recommendation) -> dict:
    return {
        "id": r.id,
        "rule": r.rule,
        "kind": r.kind,
        "title": r.title,
        "description": r.description,
        "why": r.why,
        "priority": r.priority,
        "signals": r.signals,
        "route": (r.action or {}).get("route"),
        "focus": (r.action or {}).get("focus"),
        "estimated_minutes": r.estimated_minutes,
        "source": r.source,
        "created_at": r.created_at,
    }


def active_recommendations(db: Session, user: User, limit: int = 5) -> list[Recommendation]:
    recs = list(
        db.scalars(select(Recommendation).where(Recommendation.user_id == user.id, Recommendation.status == "active").order_by(Recommendation.priority.desc()))
    )
    newest = max((ensure_aware(r.created_at) for r in recs), default=None)
    expired = any(r.expires_at and ensure_aware(r.expires_at) < utcnow() for r in recs)
    if not recs or expired or (newest and utcnow() - newest > timedelta(hours=6)):
        recs = learning_planner.refresh_recommendations(db, user)
        db.commit()
    return sorted(recs, key=lambda r: r.priority, reverse=True)[:limit]


def mission_out(mission: DailyMission | None) -> dict | None:
    if mission is None:
        return None
    done = sum(1 for t in mission.tasks if t.get("completed"))
    return {
        "id": mission.id,
        "day": mission.day.isoformat(),
        "title": mission.title,
        "summary": mission.summary,
        "focus": mission.focus,
        "tasks": mission.tasks,
        "status": mission.status,
        "completed_tasks": done,
        "total_tasks": len(mission.tasks),
        "bonus_xp": mission.bonus_xp,
        "generated_by": mission.generated_by,
    }


def _skill_rows(db: Session, user: User) -> list[dict]:
    profiles = progress_analyst.all_skill_profiles(db, user)
    return [
        {
            "skill": s,
            "label": SKILL_LABELS[s],
            "score": round(p.score, 1),
            "band": p.band,
            "trend": p.trend,
            "difficulty": p.difficulty,
            "attempts": p.attempts,
            "confidence": p.confidence,
            "last_practiced_at": p.last_practiced_at,
        }
        for s, p in profiles.items()
    ]


def _trend_headline(db: Session, user: User, skills: list[dict]) -> str:
    before = progress_analyst.skill_snapshot_delta(db, user, days=14)
    pairs = [(row["score"], before.get(row["skill"])) for row in skills if row["attempts"] and before.get(row["skill"]) is not None]
    if not pairs:
        return "SI is still learning about you - every session makes your estimate more accurate."
    delta = sum(now - then for now, then in pairs) / len(pairs)
    if delta >= 2:
        return "Your estimated level is improving."
    if delta <= -2:
        return "Your recent scores have dipped slightly - SI has adjusted your plan."
    return "Your estimated level is holding steady - consistent practice will move it up."


def dashboard(db: Session, user: User) -> dict:
    profile = user.profile
    skills = _skill_rows(db, user)
    recs = active_recommendations(db, user)
    mission = learning_planner.get_or_create_mission(db, user) if profile.onboarding_completed else None
    weakest = gamification_weakest(skills)
    gamification.ensure_week_challenges(db, user, weakest)
    db.commit()
    tz = profile.timezone
    minutes = stats.minutes_by_day(db, user, 7)
    xp_days = stats.xp_by_day(db, user, 7)
    counts = stats.vocab_counts(db, user.id)
    recent_mistakes = db.scalars(
        select(Mistake).where(Mistake.user_id == user.id, Mistake.status != "mastered").order_by(Mistake.last_seen_at.desc()).limit(5)
    ).all()
    feed = db.scalars(select(SIEvent).where(SIEvent.user_id == user.id).order_by(SIEvent.created_at.desc()).limit(6)).all()
    top = recs[0] if recs else None
    weak = (profile.weak_areas or [None])[0]
    insight = {
        "headline": _trend_headline(db, user, skills),
        "weakness": f"Your biggest weakness this week is {weak['label']}." if weak else None,
        "weakness_reason": weak.get("reason") if weak else None,
        "suggestion": f"SI recommends: {top.title} ({top.estimated_minutes} minutes)." if top else None,
    }
    today = local_today(tz)
    return {
        "greeting": _greeting(user),
        "name": user.name,
        "goal": profile.goal,
        "goal_label": build_goal_label(profile),
        "module": profile.ielts_module,
        "estimated_band": profile.estimated_band,
        "band_label": "AI Estimated Band",
        "target_band": profile.target_band,
        "band_confidence": profile.band_confidence,
        "cefr": profile.estimated_cefr,
        "days_to_test": (profile.test_date - today).days if profile.test_date and profile.test_date >= today else None,
        "level": gamification.level_info(db, user),
        "today_xp": stats.xp_today(db, user),
        "streak": gamification.display_streak(db, user),
        "weekly": [{"day": d.isoformat(), "label": d.strftime("%a"), "minutes": minutes[d], "xp": xp_days.get(d, 0)} for d in sorted(minutes)],
        "weekly_minutes": sum(minutes.values()),
        "weekly_goal_minutes": (profile.daily_minutes or 30) * 7,
        "skills": skills,
        "vocabulary": counts
        | {"due": stats.vocab_due_count(db, user.id), "strength": round(counts["known"] / counts["total"] * 100, 1) if counts["total"] else 0.0},
        "weaknesses": (profile.weak_areas or [])[:3],
        "strengths": (profile.strong_areas or [])[:3],
        "recent_mistakes": [mistake_out(m).model_dump() for m in recent_mistakes],
        "recommendation": rec_out(top) if top else None,
        "recommendations": [rec_out(r) for r in recs[:4]],
        "mission": mission_out(mission),
        "insight": insight,
        "si_feed": [
            {"id": e.id, "source": e.source, "signal": e.signal, "title": e.title, "detail": e.detail, "actions": e.actions, "created_at": e.created_at}
            for e in feed
        ],
        "onboarding_completed": profile.onboarding_completed,
        "diagnostic_completed": profile.diagnostic_completed,
        "ai": {"provider": settings.effective_ai_provider, "mock_mode": settings.ai_is_mock},
    }


def build_goal_label(profile) -> str:
    if profile.goal == "ielts":
        return f"IELTS {profile.ielts_module.replace('_', ' ').title()} · target band {profile.target_band:g}"
    return "Improve my English"


def gamification_weakest(skills: list[dict]) -> str | None:
    practised = [s for s in skills if s["attempts"]]
    return min(practised, key=lambda s: s["score"])["skill"] if practised else None


# --- Progress ------------------------------------------------------------------------------------

CHART_QUESTIONS = {
    "skills_radar": "Which skill needs attention right now?",
    "band_history": "Is my AI estimated band moving towards my target?",
    "weekly_scores": "Which skills improved over the last few weeks?",
    "vocabulary_growth": "Is my active vocabulary growing?",
    "mistake_reduction": "Am I making fewer mistakes in my writing?",
    "consistency": "Am I practising consistently?",
}


def progress(db: Session, user: User, days: int = 30) -> dict:
    tz = user.profile.timezone
    zone = get_zone(tz)
    skills = _skill_rows(db, user)
    target_score = band_to_score(user.profile.target_band)
    snapshots = list(db.scalars(select(ProgressSnapshot).where(ProgressSnapshot.user_id == user.id).order_by(ProgressSnapshot.day.asc())))
    since_day = local_today(tz) - timedelta(days=days - 1)
    since = stats.local_day_start_utc(since_day, tz)
    sessions = db.scalars(
        select(StudySession).where(
            StudySession.user_id == user.id, StudySession.started_at >= stats.local_day_start_utc(local_today(tz) - timedelta(weeks=8), tz)
        )
    ).all()
    weekly: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for s in sessions:
        if s.score is not None and s.activity in SKILLS:
            weekly[iso_week_key(s.started_at.astimezone(zone).date())][s.activity].append(s.score)
    weekly_scores = [{"week": w, **{skill: round(sum(v) / len(v), 1) for skill, v in data.items()}} for w, data in sorted(weekly.items())]

    error_counts = dict(
        db.execute(
            select(WritingError.evaluation_id, func.count(WritingError.id)).where(WritingError.user_id == user.id).group_by(WritingError.evaluation_id)
        ).all()
    )
    eval_rows = db.execute(
        select(WritingEvaluation.id, WritingEvaluation.created_at, WritingEvaluation.metrics).where(WritingEvaluation.user_id == user.id)
    ).all()
    mistake_weeks: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for eid, created_at, metrics in eval_rows:
        week = iso_week_key(created_at.astimezone(zone).date())
        mistake_weeks[week][0] += error_counts.get(eid, 0)
        mistake_weeks[week][1] += int((metrics or {}).get("word_count", 0))
    mistake_reduction = [
        {"week": w, "errors": e, "words": n, "per_100_words": round(e / n * 100, 2) if n else None} for w, (e, n) in sorted(mistake_weeks.items())
    ]

    minutes = stats.minutes_by_day(db, user, days)
    xp_days = stats.xp_by_day(db, user, days)
    consistency = [{"day": d.isoformat(), "minutes": minutes[d], "xp": xp_days.get(d, 0)} for d in sorted(minutes)]
    return {
        "chart_questions": CHART_QUESTIONS,
        "target_band": user.profile.target_band,
        "estimated_band": user.profile.estimated_band,
        "cefr": user.profile.estimated_cefr,
        "skills": skills,
        "skills_radar": [{"skill": s["skill"], "label": s["label"], "score": s["score"], "target": target_score} for s in skills],
        "band_history": [
            {
                "day": s.day.isoformat(),
                "overall": s.overall_band,
                **{k: (s.skills or {}).get(k, {}).get("band") for k in ("reading", "listening", "writing", "speaking")},
            }
            for s in snapshots
        ],
        "weekly_scores": weekly_scores,
        "vocabulary_growth": [{"day": s.day.isoformat(), "known": s.vocab_known, "mastered": s.vocab_mastered} for s in snapshots],
        "mistake_reduction": mistake_reduction,
        "consistency": consistency,
        "totals": {
            "sessions": len([s for s in sessions if ensure_aware(s.started_at) >= since]),
            "minutes": sum(minutes.values()),
            "active_days": sum(1 for v in minutes.values() if v > 0),
            "xp": sum(xp_days.values()),
        },
        "insights": progress_insights(db, user, skills),
    }


def progress_insights(db: Session, user: User, skills: list[dict]) -> dict:
    snap = progress_analyst.snapshot(db, user)
    if snap.insights and snap.insights.get("provider") == ai_client.provider_name:
        return snap.insights
    before = progress_analyst.skill_snapshot_delta(db, user, days=14)
    now = utcnow()
    recent = stats.mistake_window_counts(db, user.id, now - timedelta(days=14), now)
    previous = stats.mistake_window_counts(db, user.id, now - timedelta(days=28), now - timedelta(days=14))
    trends = [
        {"subcategory": sub, "label": label_for(sub), "recent": recent.get(sub, 0), "previous": previous.get(sub, 0)}
        for sub in sorted(set(recent) | set(previous), key=lambda k: -(recent.get(k, 0) + previous.get(k, 0)))[:6]
    ]
    skill_data = [
        {"skill": s["skill"], "score": s["score"] if s["attempts"] else None, "score_before": before.get(s["skill"]), "band": s["band"]} for s in skills
    ]
    ctx = build_context(db, user)
    try:
        parsed, result = ai_client.generate_model(
            "progress_insights",
            {
                "target_band": user.profile.target_band,
                "skills": "\n".join(
                    f"- {d['skill']}: now {d['score']}, two weeks ago {d['score_before']}, band {d['band']}" for d in skill_data if d["score"] is not None
                )
                or "(no data yet)",
                "mistake_trends": "\n".join(f"- {t['label']}: {t['recent']} recent vs {t['previous']} before" for t in trends) or "(no mistakes recorded)",
                "activity": "; ".join(ctx.recent_activity) or "(no recent sessions)",
            },
            ProgressInsightsAI,
            user_id=user.id,
            mock_context={"skills": skill_data, "mistake_trends": trends, "target_band": user.profile.target_band},
        )
        data = parsed.model_dump() | {"provider": result.provider, "generated_at": now.isoformat()}
    except AIError:
        logger.info("Progress insights unavailable")
        return {
            "headline": "Insights are temporarily unavailable - your charts are up to date.",
            "improvements": [],
            "regressions": [],
            "recurring_weaknesses": [],
            "skill_gaps": [],
            "next_focus": "",
            "provider": "none",
        }
    snap.insights = data
    db.commit()
    return data


# --- Missions & achievements ------------------------------------------------------------------------


def missions(db: Session, user: User) -> dict:
    mission = learning_planner.get_or_create_mission(db, user)
    skills = _skill_rows(db, user)
    challenges = gamification.ensure_week_challenges(db, user, gamification_weakest(skills))
    db.commit()
    history = db.scalars(select(DailyMission).where(DailyMission.user_id == user.id).order_by(DailyMission.day.desc()).limit(14)).all()
    return {
        "today": mission_out(mission),
        "challenges": [
            {
                "id": c.id,
                "code": c.code,
                "title": c.title,
                "description": c.description,
                "target": c.target,
                "progress": c.progress,
                "xp_reward": c.xp_reward,
                "completed": c.completed_at is not None,
                "week": c.week,
            }
            for c in challenges
        ],
        "streak": gamification.display_streak(db, user),
        "history": [
            {"day": m.day.isoformat(), "status": m.status, "completed_tasks": sum(1 for t in m.tasks if t.get("completed")), "total_tasks": len(m.tasks)}
            for m in history
        ],
    }


def achievements(db: Session, user: User) -> dict:
    recent_xp = db.scalars(select(XPTransaction).where(XPTransaction.user_id == user.id).order_by(XPTransaction.created_at.desc()).limit(15)).all()
    completed_challenges = db.scalars(
        select(UserChallenge)
        .where(UserChallenge.user_id == user.id, UserChallenge.completed_at.is_not(None))
        .order_by(UserChallenge.completed_at.desc())
        .limit(10)
    ).all()
    return {
        "level": gamification.level_info(db, user),
        "streak": gamification.display_streak(db, user),
        "achievements": gamification.achievement_progress(db, user),
        "recent_xp": [{"amount": x.amount, "reason": x.reason, "description": x.description, "created_at": x.created_at} for x in recent_xp],
        "completed_challenges": [{"title": c.title, "week": c.week, "xp_reward": c.xp_reward} for c in completed_challenges],
    }
