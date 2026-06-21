from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.fireworks import FireworksReasoningAdapter
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import (
    get_app_settings,
    get_data_spine_service,
    get_fireworks_reasoning_adapter,
    get_object_recovery_workflow,
)
from app.schemas import LastSeenObject
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


def test_query_uses_memory_and_opens_recovery_task_when_object_is_not_current() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-KEYS-1",
                "timestamp_utc": "2026-06-21T16:00:00Z",
                "objects": [
                    {
                        "label": "keys",
                        "confidence": 0.84,
                        "relative_location": "left side of the table",
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

    response = _client(service).post(
        "/api/query",
        json={"query": "Where are my keys?", "session_id": "browser-session"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "object_location"
    assert payload["used_current_perception"] is False
    assert payload["used_memory"] is True
    assert payload["needs_human_verification"] is True
    assert payload["evidence_observation_ids"] == [repository.last_seen["keys"].last_seen_observation_id]
    assert payload["task_id"] in repository.tasks
    assert repository.tasks[payload["task_id"]].metadata["object_key"] == "keys"
    assert "left side of the table" in payload["answer"]
    assert "test-api-key" not in response.text


def test_query_uses_latest_observation_without_opening_task_when_object_is_visible() -> None:
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
                        "confidence": 0.9,
                        "relative_location": "beside the blue bottle",
                    }
                ],
            }
        ],
        room_id="kitchen",
    )

    response = _client(service).post("/api/query", json={"query": "Where are my keys?"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["confidence"] == "high"
    assert payload["used_current_perception"] is True
    assert payload["used_memory"] is False
    assert payload["task_id"] is None
    assert repository.tasks == {}
    assert "beside the blue bottle" in payload["answer"]


def test_query_does_not_invent_location_without_evidence() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)

    response = _client(service).post("/api/query", json={"query": "Where is my wallet?"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["confidence"] == "low"
    assert payload["used_current_perception"] is False
    assert payload["used_memory"] is False
    assert payload["evidence_observation_ids"] == []
    assert payload["task_id"] is None
    assert "do not have enough live observation evidence" in payload["answer"]


def test_langgraph_workflow_fallback_opens_memory_recovery_plan() -> None:
    memory = LastSeenObject(
        object_key="keys",
        display_name="keys",
        last_seen_at="2026-06-21T16:00:00Z",
        last_seen_room="kitchen",
        last_seen_relative_location="left side of the table",
        last_seen_observation_id="obs_keys",
        last_confidence=0.8,
        evidence_observation_ids=["obs_keys"],
    )
    workflow = ObjectRecoveryWorkflow(force_disabled=True)

    status = workflow.status()
    plan = workflow.plan_recovery(
        query="Where are my keys?",
        object_key="keys",
        memory=memory,
        current_visible=False,
    )

    assert status.state == "degraded"
    assert plan["should_open_task"] is True
    assert "left side of the table" in plan["recommended_action"]
