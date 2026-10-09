import json

from app.core.config import settings
from tests.samples import SPEAKING_ANSWER

PAUSES = json.dumps({"measured": True, "count": 3, "long_count": 1, "total_silence_seconds": 2.5})


def _answer(learner, session_id, text=SPEAKING_ANSWER, **extra):
    data = {"session_id": str(session_id), "transcript": text, "transcript_source": "browser", "duration_seconds": "28", "pauses": PAUSES} | extra
    return learner.post("/speaking/session/respond", data=data)


def test_full_mock_test_runs_through_all_parts_and_evaluates(onboarded):
    r = onboarded.post("/speaking/session/start", json={"mode": "full"})
    assert r.status_code == 201, r.text
    start = r.json()
    turn = start["turn"]
    assert turn["part"] == 1 and turn["examiner_text"]
    assert "speech" in start
    parts_seen, followups = {1}, 0
    for _ in range(25):
        r = _answer(onboarded, start["session"]["id"])
        assert r.status_code == 200, r.text
        body = r.json()
        assert "band" not in json.dumps(body["transcript"]).lower(), "no scores are shown during the test"
        if body["done"]:
            break
        nxt = body["next"]
        parts_seen.add(nxt["part"])
        followups += nxt["is_followup"]
        if nxt["kind"] == "cue_card":
            assert nxt["cue_card"]["bullets"] and nxt["prep_seconds"] == 60
    assert body["done"] and parts_seen == {1, 2, 3}
    assert followups >= 1, "the examiner asks follow-up questions"

    r = onboarded.post("/speaking/session/finish", json={"session_id": start["session"]["id"]})
    assert r.status_code == 200, r.text
    finished = r.json()
    evaluation = finished["session"]["evaluation"]
    assert evaluation["label"] == "AI Estimated Band" and 0 < evaluation["overall_band"] <= 9
    assert evaluation["pronunciation"] is None, "pronunciation is not invented without audio evidence"
    assert evaluation["pronunciation_note"]
    assert evaluation["hesitation"]["measured"] is True
    assert finished["outcome"]["xp_gained"] >= 60
    transcripts = finished["session"]["transcripts"]
    assert len(transcripts) >= 10 and all(t["transcript"] for t in transcripts)
    history = onboarded.get("/speaking/history").json()
    assert history["total"] == 1 and history["items"][0]["overall_band"] == evaluation["overall_band"]


def test_empty_answers_are_rejected_and_typed_answers_accepted(onboarded):
    start = onboarded.post("/speaking/session/start", json={"mode": "part1"}).json()
    sid = start["session"]["id"]
    r = onboarded.post("/speaking/session/respond", data={"session_id": str(sid), "transcript": "   "})
    assert r.status_code == 422 and r.json()["error"]["code"] == "empty_answer"
    r = onboarded.post("/speaking/session/respond", data={"session_id": str(sid), "transcript": SPEAKING_ANSWER, "transcript_source": "typed"})
    assert r.status_code == 200 and r.json()["transcript"]["transcript_source"] == "typed"


def test_finish_requires_an_answer_and_abandon_works(onboarded):
    start = onboarded.post("/speaking/session/start", json={"mode": "part1"}).json()
    sid = start["session"]["id"]
    r = onboarded.post("/speaking/session/finish", json={"session_id": sid})
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_answers"
    assert onboarded.post(f"/speaking/session/{sid}/abandon").status_code == 200
    assert onboarded.get(f"/speaking/sessions/{sid}").json()["status"] == "abandoned"


def test_recordings_are_stored_and_replayable_by_owner_only(onboarded, make_learner):
    start = onboarded.post("/speaking/session/start", json={"mode": "part1"}).json()
    files = {"audio": ("answer.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm")}
    r = onboarded.post(
        "/speaking/session/respond",
        data={"session_id": str(start["session"]["id"]), "transcript": SPEAKING_ANSWER, "transcript_source": "browser", "duration_seconds": "25"},
        files=files,
    )
    assert r.status_code == 200
    transcript = r.json()["transcript"]
    assert transcript["has_audio"] and transcript["audio_url"]
    audio = onboarded.get(f"/speaking/audio/{transcript['id']}")
    assert audio.status_code == 200 and audio.content.startswith(b"\x1aE\xdf\xa3")
    other = make_learner(onboard=True)
    assert other.get(f"/speaking/audio/{transcript['id']}").status_code == 404


def test_recordings_are_only_ever_served_as_audio(onboarded):
    start = onboarded.post("/speaking/session/start", json={"mode": "part1"}).json()
    files = {"audio": ("answer.html", b"<script>alert(1)</script>", "text/html")}
    r = onboarded.post("/speaking/session/respond", data={"session_id": str(start["session"]["id"]), "transcript": SPEAKING_ANSWER}, files=files)
    assert r.status_code == 200
    audio = onboarded.get(f"/speaking/audio/{r.json()['transcript']['id']}")
    assert audio.headers["content-type"].startswith("audio/") and audio.headers["x-content-type-options"] == "nosniff"


def test_oversized_recordings_are_rejected(onboarded, monkeypatch):
    monkeypatch.setattr(settings, "max_audio_upload_mb", 1)
    start = onboarded.post("/speaking/session/start", json={"mode": "part1"}).json()
    files = {"audio": ("answer.webm", b"\0" * (1024 * 1024 + 10), "audio/webm")}
    r = onboarded.post("/speaking/session/respond", data={"session_id": str(start["session"]["id"]), "transcript": SPEAKING_ANSWER}, files=files)
    assert r.status_code == 422 and "smaller than 1 MB" in r.json()["error"]["message"]


def test_evaluation_outage_keeps_answers(onboarded, ai_outage):
    from app.ai.client import ai_client

    ai_client.set_provider(None)
    start = onboarded.post("/speaking/session/start", json={"mode": "part1"}).json()
    _answer(onboarded, start["session"]["id"])
    ai_client.set_provider(ai_outage)
    r = onboarded.post("/speaking/session/finish", json={"session_id": start["session"]["id"]})
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_unavailable"
    session = onboarded.get(f"/speaking/sessions/{start['session']['id']}").json()
    assert session["status"] == "evaluation_failed" and session["transcripts"]
