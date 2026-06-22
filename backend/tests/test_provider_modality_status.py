from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.afferens_adapter import AfferensAdapter, DOCUMENTED_AFFERENS_MODALITIES
from app.config import Settings
from app.main import create_app
from app.routes.dependencies import get_afferens_adapter, get_app_settings


def _client(
    settings: Settings,
    transport: httpx.MockTransport,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_afferens_adapter] = lambda: AfferensAdapter(
        settings,
        transport=transport,
    )
    return TestClient(app)


def test_perception_modalities_missing_key_does_not_probe_live_api() -> None:
    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Missing-key modality status must not call Afferens")

    client = _client(
        Settings(environment="test", afferens_api_key=None, database_enabled=False),
        httpx.MockTransport(fail_if_called),
    )

    response = client.get("/api/perception/modalities")
    payload = response.json()

    assert response.status_code == 200
    assert [item["modality"] for item in payload["modalities"]] == [
        modality.value for modality in DOCUMENTED_AFFERENS_MODALITIES
    ]
    assert {item["state"] for item in payload["modalities"]} == {"unavailable"}
    assert "api_key" not in response.text


def test_perception_modalities_reports_live_vision_and_no_events_for_others() -> None:
    requested_modalities: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        modality = request.url.params["modality"]
        requested_modalities.append(modality)
        if modality == "vision":
            return httpx.Response(
                200,
                json={
                    "events": [
                        {
                            "event_id": "LIVE-VIS-C9",
                            "timestamp_utc": "2026-06-22T10:00:00Z",
                            "source_node_id": "LAPTOP-WEBCAM-01",
                            "modality": "VISION",
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"events": []})

    client = _client(
        Settings(
            environment="test",
            afferens_base_url="https://afferens.test",
            afferens_api_key="test-api-key",
            database_enabled=False,
        ),
        httpx.MockTransport(handler),
    )

    response = client.get("/api/perception/modalities")
    payload = response.json()
    statuses = {item["modality"]: item for item in payload["modalities"]}

    assert response.status_code == 200
    assert requested_modalities == [
        modality.value.lower() for modality in DOCUMENTED_AFFERENS_MODALITIES
    ]
    assert statuses["VISION"]["state"] == "available"
    assert statuses["VISION"]["latest_event_id"] == "LIVE-VIS-C9"
    assert statuses["VISION"]["source_node_id"] == "LAPTOP-WEBCAM-01"
    assert statuses["ACOUSTIC"]["state"] == "no_live_events"
    assert statuses["SPATIAL"]["state"] == "no_live_events"
    assert "test-api-key" not in response.text


def test_providers_status_is_redacted_and_reports_configured_live_afferens() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "events": [
                    {
                        "event_id": "LIVE-VIS-PROVIDER",
                        "timestamp_utc": "2026-06-22T10:00:00Z",
                        "source_node_id": "PHONE-01",
                        "modality": "VISION",
                    }
                ]
            },
        )

    client = _client(
        Settings(
            environment="test",
            afferens_base_url="https://afferens.test",
            afferens_api_key="secret-afferens-key",
            fireworks_api_key="secret-fireworks-key",
            fireworks_model="accounts/fireworks/models/test-model",
            langsmith_tracing=True,
            langsmith_api_key="secret-langsmith-key",
            gemini_api_key="secret-gemini-key",
            parcle_api_key="secret-parcle-key",
            database_enabled=False,
            action_yolo_fall_enabled=False,
            action_yolo_fall_model_path=None,
        ),
        httpx.MockTransport(handler),
    )

    response = client.get("/api/providers/status")
    payload = response.json()
    providers = {item["provider"]: item for item in payload["providers"]}

    assert response.status_code == 200
    assert payload["ok"] is True
    assert providers["afferens"]["state"] == "live"
    assert providers["afferens"]["details"]["base_url"] == "https://afferens.test"
    assert providers["fireworks"]["state"] == "configured"
    assert providers["fireworks"]["details"]["model"] == "accounts/fireworks/models/test-model"
    assert providers["semantic_memory"]["state"] == "vector_enabled"
    assert providers["semantic_memory"]["details"]["embedding_provider"] == "deterministic_local"
    assert providers["semantic_memory"]["details"]["vector_retrieval_enabled"] is True
    assert providers["semantic_memory"]["details"]["lexical_fallback_enabled"] is True
    assert providers["action_runtime"]["state"] == "degraded"
    actuation = providers["action_runtime"]["details"]["afferens_actuation"]
    assert actuation["state"] == "disabled"
    assert actuation["safe_commands"] == ["CAPTURE_FRAME", "TRIGGER_ALARM"]
    assert actuation["requires_live_evidence_linkage"] is True
    assert actuation["resolution_requires"] == "live_verification_or_human_ack"

    for secret in (
        "secret-afferens-key",
        "secret-fireworks-key",
        "secret-langsmith-key",
        "secret-gemini-key",
        "secret-parcle-key",
    ):
        assert secret not in response.text


def test_provider_status_legacy_alias_matches_canonical_route() -> None:
    client = _client(
        Settings(
            environment="test",
            afferens_api_key=None,
            fireworks_api_key=None,
            database_enabled=False,
        ),
        httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(
                AssertionError("Missing Afferens key should not call Afferens")
            )
        ),
    )

    canonical = client.get("/api/providers/status")
    alias = client.get("/api/provider-status")

    assert canonical.status_code == 200
    assert alias.status_code == 200
    assert alias.json() == canonical.json()


def test_providers_status_reports_deferred_optional_providers_honestly() -> None:
    client = _client(
        Settings(
            environment="test",
            afferens_api_key=None,
            fireworks_api_key=None,
            gemini_api_key="configured-but-deferred",
            parcel_api_key="configured-but-unimplemented",
            database_enabled=False,
        ),
        httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(
                AssertionError("Missing Afferens key should not call Afferens")
            )
        ),
    )

    response = client.get("/api/providers/status")
    providers = {item["provider"]: item for item in response.json()["providers"]}

    assert response.status_code == 200
    assert providers["afferens"]["state"] == "missing_key"
    assert providers["fireworks"]["state"] == "missing_key"
    assert providers["gemini"]["state"] == "deferred"
    assert providers["gemini"]["details"]["key_configured"] is True
    assert providers["parcle"]["state"] == "deferred"
    assert providers["parcle"]["details"]["aliases"] == ["parcel"]
    assert providers["parcle"]["details"]["key_configured"] is True
    assert providers["action_runtime"]["details"]["afferens_actuation"]["state"] == "disabled"
    assert "configured-but-deferred" not in response.text
    assert "configured-but-unimplemented" not in response.text
