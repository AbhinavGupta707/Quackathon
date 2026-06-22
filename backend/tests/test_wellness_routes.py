from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_data_spine_service
from app.schemas import DetectedObject, HomeZone, HumanPresence, Observation
from app.services import DataSpineService


def _client() -> tuple[TestClient, InMemoryDataRepository, DataSpineService]:
    app = create_app()
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    app.dependency_overrides[get_data_spine_service] = lambda: service
    return TestClient(app), repository, service


def _observation(
    observation_id: str,
    *,
    timestamp: datetime,
    objects: list[DetectedObject],
    room_id: str = "kitchen_zone",
    human_presence: HumanPresence = HumanPresence.UNKNOWN,
    risk_signals: list[str] | None = None,
) -> Observation:
    return Observation(
        id=observation_id,
        raw_event_id=f"aff_{observation_id}",
        provider_event_id=f"LIVE-{observation_id}",
        timestamp_utc=timestamp,
        room_id=room_id,
        scene_summary="Live Afferens evidence is available.",
        human_presence=human_presence,
        objects=objects,
        risk_signals=risk_signals or [],
    )


def test_hydration_summary_shows_water_visible_context_without_counting_intake() -> None:
    client, repository, service = _client()
    observed_at = datetime(2026, 6, 21, 9, 15, tzinfo=timezone.utc)
    service.create_home_zone(
        HomeZone(
            id="kitchen_zone",
            name="Kitchen table",
            room_type="kitchen",
            aliases=["kitchen"],
        )
    )
    repository.persist_observation(
        _observation(
            "obs_water",
            timestamp=observed_at,
            objects=[
                DetectedObject(
                    object_key="water_bottle",
                    label="water bottle",
                    display_name="water bottle",
                    confidence=0.88,
                ),
                DetectedObject(
                    object_key="keys",
                    label="keys",
                    display_name="keys",
                    confidence=0.7,
                ),
            ],
        )
    )

    response = client.get("/api/hydration/summary?date=2026-06-21")
    payload = response.json()

    assert response.status_code == 200
    assert payload["date"] == "2026-06-21"
    summary = payload["summary"]
    assert summary["water_events"] == 0
    assert summary["status"] == "consider_prompting"
    assert summary["evidence_ids"] == ["obs_water"]
    assert summary["events"][0]["id"] == "hyd_obs_obs_water"
    assert summary["events"][0]["type"] == "water_visible"
    assert summary["events"][0]["zone_name"] == "Kitchen table"
    assert summary["events"][0]["metadata"]["candidate_only"] is True
    assert "object visibility alone does not count as hydration" in summary["message"].lower()


def test_hydration_event_create_persists_manual_candidate_without_claiming_certainty() -> None:
    client, _repository, _service = _client()

    response = client.post(
        "/api/hydration/events",
        json={
            "type": "drink_candidate",
            "occurred_at": "2026-06-21T10:00:00Z",
            "confidence": "medium",
            "zone_id": "living_room",
            "evidence_ids": ["obs_drink"],
            "metadata": {"source": "caregiver_report", "note": "Possible sip seen."},
        },
    )
    event = response.json()["event"]

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert event["id"].startswith("hyd_")
    assert event["type"] == "drink_candidate"
    assert event["confidence"] == "medium"
    assert event["evidence_ids"] == ["obs_drink"]
    assert event["metadata"]["human_verification_required"] is True

    summary = client.get("/api/hydration/summary?date=2026-06-21").json()["summary"]
    assert summary["water_events"] == 1
    assert summary["events"][0]["type"] == "drink_candidate"


def test_wellness_generate_creates_hydration_prompt_and_ack_is_idempotent() -> None:
    client, repository, _service = _client()
    observed_at = datetime(2026, 6, 21, 11, 0, tzinfo=timezone.utc)
    repository.persist_observation(
        _observation(
            "obs_keys_only",
            timestamp=observed_at,
            objects=[
                DetectedObject(
                    object_key="keys",
                    label="keys",
                    display_name="keys",
                    confidence=0.7,
                )
            ],
        )
    )

    first_response = client.post("/api/wellness/checks/generate", json={"date": "2026-06-21"})
    checks = first_response.json()["checks"]

    assert first_response.status_code == 200
    hydration_checks = [item for item in checks if item["type"] == "hydration_prompt"]
    assert len(hydration_checks) == 1
    assert hydration_checks[0]["severity"] == "medium"
    assert "visibility alone is context only" in hydration_checks[0]["body"].lower()
    assert "emergency" not in hydration_checks[0]["body"].lower()

    notifications = client.get("/api/alerts/notifications?date=2026-06-21").json()[
        "notifications"
    ]
    hydration_notifications = [
        item for item in notifications if item["type"] == "hydration_prompt"
    ]
    assert len(hydration_notifications) == 1
    assert hydration_notifications[0]["wellness_check_id"] == hydration_checks[0]["id"]
    assert hydration_notifications[0]["requires_live_verification"] is False
    assert "does not count as intake" in hydration_notifications[0]["body"].lower()

    second_response = client.post("/api/wellness/checks/generate", json={"date": "2026-06-21"})
    second_hydration = [
        item for item in second_response.json()["checks"] if item["type"] == "hydration_prompt"
    ]
    assert [item["id"] for item in second_hydration] == [hydration_checks[0]["id"]]

    ack_response = client.post(
        f"/api/wellness/checks/{hydration_checks[0]['id']}/ack",
        json={"acknowledged_by": "family", "note": "Called to check in."},
    )
    acked = ack_response.json()["check"]
    assert ack_response.status_code == 200
    assert acked["status"] == "acknowledged"
    assert acked["acknowledged_at"] is not None
    assert acked["evidence_ids"] == hydration_checks[0]["evidence_ids"]

    ack_again = client.post(
        f"/api/wellness/checks/{hydration_checks[0]['id']}/ack",
        json={"acknowledged_by": "caregiver", "note": "Second click."},
    )
    assert ack_again.status_code == 200
    assert ack_again.json()["check"]["acknowledged_at"] == acked["acknowledged_at"]


def test_wellness_generate_does_not_create_fall_check_from_observation_risk_words() -> None:
    client, repository, _service = _client()
    observed_at = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    repository.persist_observation(
        _observation(
            "obs_person",
            timestamp=observed_at,
            human_presence=HumanPresence.VISIBLE,
            objects=[
                DetectedObject(
                    object_key="person",
                    label="person",
                    display_name="person",
                    confidence=0.84,
                )
            ],
        )
    )

    ordinary_response = client.post("/api/wellness/checks/generate", json={"date": "2026-06-21"})
    ordinary_types = {item["type"] for item in ordinary_response.json()["checks"]}
    assert "possible_fall_check" not in ordinary_types
    assert "unusual_stillness_check" not in ordinary_types

    repository.persist_observation(
        _observation(
            "obs_possible_fall",
            timestamp=datetime(2026, 6, 21, 12, 5, tzinfo=timezone.utc),
            objects=[],
            risk_signals=["possible_fall_signal_human_verification_required"],
        )
    )

    fall_response = client.post("/api/wellness/checks/generate", json={"date": "2026-06-21"})
    fall_checks = [
        item for item in fall_response.json()["checks"] if item["type"] == "possible_fall_check"
    ]

    assert fall_response.status_code == 200
    assert fall_checks == []

    repository.persist_observation(
        _observation(
            "obs_possible_stillness",
            timestamp=datetime(2026, 6, 21, 12, 10, tzinfo=timezone.utc),
            objects=[],
            risk_signals=["possible_unusual_stillness_human_verification_required"],
        )
    )

    stillness_response = client.post("/api/wellness/checks/generate", json={"date": "2026-06-21"})
    stillness_checks = [
        item
        for item in stillness_response.json()["checks"]
        if item["type"] == "unusual_stillness_check"
    ]

    assert len(stillness_checks) == 1
    assert stillness_checks[0]["severity"] == "medium"
    assert stillness_checks[0]["confidence"] == "medium"
    assert stillness_checks[0]["evidence_ids"] == ["obs_possible_stillness"]
    assert "human verification is required" in stillness_checks[0]["body"].lower()
