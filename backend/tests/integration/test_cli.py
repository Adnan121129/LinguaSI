from sqlalchemy import func, select

from app.cli import main
from app.models import User


def _user(db, email: str) -> User | None:
    db.expire_all()
    return db.scalar(select(User).where(func.lower(User.email) == email))


def test_create_admin_creates_an_account_that_can_sign_in(db, client):
    assert main(["create-admin", "--email", "Ops@LinguaSI.app", "--name", "Ops", "--password", "a-long-admin-pass"]) == 0
    user = _user(db, "ops@linguasi.app")
    assert user is not None and user.role == "admin" and user.is_active
    res = client.post("/auth/login", json={"email": "ops@linguasi.app", "password": "a-long-admin-pass"})
    assert res.status_code == 200


def test_create_admin_promotes_an_existing_learner(db, make_learner):
    learner = make_learner()
    assert main(["create-admin", "--email", learner.email]) == 0
    assert _user(db, learner.email.lower()).role == "admin"


def test_create_admin_rejects_emails_the_sign_in_form_would_reject(db, capsys):
    assert main(["create-admin", "--email", "admin@linguasi.local", "--password", "a-long-admin-pass"]) == 1
    assert "Invalid email address" in capsys.readouterr().err
    assert _user(db, "admin@linguasi.local") is None


def test_create_admin_requires_a_reasonable_password(db, capsys):
    assert main(["create-admin", "--email", "short@linguasi.app", "--password", "short"]) == 1
    assert "at least 8 characters" in capsys.readouterr().err
    assert _user(db, "short@linguasi.app") is None
