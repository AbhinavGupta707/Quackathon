from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.providers.fireworks import FireworksReasoningAdapter
from app.routes.dependencies import (
    get_app_settings,
    get_data_spine_service,
    get_fireworks_reasoning_adapter,
)
from app.schemas import (
    ActionEvent,
    ActionEventType,
    Alert,
    AlertSeverity,
    CareNote,
    CareNoteAudience,
    DetectedObject,
    FamilyMessage,
    FamilyMessageStatus,
    HomeZone,
    HydrationEvent,
    HydrationEventType,
    Observation,
    QueryConfidence,
    Task,
    TaskState,
    TaskType,
    WellnessCheck,
    WellnessCheckStatus,
    WellnessCheckType,
    utc_now,
)
from app.services import DataSpineService


def _client() -> tuple[TestClient, InMemoryDataRepository, DataSpineService]:
    app = create_app()
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    settings = Settings(environment="test", fireworks_api_key=None, database_enabled=False)
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_data_spine_service] = lambda: service
    app.dependency_overrides[get_fireworks_reasoning_adapter] = lambda: FireworksReasoningAdapter(
        settings
    )
    return TestClient(app), repository, service


def _observation() -> Observation:
    observed_at = utc_now()
    return Observation(
        id="obs_c5_bottle",
        raw_event_id="aff_c5_bottle",
        provider_event_id="LIVE-C5-BOTTLE",
        timestamp_utc=observed_at,
        room_id="kitchen_zone",
        scene_summary="A bottle and keys are visible on the table.",
        objects=[
            DetectedObject(
                object_key="bottle",
                label="bottle",
                display_name="water bottle",
                confidence=0.86,
                relative_location="on the table",
            ),
            DetectedObject(
                object_key="keys",
                label="keys",
                display_name="keys",
                confidence=0.72,
                relative_location="beside the bottle",
            ),
        ],
    )


def test_activity_timeline_derives_events_from_existing_evidence() -> None:
    client, repository, service = _client()
    observation = repository.persist_observation(_observation())
    service.create_home_zone(
        HomeZone(
            id="kitchen_zone",
            name="Kitchen table",
            room_type="kitchen",
            aliases=["kitchen"],
            is_default=False,
        )
    )
    task = service.create_task(
        Task(
            id="task_c5_keys",
            type=TaskType.OBJECT_RECOVERY,
            state=TaskState.OPEN,
            title="Find keys",
            body="Keys may need checking.",
            recommended_action="Check the kitchen table.",
            evidence_observation_ids=[observation.id],
            metadata={"room_id": "kitchen_zone"},
            created_at=observation.timestamp_utc,
            updated_at=observation.timestamp_utc,
        )
    )
    repository.create_alert(
        Alert(
            id="alert_c5",
            task_id=task.id,
            hazard_type="medicine_left_out",
            severity=AlertSeverity.MEDIUM,
            title="Possible medicine left out",
            body="Medicine appears visible.",
            recommended_action="Please verify in person.",
            evidence_observation_ids=[observation.id],
            created_at=observation.timestamp_utc,
        )
    )

    response = client.get(f"/api/activity/timeline?date={observation.timestamp_utc.date()}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["date"] == observation.timestamp_utc.date().isoformat()
    event_types = {event["type"] for event in payload["events"]}
    assert {"object_seen", "task_opened", "safety_alert"}.issubset(event_types)
    object_event = next(event for event in payload["events"] if event["type"] == "object_seen")
    assert object_event["zone_name"] == "Kitchen table"
    assert object_event["evidence_ids"] == [observation.id]


def test_activity_timeline_includes_c13_sources_with_conservative_labels() -> None:
    client, repository, service = _client()
    observation = repository.persist_observation(_observation())
    service.create_home_zone(
        HomeZone(
            id="kitchen_zone",
            name="Kitchen table",
            room_type="kitchen",
            aliases=["kitchen"],
            is_default=False,
        )
    )
    repository.create_hydration_event(
        HydrationEvent(
            id="hyd_c13_water",
            type=HydrationEventType.WATER_VISIBLE,
            occurred_at=observation.timestamp_utc + timedelta(minutes=1),
            confidence=QueryConfidence.LOW,
            zone_id="kitchen_zone",
            evidence_ids=[observation.id],
            metadata={"source": "afferens_observation", "object_keys": ["bottle"]},
        )
    )
    repository.create_action_event(
        ActionEvent(
            id="act_c13_drink",
            type=ActionEventType.DRINK_CANDIDATE,
            occurred_at=observation.timestamp_utc + timedelta(minutes=2),
            confidence=QueryConfidence.MEDIUM,
            source="browser_mediapipe",
            zone_id="kitchen_zone",
            evidence_ids=[observation.id],
            metadata={"temporal_window_seconds": 4.0},
        )
    )
    repository.create_wellness_check(
        WellnessCheck(
            id="well_c13_fall",
            type=WellnessCheckType.POSSIBLE_FALL_CHECK,
            severity=AlertSeverity.MEDIUM,
            status=WellnessCheckStatus.OPEN,
            title="Possible fall check",
            body="A possible fall candidate persisted in action telemetry.",
            confidence=QueryConfidence.MEDIUM,
            occurred_at=observation.timestamp_utc + timedelta(minutes=3),
            zone_id="kitchen_zone",
            evidence_ids=[observation.id],
            metadata={"source": "action_event", "action_event_id": "act_fall"},
        )
    )
    repository.create_family_message(
        FamilyMessage(
            id="fam_c13",
            title="Lunch reminder",
            body="Your lunch is in the kitchen.",
            starts_at=observation.timestamp_utc + timedelta(minutes=4),
            created_at=observation.timestamp_utc,
        )
    )
    repository.create_care_note(
        CareNote(
            id="care_c13",
            date=observation.timestamp_utc.date(),
            audience=CareNoteAudience.FAMILY,
            summary="Conservative note from cited activity.",
            evidence_ids=[observation.id],
            created_at=observation.timestamp_utc + timedelta(minutes=5),
        )
    )

    response = client.get(f"/api/activity/timeline?date={observation.timestamp_utc.date()}")
    events = response.json()["events"]

    assert response.status_code == 200
    sources = {event["source"] for event in events}
    assert {
        "afferens_observation",
        "hydration_event",
        "action_event",
        "wellness_check",
        "family_message",
        "care_note",
    }.issubset(sources)
    by_source = {event["source"]: event for event in events}
    assert by_source["hydration_event"]["title"] == "Water nearby"
    assert by_source["hydration_event"]["evidence_ids"] == [observation.id]
    assert by_source["hydration_event"]["metadata"]["conservative_labels"] == ["water_nearby"]
    assert by_source["action_event"]["title"] == "Possible drink action"
    assert by_source["action_event"]["metadata"]["source_ids"] == ["act_c13_drink"]
    assert by_source["wellness_check"]["title"] == "Possible fall check"
    assert by_source["wellness_check"]["metadata"]["conservative_labels"] == ["possible_fall_check"]
    assert by_source["care_note"]["metadata"]["source_ids"] == ["care_c13"]
    timeline_text = response.text.lower()
    assert "diagnosis" in timeline_text
    assert "fall detected" not in timeline_text
    assert "drank water" not in timeline_text


def test_diary_generate_persists_evidence_linked_conservative_summary() -> None:
    client, repository, _service = _client()
    observation = repository.persist_observation(_observation())

    response = client.post(
        "/api/diary/generate",
        json={"date": observation.timestamp_utc.date().isoformat()},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["diary"]["date"] == observation.timestamp_utc.date().isoformat()
    assert payload["diary"]["source"] == "deterministic"
    assert payload["diary"]["evidence_ids"] == [observation.id]
    assert "evidence-backed" in payload["diary"]["summary"]
    assert "diagnosis" not in payload["diary"]["summary"].lower()
    assert "emergency" not in payload["diary"]["summary"].lower()

    get_response = client.get(f"/api/diary?date={observation.timestamp_utc.date()}")
    assert get_response.status_code == 200
    assert get_response.json()["diary"]["id"] == payload["diary"]["id"]


def test_diary_generate_summarizes_action_and_wellness_timeline_safely() -> None:
    client, repository, _service = _client()
    observation = repository.persist_observation(_observation())
    repository.create_action_event(
        ActionEvent(
            id="act_diary_drink",
            type=ActionEventType.DRINK_CANDIDATE,
            occurred_at=observation.timestamp_utc + timedelta(minutes=1),
            confidence=QueryConfidence.MEDIUM,
            source="browser_mediapipe",
            evidence_ids=[observation.id],
        )
    )
    repository.create_wellness_check(
        WellnessCheck(
            id="well_diary",
            type=WellnessCheckType.HYDRATION_PROMPT,
            severity=AlertSeverity.LOW,
            status=WellnessCheckStatus.OPEN,
            title="Hydration check",
            body="Only limited water-nearby evidence has appeared today.",
            confidence=QueryConfidence.LOW,
            occurred_at=observation.timestamp_utc + timedelta(minutes=2),
            evidence_ids=[observation.id],
        )
    )

    response = client.post(
        "/api/diary/generate",
        json={"date": observation.timestamp_utc.date().isoformat()},
    )
    diary = response.json()["diary"]

    assert response.status_code == 200
    assert diary["source"] == "deterministic"
    assert diary["evidence_ids"] == [observation.id]
    assert any("possible drink action" in item.lower() for item in diary["highlights"])
    assert any("wellness check" in item.lower() for item in diary["highlights"])
    assert any("open wellness check" in item.lower() for item in diary["needs_review"])
    combined = " ".join([diary["summary"], *diary["highlights"], *diary["needs_review"]]).lower()
    assert "diagnosis" not in combined
    assert "emergency" not in combined
    assert "drank water" not in combined


def test_care_note_generate_records_low_burden_follow_ups() -> None:
    client, repository, _service = _client()
    observation = repository.persist_observation(_observation())
    repository.create_alert(
        Alert(
            id="alert_care",
            hazard_type="medicine_left_out",
            severity=AlertSeverity.MEDIUM,
            title="Possible medicine left out",
            body="Medicine appears visible.",
            recommended_action="Please verify in person.",
            evidence_observation_ids=[observation.id],
            created_at=observation.timestamp_utc,
        )
    )

    response = client.post(
        "/api/care-notes/generate",
        json={"date": observation.timestamp_utc.date().isoformat(), "audience": "care_home"},
    )
    note = response.json()["note"]

    assert response.status_code == 200
    assert note["audience"] == "care_home"
    assert note["evidence_ids"] == [observation.id]
    assert note["risks"]
    assert any("verify" in item.lower() for item in note["follow_ups"])

    notes_response = client.get(f"/api/care-notes?date={observation.timestamp_utc.date()}")
    assert notes_response.status_code == 200
    assert notes_response.json()["notes"][0]["id"] == note["id"]


def test_diary_and_care_note_generation_use_fireworks_when_available() -> None:
    class MockFireworks:
        async def synthesize_daily_diary(self, **kwargs):
            assert kwargs["events"][0]["evidence_ids"] == ["obs_c5_bottle"]
            return type(
                "DiaryResult",
                (),
                {
                    "summary": "Fireworks summarized cited home-memory activity.",
                    "highlights": ["Objects appeared in cited evidence."],
                    "needs_review": ["Please verify important details in person."],
                },
            )()

        async def synthesize_care_note(self, **kwargs):
            assert kwargs["audience"] == CareNoteAudience.CARE_HOME.value
            return type(
                "CareResult",
                (),
                {
                    "summary": "Fireworks drafted a conservative care note.",
                    "bullets": ["Objects appeared in cited evidence."],
                    "risks": [],
                    "follow_ups": ["Continue ordinary check-ins."],
                },
            )()

    app = create_app()
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    observation = repository.persist_observation(_observation())
    settings = Settings(environment="test", fireworks_api_key="mock-key", database_enabled=False)
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_data_spine_service] = lambda: service
    app.dependency_overrides[get_fireworks_reasoning_adapter] = lambda: MockFireworks()
    client = TestClient(app)

    diary_response = client.post(
        "/api/diary/generate",
        json={"date": observation.timestamp_utc.date().isoformat()},
    )
    care_response = client.post(
        "/api/care-notes/generate",
        json={"date": observation.timestamp_utc.date().isoformat(), "audience": "care_home"},
    )

    assert diary_response.status_code == 200
    assert diary_response.json()["diary"]["source"] == "fireworks"
    assert diary_response.json()["diary"]["evidence_ids"] == [observation.id]
    assert "Fireworks summarized" in diary_response.json()["diary"]["summary"]
    assert care_response.status_code == 200
    assert care_response.json()["note"]["source"] == "fireworks"
    assert care_response.json()["note"]["evidence_ids"] == [observation.id]
    assert "mock-key" not in diary_response.text
    assert "mock-key" not in care_response.text


def test_family_messages_filter_active_and_acknowledge() -> None:
    client, repository, _service = _client()
    now = utc_now()
    repository.create_family_message(
        FamilyMessage(
            id="fam_future",
            title="Later",
            body="This is for later.",
            status=FamilyMessageStatus.SCHEDULED,
            starts_at=now + timedelta(hours=1),
            created_at=now,
        )
    )
    repository.create_family_message(
        FamilyMessage(
            id="fam_expired",
            title="Expired",
            body="This has expired.",
            expires_at=now - timedelta(minutes=1),
            created_at=now,
        )
    )

    create_response = client.post(
        "/api/family-messages",
        json={
            "title": "Drink water",
            "body": "Your water bottle is usually by the chair.",
            "priority": "high",
            "trigger_object_key": "bottle",
            "trigger_zone_id": "living_room",
        },
    )
    message = create_response.json()["message"]

    assert create_response.status_code == 200
    assert message["id"].startswith("fammsg_")
    assert message["status"] == "active"

    active_response = client.get("/api/family-messages/active")
    active_ids = [item["id"] for item in active_response.json()["messages"]]
    assert message["id"] in active_ids
    assert "fam_future" not in active_ids
    assert "fam_expired" not in active_ids

    ack_response = client.post(f"/api/family-messages/{message['id']}/ack")
    assert ack_response.status_code == 200
    assert ack_response.json()["message"]["status"] == "acknowledged"

    active_after_ack = client.get("/api/family-messages/active").json()["messages"]
    assert message["id"] not in [item["id"] for item in active_after_ack]

    hidden_response = client.get("/api/family-messages")
    assert message["id"] not in [item["id"] for item in hidden_response.json()["messages"]]

    visible_response = client.get("/api/family-messages?include_acknowledged=true")
    assert message["id"] in [item["id"] for item in visible_response.json()["messages"]]


def test_family_message_accepts_browser_datetime_local_values() -> None:
    client, _repository, _service = _client()
    now = utc_now()

    response = client.post(
        "/api/family-messages",
        json={
            "title": "Water nearby",
            "body": "Your water bottle is on the side table.",
            "starts_at": (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M"),
            "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        },
    )

    assert response.status_code == 200
    message = response.json()["message"]
    assert message["status"] == "active"

    active_response = client.get("/api/family-messages/active")
    assert active_response.status_code == 200
    assert message["id"] in [item["id"] for item in active_response.json()["messages"]]
