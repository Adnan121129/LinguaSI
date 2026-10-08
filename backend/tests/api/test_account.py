def test_get_and_update_profile_including_theme(onboarded):
    me = onboarded.get("/me").json()
    assert me["profile"]["goal"] == "ielts" and me["profile"]["timezone"] == "Asia/Dhaka"
    r = onboarded.patch("/me", json={"theme": "dark", "target_band": 7.5, "daily_minutes": 45})
    assert r.status_code == 200
    profile = r.json()["profile"]
    assert profile["theme"] == "dark" and profile["target_band"] == 7.5 and profile["daily_minutes"] == 45
    # Persisted: a fresh read (e.g. on another device) sees the same theme.
    assert onboarded.get("/me").json()["profile"]["theme"] == "dark"


def test_invalid_profile_values_are_rejected(onboarded):
    assert onboarded.patch("/me", json={"theme": "purple"}).status_code == 422
    assert onboarded.patch("/me", json={"target_band": 6.3}).status_code == 422
    assert onboarded.patch("/me", json={"timezone": "Mars/Base"}).status_code == 422


def test_change_password_revokes_sessions(client, learner):
    r = learner.post("/me/change-password", json={"current_password": learner.password, "new_password": "brand-new-pass-7"})
    assert r.status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": learner.tokens["refresh_token"]}).status_code == 401
    assert client.post("/auth/login", json={"email": learner.email, "password": "brand-new-pass-7"}).status_code == 200
    wrong = learner.post("/me/change-password", json={"current_password": "nope", "new_password": "brand-new-pass-8"})
    assert wrong.status_code == 401


def test_delete_account_removes_all_learning_data(client, onboarded, db):
    from app.models import User

    onboarded.get("/vocabulary/today")  # creates learner-owned rows
    assert onboarded.post("/me/delete", json={"password": "wrong"}).status_code == 401
    assert onboarded.post("/me/delete", json={"password": onboarded.password}).status_code == 200
    assert db.get(User, onboarded.id) is None
    assert client.post("/auth/login", json={"email": onboarded.email, "password": onboarded.password}).status_code == 401
