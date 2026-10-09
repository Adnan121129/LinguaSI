import pytest

from app.core.config import settings


@pytest.fixture
def admin(make_learner):
    return make_learner(email="admin@example.com", name="Admin")


def test_admin_endpoints_require_admin_role(learner, admin):
    for path in ("/admin/overview", "/admin/users", "/admin/content/vocabulary", "/admin/ai-usage", "/admin/logs", "/admin/evaluations"):
        assert learner.get(path).status_code == 403
        assert admin.get(path).status_code == 200, path


def test_admin_can_deactivate_users_which_signs_them_out(admin, onboarded, client):
    r = admin.patch(f"/admin/users/{onboarded.id}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert onboarded.get("/me").status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": onboarded.tokens["refresh_token"]}).status_code == 401
    assert admin.patch(f"/admin/users/{admin.id}", json={"is_active": False}).json()["error"]["code"] == "self_lockout"


def test_hidden_content_is_not_served_to_learners(admin, onboarded):
    passages = admin.get("/admin/content/reading?page_size=50").json()["items"]
    keep = passages[0]["id"]
    for p in passages[1:]:
        assert admin.patch(f"/admin/content/reading/{p['id']}", json={"is_active": False}).status_code == 200
    for _ in range(3):
        attempt = onboarded.post("/reading/generate", json={"question_count": 3}).json()
        assert attempt["passage"]["id"] == keep


def test_content_edits_are_validated(admin):
    item = admin.get("/admin/content/vocabulary?q=mitigate").json()["items"][0]
    ok = admin.patch(f"/admin/content/vocabulary/{item['id']}", json={"definition": "to make something bad less severe"})
    assert ok.status_code == 200 and ok.json()["data"]["source"] == "edited"
    assert admin.patch(f"/admin/content/vocabulary/{item['id']}", json={"word": "x"}).status_code == 422
    assert admin.patch(f"/admin/content/vocabulary/{item['id']}", json={"difficulty": 9}).status_code == 422
    assert admin.get("/admin/content/unknown").status_code == 404


def test_ai_usage_dashboard_reports_calls_without_content(admin, onboarded):
    onboarded.get("/dashboard")
    usage = admin.get("/admin/ai-usage?days=1").json()
    assert usage["config"]["mock_mode"] is True
    assert sum(t["calls"] for t in usage["by_task"]) >= 1
    assert "api_key" not in str(usage).lower()


def test_ai_rate_limit_returns_friendly_429(onboarded, monkeypatch):
    monkeypatch.setattr(settings, "ai_user_hourly_limit", 2)
    for _ in range(2):
        assert onboarded.post("/reading/generate", json={"question_count": 3}).status_code == 201
    r = onboarded.post("/reading/generate", json={"question_count": 3})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited" and "hourly limit" in r.json()["error"]["message"]


def test_login_attempts_are_rate_limited(client, learner):
    codes = [client.post("/auth/login", json={"email": learner.email, "password": "wrong-pass-0"}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_learners_behind_the_web_server_get_their_own_registration_allowance(client, monkeypatch):
    secret = "a-long-random-shared-secret-0123456789"
    monkeypatch.setattr(settings, "proxy_shared_secret", secret)

    def register(n: int, ip: str) -> int:
        headers = {"X-LinguaSI-Proxy-Secret": secret, "X-LinguaSI-Client-IP": ip}
        payload = {"email": f"vouched{n}@example.com", "password": "Passw0rd-123", "name": "Learner"}
        return client.post("/auth/register", json=payload, headers=headers).status_code

    assert [register(i, "203.0.113.7") for i in range(11)] == [201] * 10 + [429]
    assert register(11, "198.51.100.4") == 201
