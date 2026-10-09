"""XP, levels, streaks, achievements, daily mission progress and weekly challenges."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import iso_week_key, local_today, utcnow
from app.core.database import insert_or_existing
from app.core.levels import level_for_xp, level_progress
from app.models import Achievement, DailyMission, Streak, User, UserAchievement, UserChallenge, XPTransaction
from app.repositories import stats
from app.schemas.common import AchievementUnlocked, XPGain

STREAK_MILESTONES = {3: 20, 7: 50, 14: 100, 30: 200, 60: 300, 100: 500}
MAX_FREEZES = 2


@dataclass
class RewardState:
    gains: list[XPGain] = field(default_factory=list)
    achievements: list[AchievementUnlocked] = field(default_factory=list)
    mission_progress: list[str] = field(default_factory=list)
    mission_completed: bool = False


def award_xp(
    db: Session,
    user: User,
    amount: int,
    reason: str,
    description: str = "",
    *,
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> XPGain | None:
    if amount <= 0:
        return None
    db.add(XPTransaction(user_id=user.id, amount=amount, reason=reason, description=description[:200], ref_type=ref_type, ref_id=ref_id))
    return XPGain(amount=amount, reason=reason, description=description)


def get_streak(db: Session, user: User) -> Streak:
    streak = db.get(Streak, user.id)
    if streak is None:
        streak = insert_or_existing(
            db, Streak(user_id=user.id, current=0, longest=0, freezes=0, freezes_used=0), select(Streak).where(Streak.user_id == user.id)
        )
    return streak


def touch_streak(db: Session, user: User, state: RewardState) -> tuple[int, bool]:
    """Register activity today. Returns (current_streak, extended_today)."""
    streak = get_streak(db, user)
    today = local_today(user.profile.timezone)
    last = streak.last_active_day
    if last == today:
        return streak.current, False
    if last is None:
        streak.current = 1
    elif last == today - timedelta(days=1):
        streak.current += 1
    else:
        missed = (today - last).days - 1
        if 0 < missed <= (streak.freezes or 0):
            streak.freezes -= missed
            streak.freezes_used = (streak.freezes_used or 0) + missed
            streak.current += 1
        else:
            streak.current = 1
    streak.last_active_day = today
    streak.longest = max(streak.longest or 0, streak.current)
    if streak.current % 7 == 0:
        streak.freezes = min(MAX_FREEZES, (streak.freezes or 0) + 1)
    bonus = STREAK_MILESTONES.get(streak.current)
    if bonus:
        gain = award_xp(db, user, bonus, "streak_bonus", f"{streak.current}-day streak bonus")
        if gain:
            state.gains.append(gain)
    return streak.current, True


def display_streak(db: Session, user: User) -> dict:
    streak = get_streak(db, user)
    today = local_today(user.profile.timezone)
    current = streak.current or 0
    at_risk = False
    if streak.last_active_day is None:
        current = 0
    else:
        gap = (today - streak.last_active_day).days
        if gap == 1:
            at_risk = True
        elif gap > 1 and gap - 1 > (streak.freezes or 0):
            current = 0
        elif gap > 1:
            at_risk = True
    return {
        "current": current,
        "longest": streak.longest or 0,
        "freezes": streak.freezes or 0,
        "active_today": streak.last_active_day == today,
        "at_risk": at_risk,
    }


def level_info(db: Session, user: User) -> dict:
    return level_progress(stats.total_xp(db, user.id))


def check_achievements(db: Session, user: User, state: RewardState) -> None:
    earned_ids = set(db.scalars(select(UserAchievement.achievement_id).where(UserAchievement.user_id == user.id)))
    candidates = [a for a in db.scalars(select(Achievement).order_by(Achievement.sort_order)) if a.id not in earned_ids]
    if not candidates:
        return
    level = level_for_xp(stats.total_xp(db, user.id))
    metrics = stats.achievement_metrics(db, user, level=level)
    for ach in candidates:
        metric = ach.criteria.get("metric")
        target = ach.criteria.get("value", 1)
        if metric in metrics and metrics[metric] >= target:
            unlocked = UserAchievement(user_id=user.id, achievement_id=ach.id, earned_at=utcnow())
            earned = select(UserAchievement).where(UserAchievement.user_id == user.id, UserAchievement.achievement_id == ach.id)
            if insert_or_existing(db, unlocked, earned) is not unlocked:
                continue  # a concurrent request unlocked it a moment ago and awarded the XP
            gain = award_xp(db, user, ach.xp_reward, "achievement", f"Achievement: {ach.name}", ref_type="achievement", ref_id=ach.id)
            if gain:
                state.gains.append(gain)
            state.achievements.append(
                AchievementUnlocked(code=ach.code, name=ach.name, description=ach.description, icon=ach.icon, tier=ach.tier, xp_reward=ach.xp_reward)
            )


def achievement_progress(db: Session, user: User) -> list[dict]:
    earned = {ua.achievement_id: ua.earned_at for ua in db.scalars(select(UserAchievement).where(UserAchievement.user_id == user.id))}
    metrics = stats.achievement_metrics(db, user)
    result = []
    for ach in db.scalars(select(Achievement).order_by(Achievement.sort_order)):
        metric = ach.criteria.get("metric")
        target = float(ach.criteria.get("value", 1))
        value = float(metrics.get(metric, 0))
        result.append(
            {
                "code": ach.code,
                "name": ach.name,
                "description": ach.description,
                "icon": ach.icon,
                "category": ach.category,
                "tier": ach.tier,
                "xp_reward": ach.xp_reward,
                "earned": ach.id in earned,
                "earned_at": earned.get(ach.id),
                "progress": min(1.0, value / target) if target else 1.0,
                "current": value,
                "target": target,
            }
        )
    return result


# --- Daily missions ---------------------------------------------------------------------------


def record_mission_progress(db: Session, user: User, metrics: dict[str, int], state: RewardState) -> None:
    if not metrics:
        return
    today = local_today(user.profile.timezone)
    mission = db.scalar(select(DailyMission).where(DailyMission.user_id == user.id, DailyMission.day == today))
    if mission is None or mission.status == "completed":
        return
    tasks = [dict(t) for t in mission.tasks]
    changed = False
    for task in tasks:
        metric = task.get("metric")
        if task.get("completed") or metric not in metrics:
            continue
        task["progress"] = min(task["target"], task.get("progress", 0) + metrics[metric])
        changed = True
        if task["progress"] >= task["target"]:
            task["completed"] = True
            gain = award_xp(db, user, task.get("xp", 15), "mission_task", f"Mission task: {task['title']}", ref_type="mission", ref_id=mission.id)
            if gain:
                state.gains.append(gain)
            state.mission_progress.append(f"Mission task completed: {task['title']}")
        else:
            state.mission_progress.append(f"{task['title']}: {task['progress']}/{task['target']}")
    if changed:
        mission.tasks = tasks
    if tasks and all(t.get("completed") for t in tasks):
        mission.status = "completed"
        mission.completed_at = utcnow()
        state.mission_completed = True
        if not mission.bonus_awarded:
            mission.bonus_awarded = True
            gain = award_xp(db, user, mission.bonus_xp, "mission_complete", "Daily mission completed", ref_type="mission", ref_id=mission.id)
            if gain:
                state.gains.append(gain)


# --- Weekly challenges ------------------------------------------------------------------------

CHALLENGE_TEMPLATES = {
    "writing_tasks": ("Writing week", "Complete {n} writing tasks this week.", 3, 120),
    "speaking_sessions": ("Speak up", "Complete {n} speaking sessions this week.", 2, 120),
    "vocab_reviews": ("Word workout", "Complete {n} vocabulary reviews this week.", 60, 100),
    "reading_exercises": ("Reading sprint", "Complete {n} reading exercises this week.", 3, 100),
    "listening_exercises": ("Sharp ears", "Complete {n} listening exercises this week.", 3, 100),
    "mistakes_fixed": ("Repair crew", "Complete {n} mistake repair challenges this week.", 2, 100),
    "active_days": ("Consistency counts", "Practise on {n} different days this week.", 5, 150),
}


def ensure_week_challenges(db: Session, user: User, weakest_skill: str | None = None) -> list[UserChallenge]:
    week = iso_week_key(local_today(user.profile.timezone))
    existing = list(db.scalars(select(UserChallenge).where(UserChallenge.user_id == user.id, UserChallenge.week == week)))
    if existing:
        return existing
    skill_metric = {
        "writing": "writing_tasks",
        "speaking": "speaking_sessions",
        "reading": "reading_exercises",
        "listening": "listening_exercises",
        "vocabulary": "vocab_reviews",
        "grammar": "mistakes_fixed",
    }
    chosen = ["active_days", skill_metric.get(weakest_skill or "", "writing_tasks")]
    rng = random.Random(f"{user.id}-{week}")
    others = [m for m in CHALLENGE_TEMPLATES if m not in chosen]
    chosen.append(rng.choice(others))
    rows = []
    for metric in chosen:
        title, desc, target, xp = CHALLENGE_TEMPLATES[metric]
        row = UserChallenge(
            user_id=user.id, week=week, code=metric, title=title, description=desc.format(n=target), metric=metric, target=target, progress=0, xp_reward=xp
        )
        existing = select(UserChallenge).where(UserChallenge.user_id == user.id, UserChallenge.week == week, UserChallenge.code == metric)
        rows.append(insert_or_existing(db, row, existing))
    return rows


def record_challenge_progress(db: Session, user: User, metrics: dict[str, int], state: RewardState, *, new_active_day: bool) -> None:
    week = iso_week_key(local_today(user.profile.timezone))
    challenges = list(db.scalars(select(UserChallenge).where(UserChallenge.user_id == user.id, UserChallenge.week == week)))
    for ch in challenges:
        if ch.completed_at is not None:
            continue
        inc = 1 if (ch.metric == "active_days" and new_active_day) else metrics.get(ch.metric, 0)
        if not inc:
            continue
        ch.progress = min(ch.target, ch.progress + inc)
        if ch.progress >= ch.target:
            ch.completed_at = utcnow()
            gain = award_xp(db, user, ch.xp_reward, "weekly_challenge", f"Weekly challenge: {ch.title}", ref_type="challenge", ref_id=ch.id)
            if gain:
                state.gains.append(gain)
            state.mission_progress.append(f"Weekly challenge completed: {ch.title}")
