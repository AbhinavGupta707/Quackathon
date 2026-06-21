from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_app_settings, get_data_spine_service
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
