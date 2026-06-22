#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

try:
    import httpx  # noqa: E402
    from fastapi.testclient import TestClient  # noqa: E402

    from app.afferens_adapter import AfferensAdapter  # noqa: E402
    from app.config import Settings  # noqa: E402
    from app.main import create_app  # noqa: E402
    from app.routes.dependencies import (  # noqa: E402
        get_afferens_adapter,
        get_app_settings,
        get_runtime_monitor_supervisor,
    )
    from app.runtime_supervisor import (  # noqa: E402
        InMemoryRuntimeMonitorStore,
        RuntimeMonitorSupervisor,
    )
except ModuleNotFoundError as exc:
    print(
        "SKIP offline no-key/provider redaction smoke: "
        f"missing backend dependency {exc.name!r}. Install backend test deps first.",
        file=sys.stderr,
    )
    raise SystemExit(3) from exc


SENTINELS = (
    "secret-afferens-provider-key",
    "secret-fireworks-provider-key",
    "secret-langsmith-provider-key",
    "secret-gemini-provider-key",
    "secret-parcle-provider-key",
    "secret-parcel-provider-key",
)


def _client(settings: Settings, transport: httpx.MockTransport) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_afferens_adapter] = lambda: AfferensAdapter(
        settings,
        transport=transport,
    )
    app.dependency_overrides[get_runtime_monitor_supervisor] = lambda: RuntimeMonitorSupervisor(
        settings,
        adapter=AfferensAdapter(settings, transport=transport),
        store=InMemoryRuntimeMonitorStore(),
        idle_sleep_seconds=3600,
    )
    return TestClient(app)


def _assert_no_secret_text(label: str, body: str) -> None:
    lowered = body.lower()
    forbidden_fields = (
        '"api_key"',
        '"apikey"',
        "secret-afferens",
        "secret-fireworks",
        "secret-langsmith",
        "secret-gemini",
        "secret-parcle",
        "secret-parcel",
    )
    for value in SENTINELS:
        if value in body:
            raise AssertionError(f"{label} exposed sentinel secret {value!r}")
        first_fragment = value[:12]
        last_fragment = value[-8:]
        if first_fragment in body or last_fragment in body:
            raise AssertionError(f"{label} exposed a sentinel secret fragment")
    for field in forbidden_fields:
        if field in lowered:
            raise AssertionError(f"{label} exposed secret-shaped text {field!r}")


def _json_text(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True)


def _missing_key_client() -> TestClient:
    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("missing-key smoke must not call Afferens")

    settings = Settings(
        environment="test",
        afferens_api_key=None,
        fireworks_api_key=None,
        langsmith_api_key=None,
        gemini_api_key=None,
        parcle_api_key=None,
        parcel_api_key=None,
        database_enabled=False,
        action_yolo_fall_enabled=False,
    )
    return _client(settings, httpx.MockTransport(fail_if_called))


def _configured_provider_client() -> TestClient:
    def live_vision(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/perception":
            raise AssertionError(f"unexpected outbound request: {request.url}")
        return httpx.Response(
            200,
            json={
                "events": [
                    {
                        "event_id": "LIVE-PROVIDER-REDACTION",
                        "timestamp_utc": "2026-06-22T12:00:00Z",
                        "source_node_id": "PHONE-AFFERENS-NODE",
                        "modality": "VISION",
                    }
                ]
            },
        )

    settings = Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key=SENTINELS[0],
        fireworks_api_key=SENTINELS[1],
        langsmith_tracing=True,
        langsmith_api_key=SENTINELS[2],
        gemini_api_key=SENTINELS[3],
        parcle_api_key=SENTINELS[4],
        parcel_api_key=SENTINELS[5],
        database_enabled=False,
        action_yolo_fall_enabled=False,
    )
    return _client(settings, httpx.MockTransport(live_vision))


def smoke_missing_key_surfaces() -> None:
    client = _missing_key_client()
    checks = (
        ("health", client.get("/api/health")),
        ("providers/status", client.get("/api/providers/status")),
        ("perception/modalities", client.get("/api/perception/modalities")),
        ("action runtime status", client.get("/api/action-events/runtime/status")),
        ("runtime monitor status", client.get("/api/runtime/monitor/status")),
    )
    for label, response in checks:
        if response.status_code == 503 and "Database runtime is disabled." in response.text:
            _assert_no_secret_text(label, response.text)
            continue
        if response.status_code != 200:
            raise AssertionError(f"{label} returned HTTP {response.status_code}: {response.text}")
        _assert_no_secret_text(label, response.text)

    providers = {
        item["provider"]: item for item in checks[1][1].json()["providers"]
    }
    assert providers["afferens"]["state"] == "missing_key"
    assert providers["fireworks"]["state"] == "missing_key"
    assert providers["gemini"]["state"] == "deferred"
    assert providers["parcle"]["state"] == "deferred"

    runtime_response = checks[3][1]
    if runtime_response.status_code == 200:
        runtime = runtime_response.json()
        assert runtime["fall"]["available"] is False
        assert runtime["privacy"]["raw_frames_persisted"] is False
    else:
        assert runtime_response.status_code == 503


def smoke_configured_provider_redaction() -> None:
    client = _configured_provider_client()
    response = client.get("/api/providers/status")
    if response.status_code != 200:
        raise AssertionError(f"providers/status returned HTTP {response.status_code}: {response.text}")
    _assert_no_secret_text("configured providers/status", response.text)

    payload = response.json()
    providers = {item["provider"]: item for item in payload["providers"]}
    assert providers["afferens"]["state"] == "live"
    assert providers["fireworks"]["state"] == "configured"
    assert providers["gemini"]["state"] == "deferred"
    assert providers["parcle"]["state"] == "deferred"
    assert providers["semantic_memory"]["state"] == "vector_enabled"
    assert providers["semantic_memory"]["details"]["retrieval_mode"] == "hybrid"
    assert providers["semantic_memory"]["details"]["lexical_fallback_enabled"] is True
    assert providers["action_runtime"]["details"]["privacy"]["raw_frames_persisted"] is False

    serialized = _json_text(payload)
    for secret in SENTINELS:
        assert secret not in serialized


def main() -> int:
    smoke_missing_key_surfaces()
    smoke_configured_provider_redaction()
    print("OK   offline no-key/provider redaction smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
