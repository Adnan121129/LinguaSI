from datetime import timedelta

from sqlalchemy import select

from app.core.security import hash_token
from app.models import AuthSession, User


def test_register_returns_tokens_and_profile(client):
    r = client.post("/auth/register", json={"email": "Nadia@Example.com", "password": "secret-pass-1", "name": "  Nadia   Karim "})
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"] and body["refresh_token"] and body["token_type"] == "bearer"
    assert body["user"]["email"] == "nadia@example.com"
    assert body["user"]["name"] == "Nadia Karim"
    assert body["user"]["role"] == "learner"
    assert body["user"]["profile"]["onboarding_completed"] is False


def test_password_is_stored_hashed(client, db):
    client.post("/auth/register", json={"email": "hash@example.com", "password": "secret-pass-1", "name": "Hash"})
    user = db.query(User).filter_by(email="hash@example.com").one()
    assert "secret-pass-1" not in user.password_hash


def test_duplicate_email_is_rejected(client, learner):
    r = client.post("/auth/register", json={"email": learner.email.upper(), "password": "another-pass-2", "name": "Copy"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] in ("conflict", "email_taken")


def test_weak_password_and_bad_email_are_validation_errors(client):
    r = client.post("/auth/register", json={"email": "not-an-email", "password": "short", "name": "X"})
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "validation_error"
    fields = {f["field"] for f in error["details"]["fields"]}
    assert {"email", "password"} <= fields
    r = client.post("/auth/register", json={"email": "ok@example.com", "password": "onlyletters", "name": "X"})
    assert r.status_code == 422


def test_login_success_and_failure(client, learner):
    ok = client.post("/auth/login", json={"email": learner.email, "password": learner.password})
    assert ok.status_code == 200 and ok.json()["user"]["id"] == learner.id
    bad = client.post("/auth/login", json={"email": learner.email, "password": "wrong-password-9"})
    assert bad.status_code == 401
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-9"})
    assert unknown.status_code == 401
    assert bad.json()["error"]["message"] == unknown.json()["error"]["message"], "no account enumeration"


def test_protected_routes_require_a_valid_token(client):
    assert client.get("/me").status_code == 401
    r = client.get("/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_token"


def _rotated_a_while_ago(db, refresh_token: str) -> None:
    """Move a rotation back in time, past the grace period for parallel requests."""
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(refresh_token)))
    session.revoked_at = session.revoked_at - timedelta(minutes=5)
    db.commit()


def test_refresh_rotates_tokens_and_detects_reuse(client, learner, db):
    first = learner.tokens["refresh_token"]
    r = client.post("/auth/refresh", json={"refresh_token": first})
    assert r.status_code == 200
    second = r.json()["refresh_token"]
    assert second != first
    # Presenting the rotated token again later is treated as theft: every session is revoked.
    _rotated_a_while_ago(db, first)
    reuse = client.post("/auth/refresh", json={"refresh_token": first})
    assert reuse.status_code == 401 and reuse.json()["error"]["code"] == "refresh_token_reused"
    assert client.post("/auth/refresh", json={"refresh_token": second}).status_code == 401


def test_logout_revokes_the_refresh_token(client, learner):
    token = learner.tokens["refresh_token"]
    assert client.post("/auth/logout", json={"refresh_token": token}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": token}).status_code == 401


def test_admin_emails_get_the_admin_role(client):
    r = client.post("/auth/register", json={"email": "admin@example.com", "password": "secret-pass-1", "name": "Admin"})
    assert r.json()["user"]["role"] == "admin"


def test_error_responses_include_request_id(client):
    r = client.get("/me")
    assert r.json()["error"]["request_id"]
    assert r.headers["X-Request-ID"] == r.json()["error"]["request_id"]


def test_signed_out_token_is_refused_without_ending_other_sessions(client, learner):
    phone = client.post("/auth/login", json={"email": learner.email, "password": learner.password}).json()
    assert client.post("/auth/logout", json={"refresh_token": phone["refresh_token"]}).status_code == 200
    stale = client.post("/auth/refresh", json={"refresh_token": phone["refresh_token"]})
    assert stale.status_code == 401 and stale.json()["error"]["code"] == "session_revoked"
    # Not treated as token theft: the learner's other session still works.
    assert client.post("/auth/refresh", json={"refresh_token": learner.tokens["refresh_token"]}).status_code == 200


def test_access_tokens_name_their_session(learner):
    from app.core.security import decode_access_token

    assert isinstance(decode_access_token(learner.tokens["access_token"])["sid"], int)


def test_parallel_refreshes_with_one_token_are_not_treated_as_theft(client, learner):
    # A page that fires several requests just after the access token expired sends the same refresh
    # token with each of them; every request must get working tokens.
    first = learner.tokens["refresh_token"]
    responses = [client.post("/auth/refresh", json={"refresh_token": first}) for _ in range(3)]
    assert [r.status_code for r in responses] == [200, 200, 200]
    for r in responses:
        assert client.post("/auth/refresh", json={"refresh_token": r.json()["refresh_token"]}).status_code == 200


def test_the_grace_period_never_revives_a_signed_out_session(client, learner):
    first = learner.tokens["refresh_token"]
    second = client.post("/auth/refresh", json={"refresh_token": first}).json()["refresh_token"]
    assert client.post("/auth/logout", json={"refresh_token": second}).status_code == 200
    late = client.post("/auth/refresh", json={"refresh_token": first})
    assert late.status_code == 401 and late.json()["error"]["code"] == "session_revoked"


def test_signing_out_ends_the_access_token_too(client, learner):
    assert client.post("/auth/logout", json={"refresh_token": learner.tokens["refresh_token"]}).status_code == 200
    r = learner.get("/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "session_revoked"


def test_access_tokens_keep_working_after_their_session_is_refreshed(client, learner):
    assert client.post("/auth/refresh", json={"refresh_token": learner.tokens["refresh_token"]}).status_code == 200
    assert learner.get("/me").status_code == 200
