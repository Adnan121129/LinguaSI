from app.models import Mistake, WritingError
from tests.samples import STRONG_ESSAY, WEAK_ESSAY


def _task(learner, task_type="task2"):
    r = learner.get(f"/writing/tasks?task_type={task_type}&module=academic")
    assert r.status_code == 200
    return next(t for t in r.json()["items"] if t["task_type"] == task_type)


def _start(learner, mode="exam", task_type="task2"):
    task = _task(learner, task_type)
    r = learner.post("/writing/submissions", json={"task_id": task["id"], "mode": mode})
    assert r.status_code == 201, r.text
    return r.json()


def test_task_listing_and_generation(onboarded):
    tasks = onboarded.get("/writing/tasks?task_type=task1").json()
    assert tasks["total"] >= 1 and all(t["task_type"] == "task1" for t in tasks["items"])
    assert any(t["visual"] for t in tasks["items"]), "academic Task 1 tasks include chart data"
    r = onboarded.post("/writing/generate", json={"module": "academic", "task_type": "task2", "topic": "technology"})
    assert r.status_code == 200
    generated = r.json()["task"]
    assert generated["prompt"] and generated["min_words"] == 250


def test_autosave_and_resume_draft(onboarded):
    sub = _start(onboarded)
    r = onboarded.put(f"/writing/submissions/{sub['id']}", json={"content": "First draft sentence here.", "time_spent_seconds": 60})
    assert r.status_code == 200 and r.json()["word_count"] == 4
    again = onboarded.post("/writing/submissions", json={"task_id": sub["task"]["id"], "mode": "tutor"}).json()
    assert again["id"] == sub["id"] and again["content"] == "First draft sentence here."


def test_tutor_hints_guide_without_writing_the_essay(onboarded):
    sub = _start(onboarded, mode="tutor")
    draft = WEAK_ESSAY.split("\n\n")[0]
    r = onboarded.post(f"/writing/submissions/{sub['id']}/hint", json={"question": "Is my introduction clear?", "content": draft})
    assert r.status_code == 200
    hint = r.json()
    assert hint["hints"] and hint["guiding_questions"]
    assert hint["hints_used"] == 1
    combined = " ".join(hint["hints"] + hint["observations"] + [hint["structure_feedback"]])
    assert len(combined.split()) < 400, "hints stay short - no model answer"


def test_evaluation_returns_estimated_bands_errors_and_updates_learning_profile(onboarded, db):
    sub = _start(onboarded)
    r = onboarded.post("/writing/evaluate", json={"submission_id": sub["id"], "content": WEAK_ESSAY, "time_spent_seconds": 1800})
    assert r.status_code == 200, r.text
    body = r.json()
    evaluation = body["submission"]["evaluation"]
    assert evaluation["label"] == "AI Estimated Band"
    assert "not an official IELTS score" in evaluation["disclaimer"]
    assert {c["key"] for c in evaluation["criteria"]} == {"task_response", "coherence_cohesion", "lexical_resource", "grammatical_range_accuracy"}
    assert 0 < evaluation["overall_band"] < 9
    assert evaluation["errors"], "detected errors are returned with positions"
    for err in evaluation["errors"]:
        if err["start_offset"] is not None:
            assert WEAK_ESSAY[err["start_offset"] : err["end_offset"]].lower() == err["original"].lower()
    # SI Core: XP, streak and structured mistakes stored for the tracker
    outcome = body["outcome"]
    assert outcome["xp_gained"] >= 50 and outcome["streak"] == 1
    assert db.query(WritingError).filter_by(submission_id=sub["id"]).count() == len(evaluation["errors"])
    tracked = db.query(Mistake).filter_by(user_id=onboarded.id, source="writing").all()
    assert tracked and all(m.subcategory and m.explanation for m in tracked)
    assert any(e["mistake_id"] for e in evaluation["errors"])


def test_stronger_writing_scores_higher(onboarded):
    weak = onboarded.post("/writing/evaluate", json={"submission_id": _start(onboarded)["id"], "content": WEAK_ESSAY}).json()
    strong_sub = _start(onboarded, task_type="task2")
    strong = onboarded.post("/writing/evaluate", json={"submission_id": strong_sub["id"], "content": STRONG_ESSAY}).json()
    assert strong["submission"]["evaluation"]["overall_band"] > weak["submission"]["evaluation"]["overall_band"]


def test_too_short_submission_is_rejected(onboarded):
    sub = _start(onboarded)
    r = onboarded.post("/writing/evaluate", json={"submission_id": sub["id"], "content": "Too short to evaluate."})
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_short"


def test_ai_outage_saves_submission_and_allows_retry(onboarded, ai_outage):
    sub = _start(onboarded)
    r = onboarded.post("/writing/evaluate", json={"submission_id": sub["id"], "content": WEAK_ESSAY})
    assert r.status_code == 503
    error = r.json()["error"]
    assert error["code"] == "ai_unavailable"
    assert error["message"] == "AI analysis is temporarily unavailable. Your submission has been saved and can be analyzed again."
    saved = onboarded.get(f"/writing/submissions/{sub['id']}").json()
    assert saved["status"] == "evaluation_failed" and saved["content"] == WEAK_ESSAY
    # The provider recovers: the same submission can be analysed again.
    from app.ai.client import ai_client

    ai_client.set_provider(None)
    retry = onboarded.post("/writing/evaluate", json={"submission_id": sub["id"]})
    assert retry.status_code == 200 and retry.json()["submission"]["status"] == "evaluated"


def test_history_and_double_evaluation_guard(onboarded):
    sub = _start(onboarded)
    onboarded.post("/writing/evaluate", json={"submission_id": sub["id"], "content": WEAK_ESSAY})
    again = onboarded.post("/writing/evaluate", json={"submission_id": sub["id"]})
    assert again.status_code == 422 and again.json()["error"]["code"] == "already_evaluated"
    history = onboarded.get("/writing/history").json()
    assert history["total"] == 1 and history["items"][0]["overall_band"] is not None


def test_learners_cannot_read_each_others_submissions(onboarded, make_learner):
    sub = _start(onboarded)
    other = make_learner(onboard=True)
    assert other.get(f"/writing/submissions/{sub['id']}").status_code == 404
    assert other.post("/writing/evaluate", json={"submission_id": sub["id"], "content": WEAK_ESSAY}).status_code == 404
