from app.models import ListeningQuestion, ReadingQuestion


def _answers(db, model, questions, *, correct_ids: set[int] | None = None) -> dict:
    out = {}
    for q in questions:
        row = db.get(model, q["id"])
        out[str(q["id"])] = row.answer if correct_ids is None or q["id"] in correct_ids else "zzz wrong"
    return out


def test_reading_generate_hides_answers_and_scores_with_evidence(onboarded, db):
    r = onboarded.post("/reading/generate", json={"question_count": 6})
    assert r.status_code == 201, r.text
    attempt = r.json()
    assert attempt["passage"]["paragraphs"] and len(attempt["questions"]) == 6
    assert attempt["notice"], "mock mode explains that a curated passage was selected"
    assert attempt["results"] == [] and all("answer" not in q for q in attempt["questions"])
    first_two = {q["id"] for q in attempt["questions"][:2]}
    r = onboarded.post(
        "/reading/submit",
        json={"attempt_id": attempt["id"], "answers": _answers(db, ReadingQuestion, attempt["questions"], correct_ids=first_two), "time_spent_seconds": 600},
    )
    assert r.status_code == 200
    result = r.json()["attempt"]
    assert result["correct"] == 2 and result["total"] == 6
    assert result["band"] is not None
    for item in result["results"]:
        assert item["answer"] and item["explanation"] is not None and item["evidence"]
    assert r.json()["outcome"]["xp_gained"] > 0
    history = onboarded.get("/reading/history").json()
    assert history["total"] == 1
    again = onboarded.post("/reading/submit", json={"attempt_id": attempt["id"], "answers": {}})
    assert again.status_code == 422


def test_wrong_reading_answers_become_comprehension_mistakes(onboarded, db):
    attempt = onboarded.post("/reading/generate", json={"question_count": 4}).json()
    onboarded.post("/reading/submit", json={"attempt_id": attempt["id"], "answers": _answers(db, ReadingQuestion, attempt["questions"], correct_ids=set())})
    mistakes = onboarded.get("/mistakes?source=reading").json()
    assert mistakes["total"] >= 1


def test_reading_falls_back_to_curated_content_when_ai_is_down(onboarded, ai_outage):
    r = onboarded.post("/reading/generate", json={"question_count": 5})
    assert r.status_code == 201
    assert "temporarily unavailable" in r.json()["notice"]
    assert "reading_generate" in ai_outage.calls


def test_listening_attempt_has_text_fallback_and_scores(onboarded, db):
    r = onboarded.post("/listening/generate", json={"question_count": 5})
    assert r.status_code == 201, r.text
    attempt = r.json()
    script = attempt["script"]
    assert script["audio_mode"] == "device", "without a TTS provider the client speaks the script with device voices"
    assert all(seg["text"] for seg in script["segments"]), "device voices need the text"
    assert script["transcript_hidden"] is True
    replay = onboarded.post(f"/listening/attempts/{attempt['id']}/replay")
    assert replay.status_code == 200
    r = onboarded.post(
        "/listening/submit",
        json={"attempt_id": attempt["id"], "answers": _answers(db, ListeningQuestion, attempt["questions"]), "time_spent_seconds": 400, "replays": 1},
    )
    assert r.status_code == 200
    result = r.json()["attempt"]
    assert result["correct"] == result["total"] == 5
    assert result["replays"] >= 1 and result["script"]["transcript_hidden"] is False
    assert onboarded.get("/listening/history").json()["total"] == 1


def test_other_learners_cannot_open_attempts(onboarded, make_learner):
    attempt = onboarded.post("/reading/generate", json={"question_count": 4}).json()
    other = make_learner(onboard=True)
    assert other.get(f"/reading/attempts/{attempt['id']}").status_code == 404
    assert other.post("/reading/submit", json={"attempt_id": attempt["id"], "answers": {}}).status_code == 404
