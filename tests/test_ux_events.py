from fastapi.testclient import TestClient

from app.main import app


def test_ux_events_accepts_valid_batch() -> None:
    initial_count = len(getattr(app.state, "ux_events", []))
    with TestClient(app) as client:
        response = client.post(
            "/api/ux-events",
            json={
                "events": [
                    {
                        "name": "web_vital_lcp",
                        "value": 1700,
                        "unit": "ms",
                        "severity": "low",
                        "meta": {"source": "test"},
                    }
                ]
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["accepted"] == 1
    assert len(getattr(app.state, "ux_events", [])) >= initial_count + 1


def test_ux_events_rejects_invalid_payload() -> None:
    with TestClient(app) as client:
        response = client.post("/api/ux-events", json={"events": "invalid"})
    assert response.status_code == 400
