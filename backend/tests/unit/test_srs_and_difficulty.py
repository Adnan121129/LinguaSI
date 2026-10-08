from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.analytics import srs
from app.analytics.difficulty import apply_result

NOW = datetime(2026, 1, 1, 9, tzinfo=UTC)


@dataclass
class Word:
    state: str = "new"
    correct_count: int = 0
    incorrect_count: int = 0
    streak: int = 0
    lapses: int = 0
    ease: float = 2.5
    interval_days: float = 0.0
    due_at: datetime | None = None
    last_reviewed_at: datetime | None = None


def test_correct_answers_progress_through_states_with_growing_intervals():
    w = Word()
    states, intervals = [], []
    now = NOW
    for _ in range(6):
        states.append(srs.schedule(w, 5, now))
        intervals.append(w.interval_days)
        now = w.due_at
    assert states[0] == "learning"
    assert "familiar" in states and states[-1] in ("strong", "mastered")
    assert intervals == sorted(intervals)
    assert w.due_at > NOW + timedelta(days=20)


def test_wrong_answer_resets_and_counts_a_lapse():
    w = Word()
    now = NOW
    for _ in range(4):
        srs.schedule(w, 5, now)
        now = w.due_at
    assert w.state in ("familiar", "strong", "mastered")
    ease_before = w.ease
    state = srs.schedule(w, 1, now)
    assert state == "learning"
    assert w.lapses == 1 and w.streak == 0
    assert w.due_at == now + timedelta(minutes=10)
    assert w.ease < ease_before


def test_quality_reflects_speed_and_hints():
    assert srs.quality_from(False, 1000) == 1
    assert srs.quality_from(True, 2000) == 5
    assert srs.quality_from(True, 20000) == 3
    assert srs.quality_from(True, 2000, hinted=True) == 3


def test_mark_known_fast_tracks_to_mastered():
    w = Word()
    assert srs.mark_known(w, NOW) == "mastered"
    assert w.due_at == NOW + timedelta(days=30)


@dataclass
class Profile:
    skill: str = "reading"
    score: float = 0.0
    band: float | None = None
    difficulty: int = 3
    attempts: int = 0
    confidence: float = 0.0
    trend: str = "new"
    recent: list = field(default_factory=list)
    last_practiced_at: datetime | None = None


def test_difficulty_rises_only_after_three_strong_results():
    p = Profile()
    for score in (90, 92):
        update = apply_result(p, score=score, band=7.0, difficulty=3, at=NOW)
        assert update.difficulty_after == 3, "one or two good results must not change difficulty"
    update = apply_result(p, score=88, band=7.0, difficulty=3, at=NOW)
    assert update.difficulty_after == 4 and "level 4" in update.reason


def test_difficulty_eases_after_two_weak_results():
    p = Profile()
    apply_result(p, score=40, band=5.0, difficulty=3, at=NOW)
    update = apply_result(p, score=50, band=5.0, difficulty=3, at=NOW)
    assert update.difficulty_after == 2


def test_single_bad_result_does_not_move_difficulty():
    p = Profile()
    for score in (80, 82, 78):
        apply_result(p, score=score, band=6.5, difficulty=3, at=NOW)
    update = apply_result(p, score=20, band=4.0, difficulty=3, at=NOW)
    assert update.difficulty_after == 3
    assert p.score > 20, "the skill score is smoothed, not replaced"


def test_one_outstanding_session_does_not_promote():
    p = Profile()
    for score in (70, 72):
        apply_result(p, score=score, band=6.0, difficulty=3, at=NOW)
    update = apply_result(p, score=100, band=7.5, difficulty=3, at=NOW)
    assert update.difficulty_after == 3
