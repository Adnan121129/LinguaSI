from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.core.database import engine
from app.models import Base, SpeakingSession, User, WritingEvaluation
from app.seed.demo import create_demo_learner


def test_migrations_match_the_models():
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations are out of sync: {diff}"


def test_demo_generator_replays_a_realistic_history(db):
    report = create_demo_learner(db, days=8)
    user = db.query(User).filter_by(email=report.email).one()
    assert user.is_demo and user.profile.diagnostic_completed
    assert db.query(WritingEvaluation).filter_by(user_id=user.id).count() >= 2
    assert db.query(SpeakingSession).filter_by(user_id=user.id, status="completed").count() >= 1
    assert report.actions["vocabulary_sessions"] >= 5
    again = create_demo_learner(db, days=7, reset=True)
    assert again.email == report.email
