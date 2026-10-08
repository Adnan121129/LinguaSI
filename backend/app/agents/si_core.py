"""SI Core - the orchestration layer that makes LinguaSI's intelligence cross-skill.

Every completed activity (writing, speaking, reading, listening, vocabulary, practice,
diagnostic...) is reported to SI Core as an ActivityEvent. SI Core then, in one transaction:

  1. logs the study session and updates the streak
  2. updates skill profiles through the adaptive difficulty engine        (Progress Analyst)
  3. stores errors in the mistake tracker and detects recurring patterns    (Error Analyst)
  4. credits vocabulary used in writing/speaking                            (Vocabulary Engine)
  5. reacts to signals across skills - e.g. collocation errors in Writing
     add collocations to the vocabulary queue, which then become Speaking
     targets and Reading content                                           (Vocabulary Engine)
  6. awards XP, mission and challenge progress, achievements                (gamification)
  7. refreshes the learner profile insights and daily snapshot              (Progress Analyst)
  8. refreshes recommendations                                              (Learning Planner)
  9. records a transparent SI activity feed entry for every cross-skill action

The returned ActivityOutcome tells the learner exactly what changed and why.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.agents import error_analyst, learning_planner, progress_analyst, vocabulary_engine
from app.agents.error_analyst import ErrorRecord, Signal
from app.agents.progress_analyst import SkillResult
from app.core.clock import utcnow
from app.core.levels import level_for_xp, level_title
from app.models import SIEvent, StudySession, User
from app.repositories import stats
from app.schemas.common import ActivityOutcome
from app.services import gamification

logger = logging.getLogger("linguasi.si_core")


@dataclass
class ActivityEvent:
    activity: str
    title: str
    duration_seconds: int = 0
    ref_type: str | None = None
    ref_id: int | None = None
    score: float | None = None
    skill_results: list[SkillResult] = field(default_factory=list)
    errors: list[ErrorRecord] = field(default_factory=list)
    usage_text: str | None = None
    usage_source: str | None = None  # writing | speaking
    topic: str | None = None
    xp: list[tuple[int, str, str]] = field(default_factory=list)  # (amount, reason, description)
    mission_metrics: dict[str, int] = field(default_factory=dict)
    extra_signals: list[Signal] = field(default_factory=list)
    misspelled_words: list[str] = field(default_factory=list)
    completes_kinds: set[str] = field(default_factory=set)
    focus: str | None = None
    meta: dict = field(default_factory=dict)
    started_at: datetime | None = None


def _record_si_event(db: Session, user: User, source: str, signal: str, title: str, detail: str, actions: list[str], data: dict | None = None) -> None:
    db.add(SIEvent(user_id=user.id, source=source, signal=signal, title=title[:200], detail=detail, actions=actions, data=data or {}))


def process_activity(db: Session, user: User, event: ActivityEvent) -> ActivityOutcome:
    now = utcnow()
    xp_before = stats.total_xp(db, user.id)
    level_before = level_for_xp(xp_before)
    rewards = gamification.RewardState()
    si_actions: list[str] = []

    # 1. study session + streak
    started = event.started_at or (now - timedelta(seconds=event.duration_seconds or 0))
    session = StudySession(
        user_id=user.id,
        activity=event.activity,
        ref_type=event.ref_type,
        ref_id=event.ref_id,
        title=event.title[:200],
        started_at=started,
        ended_at=now,
        duration_seconds=int(event.duration_seconds or 0),
        score=event.score,
        meta=event.meta,
    )
    db.add(session)
    streak_value, extended = gamification.touch_streak(db, user, rewards)

    # 2. skill profiles / adaptive difficulty
    for update in progress_analyst.apply_skill_results(db, user, event.skill_results):
        if update.reason:
            direction = "increased" if update.difficulty_after > update.difficulty_before else "reduced"
            message = f"{update.skill.title()} difficulty {direction} to level {update.difficulty_after}. {update.reason}"
            si_actions.append(message)
            _record_si_event(db, user, update.skill, "difficulty_change", f"{update.skill.title()} difficulty {direction}", update.reason, [message])

    # 3. mistakes and pattern signals
    signals: list[Signal] = list(event.extra_signals)
    if event.errors:
        records = error_analyst.normalise_records(event.errors, user_id=user.id)
        _, detected = error_analyst.record_errors(db, user, records)
        signals.extend(detected)
        repeated = sum(1 for r in records if r.subcategory in {s.subcategory for s in detected})
        si_actions.append(
            f"{len(records)} mistake{'s' if len(records) != 1 else ''} saved to My Mistakes"
            + (f" ({repeated} part of recurring patterns)." if repeated else ".")
        )

    # 4. vocabulary usage in context
    if event.usage_text and event.usage_source:
        used = vocabulary_engine.record_usage(db, user, event.usage_text, event.usage_source)
        if used:
            preview = ", ".join(used[:5])
            message = f"You used {len(used)} of your learning words in {event.usage_source}: {preview}."
            si_actions.append(message)
            _record_si_event(db, user, event.usage_source, "vocabulary_used", "Vocabulary used in context", message, [message], {"words": used})

    # 5. cross-skill reactions to signals
    if signals:
        vocab_actions = vocabulary_engine.react_to_signals(db, user, signals, topic=event.topic)
        si_actions.extend(vocab_actions)
        for signal in signals:
            follow_ups = [a for a in vocab_actions if signal.title.lower() in a.lower()]
            if signal.key == "collocation_weakness":
                follow_ups.append("Your next speaking session will invite you to use these collocations, and generated reading passages will include them.")
            elif signal.key == "grammar_pattern" and signal.subcategory:
                follow_ups.append(f"A '{signal.subcategory.replace('_', ' ')} repair challenge' is now recommended.")
            elif signal.key == "fluency_weakness":
                follow_ups.append("Short Part 1 fluency drills are now recommended.")
            elif signal.key == "comprehension_pattern":
                follow_ups.append("Upcoming practice will include more of this question type with explanations.")
            _record_si_event(db, user, signal.source, signal.key, signal.title, signal.detail, follow_ups, signal.data | {"subcategory": signal.subcategory})
    if event.misspelled_words:
        added = vocabulary_engine.add_misspelled_words(db, user, event.misspelled_words)
        if added:
            si_actions.append(f"Added misspelled word{'s' if len(added) > 1 else ''} to your reviews: {', '.join(added)}.")

    # 6. rewards
    for amount, reason, description in event.xp:
        gain = gamification.award_xp(db, user, amount, reason, description, ref_type=event.ref_type, ref_id=event.ref_id)
        if gain:
            rewards.gains.append(gain)
    db.flush()
    gamification.record_mission_progress(db, user, event.mission_metrics, rewards)
    gamification.ensure_week_challenges(db, user)
    gamification.record_challenge_progress(db, user, event.mission_metrics, rewards, new_active_day=extended)
    db.flush()

    # 7. learner profile insights + snapshot, 8. recommendations
    progress_analyst.refresh_insights(db, user)
    if event.completes_kinds:
        learning_planner.complete_recommendations(db, user, event.completes_kinds, event.focus)
    learning_planner.refresh_recommendations(db, user)
    gamification.check_achievements(db, user, rewards)
    db.flush()
    progress_analyst.snapshot(db, user)

    xp_after = stats.total_xp(db, user.id)
    level_after = level_for_xp(xp_after)
    session.xp_earned = xp_after - xp_before
    db.commit()

    return ActivityOutcome(
        xp_gained=xp_after - xp_before,
        xp_breakdown=rewards.gains,
        total_xp=xp_after,
        level=level_after,
        level_title=level_title(level_after),
        leveled_up=level_after > level_before,
        streak=streak_value,
        streak_extended=extended,
        achievements=rewards.achievements,
        mission_progress=rewards.mission_progress,
        mission_completed=rewards.mission_completed,
        si_actions=si_actions,
    )
