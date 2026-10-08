from app.services.content import diagnostic_bank

WRITING_SAMPLE = (
    "I think living in a big city is more better than living in the countryside. Firstly, cities have more jobs and better "
    "universities, so young people can build a career. However, cities are noisy and people has less time for their family. "
    "In conclusion, although the countryside is peaceful, but I prefer cities because they offer more opportunities."
)


def _diagnostic_answers(accuracy_cut: int = 6) -> dict:
    bank = diagnostic_bank()
    answers = {}
    for section in ("vocabulary", "grammar"):
        for i, item in enumerate(bank[section]):
            answers[item["id"]] = item["answer"] if i < accuracy_cut else "wrong"
    for section in ("reading", "listening"):
        for q in bank[section]["questions"]:
            answers[q["id"]] = q["answer"]
    return answers


def test_dashboard_before_onboarding_points_to_diagnostic(learner):
    dash = learner.get("/dashboard").json()
    assert dash["onboarding_completed"] is False
    assert dash["estimated_band"] is None


def test_onboarding_saves_goals(learner):
    r = learner.post("/onboarding", json={"goal": "general", "self_reported_level": "elementary", "daily_minutes": 15, "timezone": "Europe/London"})
    assert r.status_code == 200
    profile = r.json()["profile"]
    assert profile["goal"] == "general" and profile["onboarding_completed"] is True
    assert learner.post("/onboarding", json={"goal": "fluency", "self_reported_level": "elementary"}).status_code == 422


def test_diagnostic_produces_estimated_level_not_an_official_score(onboarded):
    start = onboarded.post("/diagnostic/start")
    assert start.status_code == 201
    body = start.json()
    assert body["vocabulary"] and body["grammar"] and body["reading"]["questions"] and body["listening"]["questions"]
    assert all("answer" not in item for item in body["vocabulary"] + body["grammar"]), "answers stay on the server"
    r = onboarded.post(
        f"/diagnostic/{body['attempt_id']}/submit",
        json={
            "answers": _diagnostic_answers(),
            "writing": WRITING_SAMPLE,
            "speaking": [{"id": "s1", "transcript": "My hometown is Sylhet. I like it because it is green and peaceful.", "duration_seconds": 12}],
        },
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["label"] == "Estimated IELTS Readiness"
    assert result["estimated_cefr"] in ("A1", "A2", "B1", "B2", "C1", "C2")
    assert result["estimated_band"] is not None and "not an official IELTS result" in result["disclaimer"]
    assert {s["key"] for s in result["sections"]} >= {"vocabulary", "grammar", "reading", "listening", "writing"}
    assert result["next_steps"] and result["focus_areas"]
    assert onboarded.get("/diagnostic/latest").json()["attempt_id"] == body["attempt_id"]
    again = onboarded.post(f"/diagnostic/{body['attempt_id']}/submit", json={"answers": {}})
    assert again.status_code == 422


def test_dashboard_after_diagnostic_is_personalised_and_explains_recommendations(onboarded):
    attempt = onboarded.post("/diagnostic/start").json()
    onboarded.post(f"/diagnostic/{attempt['attempt_id']}/submit", json={"answers": _diagnostic_answers(4), "writing": WRITING_SAMPLE, "speaking": []})
    dash = onboarded.get("/dashboard").json()
    assert dash["greeting"].endswith("Test.") or "Test" in dash["greeting"]
    assert dash["estimated_band"] is not None and dash["cefr"]
    assert dash["mission"]["tasks"], "an AI daily mission is generated"
    rec = dash["recommendation"]
    assert rec and rec["why"] and rec["route"].startswith("/")
    recs = onboarded.get("/recommendations").json()
    assert recs and all(r["why"] for r in recs)
    assert onboarded.post(f"/recommendations/{recs[0]['id']}/dismiss").status_code == 200
    assert recs[0]["id"] not in [r["id"] for r in onboarded.get("/recommendations").json()]


def test_progress_charts_each_answer_a_question(onboarded):
    attempt = onboarded.post("/diagnostic/start").json()
    onboarded.post(f"/diagnostic/{attempt['attempt_id']}/submit", json={"answers": _diagnostic_answers(), "writing": WRITING_SAMPLE, "speaking": []})
    progress = onboarded.get("/progress?days=30").json()
    assert progress["chart_questions"], "every chart declares the question it answers"
    for key in ("band_history", "skills", "weekly_scores", "vocabulary_growth", "mistake_reduction", "consistency"):
        assert key in progress
    assert progress["insights"]["headline"]
    assert onboarded.get("/progress?days=3").status_code == 422


def test_missions_and_achievements(onboarded):
    missions = onboarded.get("/missions").json()
    assert missions["today"]["tasks"] and missions["challenges"]
    assert {"current", "longest"} <= set(missions["streak"])
    achievements = onboarded.get("/achievements").json()
    assert achievements["achievements"] and achievements["level"]["level"] == 1


def test_meta_exposes_mode_without_secrets(client):
    meta = client.get("/meta").json()
    assert meta["ai"]["mock_mode"] is True and meta["ai"]["provider"] == "mock"
    assert "not official IELTS results" in meta["disclaimer"]
    assert "key" not in str(meta).lower()
