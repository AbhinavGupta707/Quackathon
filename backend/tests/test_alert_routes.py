from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_app_settings, get_data_spine_service
from app.schemas import (
    ActuationAttempt,
    ActuationState,
    FamilyMessage,
    FamilyMessagePriority,
    FamilyMessageStatus,
    Task,
    TaskState,
    TaskType,
)
from app.services import DataSpineService


def test_alert_list_and_acknowledgement_use_evidence_and_do_not_leak_secret() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    sync_result = service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-MEDICINE-1",
                "timestamp_utc": "2026-06-21T16:40:00Z",
                "objects": [
                    {
                        "label": "medicine",
                        "confidence": 0.82,
                        "relative_location": "on the counter",
                    }
                ],
            }
        ],
        room_id="kitchen",
    )
    alert = sync_result.alerts_created[0]

    app = create_app()
    settings = Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key="test-api-key",
    )
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_data_spine_service] = lambda: service
    client = TestClient(app)

    list_response = client.get("/api/alerts?status=open")
    list_payload = list_response.json()

    assert list_response.status_code == 200
    assert list_payload["alerts"][0]["id"] == alert.id
    assert list_payload["alerts"][0]["evidence_observation_ids"] == [sync_result.observations[0].id]

    ack_response = client.post(
        f"/api/alerts/{alert.id}/ack",
        json={"acknowledged_by": "caregiver", "note": "Checking now."},
    )
    ack_payload = ack_response.json()

    assert ack_response.status_code == 200
    assert ack_payload["ok"] is True
    assert ack_payload["alert"]["status"] == "acknowledged"
    assert ack_payload["alert"]["acknowledged_at"] is not None
    assert repository.alerts[alert.id].status == "acknowledged"
    assert repository.task_events[-1]["event_type"] == "alert_acknowledged"
    assert "test-api-key" not in ack_response.text


def test_caregiver_notification_queue_includes_family_recovery_and_actuation_items() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    task = service.create_task(
        Task(
            id="task_recovery_1",
            type=TaskType.OBJECT_RECOVERY,
            state=TaskState.ACTUATION_ATTEMPTED,
            title="Find keys",
            body="Keys may need recovery.",
            recommended_action="Continue live verification.",
            evidence_observation_ids=["obs_keys"],
            metadata={"actuation_resolution_required": "live_verification_or_human_ack"},
        )
    )
    repository.create_family_message(
        FamilyMessage(
            id="fam_due_1",
            title="Take a break",
            body="Please take a break.",
            priority=FamilyMessagePriority.HIGH,
            status=FamilyMessageStatus.ACTIVE,
        )
    )
    repository.create_family_message(
        FamilyMessage(
            id="fam_ack_1",
            title="Lunch reminder",
            body="Lunch is ready.",
            priority=FamilyMessagePriority.NORMAL,
            status=FamilyMessageStatus.ACKNOWLEDGED,
            acknowledged_at=task.created_at,
        )
    )
    service.create_actuation_attempt(
        ActuationAttempt(
            id="actuation_1",
            task_id=task.id,
            provider="afferens",
            command_type="CAPTURE_FRAME",
            state=ActuationState.SUCCEEDED,
            message="Captured.",
            evidence_observation_ids=["obs_keys"],
            created_at=task.created_at,
        )
    )

    app = create_app()
    settings = Settings(environment="test", afferens_api_key="test-api-key")
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_data_spine_service] = lambda: service
    client = TestClient(app)

    response = client.get("/api/alerts/notifications?include_acknowledged=true")
    payload = response.json()

    assert response.status_code == 200
    notification_types = {item["type"] for item in payload["notifications"]}
    assert "family_prompt_due" in notification_types
    assert "family_prompt_acknowledged" in notification_types
    assert "unresolved_recovery_task" in notification_types
    assert "actuation_verification_required" in notification_types

    actuation_notification = [
        item
        for item in payload["notifications"]
        if item["type"] == "actuation_verification_required"
    ][0]
    assert actuation_notification["task_id"] == task.id
    assert actuation_notification["requires_live_verification"] is True
    assert actuation_notification["metadata"]["verification_requirement"] == (
        "live_verification_or_human_ack"
    )

    queued_only = client.get("/api/alerts/notifications").json()["notifications"]
    assert "family_prompt_acknowledged" not in {item["type"] for item in queued_only}
