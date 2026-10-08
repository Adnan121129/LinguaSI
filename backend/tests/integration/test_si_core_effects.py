"""Cross-skill intelligence: one activity updates the shared learner model used by every agent."""

from app.agents.context import build_context
from app.models import Mistake, SIEvent, StudySession, User, XPTransaction
from tests.samples import WEAK_ESSAY


def _evaluate(learner):
    task = learner.get("/writing/tasks?task_type=task2&module=academic").json()["items"][0]
    sub = learner.post("/writing/submissions", json={"task_id": task["id"], "mode": "exam"}).json()
    return learner.post("/writing/evaluate", json={"submission_id": sub["id"], "content": WEAK_ESSAY, "time_spent_seconds": 1500}).json()


def test_writing_activity_updates_every_part_of_the_learner_model(onboarded, db):
    body = _evaluate(onboarded)
    user = db.get(User, onboarded.id)
    assert db.query(StudySession).filter_by(user_id=user.id, activity="writing").count() == 1
    assert db.query(XPTransaction).filter_by(user_id=user.id).count() >= 1
    assert db.query(Mistake).filter_by(user_id=user.id).count() > 0
    assert db.query(SIEvent).filter_by(user_id=user.id).count() > 0
    assert body["outcome"]["si_actions"], "SI reports what it changed across skills"
    ctx = build_context(db, user)
    assert ctx.recurring or ctx.weak_areas, "the shared context the other agents read now reflects the essay"
    prompt_view = ctx.for_prompt("speaking")
    assert "Rafi" not in prompt_view and user.email not in prompt_view, "prompts carry learning data, not personal identifiers"


def test_repeated_mistakes_are_recognised_as_recurring(onboarded):
    _evaluate(onboarded)
    _evaluate(onboarded)
    mistakes = onboarded.get("/mistakes?status=recurring").json()
    assert mistakes["total"] > 0
    assert any(m["occurrences"] >= 2 or m["repeated"] for m in mistakes["items"])


def test_recommendations_follow_the_evidence(onboarded):
    _evaluate(onboarded)
    recs = onboarded.get("/recommendations").json()
    assert recs
    joined = " ".join(r["why"] for r in recs)
    assert any(ch.isdigit() for ch in joined), "explanations cite measured facts (counts, bands, percentages)"
