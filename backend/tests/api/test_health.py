def test_liveness_and_readiness(client):
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["status"] == "ready"


def test_openapi_documents_every_router(client):
    spec = client.get("/openapi.json").json()
    tags = {tag for path in spec["paths"].values() for op in path.values() for tag in op.get("tags", [])}
    assert {"auth", "writing", "speaking", "vocabulary", "reading", "listening", "mistakes", "practice", "tutor", "lab", "admin"} <= tags
    assert client.get("/docs").status_code == 200
