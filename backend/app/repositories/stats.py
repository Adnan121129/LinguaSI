"""Aggregate queries about a learner, reused by SI Core, the dashboard, achievements and admin."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import distinct, func, select, true
from sqlalchemy.orm import Session

from app.core.clock import get_zone, local_today, start_of_week, utcnow
from app.core.levels import level_for_xp
from app.core.taxonomy import label_for
from app.models import (
    DailyMission,
    DiagnosticAttempt,
    ListeningAttempt,
    Mistake,
    PracticeSet,
    Profile,
    ReadingAttempt,
    SpeakingSession,
    Streak,
    StudySession,
    TutorConversation,
    TutorMessage,
    User,
    UserChallenge,
    UserVocabulary,
    WritingEvaluation,
    WritingSubmission,
    XPTransaction,
)


def local_day_start_utc(day: date, tz_name: str | None) -> datetime:
    return datetime.combine(day, time.min, tzinfo=get_zone(tz_name)).astimezone(UTC)


def total_xp(db: Session, user_id: int) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(XPTransaction.user_id == user_id)) or 0)


def xp_since(db: Session, user_id: int, since: datetime) -> int:
    return int(
        db.scalar(select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(XPTransaction.user_id == user_id, XPTransaction.created_at >= since)) or 0
    )


def xp_today(db: Session, user: User) -> int:
    tz = user.profile.timezone if user.profile else "UTC"
    return xp_since(db, user.id, local_day_start_utc(local_today(tz), tz))


def minutes_by_day(db: Session, user: User, days: int) -> dict[date, int]:
    tz = user.profile.timezone if user.profile else "UTC"
    zone = get_zone(tz)
    start_day = local_today(tz) - timedelta(days=days - 1)
    since = local_day_start_utc(start_day, tz)
    rows = db.execute(
        select(StudySession.started_at, StudySession.duration_seconds).where(StudySession.user_id == user.id, StudySession.started_at >= since)
    ).all()
    result: dict[date, int] = {start_day + timedelta(days=i): 0 for i in range(days)}
    for started_at, seconds in rows:
        day = started_at.astimezone(zone).date()
        if day in result:
            result[day] += max(1, round((seconds or 0) / 60))
    return result


def xp_by_day(db: Session, user: User, days: int) -> dict[date, int]:
    tz = user.profile.timezone if user.profile else "UTC"
    zone = get_zone(tz)
    start_day = local_today(tz) - timedelta(days=days - 1)
    since = local_day_start_utc(start_day, tz)
    rows = db.execute(select(XPTransaction.created_at, XPTransaction.amount).where(XPTransaction.user_id == user.id, XPTransaction.created_at >= since)).all()
    result: dict[date, int] = {start_day + timedelta(days=i): 0 for i in range(days)}
    for created_at, amount in rows:
        day = created_at.astimezone(zone).date()
        if day in result:
            result[day] += amount
    return result


def vocab_counts(db: Session, user_id: int) -> dict[str, int]:
    rows = db.execute(select(UserVocabulary.state, func.count(UserVocabulary.id)).where(UserVocabulary.user_id == user_id).group_by(UserVocabulary.state)).all()
    counts = {state: 0 for state in ("new", "learning", "familiar", "strong", "mastered")}
    counts.update({state: n for state, n in rows})
    counts["total"] = sum(n for _, n in rows)
    counts["known"] = counts["familiar"] + counts["strong"] + counts["mastered"]
    return counts


def vocab_due_count(db: Session, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(UserVocabulary.id)).where(UserVocabulary.user_id == user_id, UserVocabulary.due_at <= utcnow(), UserVocabulary.state != "new")
        )
        or 0
    )


def mistake_counts(db: Session, user_id: int) -> dict[str, int]:
    rows = db.execute(
        select(Mistake.status, func.count(Mistake.id), func.coalesce(func.sum(Mistake.occurrences), 0))
        .where(Mistake.user_id == user_id)
        .group_by(Mistake.status)
    ).all()
    counts = {"unresolved": 0, "corrected": 0, "mastered": 0}
    occurrences = 0
    for status, n, occ in rows:
        counts[status] = n
        occurrences += int(occ)
    counts["total"] = sum(counts.values())
    counts["occurrences"] = occurrences
    return counts


# Missed vocabulary reviews are scheduled again by the spaced-repetition engine, so they are kept out of
# "recurring mistake" analysis (weak areas, AI context, revision focus), which is about language production.
RECALL_SUBCATEGORIES = ("vocabulary_recall",)


def recurring_mistakes(db: Session, user_id: int, days: int = 30, limit: int = 5, min_count: int = 2, *, include_recall: bool = False) -> list[dict]:
    since = utcnow() - timedelta(days=days)
    rows = db.execute(
        select(Mistake.subcategory, Mistake.category, func.sum(Mistake.occurrences).label("n"), func.max(Mistake.last_seen_at))
        .where(
            Mistake.user_id == user_id,
            Mistake.last_seen_at >= since,
            Mistake.status != "mastered",
            true() if include_recall else Mistake.subcategory.not_in(RECALL_SUBCATEGORIES),
        )
        .group_by(Mistake.subcategory, Mistake.category)
        .order_by(func.sum(Mistake.occurrences).desc())
        .limit(limit)
    ).all()
    result = []
    for sub, cat, n, last in rows:
        if int(n) < min_count:
            continue
        example = db.scalar(select(Mistake).where(Mistake.user_id == user_id, Mistake.subcategory == sub).order_by(Mistake.last_seen_at.desc()).limit(1))
        result.append(
            {
                "subcategory": sub,
                "category": cat,
                "label": label_for(sub),
                "count": int(n),
                "last_seen": last,
                "example": {"original": example.original, "corrected": example.corrected} if example else None,
            }
        )
    return result


def mistake_window_counts(db: Session, user_id: int, start: datetime, end: datetime) -> dict[str, int]:
    rows = db.execute(
        select(Mistake.subcategory, func.count(Mistake.id))
        .where(Mistake.user_id == user_id, Mistake.first_seen_at >= start, Mistake.first_seen_at < end)
        .group_by(Mistake.subcategory)
    ).all()
    return {sub: int(n) for sub, n in rows}


def achievement_metrics(db: Session, user: User, level: int | None = None) -> dict[str, float]:
    uid = user.id
    profile: Profile = user.profile
    week_start_day = start_of_week(local_today(profile.timezone))
    week_start = local_day_start_utc(week_start_day, profile.timezone)
    counts = vocab_counts(db, uid)
    first_diag = db.scalar(
        select(DiagnosticAttempt.estimated_band)
        .where(DiagnosticAttempt.user_id == uid, DiagnosticAttempt.status == "completed")
        .order_by(DiagnosticAttempt.completed_at.asc())
        .limit(1)
    )
    band_improvement = 0.0
    if first_diag is not None and profile.estimated_band is not None:
        band_improvement = profile.estimated_band - first_diag
    streak = db.get(Streak, uid)
    return {
        "diagnostic_completed": float(profile.diagnostic_completed),
        "writing_submissions": db.scalar(
            select(func.count(WritingSubmission.id)).where(WritingSubmission.user_id == uid, WritingSubmission.status == "evaluated")
        )
        or 0,
        "writing_band_max": db.scalar(select(func.max(WritingEvaluation.overall_band)).where(WritingEvaluation.user_id == uid)) or 0,
        "speaking_sessions": db.scalar(select(func.count(SpeakingSession.id)).where(SpeakingSession.user_id == uid, SpeakingSession.status == "completed"))
        or 0,
        "reading_attempts": db.scalar(select(func.count(ReadingAttempt.id)).where(ReadingAttempt.user_id == uid, ReadingAttempt.status == "submitted")) or 0,
        "reading_high_scores": db.scalar(
            select(func.count(ReadingAttempt.id)).where(ReadingAttempt.user_id == uid, ReadingAttempt.status == "submitted", ReadingAttempt.accuracy >= 85)
        )
        or 0,
        "listening_attempts": db.scalar(select(func.count(ListeningAttempt.id)).where(ListeningAttempt.user_id == uid, ListeningAttempt.status == "submitted"))
        or 0,
        "vocab_known": counts["known"],
        "vocab_mastered": counts["mastered"],
        "grammar_high_scores": db.scalar(
            select(func.count(PracticeSet.id)).where(PracticeSet.user_id == uid, PracticeSet.status == "completed", PracticeSet.accuracy >= 80)
        )
        or 0,
        "mistakes_mastered": db.scalar(select(func.count(Mistake.id)).where(Mistake.user_id == uid, Mistake.status == "mastered")) or 0,
        "streak": streak.current if streak else 0,
        "missions_completed": db.scalar(select(func.count(DailyMission.id)).where(DailyMission.user_id == uid, DailyMission.status == "completed")) or 0,
        "band_improvement": band_improvement,
        "level": level if level is not None else level_for_xp(total_xp(db, uid)),
        "tutor_messages": db.scalar(
            select(func.count(TutorMessage.id))
            .join(TutorConversation, TutorConversation.id == TutorMessage.conversation_id)
            .where(TutorConversation.user_id == uid, TutorMessage.role == "user")
        )
        or 0,
        "skills_this_week": db.scalar(
            select(func.count(distinct(StudySession.activity))).where(
                StudySession.user_id == uid,
                StudySession.started_at >= week_start,
                StudySession.activity.in_(("writing", "speaking", "reading", "listening", "vocabulary", "grammar")),
            )
        )
        or 0,
        "challenges_completed": db.scalar(select(func.count(UserChallenge.id)).where(UserChallenge.user_id == uid, UserChallenge.completed_at.is_not(None)))
        or 0,
    }


def active_days(db: Session, user: User, since_day: date) -> int:
    tz = user.profile.timezone
    zone = get_zone(tz)
    rows = db.scalars(
        select(StudySession.started_at).where(StudySession.user_id == user.id, StudySession.started_at >= local_day_start_utc(since_day, tz))
    ).all()
    return len({r.astimezone(zone).date() for r in rows})


def skill_session_counts(db: Session, user_id: int, since: datetime) -> dict[str, int]:
    rows = db.execute(
        select(StudySession.activity, func.count(StudySession.id))
        .where(StudySession.user_id == user_id, StudySession.started_at >= since)
        .group_by(StudySession.activity)
    ).all()
    return {a: int(n) for a, n in rows}


def question_type_accuracy(db: Session, user_id: int, model, limit: int = 8) -> dict[str, dict]:
    """Per question-type accuracy over the learner's recent reading or listening attempts."""
    attempts = db.scalars(select(model).where(model.user_id == user_id, model.status == "submitted").order_by(model.submitted_at.desc()).limit(limit)).all()
    stats: dict[str, dict] = {}
    for attempt in attempts:
        for result in attempt.results or []:
            entry = stats.setdefault(result.get("qtype", "other"), {"correct": 0, "total": 0})
            entry["total"] += 1
            entry["correct"] += 1 if result.get("correct") else 0
    for entry in stats.values():
        entry["accuracy"] = round(entry["correct"] / entry["total"] * 100, 1) if entry["total"] else 0.0
    return stats
