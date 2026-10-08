from app.models import PracticeSet
from tests.samples import WEAK_ESSAY


def _evaluated_learner(onboarded):
    task = onboarded.get("/writing/tasks?task_type=task2&module=academic").json()["items"][0]
    sub = onboarded.post("/writing/submissions", json={"task_id": task["id"], "mode": "exam"}).json()
    assert onboarded.post("/writing/evaluate", json={"submission_id": sub["id"], "content": WEAK_ESSAY}).status_code == 200
    return onboarded


def _answers(db, practice_id: int, *, correct: bool = True) -> dict:
    ps = db.get(PracticeSet, practice_id)
    return {item["id"]: (item["answer"] if correct else "zzz") for item in ps.items}


def test_mistakes_are_listed_filtered_and_summarised(onboarded):
    learner = _evaluated_learner(onboarded)
    listing = learner.get("/mistakes").json()
    assert listing["total"] > 0
    first = listing["items"][0]
    assert {"original", "corrected", "explanation", "category", "subcategory", "status"} <= set(first)
    grammar = learner.get("/mistakes?category=grammar").json()
    assert all(m["category"] == "grammar" for m in grammar["items"])
    summary = learner.get("/mistakes/summary").json()
    assert summary["totals"]["total"] == listing["total"]
    detail = learner.get(f"/mistakes/{first['id']}").json()
    assert "guide" in detail and "related" in detail


def test_targeted_practice_masters_a_mistake_after_two_correct_rounds(onboarded, db):
    learner = _evaluated_learner(onboarded)
    mistake = next(m for m in learner.get("/mistakes?category=grammar").json()["items"])
    for _ in range(2):
        practice = learner.post(f"/mistakes/{mistake['id']}/practice")
        assert practice.status_code == 201, practice.text
        ps = practice.json()
        assert ps["items"] and all("answer" not in i for i in ps["items"])
        r = learner.post(f"/practice/sets/{ps['id']}/submit", json={"answers": _answers(db, ps["id"]), "duration_seconds": 120})
        assert r.status_code == 200
        result = r.json()
        assert result["practice"]["accuracy"] == 100.0
        assert all(item["explanation"] is not None for item in result["practice"]["results"])
    assert mistake["id"] in result["mastered_mistakes"]
    assert learner.get(f"/mistakes/{mistake['id']}").json()["status"] == "mastered"


def test_wrong_practice_keeps_mistake_open(onboarded, db):
    learner = _evaluated_learner(onboarded)
    mistake = learner.get("/mistakes?category=grammar").json()["items"][0]
    ps = learner.post(f"/mistakes/{mistake['id']}/practice").json()
    learner.post(f"/practice/sets/{ps['id']}/submit", json={"answers": _answers(db, ps["id"], correct=False)})
    assert learner.get(f"/mistakes/{mistake['id']}").json()["status"] == "unresolved"
    resubmit = learner.post(f"/practice/sets/{ps['id']}/submit", json={"answers": {}})
    assert resubmit.status_code == 422


def test_revisit_later_and_automatic_revision_session(onboarded):
    learner = _evaluated_learner(onboarded)
    mistake = learner.get("/mistakes").json()["items"][0]
    r = learner.post(f"/mistakes/{mistake['id']}/status", json={"revisit_in_days": 3})
    assert r.status_code == 200 and r.json()["revisit_at"]
    revision = learner.post("/mistakes/revision")
    assert revision.status_code == 201
    body = revision.json()
    assert body["kind"] == "revision" and "Repair Challenge" in body["title"] and body["why"]


def test_revision_without_history_explains_why(onboarded):
    r = onboarded.post("/mistakes/revision")
    assert r.status_code == 422 and r.json()["error"]["code"] == "nothing_to_revise"


def test_practice_topics_and_custom_sets(onboarded, db):
    topics = onboarded.get("/practice/topics").json()
    focus = next(t["focus"] for t in topics if t["focus"] == "article_usage")
    ps = onboarded.post("/practice/sets", json={"focus": focus, "item_count": 5}).json()
    assert ps["total"] == len(ps["items"]) >= 3
    r = onboarded.post(f"/practice/sets/{ps['id']}/submit", json={"answers": _answers(db, ps["id"]), "duration_seconds": 90})
    assert r.json()["outcome"]["xp_gained"] > 0
    assert onboarded.post("/practice/sets", json={"focus": "not_a_topic"}).status_code == 422
