from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.fireworks import FireworksReasoningAdapter
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import (
    get_app_settings,
    get_data_spine_service,
    get_fireworks_reasoning_adapter,
)
from app.schemas import DetectedObject, HumanPresence, Observation
from app.services import DataSpineService


def _observation(*, label: str = "tv", confidence: float = 0.56) -> Observation:
    return Observation(
        id="obs_test_1",
        raw_event_id="aff_test_1",
        provider_event_id="LIVE-VIS-1",
        timestamp_utc=datetime(2026, 6, 21, 16, 0, tzinfo=timezone.utc),
        source_node_id="NODE-01",
        modality="VISION",
        classification="iphone_camera_coco",
        confidence=0.9,
        room_id="desk",
        scene_summary="A TV-like display and a bottle appear on the desk.",
        human_presence=HumanPresence.UNKNOWN,
        objects=[
            DetectedObject(
                object_key=label,
                label=label,
                display_name=label,
                confidence=confidence,
                relative_location="on the back of the desk",
            ),
            DetectedObject(
                object_key="bottle",
                label="bottle",
                display_name="bottle",
                confidence=0.71,
                relative_location="near the display",
            ),
        ],
    )


def _client(
    *,
    repository: InMemoryDataRepository,
    settings: Settings | None = None,
    fireworks_transport: httpx.MockTransport | None = None,
) -> TestClient:
    app = create_app()
    settings = settings or Settings(
        environment="test",
        database_enabled=False,
        fireworks_api_key=None,
        langsmith_tracing=False,
        langsmith_api_key=None,
    )
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_data_spine_service] = lambda: DataSpineService(repository)
    app.dependency_overrides[get_fireworks_reasoning_adapter] = lambda: FireworksReasoningAdapter(
        settings,
        transport=fireworks_transport,
    )
    return TestClient(app)


def test_enrichment_latest_returns_skipped_without_observation() -> None:
    repository = InMemoryDataRepository()
    client = _client(repository=repository)

    response = client.post("/api/enrichment/latest", json={})
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is False
    assert payload["observation_id"] is None
    assert payload["provider_state"] == "skipped"
    assert payload["model_run"]["state"] == "skipped"
    assert payload["enrichment"] is None
    assert "Sync live perception first" in payload["message"]
    assert repository.enrichments == {}


def test_enrichment_latest_uses_deterministic_fallback_and_persists() -> None:
    repository = InMemoryDataRepository()
    repository.persist_observation(_observation())
    client = _client(repository=repository)

    response = client.post(
        "/api/enrichment/latest",
        json={"provider": "auto", "focus": "all", "persist": True},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["observation_id"] == "obs_test_1"
    assert payload["provider"] == "deterministic"
    assert payload["provider_state"] == "fallback"
    assert payload["model_run"]["provider"] == "deterministic"
    assert payload["model_run"]["state"] == "completed"
    assert payload["enrichment"]["source_provider"] == "deterministic"
    assert payload["enrichment"]["evidence_observation_ids"] == ["obs_test_1"]
    assert any(
        suggestion["suggested_label"] == "computer monitor or TV-like display"
        for suggestion in payload["enrichment"]["label_suggestions"]
    )
    assert any("may need checking" in note for note in payload["enrichment"]["safety_notes"])

    latest = client.get("/api/enrichment/latest").json()
    assert latest["enrichment"]["id"] == payload["enrichment"]["id"]
    assert list(repository.model_runs.values())[0].provider == "deterministic"


def test_enrichment_latest_reports_gemini_unavailable_without_fake_enrichment() -> None:
    repository = InMemoryDataRepository()
    repository.persist_observation(_observation(label="keys", confidence=0.82))
    client = _client(repository=repository)

    response = client.post("/api/enrichment/latest", json={"provider": "gemini"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is False
    assert payload["provider"] == "gemini"
    assert payload["provider_state"] == "unavailable"
    assert payload["model_run"]["state"] == "skipped"
    assert payload["enrichment"] is None
    assert repository.enrichments == {}
    assert list(repository.model_runs.values())[0].provider == "gemini"


def test_enrichment_latest_prefers_configured_fireworks_with_mocked_provider() -> None:
    repository = InMemoryDataRepository()
    repository.persist_observation(_observation())
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Fireworks suggests the TV-like label may be a monitor.",
                                    "label_suggestions": [
                                        {
                                            "object_key": "tv",
                                            "afferens_label": "tv",
                                            "suggested_label": "computer monitor",
                                            "confidence": 0.74,
                                            "reason": "The scene context indicates a desk display.",
                                        }
                                    ],
                                    "safety_notes": ["Human verification required for safety decisions."],
                                    "spatial_notes": ["The display appears on the back of the desk."],
                                }
                            )
                        }
                    }
                ]
            },
        )

    settings = Settings(
        environment="test",
        database_enabled=False,
        fireworks_base_url="https://fireworks.test/inference/v1",
        fireworks_api_key="fireworks-secret-key",
        fireworks_model="accounts/fireworks/models/test-vlm",
    )
    client = _client(
        repository=repository,
        settings=settings,
        fireworks_transport=httpx.MockTransport(handler),
    )

    response = client.post("/api/enrichment/latest", json={"provider": "auto"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["provider"] == "fireworks"
    assert payload["provider_state"] == "used"
    assert payload["model_run"]["model"] == "accounts/fireworks/models/test-vlm"
    assert payload["enrichment"]["label_suggestions"][0]["suggested_label"] == "computer monitor"
    assert captured_request is not None
    assert captured_request.url.path == "/inference/v1/chat/completions"
    assert "fireworks-secret-key" not in response.text
