from __future__ import annotations

from datetime import datetime

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
from app.schemas import (
    AlertSeverity,
    DetectedObject,
    FamilyMessage,
    HumanPresence,
    Observation,
    QueryConfidence,
    WellnessCheck,
    WellnessCheckStatus,
    WellnessCheckType,
    utc_now,
)
from app.services import DataSpineService
from app.workflows.object_recovery import ObjectRecoveryWorkflow


def _settings() -> Settings:
    return Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key=None,
        fireworks_api_key=None,
        database_enabled=False,
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


def _observation(
    observation_id: str,
    *,
    objects: list[DetectedObject],
    timestamp: datetime | None = None,
    risk_signals: list[str] | None = None,
) -> Observation:
    observed_at = timestamp or utc_now()
    return Observation(
        id=observation_id,
        raw_event_id=f"aff_{observation_id}",
        provider_event_id=f"LIVE-{observation_id}",
        timestamp_utc=observed_at,
        room_id="kitchen_zone",
        scene_summary="Live Afferens evidence is available.",
        human_presence=HumanPresence.UNKNOWN,
        objects=objects,
        risk_signals=risk_signals or [],
    )


def test_assistant_routes_object_location_through_query_service_and_opens_recovery() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-ASSISTANT-KEYS",
                "timestamp_utc": "2026-06-22T09:00:00Z",
                "objects": [
                    {
                        "label": "keys",
                        "confidence": 0.86,
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
                "entity_id": "LIVE-ASSISTANT-MUG",
                "timestamp_utc": "2026-06-22T09:05:00Z",
                "objects": [{"label": "mug", "confidence": 0.8}],
            }
        ],
        room_id="kitchen",
    )

    response = _client(service).post(
        "/api/assistant/ask",
        json={"query": "Help me find my keys", "session_id": "browser-session"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["intent"] == "guided_recovery"
    assert payload["provider"] == "deterministic"
    assert payload["used_memory"] is True
    assert payload["used_current_perception"] is False
    assert payload["needs_human_verification"] is True
    assert payload["evidence_ids"] == [repository.last_seen["keys"].last_seen_observation_id]
    assert payload["source_ids"] == payload["evidence_ids"]
    assert payload["task_id"] in repository.tasks
    assert payload["route_metadata"]["routed_to"] == "query_answer_service"
    assert "left side of the table" in payload["answer"]
    assert "test-api-key" not in response.text


def test_assistant_diary_generates_evidence_backed_daily_recall() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    observed_at = utc_now()
    repository.persist_observation(
        _observation(
            "obs_assistant_diary",
            timestamp=observed_at,
            objects=[
                DetectedObject(
                    object_key="bottle",
                    label="bottle",
                    display_name="water bottle",
                    confidence=0.82,
                    relative_location="on the breakfast table",
                )
            ],
        )
    )

    response = _client(service).post(
        "/api/assistant/ask",
        json={"query": "What did I do today?"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "diary"
    assert payload["used_memory"] is True
    assert payload["evidence_ids"] == ["obs_assistant_diary"]
    assert payload["source_ids"][0].startswith("diary_")
    assert "evidence-backed" in payload["answer"]
    assert "verify" in payload["next_step"].lower()


def test_assistant_semantic_memory_plainly_reports_no_cited_evidence() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)

    response = _client(service).post(
        "/api/assistant/ask",
        json={"query": "What do you remember about my art class?"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "semantic_memory"
    assert payload["confidence"] == "low"
    assert payload["used_memory"] is False
    assert payload["evidence_ids"] == []
    assert payload["source_ids"] == []
    assert "do not have cited memory" in payload["answer"]


def test_assistant_semantic_memory_reports_hybrid_provider_when_memory_matches() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-ASSISTANT-BOTTLE",
                "timestamp_utc": "2026-06-21T16:00:00Z",
                "objects": [
                    {
                        "label": "bottle",
                        "confidence": 0.86,
                        "relative_location": "on the kitchen table",
                    }
                ],
            }
        ],
        room_id="kitchen_zone",
    )

    response = _client(service).post(
        "/api/assistant/ask",
        json={"query": "What do you remember about the kitchen bottle?"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "semantic_memory"
    assert payload["provider"] == "hybrid_local_vector"
    assert payload["used_memory"] is True
    assert payload["evidence_ids"]


def test_assistant_surfaces_active_family_prompt() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    repository.create_family_message(
        FamilyMessage(
            id="fam_assistant",
            title="Appointment reminder",
            body="Your appointment is at 2 pm. Your shoes are by the door.",
            created_at=utc_now(),
        )
    )

    response = _client(service).post(
        "/api/assistant/ask",
        json={"query": "What was I supposed to remember?"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "family_message"
    assert payload["used_memory"] is True
    assert payload["source_ids"] == ["fam_assistant"]
    assert "Appointment reminder" in payload["answer"]
    assert "verify" in payload["answer"].lower()


def test_assistant_hydration_keeps_water_visibility_context_only() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    repository.persist_observation(
        _observation(
            "obs_assistant_water",
            objects=[
                DetectedObject(
                    object_key="water_bottle",
                    label="water bottle",
                    display_name="water bottle",
                    confidence=0.9,
                )
            ],
        )
    )

    response = _client(service).post(
        "/api/assistant/ask",
        json={"query": "Should I drink water?"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "hydration"
    assert payload["needs_human_verification"] is True
    assert payload["evidence_ids"] == ["obs_assistant_water"]
    assert "object visibility alone does not count as hydration" in payload["answer"].lower()
    assert "does not count as drinking" in payload["next_step"].lower()


def test_assistant_wellness_uses_action_backed_conservative_wording() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    observed_at = utc_now()
    service.create_wellness_check(
        WellnessCheck(
            id="well_assistant_possible_fall",
            type=WellnessCheckType.POSSIBLE_FALL_CHECK,
            severity=AlertSeverity.MEDIUM,
            status=WellnessCheckStatus.OPEN,
            title="Possible fall check",
            body=(
                "A possible fall candidate persisted in action telemetry. "
                "Please check in; human verification is required."
            ),
            confidence=QueryConfidence.MEDIUM,
            occurred_at=observed_at,
            zone_id="kitchen_zone",
            evidence_ids=["obs_assistant_possible_fall"],
            metadata={
                "source": "action_event",
                "reason": "action_fall_persistent",
                "human_verification_required": True,
            },
        )
    )

    response = _client(service).post(
        "/api/assistant/ask",
        json={"query": "Is there a wellness check today?"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "wellness"
    assert payload["used_current_perception"] is True
    assert payload["used_memory"] is True
    assert payload["evidence_ids"] == ["obs_assistant_possible_fall"]
    assert "possible" in payload["answer"].lower()
    assert "human verification is required" in payload["answer"].lower()
    assert "detected" not in payload["answer"].lower()


def test_assistant_setup_status_reports_activation_layers_without_secrets() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)

    response = _client(service).post(
        "/api/assistant/ask",
        json={"query": "Is the Afferens node setup working?"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "setup_status"
    assert payload["used_current_perception"] is False
    assert "Afferens API key is not configured" in payload["answer"]
    assert "https://afferens.com/node" in payload["next_step"]
    assert "api-key" not in response.text.lower()


def test_assistant_unsupported_query_lists_supported_options() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)

    response = _client(service).post(
        "/api/assistant/ask",
        json={"query": "Write me a poem about clouds"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["intent"] == "unsupported"
    assert payload["confidence"] == "low"
    assert payload["used_memory"] is False
    assert payload["evidence_ids"] == []
    assert "object finding" in payload["answer"]
    assert "medical advice" in payload["answer"]
