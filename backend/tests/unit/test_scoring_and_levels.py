import pytest

from app.analytics.scoring import check_answer, normalize_completion
from app.core.levels import accuracy_to_band, band_to_cefr, level_for_xp, level_progress, round_band, round_band_down


@pytest.mark.parametrize(("given", "expected"), [("true", True), ("T", True), ("False", False), ("not given", False)])
def test_true_false_not_given(given, expected):
    ok, _ = check_answer(given, "TRUE", qtype="true_false_not_given")
    assert ok is expected


def test_multiple_choice_accepts_letter_or_text():
    options = ["A. a bus", "B. a train", "C. a bicycle"]
    assert check_answer("B", "a train", qtype="multiple_choice", options=options)[0]
    assert check_answer("a train", "a train", qtype="multiple_choice", options=options)[0]
    assert not check_answer("A", "a train", qtype="multiple_choice", options=options)[0]


def test_completion_respects_word_limit_and_spelling():
    ok, note = check_answer("the old railway station", "railway station", qtype="sentence_completion", word_limit=2)
    assert not ok and "2" in note
    assert check_answer("Railway Station", "railway station", qtype="sentence_completion", word_limit=2)[0]
    ok, note = check_answer("railway stations", "railway station", qtype="sentence_completion")
    assert not ok and "plural" in note


def test_empty_answers_are_wrong():
    assert check_answer("", "TRUE", qtype="true_false_not_given") == (False, "No answer given.")


def test_normalize_completion_strips_articles_and_numbers():
    assert normalize_completion("The  Three Bridges") == normalize_completion("3 bridges")


def test_band_rounding_rules():
    assert round_band(6.25) == 6.5
    assert round_band(6.75) == 7.0
    assert round_band(6.1) == 6.0
    assert round_band_down(6.9) == 6.5
    assert band_to_cefr(6.5) == "B2"
    assert band_to_cefr(7.0) == "C1"


def test_accuracy_to_band_increases_with_accuracy_and_difficulty():
    assert accuracy_to_band(90, 3) > accuracy_to_band(60, 3)
    assert accuracy_to_band(80, 5) >= accuracy_to_band(80, 2)


def test_xp_levels_are_monotonic():
    levels = [level_for_xp(xp) for xp in range(0, 6000, 250)]
    assert levels == sorted(levels)
    progress = level_progress(1234)
    assert 0 <= progress["progress"] <= 1 and progress["level"] == level_for_xp(1234)
