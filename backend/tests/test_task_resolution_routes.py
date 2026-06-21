from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.ids import new_id
from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_afferens_adapter, get_app_settings, get_data_spine_service
from app.schemas import Task, TaskState, TaskType
from app.services import DataSpineService


def _settings() -> Settings:
    return Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key="test-api-key",
    )


def _client(service: DataSpineService, transport: httpx.MockTransport) -> TestClient:
    app = create_app()
    settings = _settings()
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_data_spine_service] = lambda: service
    app.dependency_overrides[get_afferens_adapter] = lambda: AfferensAdapter(
        settings,
        transport=transport,
    )
    return TestClient(app)


def _recovery_task() -> Task:
    return Task(
        id=new_id("task"),
        type=TaskType.OBJECT_RECOVERY,
        state=TaskState.OPEN,
        title="Find keys",
        body="I last saw keys in the kitchen.",
        recommended_action="Check the kitchen and verify in person.",
        evidence_observation_ids=["obs_previous"],
        metadata={"object_key": "keys", "display_name": "keys"},
    )


def test_verify_task_fetches_live_afferens_and_marks_recovery_verified() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    task = service.create_task(_recovery_task())
    client = _client(
        service,
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "events": [
                        {
                            "entity_id": "LIVE-VERIFY-KEYS",
                            "timestamp_utc": "2026-06-21T16:30:00Z",
                            "objects": [
                                {
                                    "label": "keys",
                                    "confidence": 0.91,
                                    "relative_location": "center of the table",
                                }
                            ],
                        }
                    ]
                },
            )
        ),
    )

    response = client.post(f"/api/tasks/{task.id}/verify", json={"room_id": "kitchen"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["verification"]["state"] == "verified"
    assert payload["verification"]["observation_id"] in repository.observations
    assert payload["task"]["state"] == "verified_resolved"
    assert repository.tasks[task.id].metadata["resolution_source"] == "live_afferens_verification"
    assert "test-api-key" not in response.text


def test_resolve_task_records_human_resolution_audit_state() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    task = service.create_task(_recovery_task())
    client = _client(
        service,
        httpx.MockTransport(lambda request: httpx.Response(404, json={"detail": "no live"})),
    )

    response = client.post(
        f"/api/tasks/{task.id}/resolve",
        json={"resolved_by": "user", "resolution_note": "I found the keys."},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["task"]["state"] == "verified_resolved"
    assert payload["task"]["metadata"]["resolution_source"] == "human_reported"
    assert payload["task"]["metadata"]["resolution_note"] == "I found the keys."
    assert repository.task_events[-1]["event_type"] == "human_resolved"
