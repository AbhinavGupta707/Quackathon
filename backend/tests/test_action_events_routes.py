from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_app_settings, get_data_spine_service, get_yolo_fall_adapter
from app.schemas import ActionRuntimeFallStatus
from app.services import DataSpineService
from app.yolo_fall_adapter import FallInferenceResult


def _client(
    *,
    settings: Settings | None = None,
    fall_adapter: object | None = None,
) -> tuple[TestClient, InMemoryDataRepository, DataSpineService]:
    app = create_app()
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    runtime_settings = settings or Settings(
        environment="test",
        database_enabled=False,
        action_yolo_fall_enabled=False,
        action_fall_persistence_seconds=3.5,
        action_fall_debounce_seconds=120,
        action_drink_min_window_seconds=1.0,
    )
    app.dependency_overrides[get_data_spine_service] = lambda: service
    app.dependency_overrides[get_app_settings] = lambda: runtime_settings
    if fall_adapter is not None:
        app.dependency_overrides[get_yolo_fall_adapter] = lambda: fall_adapter
    return TestClient(app), repository, service


def test_action_event_create_and_list_persists_contract_fields() -> None:
    client, _repository, _service = _client()

    response = client.post(
        "/api/action-events",
        json={
            "type": "action_inconclusive",
            "occurred_at": "2026-06-21T18:45:00Z",
            "confidence": "low",
            "score": 0.2,
            "source": "browser_mediapipe",
            "source_node_id": "LAPTOP-WEBCAM-01",
            "zone_id": "living_room",
            "evidence_ids": ["obs_1"],
            "metadata": {"reason": "test_event"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["wellness_check_id"] is None
    assert payload["hydration_event_id"] is None
    event = payload["event"]
    assert event["id"].startswith("act_")
    assert event["type"] == "action_inconclusive"
    assert event["source"] == "browser_mediapipe"
    assert event["metadata"]["raw_video_stored"] is False

    listed = client.get("/api/action-events?date=2026-06-21&type=action_inconclusive").json()
    assert [item["id"] for item in listed["events"]] == [event["id"]]


def test_action_event_create_rejects_direct_drink_candidate_shortcut() -> None:
    client, _repository, _service = _client()

    response = client.post(
        "/api/action-events",
        json={
            "type": "drink_candidate",
            "occurred_at": "2026-06-21T12:12:00Z",
            "confidence": "medium",
            "score": 0.72,
            "source": "manual_shortcut_attempt",
            "source_node_id": "BROWSER-ACTION-NODE",
            "evidence_ids": ["obs_direct_drink"],
            "metadata": {
                "reason": "direct_drink_shortcut",
            },
        },
    )
    payload = response.json()

    assert response.status_code == 422
    assert "/api/action-events/drink/evaluate" in payload["detail"]

    summary = client.get("/api/hydration/summary?date=2026-06-21").json()["summary"]
    assert summary["water_events"] == 0


def test_fall_evaluate_requires_persistence_before_wellness_check() -> None:
    client, _repository, _service = _client(
        settings=Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path="/tmp/fake-fall-model.pt",
            action_fall_persistence_seconds=3.5,
            action_fall_debounce_seconds=120,
        ),
        fall_adapter=_FakeFallAdapter(),
    )

    inconclusive_response = client.post(
        "/api/action-events/fall/evaluate",
        json={
            "occurred_at": "2026-06-21T18:50:00Z",
            "source": "local_yolo_fall",
            "source_node_id": "LAPTOP-WEBCAM-01",
            "zone_id": "living_room",
            "evidence_ids": ["obs_fall_1"],
            "posture_state": "fallen",
            "persistence_seconds": 2.0,
            "confidence": "medium",
            "score": 0.82,
        },
    )
    inconclusive = inconclusive_response.json()

    assert inconclusive_response.status_code == 200
    assert inconclusive["decision"] == "action_inconclusive"
    assert inconclusive["wellness_check_id"] is None
    assert inconclusive["event"]["metadata"]["reason"] == "fall_persistence_threshold_not_met"
    assert inconclusive["event"]["metadata"]["adapter_status"] == "configured"

    candidate_response = client.post(
        "/api/action-events/fall/evaluate",
        json={
            "occurred_at": "2026-06-21T18:50:05Z",
            "source": "local_yolo_fall",
            "source_node_id": "LAPTOP-WEBCAM-01",
            "zone_id": "living_room",
            "evidence_ids": ["obs_fall_2"],
            "fallen": True,
            "persistence_seconds": 3.8,
            "confidence": "medium",
            "score": 0.86,
        },
    )
    candidate = candidate_response.json()

    assert candidate_response.status_code == 200
    assert candidate["decision"] == "fall_candidate"
    assert candidate["wellness_check_id"] is not None
    assert "escalated notification to caregiver" in candidate["message"].lower()

    checks = client.get("/api/wellness/checks?date=2026-06-21").json()["checks"]
    fall_checks = [item for item in checks if item["type"] == "possible_fall_check"]
    assert len(fall_checks) == 1
    assert fall_checks[0]["id"] == candidate["wellness_check_id"]
    assert fall_checks[0]["title"] == "Possible fall candidate"
    assert "escalated to the caregiver for a possible fall" in fall_checks[0]["body"].lower()
    assert "detected" not in fall_checks[0]["body"].lower()

    notifications = client.get("/api/alerts/notifications?date=2026-06-21").json()[
        "notifications"
    ]
    fall_notifications = [
        item for item in notifications if item["type"] == "possible_fall_check"
    ]
    assert len(fall_notifications) == 1
    assert fall_notifications[0]["wellness_check_id"] == candidate["wellness_check_id"]
    assert fall_notifications[0]["requires_live_verification"] is True
    assert fall_notifications[0]["title"] == "Possible fall candidate"
    assert "escalated to the caregiver for a possible fall" in fall_notifications[0]["body"].lower()
    assert "detected" not in fall_notifications[0]["body"].lower()

    debounced_response = client.post(
        "/api/action-events/fall/evaluate",
        json={
            "occurred_at": "2026-06-21T18:50:30Z",
            "source": "local_yolo_fall",
            "source_node_id": "LAPTOP-WEBCAM-01",
            "evidence_ids": ["obs_fall_3"],
            "fallen": True,
            "persistence_seconds": 4.0,
            "confidence": "medium",
        },
    )
    assert debounced_response.json()["wellness_check_id"] == candidate["wellness_check_id"]
    checks_after = client.get("/api/wellness/checks?date=2026-06-21").json()["checks"]
    assert len([item for item in checks_after if item["type"] == "possible_fall_check"]) == 1


def test_fall_evaluate_local_yolo_unavailable_never_creates_candidate() -> None:
    client, _repository, _service = _client()

    response = client.post(
        "/api/action-events/fall/evaluate",
        json={
            "occurred_at": "2026-06-21T18:50:05Z",
            "source": "local_yolo_fall",
            "source_node_id": "NO-YOLO-01",
            "zone_id": "living_room",
            "evidence_ids": ["obs_fall_disabled"],
            "fallen": True,
            "persistence_seconds": 4.0,
            "confidence": "medium",
            "score": 0.86,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"] == "action_inconclusive"
    assert payload["wellness_check_id"] is None
    assert payload["event"]["metadata"]["reason"] == "fall_model_runtime_unavailable"
    assert payload["event"]["metadata"]["adapter_status"] == "disabled"

    checks = client.get("/api/wellness/checks?date=2026-06-21").json()["checks"]
    assert [item for item in checks if item["type"] == "possible_fall_check"] == []


def test_runtime_status_reports_disabled_yolo_without_blocking_drink_runtime() -> None:
    client, _repository, _service = _client()

    response = client.get("/api/action-events/runtime/status")
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["fall"]["enabled"] is False
    assert payload["fall"]["available"] is False
    assert payload["fall"]["state"] == "disabled"
    assert payload["fall"]["unavailable_reason"] == "disabled"
    assert payload["fall"]["model_file_exists"] is False
    assert payload["drink"]["available"] is True
    assert payload["drink"]["provider"] == "browser_mediapipe"
    assert payload["privacy"]["raw_video_storage_enabled"] is False
    assert payload["privacy"]["raw_frames_persisted"] is False


def test_runtime_status_reports_missing_model_path_and_missing_file(tmp_path) -> None:
    missing_path_client, _repository, _service = _client(
        settings=Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path=None,
        )
    )

    missing_path = missing_path_client.get("/api/action-events/runtime/status").json()

    assert missing_path["fall"]["available"] is False
    assert missing_path["fall"]["state"] == "unavailable"
    assert missing_path["fall"]["unavailable_reason"] == "missing_model_path"
    assert missing_path["fall"]["model_path_configured"] is False
    assert missing_path["fall"]["model_file_exists"] is False

    missing_file_client, _repository, _service = _client(
        settings=Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path=str(tmp_path / "fall-model.pt"),
        )
    )

    missing_file = missing_file_client.get("/api/action-events/runtime/status").json()

    assert missing_file["fall"]["available"] is False
    assert missing_file["fall"]["state"] == "unavailable"
    assert missing_file["fall"]["unavailable_reason"] == "missing_model_file"
    assert missing_file["fall"]["model_path_configured"] is True
    assert missing_file["fall"]["model_file_exists"] is False


def test_fall_infer_frame_unavailable_runtime_records_inconclusive_without_fabricating_candidate() -> None:
    client, _repository, _service = _client()

    response = client.post(
        "/api/action-events/fall/infer-frame",
        files={"frame": ("frame.jpg", b"not-a-real-image", "image/jpeg")},
        data={
            "source_node_id": "YOLO-UNAVAILABLE-01",
            "zone_id": "living_room",
            "evidence_ids": "obs_1, obs_2",
            "occurred_at": "2026-06-21T18:50:00Z",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"] == "action_inconclusive"
    assert payload["wellness_check_id"] is None
    assert payload["event"]["source"] == "local_yolo_fall"
    assert payload["event"]["evidence_ids"] == ["obs_1", "obs_2"]
    assert payload["event"]["metadata"]["reason"] == "fall_model_runtime_unavailable"
    assert payload["event"]["metadata"]["adapter_status"] == "disabled"
    assert payload["event"]["metadata"]["raw_frame_persisted"] is False
    assert payload["event"]["metadata"]["raw_video_stored"] is False


def test_fall_infer_frame_rejects_oversized_frame_upload() -> None:
    client, _repository, _service = _client(
        settings=Settings(
            environment="test",
            database_enabled=False,
            action_max_frame_bytes=5,
        )
    )

    response = client.post(
        "/api/action-events/fall/infer-frame",
        files={"frame": ("frame.jpg", b"too-large-frame", "image/jpeg")},
    )

    assert response.status_code == 413
    assert "5 bytes or smaller" in response.json()["detail"]


def test_fall_infer_frame_requires_persistence_before_candidate_and_wellness_check() -> None:
    client, _repository, _service = _client(
        settings=Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path="/tmp/fake-fall-model.pt",
            action_fall_persistence_seconds=3.5,
            action_fall_debounce_seconds=120,
        ),
        fall_adapter=_FakeFallAdapter(),
    )

    first_response = client.post(
        "/api/action-events/fall/infer-frame",
        files={"frame": ("frame.jpg", b"fake-image-1", "image/jpeg")},
        data={
            "source_node_id": "FAKE-YOLO-01",
            "zone_id": "living_room",
            "evidence_ids": "obs_fall_1",
            "occurred_at": "2026-06-21T18:50:00Z",
        },
    )
    first = first_response.json()

    assert first_response.status_code == 200
    assert first["decision"] == "action_inconclusive"
    assert first["wellness_check_id"] is None
    assert first["event"]["metadata"]["persistence_seconds"] == 0.0
    assert first["event"]["metadata"]["raw_frame_persisted"] is False
    assert first["event"]["metadata"]["raw_video_stored"] is False

    second_response = client.post(
        "/api/action-events/fall/infer-frame",
        files={"frame": ("frame.jpg", b"fake-image-2", "image/jpeg")},
        data={
            "source_node_id": "FAKE-YOLO-01",
            "zone_id": "living_room",
            "evidence_ids": "obs_fall_2",
            "occurred_at": "2026-06-21T18:50:04Z",
        },
    )
    second = second_response.json()

    assert second_response.status_code == 200
    assert second["decision"] == "fall_candidate"
    assert second["wellness_check_id"] is not None
    assert second["event"]["metadata"]["persistence_seconds"] == 4.0
    assert second["event"]["metadata"]["model_provider"] == "ultralytics"
    assert second["event"]["metadata"]["raw_frame_persisted"] is False

    checks = client.get("/api/wellness/checks?date=2026-06-21").json()["checks"]
    assert [check["id"] for check in checks if check["type"] == "possible_fall_check"] == [
        second["wellness_check_id"]
    ]


def test_fall_infer_frame_auto_scan_does_not_persist_inconclusive_rows() -> None:
    client, _repository, _service = _client(
        settings=Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path="/tmp/fake-fall-model.pt",
            action_fall_persistence_seconds=3.5,
            action_fall_debounce_seconds=120,
        ),
        fall_adapter=_FakeFallAdapter(),
    )

    first_response = client.post(
        "/api/action-events/fall/infer-frame",
        files={"frame": ("frame.jpg", b"fake-image-1", "image/jpeg")},
        data={
            "source_node_id": "AUTO-YOLO-01",
            "zone_id": "living_room",
            "occurred_at": "2026-06-21T18:50:00Z",
            "persist_inconclusive": "false",
        },
    )
    first = first_response.json()

    assert first_response.status_code == 200
    assert first["decision"] == "action_inconclusive"
    assert first["event"]["metadata"]["persisted"] is False
    assert client.get("/api/action-events?date=2026-06-21").json()["events"] == []

    second_response = client.post(
        "/api/action-events/fall/infer-frame",
        files={"frame": ("frame.jpg", b"fake-image-2", "image/jpeg")},
        data={
            "source_node_id": "AUTO-YOLO-01",
            "zone_id": "living_room",
            "occurred_at": "2026-06-21T18:50:04Z",
            "persist_inconclusive": "false",
        },
    )
    second = second_response.json()

    assert second_response.status_code == 200
    assert second["decision"] == "fall_candidate"
    assert second["wellness_check_id"] is not None
    listed = client.get("/api/action-events?date=2026-06-21").json()["events"]
    assert [event["id"] for event in listed] == [second["event"]["id"]]


def test_fall_infer_frame_low_confidence_fallen_label_stays_inconclusive() -> None:
    client, _repository, _service = _client(
        settings=Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path="/tmp/fake-fall-model.pt",
            action_fall_persistence_seconds=3.5,
        ),
        fall_adapter=_LowConfidenceFallAdapter(),
    )

    for timestamp in ("2026-06-21T19:00:00Z", "2026-06-21T19:00:04Z"):
        response = client.post(
            "/api/action-events/fall/infer-frame",
            files={"frame": ("frame.jpg", b"fake-image", "image/jpeg")},
            data={
                "source_node_id": "LOWCONF-YOLO-01",
                "zone_id": "living_room",
                "occurred_at": timestamp,
            },
        )
        payload = response.json()

        assert response.status_code == 200
        assert payload["decision"] == "action_inconclusive"
        assert payload["wellness_check_id"] is None
        assert payload["event"]["metadata"]["model_label"] == "fallen"
        assert payload["event"]["metadata"]["confidence_threshold_met"] is False

    checks = client.get("/api/wellness/checks?date=2026-06-21").json()["checks"]
    assert [check for check in checks if check["type"] == "possible_fall_check"] == []


def test_drink_evaluate_rejects_object_visibility_only_without_hydration_count() -> None:
    client, _repository, _service = _client()

    response = client.post(
        "/api/action-events/drink/evaluate",
        json={
            "occurred_at": "2026-06-21T12:00:00Z",
            "source": "browser_mediapipe",
            "object_keys": ["water_bottle"],
            "object_visible": True,
            "evidence_ids": ["obs_water"],
            "confidence": "medium",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"] == "action_inconclusive"
    assert payload["hydration_event_id"] is None
    assert payload["event"]["metadata"]["reason"] == "object_visibility_only"
    assert "object visibility alone" in payload["message"].lower()

    summary = client.get("/api/hydration/summary?date=2026-06-21").json()["summary"]
    assert summary["water_events"] == 0
    assert summary["status"] == "unknown"


def test_drink_evaluate_rejects_explicit_action_without_temporal_evidence() -> None:
    client, _repository, _service = _client()

    response = client.post(
        "/api/action-events/drink/evaluate",
        json={
            "occurred_at": "2026-06-21T12:03:00Z",
            "source": "browser_mediapipe",
            "object_keys": ["cup_or_bottle_context"],
            "object_visible": True,
            "explicit_action_telemetry": True,
            "hand_object_contact": False,
            "hand_to_mouth_motion": True,
            "object_near_mouth": False,
            "temporal_window_seconds": 1.4,
            "evidence_ids": ["obs_pose_only"],
            "confidence": "medium",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"] == "action_inconclusive"
    assert payload["hydration_event_id"] is None
    assert payload["event"]["metadata"]["explicit_action_telemetry"] is True
    assert payload["event"]["metadata"]["reason"] == "drink_action_threshold_not_met"
    assert "temporal evidence" in payload["message"].lower()

    summary = client.get("/api/hydration/summary?date=2026-06-21").json()["summary"]
    assert summary["water_events"] == 0
    assert summary["status"] == "unknown"


def test_drink_evaluate_rejects_hand_motion_without_live_object_context() -> None:
    client, _repository, _service = _client()

    response = client.post(
        "/api/action-events/drink/evaluate",
        json={
            "occurred_at": "2026-06-21T12:04:00Z",
            "source": "browser_mediapipe",
            "object_keys": [],
            "object_visible": False,
            "explicit_action_telemetry": True,
            "hand_object_contact": True,
            "hand_to_mouth_motion": True,
            "object_near_mouth": True,
            "temporal_window_seconds": 1.4,
            "evidence_ids": ["obs_no_water_context"],
            "confidence": "medium",
            "score": 0.72,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"] == "action_inconclusive"
    assert payload["hydration_event_id"] is None
    assert payload["event"]["metadata"]["reason"] == "live_object_context_required"
    assert "live afferens" in payload["message"].lower()

    summary = client.get("/api/hydration/summary?date=2026-06-21").json()["summary"]
    assert summary["water_events"] == 0


def test_drink_evaluate_records_candidate_and_hydration_event_only_with_action_signal() -> None:
    client, _repository, _service = _client()

    response = client.post(
        "/api/action-events/drink/evaluate",
        json={
            "occurred_at": "2026-06-21T12:05:00Z",
            "source": "browser_mediapipe",
            "source_node_id": "LAPTOP-WEBCAM-01",
            "object_keys": ["cup"],
            "object_visible": True,
            "explicit_action_telemetry": True,
            "hand_object_contact": True,
            "hand_to_mouth_motion": True,
            "object_near_mouth": True,
            "temporal_window_seconds": 1.4,
            "evidence_ids": ["obs_drink"],
            "confidence": "medium",
            "score": 0.74,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"] == "drink_candidate"
    assert payload["hydration_event_id"] is not None
    assert payload["event"]["metadata"]["reason"] == "drink_action_threshold_met"

    summary = client.get("/api/hydration/summary?date=2026-06-21").json()["summary"]
    assert summary["water_events"] == 1
    assert summary["status"] == "consider_prompting"
    assert summary["events"][0]["type"] == "drink_candidate"
    assert summary["events"][0]["metadata"]["action_event_id"] == payload["event"]["id"]


class _FakeFallAdapter:
    def status(self) -> ActionRuntimeFallStatus:
        return ActionRuntimeFallStatus(
            enabled=True,
            available=True,
            state="ready",
            provider="ultralytics",
            model_path_configured=True,
            model_file_exists=True,
            model_loaded=True,
            labels=["fallen", "not_fallen"],
            message="Fake YOLO fall adapter is ready.",
        )

    def infer_frame(self, frame_bytes: bytes) -> FallInferenceResult:
        return FallInferenceResult(
            available=True,
            fallen=True,
            confidence=0.9,
            label="fallen",
            message="Fake YOLO fall inference completed.",
            metadata={
                "confidence_threshold": 0.6,
                "confidence_threshold_met": True,
                "raw_frame_persisted": False,
            },
        )


class _LowConfidenceFallAdapter(_FakeFallAdapter):
    def infer_frame(self, frame_bytes: bytes) -> FallInferenceResult:
        return FallInferenceResult(
            available=True,
            fallen=False,
            confidence=0.4,
            label="fallen",
            message="Fake low-confidence YOLO fall inference completed.",
            metadata={
                "confidence_threshold": 0.6,
                "confidence_threshold_met": False,
                "raw_frame_persisted": False,
            },
        )
