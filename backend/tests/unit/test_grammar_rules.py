import pytest

from app.analytics.grammar_rules import detect_errors
from tests.samples import STRONG_ESSAY, WEAK_ESSAY


def _found(text: str) -> set[tuple[str, str]]:
    return {(e.original.lower(), e.corrected.lower()) for e in detect_errors(text, mode="writing", academic=False)}


@pytest.mark.parametrize(
    ("sentence", "original", "corrected"),
    [
        ("She go to school every day.", "she go", "she goes"),
        ("He like football very much.", "he like", "he likes"),
        ("They goes home after work.", "they goes", "they go"),
        ("There is many reasons for this.", "there is many", "there are many"),
        ("We should discuss about this issue.", "discuss about", "discuss"),
        ("Governments should invest on education.", "invest on", "invest in"),
        ("I visit them every days.", "every days", "every day"),
        ("People should help theirselves.", "theirselves", "themselves"),
        ("Students can not afford it.", "can not", "cannot"),
        ("Everyone have a phone now.", "everyone have", "everyone has"),
    ],
)
def test_detects_common_learner_errors(sentence, original, corrected):
    assert (original, corrected) in _found(sentence)


@pytest.mark.parametrize(
    "sentence",
    [
        "Does she go to the gym?",
        "Doesn't he like coffee?",
        "She and he go to the same school.",
        "I think she likes it.",
        "He said that she would go later.",
        "Let it go.",
    ],
)
def test_no_false_positives_on_correct_sentences(sentence):
    assert detect_errors(sentence, mode="writing", academic=False) == []


def test_offsets_point_at_the_error_in_the_original_text():
    errors = detect_errors(WEAK_ESSAY)
    assert errors, "the weak essay contains several detectable errors"
    for e in errors:
        if e.highlight:
            assert WEAK_ESSAY[e.start : e.end].lower() == e.original.lower()


def test_clean_essay_has_no_detections():
    assert detect_errors(STRONG_ESSAY) == []


def test_errors_carry_taxonomy_and_explanations():
    for e in detect_errors(WEAK_ESSAY):
        assert e.category and e.subcategory and e.explanation
        assert e.severity in {"low", "medium", "high"}
