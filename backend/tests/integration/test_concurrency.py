"""Two requests for the same learner creating the same first-use row at once."""

from sqlalchemy import delete, select

from app.agents.progress_analyst import get_skill_profile
from app.core.database import SessionLocal, insert_or_existing
from app.models import LearnerSkillProfile, User


def _profile(user_id: int, score: float) -> LearnerSkillProfile:
    return LearnerSkillProfile(user_id=user_id, skill="reading", score=score, confidence=0.0, trend="new", difficulty=2, attempts=0, recent=[])


def test_losing_a_creation_race_returns_the_winners_row(db, learner):
    user = db.get(User, learner.user["id"])
    db.execute(delete(LearnerSkillProfile).where(LearnerSkillProfile.user_id == user.id))
    db.commit()
    query = select(LearnerSkillProfile).where(LearnerSkillProfile.user_id == user.id, LearnerSkillProfile.skill == "reading")

    # Another request creates the row and commits after this one checked that it didn't exist.
    with SessionLocal() as other:
        other.add(_profile(user.id, score=42.0))
        other.commit()

    mine = _profile(user.id, score=0.0)
    found = insert_or_existing(db, mine, query)
    assert found is not mine and found.score == 42.0
    # The request carries on in the same transaction.
    assert get_skill_profile(db, user, "reading") is found
    db.commit()


def test_winning_the_race_inserts_the_row(db, learner):
    user = db.get(User, learner.user["id"])
    db.execute(delete(LearnerSkillProfile).where(LearnerSkillProfile.user_id == user.id))
    db.commit()
    mine = _profile(user.id, score=7.0)
    query = select(LearnerSkillProfile).where(LearnerSkillProfile.user_id == user.id, LearnerSkillProfile.skill == "reading")
    assert insert_or_existing(db, mine, query) is mine
    db.commit()
    assert db.scalar(query).score == 7.0
