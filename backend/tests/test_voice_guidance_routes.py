from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.guidance import GuidedRecoveryService
from app.main import create_app
from app.providers.fireworks import FireworksReasoningAdapter
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import (
    get_app_settings,
    get_data_spine_service,
    get_fireworks_reasoning_adapter,
    get_object_recovery_workflow,
)
from app.schemas import GuidedRecoveryStartRequest
from app.services import DataSpineService
from app.workflows.object_recovery import ObjectRecoveryWorkflow


def _settings() -> Settings:
    return Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key="test-api-key",
        fireworks_api_key=None,
    )


def _client(service: DataSpineService) -> TestClient:
    app = create_app()
    settings = _settings()
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_data_spine_service] = lambda: service
    app.dependency_overrides[get_fireworks_reasoning_adapter] = lambda: FireworksReasoningAdapter(
        settings
    )
    app.dependency_overrides[get_object_recovery_workflow] = lambda: ObjectRecoveryWorkflow(
        force_disabled=True
    )
    return TestClient(app)


def _seed_missing_bowl(service: DataSpineService) -> None:
    service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-BOWL-1",
                "timestamp_utc": "2026-06-21T16:00:00Z",
                "objects": [
                    {
                        "label": "bowl",
                        "confidence": 0.86,
                        "relative_location": "right side of the table",
                    }
                ],
            }
        ],
        room_id="kitchen",
    )
    service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-MUG-1",
                "timestamp_utc": "2026-06-21T16:05:00Z",
                "objects": [{"label": "mug", "confidence": 0.8}],
            }
        ],
        room_id="kitchen",
    )


def test_voice_query_reuses_normal_query_path_and_returns_spoken_text() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-KEYS-CURRENT",
                "timestamp_utc": "2026-06-21T16:10:00Z",
                "objects": [
                    {
                        "label": "keys",
                        "confidence": 0.91,
                        "relative_location": "beside the blue bottle",
                    }
                ],
            }
        ],
        room_id="kitchen",
    )

    response = _client(service).post(
        "/api/voice/query",
        json={
            "query": "Where are my keys?",
            "session_id": "voice-session",
            "speak": True,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["query_result"]["used_current_perception"] is True
    assert payload["query_result"]["used_memory"] is False
    assert payload["query_result"]["task_id"] is None
    assert "beside the blue bottle" in payload["spoken_text"]
    assert "verify" in payload["spoken_text"].lower()
    assert len(repository.queries) == 1
    assert next(iter(repository.queries.values())).session_id == "voice-session"
    assert "test-api-key" not in response.text


def test_voice_query_rejects_raw_audio_fields() -> None:
    response = _client(DataSpineService(InMemoryDataRepository())).post(
        "/api/voice/query",
        json={
            "query": "Where are my keys?",
            "audio_blob": "data:audio/wav;base64,AAAA",
        },
    )

    assert response.status_code == 422
    assert "audio_blob" in response.text


def test_guided_recovery_start_opens_task_for_missing_object() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    _seed_missing_bowl(service)

    response = _client(service).post(
        "/api/guidance/recovery/start",
        json={"object_key": "bowl", "session_id": "browser-session"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["task"]["id"] in repository.tasks
    assert payload["task"]["type"] == "object_recovery"
    assert payload["task"]["state"] == "open"
    assert payload["task"]["metadata"]["object_key"] == "bowl"
    assert payload["task"]["metadata"]["opened_from_guided_recovery"] is True
    assert payload["task"]["metadata"]["session_id"] == "browser-session"
    assert payload["task"]["evidence_observation_ids"] == [
        repository.last_seen["bowl"].last_seen_observation_id
    ]
    assert payload["next_instruction"] == (
        "Point the Afferens Node at kitchen near right side of the table, "
        "then sync live perception again."
    )
    assert repository.task_events[-1]["event_type"] == "guided_recovery_started"
    assert "test-api-key" not in response.text


def test_guided_recovery_reuses_open_task_for_same_object() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    _seed_missing_bowl(service)
    client = _client(service)

    first = client.post("/api/guidance/recovery/start", json={"object_key": "bowl"}).json()
    second = client.post(
        "/api/guidance/recovery/start",
        json={"object_key": "Where is my bowl?"},
    ).json()

    assert first["ok"] is True
    assert second["ok"] is True
    assert first["task"]["id"] == second["task"]["id"]
    assert len(repository.tasks) == 1
    assert repository.task_events[-1]["event_type"] == "guided_recovery_reused"


def test_guided_recovery_returns_honest_no_evidence_state_without_task() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)

    response = _client(service).post(
        "/api/guidance/recovery/start",
        json={"object_key": "wallet"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is False
    assert payload["task"] is None
    assert payload["next_instruction"].startswith("I do not have live Afferens evidence")
    assert repository.tasks == {}


def test_guided_recovery_uses_deterministic_fallback_when_workflow_is_disabled() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    _seed_missing_bowl(service)
    guidance = GuidedRecoveryService(
        service,
        workflow=ObjectRecoveryWorkflow(force_disabled=True),
    )

    response = guidance.start(GuidedRecoveryStartRequest(object_key="bowl"))

    assert response.ok is True
    assert response.task is not None
    assert response.task.recommended_action == (
        "Check kitchen near right side of the table, then verify in person."
    )
    assert response.next_instruction == (
        "Point the Afferens Node at kitchen near right side of the table, "
        "then sync live perception again."
    )
