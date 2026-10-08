"""The complete acceptance journey from the build specification, end to end through the HTTP API."""

import json

from app.models import ListeningQuestion, PracticeSet, ReadingQuestion
from app.services.content import diagnostic_bank
from tests.samples import SPEAKING_ANSWER, WEAK_ESSAY


def test_complete_learner_journey(client, db):
    # 1. Register and create the learner profile
    reg = client.post("/auth/register", json={"email": "journey@example.com", "password": "journey-pass-1", "name": "Rafi Hasan"})
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    refresh_token = reg.json()["refresh_token"]
    onboarding = {
        "goal": "ielts",
        "ielts_module": "academic",
        "self_reported_level": "intermediate",
        "target_band": 7.0,
        "daily_minutes": 30,
        "timezone": "UTC",
    }
    assert client.post("/onboarding", headers=headers, json=onboarding).status_code == 200

    # 2. Diagnostic -> estimated level
    attempt = client.post("/diagnostic/start", headers=headers).json()
    bank = diagnostic_bank()
    answers = {i["id"]: i["answer"] for s in ("vocabulary", "grammar") for i in bank[s]}
    answers |= {q["id"]: q["answer"] for s in ("reading", "listening") for q in bank[s]["questions"]}
    diag = client.post(
        f"/diagnostic/{attempt['attempt_id']}/submit",
        headers=headers,
        json={"answers": answers, "writing": WEAK_ESSAY.split("\n\n")[1], "speaking": [{"id": "s1", "transcript": SPEAKING_ANSWER, "duration_seconds": 25}]},
    ).json()
    assert diag["estimated_band"] is not None and diag["estimated_cefr"]

    # 3. Personalised dashboard with an explained recommendation
    dash = client.get("/dashboard", headers=headers).json()
    assert dash["recommendation"]["why"] and dash["mission"]["tasks"]

    # 4. Writing task -> AI evaluation -> mistakes stored
    task = client.get("/writing/tasks?task_type=task2&module=academic", headers=headers).json()["items"][0]
    sub = client.post("/writing/submissions", headers=headers, json={"task_id": task["id"], "mode": "exam"}).json()
    evaluated = client.post("/writing/evaluate", headers=headers, json={"submission_id": sub["id"], "content": WEAK_ESSAY, "time_spent_seconds": 2100}).json()
    assert evaluated["submission"]["evaluation"]["overall_band"] > 0
    mistakes = client.get("/mistakes?source=writing", headers=headers).json()
    assert mistakes["total"] > 0

    # 5. Targeted exercise generated from a stored mistake
    target = next(m for m in mistakes["items"] if m["category"] == "grammar")
    practice = client.post(f"/mistakes/{target['id']}/practice", headers=headers).json()
    full = db.get(PracticeSet, practice["id"])
    result = client.post(f"/practice/sets/{practice['id']}/submit", headers=headers, json={"answers": {i["id"]: i["answer"] for i in full.items}}).json()
    assert result["practice"]["accuracy"] == 100.0

    # 6. Vocabulary review
    session = client.get("/vocabulary/today", headers=headers).json()
    ex = session["exercises"][0]
    client.post("/vocabulary/review", headers=headers, json={"exercise_id": ex["id"], "answer": "a guess", "response_ms": 5000})
    client.post("/vocabulary/session/complete", headers=headers, json={"started_at": session["started_at"], "duration_seconds": 60})

    # 7. Speaking mock test -> evaluation
    start = client.post("/speaking/session/start", headers=headers, json={"mode": "part1"}).json()
    done = False
    while not done:
        r = client.post(
            "/speaking/session/respond",
            headers=headers,
            data={
                "session_id": str(start["session"]["id"]),
                "transcript": SPEAKING_ANSWER,
                "transcript_source": "browser",
                "duration_seconds": "26",
                "pauses": json.dumps({"count": 2, "long_count": 0, "total_silence_seconds": 1.5}),
            },
        )
        done = r.json()["done"]
    speaking = client.post("/speaking/session/finish", headers=headers, json={"session_id": start["session"]["id"]}).json()
    assert speaking["session"]["evaluation"]["overall_band"] > 0

    # 8. Reading and listening practice
    reading = client.post("/reading/generate", headers=headers, json={"question_count": 4}).json()
    r_answers = {str(q["id"]): db.get(ReadingQuestion, q["id"]).answer for q in reading["questions"]}
    assert client.post("/reading/submit", headers=headers, json={"attempt_id": reading["id"], "answers": r_answers}).json()["attempt"]["accuracy"] == 100.0
    listening = client.post("/listening/generate", headers=headers, json={"question_count": 4}).json()
    l_answers = {str(q["id"]): db.get(ListeningQuestion, q["id"]).answer for q in listening["questions"]}
    assert client.post("/listening/submit", headers=headers, json={"attempt_id": listening["id"], "answers": l_answers}).status_code == 200

    # 9. XP, streak and progress reflect everything
    dash = client.get("/dashboard", headers=headers).json()
    assert dash["level"]["xp"] >= 200 and dash["streak"]["current"] == 1 and dash["streak"]["active_today"]
    assert {s["skill"] for s in dash["skills"] if s["attempts"]} >= {"writing", "speaking", "reading", "listening"}
    progress = client.get("/progress", headers=headers).json()
    assert progress["totals"]["sessions"] >= 6 and progress["totals"]["xp"] == dash["level"]["xp"]
    assert dash["si_feed"], "SI explains the cross-skill actions it took"

    # 10. Theme switch persists on the server
    assert client.patch("/me", headers=headers, json={"theme": "dark"}).json()["profile"]["theme"] == "dark"

    # 11. Return later: a new session restores the same learner state
    refreshed = client.post("/auth/refresh", json={"refresh_token": refresh_token}).json()
    later = {"Authorization": f"Bearer {refreshed['access_token']}"}
    me = client.get("/me", headers=later).json()
    assert me["profile"]["theme"] == "dark" and me["profile"]["diagnostic_completed"]
    history = client.get("/writing/history", headers=later).json()
    assert history["total"] == 2, "the diagnostic writing sample and the practice essay"
    assert any(item["task_id"] == task["id"] and item["overall_band"] for item in history["items"])
    assert client.get("/speaking/history", headers=later).json()["total"] == 1
