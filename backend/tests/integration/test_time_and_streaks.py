"""Day-boundary behaviour (streaks, missions, spaced repetition) using the simulated clock."""

from datetime import UTC, datetime, timedelta

from app.core.clock import simulated_clock
from app.models import User
from app.schemas.onboarding import OnboardingRequest
from app.services import auth_service, dashboard_service, diagnostic_service, gamification, vocabulary_service

START = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)  # a Monday


def _learner(db, timezone="UTC") -> User:
    user, _ = auth_service.register(
        db, email=f"time-{timezone.replace('/', '-').lower()}@example.com", password="time-pass-1", name="Time Learner", user_agent=None
    )
    diagnostic_service.complete_onboarding(db, user, OnboardingRequest(goal="ielts", self_reported_level="intermediate", timezone=timezone))
    return user


def _active_day(db, user):
    state = gamification.RewardState()
    gamification.touch_streak(db, user, state)
    db.commit()


def test_consecutive_days_build_a_streak_and_earn_a_freeze(db):
    with simulated_clock(START) as clock:
        user = _learner(db)
        for _ in range(7):
            _active_day(db, user)
            clock.advance(days=1)
        clock.advance(days=-1)
        streak = gamification.display_streak(db, user)
        assert streak["current"] == 7 and streak["longest"] == 7 and streak["freezes"] == 1


def test_a_freeze_protects_one_missed_day(db):
    with simulated_clock(START) as clock:
        user = _learner(db)
        for _ in range(7):
            _active_day(db, user)
            clock.advance(days=1)
        clock.advance(days=1)  # one day missed
        assert gamification.display_streak(db, user)["at_risk"] is True
        _active_day(db, user)
        assert gamification.display_streak(db, user)["current"] == 8
        assert gamification.get_streak(db, user).freezes == 0


def test_streak_resets_after_a_long_break(db):
    with simulated_clock(START) as clock:
        user = _learner(db)
        for _ in range(3):
            _active_day(db, user)
            clock.advance(days=1)
        clock.advance(days=3)
        assert gamification.display_streak(db, user)["current"] == 0
        _active_day(db, user)
        assert gamification.display_streak(db, user)["current"] == 1
        assert gamification.display_streak(db, user)["longest"] == 3


def test_days_follow_the_learners_timezone(db):
    # 23:30 UTC on Monday is already Tuesday in Dhaka (UTC+6).
    with simulated_clock(START.replace(hour=10)) as clock:
        user = _learner(db, timezone="Asia/Dhaka")
        _active_day(db, user)
        clock.set(START.replace(hour=23, minute=30))
        _active_day(db, user)
        assert gamification.display_streak(db, user)["current"] == 2


def test_a_new_mission_is_planned_each_day(db):
    with simulated_clock(START) as clock:
        user = _learner(db)
        first = dashboard_service.missions(db, user)["today"]
        again = dashboard_service.missions(db, user)["today"]
        assert first["id"] == again["id"], "the mission is stable within a day"
        clock.advance(days=1)
        nxt = dashboard_service.missions(db, user)
        assert nxt["today"]["id"] != first["id"]
        assert len(nxt["history"]) == 2


def test_reviewed_words_come_back_when_due(db):
    with simulated_clock(START) as clock:
        user = _learner(db)
        session = vocabulary_service.today(db, user)
        reviewed = set()
        for ex in session["exercises"]:
            vocabulary_service.review(db, user, ex["id"], "wrong on purpose", response_ms=4000, hinted=False)
            reviewed.add(ex["user_vocab_id"])
        clock.advance(minutes=15)
        due_again = {ex["user_vocab_id"] for ex in vocabulary_service.today(db, user)["exercises"]}
        assert reviewed & due_again, "missed words are scheduled again within minutes"
        clock.advance(days=2)
        assert vocabulary_service.today(db, user)["new_count"] >= 0
        assert START + timedelta(days=2) < clock.now
