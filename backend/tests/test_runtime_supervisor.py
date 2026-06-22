from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_runtime_monitor_supervisor
from app.runtime_supervisor import InMemoryRuntimeMonitorStore, RuntimeMonitorSupervisor
from app.schemas import (
    AfferensConnectionState,
    AfferensFetchResult,
    AfferensStatus,
    HomeZone,
    RuntimeMonitorStartRequest,
    utc_now,
)
from app.services import DataSpineService


class FakeAfferensAdapter:
    def __init__(self, results: list[AfferensFetchResult]) -> None:
        self.results = results
        self.calls = 0
        self.limits: list[int] = []

    async def fetch_events(self, *, limit: int = 1) -> AfferensFetchResult:
        self.calls += 1
        self.limits.append(limit)
        if self.calls <= len(self.results):
            return self.results[self.calls - 1]
        return self.results[-1]


def _live_result(event: dict[str, Any]) -> AfferensFetchResult:
    return AfferensFetchResult(
        status=AfferensStatus(
            configured=True,
            base_url="https://afferens.test",
            state=AfferensConnectionState.LIVE,
            message="Live Afferens Vision event available.",
            latest_event_id=str(event.get("entity_id")),
            latest_timestamp_utc=utc_now(),
            source_node_id="NODE-01",
            modality="VISION",
        ),
        raw_event=event,
        raw_events=[event],
    )


def _no_live_result(message: str = "No live Afferens Vision events are available.") -> AfferensFetchResult:
    return AfferensFetchResult(
        status=AfferensStatus(
            configured=True,
            base_url="https://afferens.test",
            state=AfferensConnectionState.NO_LIVE_EVENTS,
            message=message,
        )
    )


def _live_batch_result(events: list[dict[str, Any]]) -> AfferensFetchResult:
    latest = events[0]
    return AfferensFetchResult(
        status=AfferensStatus(
            configured=True,
            base_url="https://afferens.test",
            state=AfferensConnectionState.LIVE,
            message="Live Afferens Vision events available.",
            latest_event_id=str(latest.get("entity_id")),
            latest_timestamp_utc=utc_now(),
            source_node_id="NODE-01",
            modality="VISION",
        ),
        raw_event=latest,
        raw_events=events,
    )


def _supervisor(
    adapter: FakeAfferensAdapter,
) -> tuple[RuntimeMonitorSupervisor, InMemoryDataRepository]:
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
    return supervisor, repository


async def test_runtime_background_loop_ticks_without_status_polling() -> None:
    adapter = FakeAfferensAdapter(
        [
            _live_result(
                {
                    "entity_id": "LIVE-VIS-C9-1",
                    "timestamp_utc": "2026-06-22T10:00:00Z",
                    "source_node_id": "NODE-01",
                    "modality": "VISION",
                    "objects": [{"label": "keys", "confidence": 0.91}],
                }
            )
        ]
    )
    supervisor, repository = _supervisor(adapter)

    supervisor.start_background()
    try:
        await supervisor.start_monitor(
            RuntimeMonitorStartRequest(
                mode="home_memory",
                poll_interval_seconds=3,
                max_tokens_per_hour=420,
                zone_id="kitchen",
            )
        )
        for _ in range(50):
            if adapter.calls:
                break
            await asyncio.sleep(0.01)
    finally:
        await supervisor.stop_background()

    status = supervisor.current_status()
    assert adapter.calls == 1
    assert status.state == "running"
    assert status.source == "background_supervisor"
    assert status.observations_synced == 1
    assert status.token_budget.estimated_tokens_used_this_hour == 14
    assert repository.latest_observation() is not None
    assert repository.latest_observation().room_id == "kitchen"  # type: ignore[union-attr]


async def test_runtime_tick_uses_selected_zone_calibration_for_object_memory() -> None:
    adapter = FakeAfferensAdapter(
        [
            _live_result(
                {
                    "entity_id": "LIVE-VIS-C13-REGION",
                    "timestamp_utc": "2026-06-22T10:00:00Z",
                    "source_node_id": "NODE-01",
                    "modality": "VISION",
                    "objects": [
                        {
                            "label": "remote",
                            "confidence": 0.91,
                            "bbox": [0.0, 0.6, 0.4, 0.9],
                        }
                    ],
                }
            )
        ]
    )
    supervisor, repository = _supervisor(adapter)
    repository.create_home_zone(
        HomeZone(
            id="living_room_zone",
            name="Living room",
            room_type="living_room",
            region_strategy="quadrants",
            created_at=utc_now(),
        )
    )

    await supervisor.start_monitor(
        RuntimeMonitorStartRequest(
            mode="home_memory",
            poll_interval_seconds=3,
            max_tokens_per_hour=420,
            zone_id="living_room_zone",
        )
    )
    await supervisor.tick_once(force=True)

    memory = repository.list_last_seen_objects()[0]
    assert memory.object_key == "remote"
    assert memory.last_seen_room == "Living room"
    assert memory.last_seen_room_id == "living_room_zone"
    assert memory.last_seen_region_label == "bottom left area"
    assert memory.location_assignment_source == "calibrated_region"


async def test_runtime_dedupes_repeated_afferens_event_ids() -> None:
    event = {
        "entity_id": "LIVE-VIS-C9-SAME",
        "timestamp_utc": "2026-06-22T10:00:00Z",
        "source_node_id": "NODE-01",
        "modality": "VISION",
        "objects": [{"label": "bottle", "confidence": 0.88}],
    }
    adapter = FakeAfferensAdapter([_live_result(event), _live_result(event)])
    supervisor, repository = _supervisor(adapter)

    await supervisor.start_monitor(
        RuntimeMonitorStartRequest(poll_interval_seconds=3, max_tokens_per_hour=420)
    )
    first_status = await supervisor.tick_once(force=True)
    second_status = await supervisor.tick_once(force=True)

    assert adapter.calls == 2
    assert first_status.observations_synced == 1
    assert second_status.observations_synced == 1
    assert len(repository.observations) == 1
    assert len(repository.raw_events) == 1
    assert second_status.last_provider_event_id == "LIVE-VIS-C9-SAME"


async def test_runtime_syncs_new_event_batch_to_reduce_missed_objects() -> None:
    older = {
        "entity_id": "LIVE-VIS-C9-OLDER",
        "timestamp_utc": "2026-06-22T10:00:00Z",
        "source_node_id": "NODE-01",
        "modality": "VISION",
        "objects": [{"label": "mouse", "confidence": 0.81}],
    }
    newer = {
        "entity_id": "LIVE-VIS-C9-NEWER",
        "timestamp_utc": "2026-06-22T10:00:04Z",
        "source_node_id": "NODE-01",
        "modality": "VISION",
        "objects": [{"label": "portal", "confidence": 0.74}],
    }
    adapter = FakeAfferensAdapter([_live_batch_result([newer, older])])
    supervisor, repository = _supervisor(adapter)

    await supervisor.start_monitor(
        RuntimeMonitorStartRequest(poll_interval_seconds=3, max_tokens_per_hour=420)
    )
    status = await supervisor.tick_once(force=True)

    assert adapter.limits == [5]
    assert status.observations_synced == 2
    assert status.last_provider_event_id == "LIVE-VIS-C9-NEWER"
    assert set(repository.last_seen) == {"mouse", "portal"}


async def test_runtime_pauses_before_exceeding_hourly_token_budget() -> None:
    adapter = FakeAfferensAdapter(
        [
            _live_result(
                {
                    "entity_id": "LIVE-VIS-C9-BUDGET",
                    "timestamp_utc": "2026-06-22T10:00:00Z",
                    "objects": [{"label": "cup", "confidence": 0.8}],
                }
            )
        ]
    )
    supervisor, _ = _supervisor(adapter)

    await supervisor.start_monitor(
        RuntimeMonitorStartRequest(poll_interval_seconds=3, max_tokens_per_hour=14)
    )
    running_status = await supervisor.tick_once(force=True)
    paused_status = await supervisor.tick_once(force=True)

    assert adapter.calls == 1
    assert running_status.token_budget.estimated_tokens_used_this_hour == 14
    assert paused_status.state == "paused"
    assert paused_status.last_error == "Afferens Vision token budget is paused until the next hour."


async def test_runtime_enters_degraded_backoff_on_provider_errors() -> None:
    adapter = FakeAfferensAdapter([_no_live_result()])
    supervisor, repository = _supervisor(adapter)

    await supervisor.start_monitor(
        RuntimeMonitorStartRequest(poll_interval_seconds=3, max_tokens_per_hour=420)
    )
    status = await supervisor.tick_once(force=True)

    assert adapter.calls == 1
    assert status.state == "degraded"
    assert status.backoff_seconds >= 15
    assert status.last_error == "No live Afferens Vision events are available."
    assert status.token_budget.estimated_tokens_used_this_hour == 14
    assert repository.latest_observation() is None


def test_runtime_routes_report_state_without_route_ticking() -> None:
    adapter = FakeAfferensAdapter(
        [
            _live_result(
                {
                    "entity_id": "LIVE-VIS-C9-ROUTE",
                    "timestamp_utc": "2026-06-22T10:00:00Z",
                    "objects": [{"label": "keys", "confidence": 0.9}],
                }
            )
        ]
    )
    supervisor, _ = _supervisor(adapter)
    app = create_app()
    app.dependency_overrides[get_runtime_monitor_supervisor] = lambda: supervisor

    client = TestClient(app)
    start_response = client.post(
        "/api/runtime/monitor/start",
        json={
            "mode": "home_memory",
            "poll_interval_seconds": 45,
            "zone_id": "default_home_zone",
            "max_tokens_per_hour": 420,
        },
    )
    status_response = client.get("/api/runtime/monitor/status")
    stop_response = client.post("/api/runtime/monitor/stop")

    assert start_response.status_code == 200
    assert start_response.json()["monitor"]["source"] == "background_supervisor"
    assert start_response.json()["monitor"]["token_budget"]["estimated_tokens_per_call"] == 14
    assert status_response.status_code == 200
    assert status_response.json()["monitor"]["state"] == "running"
    assert stop_response.status_code == 200
    assert stop_response.json()["monitor"]["state"] == "off"
    assert adapter.calls == 0
