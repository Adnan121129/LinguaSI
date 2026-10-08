from app.analytics.speaking_metrics import aggregate, analyze_response, count_fillers, heuristic_speaking
from tests.samples import SPEAKING_ANSWER


def test_measured_duration_and_pauses_are_used():
    m = analyze_response(
        SPEAKING_ANSWER, question="Do you work or study?", part=1, duration_seconds=30, pauses={"count": 4, "long_count": 1, "total_silence_seconds": 3.2}
    )
    assert m.pauses_measured is True
    assert m.long_pauses == 1
    assert 80 < m.wpm < 120


def test_unknown_duration_is_estimated_and_pauses_not_claimed():
    m = analyze_response(SPEAKING_ANSWER, question="Do you work or study?", part=1)
    assert m.pauses_measured is False


def test_fillers_are_counted():
    fillers = count_fillers("Um, I think, uh, it's like, you know, quite good. Um.")
    assert sum(fillers.values()) >= 4


def test_pronunciation_is_not_assessed_without_audio_evidence():
    m = analyze_response(SPEAKING_ANSWER, question="Do you work or study?", part=1, duration_seconds=30)
    agg = aggregate([{"transcript": SPEAKING_ANSWER, "part": 1, "metrics": m.to_dict(), "stt_confidence": None}])
    result = heuristic_speaking(agg, [])
    assert result.pronunciation is None
    assert 0 < result.overall <= 9
