from __future__ import annotations

from fastapi.testclient import TestClient

from src.service.app import app


def test_liveness():
    client = TestClient(app)
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "live"
    assert "X-Request-Id" in response.headers


def test_prediction_rejects_unknown_schema():
    client = TestClient(app)
    response = client.post(
        "/v1/predictions",
        json={
            "schemaVersion": "9.0",
            "features": [
                {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10, "origin": "simulated", "quality": "ok"},
                {"timestamp": "2026-09-01T00:05:00Z", "cpu_utilization": 11, "origin": "simulated", "quality": "ok"},
            ],
        },
    )
    assert response.status_code == 400
