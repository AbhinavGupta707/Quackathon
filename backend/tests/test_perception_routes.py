from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_afferens_adapter, get_app_settings, get_data_spine_service
from app.services import DataSpineService


def test_perception_sync_fetches_live_afferens_and_updates_memory() -> None:
    app = create_app()
    settings = Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key="test-api-key",
    )
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "events": [
                    {
                        "entity_id": "LIVE-VIS-1",
                        "timestamp_utc": "2026-06-21T16:00:00Z",
                        "source_node_id": "NODE-01",
                        "modality": "VISION",
                        "objects": [
                            {
                                "label": "keys",
                                "confidence": 0.84,
                                "relative_location": "left side of the table",
                            }
                        ],
                    }
                ]
            },
        )

    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_afferens_adapter] = lambda: AfferensAdapter(
        settings,
        transport=httpx.MockTransport(handler),
    )
    app.dependency_overrides[get_data_spine_service] = lambda: service

    response = TestClient(app).post(
        "/api/perception/sync",
        json={"limit": 1, "room_id": "kitchen"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert captured_request is not None
    assert captured_request.url.path == "/api/perception"
    assert payload["observations"][0]["objects"][0]["object_key"] == "keys"
    assert payload["objects_updated"][0]["last_seen_room"] == "kitchen"
    assert payload["objects_updated"][0]["evidence_observation_ids"] == [
        payload["observations"][0]["id"]
    ]
    assert payload["tasks_created"] == []
    assert "test-api-key" not in response.text

    second_response = TestClient(app).post(
        "/api/perception/sync",
        json={"limit": 1, "room_id": "kitchen"},
    )
    assert second_response.status_code == 200
    assert len(repository.raw_events) == 1

    latest = TestClient(app).get("/api/observations/latest").json()
    objects = TestClient(app).get("/api/objects/last-seen").json()
    assert latest["observation"]["provider_event_id"] == "LIVE-VIS-1"
    assert objects["objects"][0]["object_key"] == "keys"


def test_perception_sync_returns_honest_no_live_state() -> None:
    app = create_app()
    settings = Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key="test-api-key",
    )
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_afferens_adapter] = lambda: AfferensAdapter(
        settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"events": []})),
    )
    app.dependency_overrides[get_data_spine_service] = lambda: DataSpineService(
        InMemoryDataRepository()
    )

    response = TestClient(app).post("/api/perception/sync", json={"limit": 1})
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is False
    assert payload["status"]["state"] == "no_live_events"
    assert payload["observations"] == []


def test_durable_routes_return_503_without_database_url_and_do_not_leak_secret() -> None:
    app = create_app()
    settings = Settings(
        environment="test",
        afferens_api_key="super-secret-afferens-key",
        database_url=None,
    )
    app.dependency_overrides[get_app_settings] = lambda: settings

    response = TestClient(app).get("/api/objects/last-seen")

    assert response.status_code == 503
    assert "DATABASE_URL is not configured" in response.text
    assert "super-secret-afferens-key" not in response.text
