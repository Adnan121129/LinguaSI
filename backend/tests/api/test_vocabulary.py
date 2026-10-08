from datetime import UTC, datetime

from sqlalchemy import select

from app.agents import vocabulary_engine
from app.models import UserVocabulary, VocabularyItem


def _correct_answer(db, exercise_id: str) -> str:
    uv_id, ex_type, seed = vocabulary_engine.parse_exercise_id(exercise_id)
    uv = db.get(UserVocabulary, uv_id)
    item = db.get(VocabularyItem, uv.item_id)
    pool = list(db.scalars(select(VocabularyItem)))
    exercise = vocabulary_engine.build_exercise(uv, item, pool, ex_type, seed)
    return item.example if exercise.input == "sentence" else exercise.answer


def test_today_session_introduces_starter_words(onboarded):
    r = onboarded.get("/vocabulary/today")
    assert r.status_code == 200
    session = r.json()
    assert session["new_count"] > 0 and session["exercises"]
    for ex in session["exercises"]:
        assert ex["type"] in vocabulary_engine.EXERCISE_TYPES
        assert "answer" not in ex, "answers are never sent before the learner responds"
    assert session["counts"]["new"] >= session["new_count"]


def test_review_updates_spaced_repetition_state(onboarded, db):
    exercise = onboarded.get("/vocabulary/today").json()["exercises"][0]
    answer = _correct_answer(db, exercise["id"])
    r = onboarded.post("/vocabulary/review", json={"exercise_id": exercise["id"], "answer": answer, "response_ms": 2500})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correct"] is True and body["state_before"] == "new" and body["state_after"] == "learning"
    assert datetime.fromisoformat(body["next_review_at"]) > datetime.now(UTC)
    assert body["xp_gained"] >= 2

    wrong = onboarded.get("/vocabulary/today").json()["exercises"][0]
    r = onboarded.post("/vocabulary/review", json={"exercise_id": wrong["id"], "answer": "definitely wrong", "response_ms": 9000})
    assert r.json()["correct"] is False and r.json()["correct_answer"]


def test_completing_a_session_feeds_si_core(onboarded, db):
    session = onboarded.get("/vocabulary/today").json()
    for ex in session["exercises"][:4]:
        onboarded.post("/vocabulary/review", json={"exercise_id": ex["id"], "answer": _correct_answer(db, ex["id"]), "response_ms": 3000})
    ex = session["exercises"][4]
    onboarded.post("/vocabulary/review", json={"exercise_id": ex["id"], "answer": "wrong", "response_ms": 3000})
    r = onboarded.post("/vocabulary/session/complete", json={"started_at": session["started_at"], "duration_seconds": 240})
    body = r.json()
    assert body["reviews"] == 5 and body["correct"] == 4 and body["accuracy"] == 80.0
    assert body["outcome"]["xp_gained"] > 0
    mistakes = onboarded.get("/mistakes?category=vocabulary").json()
    assert mistakes["total"] == 1, "a missed word is tracked so it can be revisited"


def test_invalid_or_foreign_exercise_ids_are_rejected(onboarded, make_learner):
    exercise = onboarded.get("/vocabulary/today").json()["exercises"][0]
    other = make_learner(onboard=True)
    assert other.post("/vocabulary/review", json={"exercise_id": exercise["id"], "answer": "x"}).status_code == 404
    assert onboarded.post("/vocabulary/review", json={"exercise_id": "not.valid", "answer": "x"}).status_code == 422


def test_word_bank_add_mark_known_and_insights(onboarded):
    bank = onboarded.get("/vocabulary/bank?q=mitigate").json()
    item = bank["items"][0]
    assert onboarded.post("/vocabulary/words", json={"item_id": item["id"]}).status_code == 200
    words = onboarded.get("/vocabulary/words").json()["items"]
    word = next(w for w in words if w["item"]["id"] == item["id"])
    assert onboarded.post(f"/vocabulary/words/{word['user_vocab_id']}/known").status_code == 200
    mastered = onboarded.get("/vocabulary/words?state=mastered").json()["items"]
    assert any(w["item"]["id"] == item["id"] for w in mastered)
    insights = onboarded.get("/vocabulary/insights").json()
    assert "counts" in insights and "retention" in insights


def test_explanations_fall_back_gracefully_during_outage(onboarded, ai_outage):
    item = onboarded.get("/vocabulary/bank").json()["items"][0]
    r = onboarded.post(f"/vocabulary/items/{item['id']}/explain")
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_unavailable"
