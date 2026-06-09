"""Health endpoint test. Works whether or not deps are up: /health must always
return 200 with an honest status (rule 4: honestly-down beats silently-stale)."""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_200_and_honest_status() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["service"]
    dep_names = {d["name"] for d in body["dependencies"]}
    assert {"postgres", "redis"} <= dep_names


def test_root_is_not_404() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
