from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.main import create_app
from app.routes.dependencies import get_afferens_adapter, get_app_settings


def _client_with_transport(transport: httpx.MockTransport) -> TestClient:
    app = create_app()
    settings = Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key="test-api-key",
    )
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_afferens_adapter] = lambda: AfferensAdapter(
        settings,
        transport=transport,
    )
    return TestClient(app)


def test_afferens_latest_returns_live_event_without_secret() -> None:
    client = _client_with_transport(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "event": {
                        "event_id": "LIVE-VIS-123",
                        "timestamp": "2026-06-21T16:00:00Z",
                        "node_id": "USB-CAM-01",
                        "modality": "VISION",
                    }
                },
            )
        )
    )

    response = client.get("/api/afferens/latest")
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["status"]["configured"] is True
    assert payload["status"]["latest_event_id"] == "LIVE-VIS-123"
    assert payload["raw_event"]["event_id"] == "LIVE-VIS-123"
    assert "test-api-key" not in response.text


def test_afferens_status_maps_inactive_key_without_secret() -> None:
    client = _client_with_transport(
        httpx.MockTransport(lambda request: httpx.Response(403, json={"detail": "inactive"}))
    )

    response = client.get("/api/afferens/status")
    payload = response.json()

    assert response.status_code == 200
    assert payload["state"] == "inactive_key"
    assert payload["configured"] is True
    assert "test-api-key" not in response.text


def test_health_reports_provider_state() -> None:
    client = _client_with_transport(
        httpx.MockTransport(lambda request: httpx.Response(404, json={"detail": "none"}))
    )

    response = client.get("/api/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "test"
    assert payload["services"]["afferens"]["state"] == "degraded"
    assert payload["services"]["database"]["state"] == "degraded"
