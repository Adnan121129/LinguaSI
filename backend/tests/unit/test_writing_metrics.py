from app.analytics.grammar_rules import detect_errors
from app.analytics.writing_metrics import analyze_essay, heuristic_evaluation
from tests.samples import STRONG_ESSAY, WEAK_ESSAY

PROMPT = "The best way to protect the environment is for individuals to change their behaviour, rather than for governments to introduce new laws."


def _evaluate(text: str, prompt: str = PROMPT):
    errors = detect_errors(text)
    analysis = analyze_essay(text, task_type="task2", module="academic", prompt=prompt, min_words=250, errors=errors)
    return analysis, heuristic_evaluation(analysis, errors, task_type="task2", module="academic", category="opinion")


def test_analysis_measures_basic_features():
    analysis, _ = _evaluate(STRONG_ESSAY)
    assert analysis.word_count > 250
    assert analysis.paragraph_count == 5
    assert 0 < analysis.lexical_diversity <= 1


def test_stronger_essay_receives_higher_estimated_band():
    _, weak = _evaluate(WEAK_ESSAY)
    _, strong = _evaluate(STRONG_ESSAY)
    assert strong.overall > weak.overall
    assert set(strong.criteria) == {"task_response", "coherence_cohesion", "lexical_resource", "grammatical_range_accuracy"}
    for result in strong.criteria.values():
        assert 0 <= result.band <= 9 and (result.band * 2).is_integer()


def test_short_essay_is_flagged_for_word_count():
    _, weak = _evaluate(WEAK_ESSAY)
    assert any("250" in w for w in weak.weaknesses + weak.task_response_issues)
