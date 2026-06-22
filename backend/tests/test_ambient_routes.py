from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_runtime_monitor_supervisor
from app.runtime_supervisor import InMemoryRuntimeMonitorStore, RuntimeMonitorSupervisor
from app.services import DataSpineService
from tests.test_runtime_supervisor import FakeAfferensAdapter, _live_result, _no_live_result


def _client_with_runtime_supervisor(
    adapter: FakeAfferensAdapter,
) -> tuple[TestClient, InMemoryDataRepository, RuntimeMonitorSupervisor]:
    app = create_app()
    settings = Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key="test-api-key",
        database_enabled=False,
    )
    repository = InMemoryDataRepository()
    supervisor = RuntimeMonitorSupervisor(
        settings,
        adapter=adapter,  # type: ignore[arg-type]
        store=InMemoryRuntimeMonitorStore(),
        data_spine=DataSpineService(repository),
        idle_sleep_seconds=0.01,
    )
    app.dependency_overrides[get_runtime_monitor_supervisor] = lambda: supervisor
    return TestClient(app), repository, supervisor


def test_ambient_start_status_and_stop_wraps_autonomous_runtime_without_ticking() -> None:
    adapter = FakeAfferensAdapter(
        [
            _live_result(
                {
                    "entity_id": "LIVE-VIS-AMBIENT-1",
                    "timestamp_utc": "2026-06-22T10:00:00Z",
                    "source_node_id": "NODE-01",
                    "modality": "VISION",
                    "objects": [{"label": "bottle", "confidence": 0.9}],
                }
            )
        ]
    )
    client, repository, _ = _client_with_runtime_supervisor(adapter)

    start_response = client.post(
        "/api/ambient/start",
        json={
            "mode": "active_recovery",
            "poll_interval_seconds": 5,
            "duration_seconds": 30,
            "target_object_key": "bottle",
            "zone_id": "study",
        },
    )
    start_payload = start_response.json()

    assert start_response.status_code == 200
    assert start_payload["monitor"]["state"] == "running"
    assert start_payload["monitor"]["mode"] == "active_recovery"
    assert start_payload["monitor"]["estimated_afferens_tokens_per_call"] == 14
    assert start_payload["monitor"]["target_visible_now"] is None
    assert start_payload["monitor"]["observations_synced"] == 0
    assert adapter.calls == 0
    assert repository.latest_observation() is None

    status_response = client.get("/api/ambient/status")
    assert status_response.status_code == 200
    assert status_response.json()["monitor"]["state"] == "running"
    assert adapter.calls == 0

    stop_response = client.post("/api/ambient/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["monitor"]["state"] == "off"


async def test_ambient_compatibility_reports_runtime_errors_after_background_tick() -> None:
    adapter = FakeAfferensAdapter([_no_live_result()])
    client, repository, supervisor = _client_with_runtime_supervisor(adapter)

    response = client.post(
        "/api/ambient/start",
        json={"mode": "ambient", "poll_interval_seconds": 30},
    )
    assert response.status_code == 200

    status = await supervisor.tick_once(force=True)
    assert status.state == "degraded"

    payload = client.get("/api/ambient/status").json()
    assert payload["monitor"]["state"] == "running"
    assert payload["monitor"]["last_error"] == "No live Afferens Vision events are available."
    assert payload["monitor"]["observations_synced"] == 0
    assert repository.latest_observation() is None
