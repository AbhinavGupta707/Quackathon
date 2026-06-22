from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_afferens_adapter, get_app_settings, get_data_spine_service
from app.schemas import Task, TaskState, TaskType
from app.services import DataSpineService


def _settings(*, actuation_enabled: bool) -> Settings:
    return Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key="test-api-key",
        afferens_actuation_enabled=actuation_enabled,
    )


def _client(
    service: DataSpineService,
    settings: Settings,
    transport: httpx.MockTransport,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_data_spine_service] = lambda: service
    app.dependency_overrides[get_afferens_adapter] = lambda: AfferensAdapter(
        settings,
        transport=transport,
    )
    return TestClient(app)


def _safety_task(service: DataSpineService):
    result = service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-STOVE-ACTUATE",
                "timestamp_utc": "2026-06-21T16:00:00Z",
                "person_visible": False,
                "objects": [{"label": "stove", "confidence": 0.84}],
            }
        ],
        room_id="kitchen",
    )
    return result.tasks_created[0], result.alerts_created[0]


def test_capture_frame_actuation_disabled_records_skipped_attempt_without_provider_call() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    task, alert = _safety_task(service)

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Disabled actuation must not call Afferens")

    client = _client(
        service,
        _settings(actuation_enabled=False),
        httpx.MockTransport(fail_if_called),
    )

    response = client.post(
        "/api/actuate/capture-frame",
        json={"task_id": task.id, "alert_id": alert.id, "reason": "guided_recovery_verification"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["attempt"]["state"] == "skipped"
    assert payload["attempt"]["command_type"] == "CAPTURE_FRAME"
    assert "disabled" in payload["attempt"]["message"]
    assert repository.actuation_attempts[payload["attempt"]["id"]].alert_id == alert.id
    assert repository.tasks[task.id].state == TaskState.OPEN
    assert repository.tasks[task.id].metadata["last_actuation_state"] == "skipped"
    assert repository.tasks[task.id].metadata["actuation_verification_required"] is True
    assert repository.tasks[task.id].metadata["actuation_resolution_required"] == (
        "live_verification_or_human_ack"
    )
    assert repository.task_events[-1]["event_type"] == "actuation_attempt_skipped"
    assert "test-api-key" not in response.text


def test_alarm_actuation_enabled_posts_official_afferens_body_and_updates_task() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    task, alert = _safety_task(service)
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "status": 200,
                "accepted": True,
                "api_key": "provider-secret-that-must-not-leak",
            },
        )

    client = _client(
        service,
        _settings(actuation_enabled=True),
        httpx.MockTransport(handler),
    )

    response = client.post(
        "/api/actuate/alarm",
        json={
            "task_id": task.id,
            "alert_id": alert.id,
            "reason": "unattended_cooking_possible",
            "severity": "medium",
            "target_node_id": "NODE-01",
            "use_afferens": True,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert captured_request is not None
    assert captured_request.url.path == "/api/actuation"
    assert captured_request.headers["X-API-KEY"] == "test-api-key"
    request_body = json.loads(captured_request.content)
    assert request_body["command_type"] == "TRIGGER_ALARM"
    assert request_body["target_node_id"] == "NODE-01"
    assert request_body["parameters"]["reason"] == "unattended_cooking_possible"

    assert payload["attempt"]["state"] == "succeeded"
    assert payload["attempt"]["provider"] == "afferens"
    assert payload["attempt"]["response_payload"]["api_key"] == "[redacted]"
    assert repository.tasks[task.id].state == TaskState.ACTUATION_ATTEMPTED
    assert repository.tasks[task.id].metadata["last_actuation_command"] == "TRIGGER_ALARM"
    assert repository.tasks[task.id].metadata["last_actuation_requires_live_verification"] is True
    assert repository.task_events[-1]["event_type"] == "actuation_attempt_succeeded"
    assert "test-api-key" not in response.text
    assert "provider-secret-that-must-not-leak" not in response.text

    notifications = client.get("/api/alerts/notifications").json()["notifications"]
    verification_notifications = [
        item for item in notifications if item["type"] == "actuation_verification_required"
    ]
    assert len(verification_notifications) == 1
    assert verification_notifications[0]["task_id"] == task.id
    assert verification_notifications[0]["requires_live_verification"] is True


def test_actuation_rejects_task_without_live_evidence_linkage() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    task = service.create_task(
        Task(
            id="task_without_evidence",
            type=TaskType.SAFETY_ALERT,
            state=TaskState.OPEN,
            title="Manual task",
            body="No live evidence is linked.",
            recommended_action="Do not actuate.",
            evidence_observation_ids=[],
        )
    )

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Evidence-gate rejection must not call Afferens")

    client = _client(
        service,
        _settings(actuation_enabled=True),
        httpx.MockTransport(fail_if_called),
    )

    response = client.post(
        "/api/actuate/alarm",
        json={"task_id": task.id, "reason": "manual_without_evidence", "use_afferens": True},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Actuation requires a task with linked live evidence."
    assert repository.actuation_attempts == {}
