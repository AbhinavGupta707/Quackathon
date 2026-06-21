from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.schemas import AfferensConnectionState


def _settings(**overrides: Any) -> Settings:
    values = {
        "afferens_base_url": "https://afferens.test",
        "afferens_api_key": "test-api-key",
        **overrides,
    }
    return Settings(**values)


@pytest.mark.parametrize(
    ("status_code", "expected_state"),
    [
        (401, AfferensConnectionState.INVALID_KEY),
        (403, AfferensConnectionState.INACTIVE_KEY),
        (404, AfferensConnectionState.NO_LIVE_EVENTS),
        (500, AfferensConnectionState.ERROR),
    ],
)
async def test_fetch_latest_maps_afferens_errors(
    status_code: int,
    expected_state: AfferensConnectionState,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code, json={"detail": "nope"})
    )

    result = await AfferensAdapter(_settings(), transport=transport).fetch_latest()

    assert result.status.state == expected_state
    assert result.raw_event is None


async def test_fetch_latest_uses_live_perception_request_shape() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "events": [
                    {
                        "id": "LIVE-VIS-MP0SH76G",
                        "timestamp_utc": "2026-06-21T16:00:00Z",
                        "source_node_id": "LAPTOP-WEBCAM-01",
                        "modality": "vision",
                    }
                ]
            },
        )

    result = await AfferensAdapter(
        _settings(),
        transport=httpx.MockTransport(handler),
    ).fetch_latest()

    assert captured_request is not None
    assert captured_request.method == "GET"
    assert captured_request.url.path == "/api/perception"
    assert captured_request.url.params["modality"] == "vision"
    assert captured_request.url.params["limit"] == "1"
    assert captured_request.headers["X-API-KEY"] == "test-api-key"
    assert result.status.state == AfferensConnectionState.LIVE
    assert result.status.latest_event_id == "LIVE-VIS-MP0SH76G"
    assert result.status.source_node_id == "LAPTOP-WEBCAM-01"
    assert result.status.modality == "VISION"
    assert result.raw_event is not None


async def test_fetch_latest_empty_success_is_no_live_events() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"events": []}))

    result = await AfferensAdapter(_settings(), transport=transport).fetch_latest()

    assert result.status.state == AfferensConnectionState.NO_LIVE_EVENTS
    assert result.raw_event is None


async def test_fetch_latest_missing_key_does_not_call_http() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP transport should not be called without a key")

    result = await AfferensAdapter(
        _settings(afferens_api_key=None),
        transport=httpx.MockTransport(handler),
    ).fetch_latest()

    assert result.status.state == AfferensConnectionState.MISSING_KEY
