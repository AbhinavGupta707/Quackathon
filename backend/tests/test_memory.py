from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.memory import ObjectMemoryService
from app.repositories import InMemoryDataRepository
from app.schemas import DetectedObject, HomeZone, LastSeenStatus, Observation, utc_now


def _observation(
    observation_id: str,
    timestamp: str,
    location: str,
    *,
    object_key: str = "keys",
    label: str = "keys",
    room_id: str = "default_home_zone",
    source_node_id: str | None = None,
    bbox: list[float] | None = None,
) -> Observation:
    return Observation(
        id=observation_id,
        raw_event_id=f"aff_{observation_id}",
        timestamp_utc=datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc),
        source_node_id=source_node_id,
        room_id=room_id,
        scene_summary=f"{label} is visible.",
        objects=[
            DetectedObject(
                object_key=object_key,
                label=label,
                display_name=label,
                confidence=0.8,
                relative_location=location,
                bbox=bbox,
            )
        ],
    )


def test_memory_updates_last_seen_with_evidence_observation_ids() -> None:
    repository = InMemoryDataRepository()
    service = ObjectMemoryService(repository)

    updated = service.update_from_observation(
        _observation("obs_new", "2026-06-21T16:02:00", "beside the blue bottle")
    )

    assert len(updated) == 1
    assert updated[0].object_key == "keys"
    assert updated[0].last_seen_relative_location == "beside the blue bottle"
    assert updated[0].last_seen_observation_id == "obs_new"
    assert updated[0].evidence_observation_ids == ["obs_new"]
    assert updated[0].status == LastSeenStatus.VISIBLE_NOW


def test_memory_does_not_overwrite_newer_evidence_with_older_observation() -> None:
    repository = InMemoryDataRepository()
    service = ObjectMemoryService(repository)

    service.update_from_observation(_observation("obs_new", "2026-06-21T16:02:00", "table"))
    older_update = service.update_from_observation(
        _observation("obs_old", "2026-06-21T16:01:00", "floor")
    )

    assert older_update == []
    assert repository.last_seen["keys"].last_seen_observation_id == "obs_new"
    assert repository.last_seen["keys"].last_seen_relative_location == "table"


def test_empty_observation_does_not_update_memory() -> None:
    repository = InMemoryDataRepository()
    service = ObjectMemoryService(repository)
    observation = Observation(
        id="obs_empty",
        raw_event_id="aff_empty",
        timestamp_utc=datetime(2026, 6, 21, 16, 0, tzinfo=timezone.utc),
        scene_summary="Live Afferens event did not include object labels.",
        objects=[],
    )

    assert service.update_from_observation(observation) == []
    assert repository.list_last_seen_objects() == []


def test_new_observation_downgrades_absent_visible_now_objects() -> None:
    repository = InMemoryDataRepository()
    service = ObjectMemoryService(repository)
    now = datetime.now(timezone.utc)

    keys_observation = _observation("obs_keys", now.isoformat(), "table")
    bottle_observation = _observation(
        "obs_bottle",
        (now + timedelta(seconds=1)).isoformat(),
        "counter",
        object_key="bottle",
        label="bottle",
    )
    repository.persist_observation(keys_observation)
    service.update_from_observation(keys_observation)
    repository.persist_observation(bottle_observation)
    updates = service.update_from_observation(bottle_observation)

    updated_by_key = {item.object_key: item for item in updates}
    assert updated_by_key["bottle"].status == LastSeenStatus.VISIBLE_NOW
    assert updated_by_key["keys"].status == LastSeenStatus.VISIBLE_RECENTLY

    memories = {item.object_key: item for item in repository.list_last_seen_objects()}
    assert memories["bottle"].status == LastSeenStatus.VISIBLE_NOW
    assert memories["keys"].status == LastSeenStatus.VISIBLE_RECENTLY


def test_last_seen_listing_decays_stale_visible_now_without_new_observation() -> None:
    repository = InMemoryDataRepository()
    service = ObjectMemoryService(repository, recent_window_seconds=60)
    old_seen_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    observation = Observation(
        id="obs_old",
        raw_event_id="aff_old",
        timestamp_utc=old_seen_at,
        scene_summary="keys is visible.",
        objects=[
            DetectedObject(
                object_key="keys",
                label="keys",
                display_name="keys",
                confidence=0.8,
                relative_location="table",
            )
        ],
    )

    service.update_from_observation(observation)

    memories = repository.list_last_seen_objects(recent_window_seconds=60)
    assert memories[0].status == LastSeenStatus.NOT_SEEN_RECENTLY


def test_older_observation_does_not_downgrade_newer_visible_now_memory() -> None:
    repository = InMemoryDataRepository()
    service = ObjectMemoryService(repository)
    now = datetime.now(timezone.utc)
    newer = _observation(
        "obs_newer",
        now.isoformat(),
        "counter",
        object_key="bottle",
        label="bottle",
    )
    older = _observation("obs_older", (now - timedelta(seconds=30)).isoformat(), "table")

    repository.persist_observation(newer)
    service.update_from_observation(newer)
    repository.persist_observation(older)
    service.update_from_observation(older)

    memories = {item.object_key: item for item in repository.list_last_seen_objects()}
    assert memories["bottle"].status == LastSeenStatus.VISIBLE_NOW
    assert memories["keys"].status == LastSeenStatus.VISIBLE_RECENTLY


def test_visible_now_requires_object_in_latest_current_observation() -> None:
    repository = InMemoryDataRepository()
    service = ObjectMemoryService(repository)
    now = datetime.now(timezone.utc)

    keys = _observation("obs_keys", now.isoformat(), "study desk")
    empty_current = Observation(
        id="obs_empty_current",
        raw_event_id="aff_empty_current",
        timestamp_utc=now + timedelta(seconds=2),
        scene_summary="Live Afferens event did not include object labels.",
        objects=[],
    )

    repository.persist_observation(keys)
    service.update_from_observation(keys)
    repository.persist_observation(empty_current)
    updates = service.update_from_observation(empty_current)

    assert {item.object_key: item.status for item in updates} == {
        "keys": LastSeenStatus.VISIBLE_RECENTLY
    }
    assert repository.list_last_seen_objects()[0].status == LastSeenStatus.VISIBLE_RECENTLY


def test_region_calibration_assigns_human_room_and_quadrant_label() -> None:
    repository = InMemoryDataRepository()
    service = ObjectMemoryService(repository)
    zone = repository.create_home_zone(
        HomeZone(
            id="study_zone",
            name="Study desk",
            room_type="study",
            aliases=["desk"],
            region_strategy="quadrants",
            created_at=utc_now(),
        )
    )
    assert [region.label for region in zone.regions] == [
        "top left area",
        "top right area",
        "bottom left area",
        "bottom right area",
    ]

    observation = _observation(
        "obs_region",
        datetime.now(timezone.utc).isoformat(),
        "",
        object_key="glasses",
        label="glasses",
        room_id="study_zone",
        bbox=[0.6, 0.1, 0.8, 0.4],
    )
    repository.persist_observation(observation)
    updated = service.update_from_observation(observation)

    memory = updated[0]
    assert memory.last_seen_room == "Study desk"
    assert memory.last_seen_room_id == "study_zone"
    assert memory.last_seen_region_id == "top_right"
    assert memory.last_seen_region_label == "top right area"
    assert memory.last_seen_relative_location == "top right area"
    assert memory.last_seen_normalized_coords == {"x": 0.7, "y": 0.25}
    assert memory.location_assignment_source == "calibrated_region"


def test_source_node_profile_assigns_room_without_using_indoor_gps() -> None:
    repository = InMemoryDataRepository()
    service = ObjectMemoryService(repository)
    repository.create_home_zone(
        HomeZone(
            id="kitchen_node_zone",
            name="Kitchen counter",
            room_type="kitchen",
            source_node_id="LAPTOP-CAM-1",
            created_at=utc_now(),
        )
    )
    observation = _observation(
        "obs_node",
        datetime.now(timezone.utc).isoformat(),
        "beside the kettle",
        object_key="mug",
        label="mug",
        source_node_id="LAPTOP-CAM-1",
    )
    observation = observation.model_copy(
        update={"evidence_metadata": {"gps": {"lat": 51.5, "lon": -0.1}}}
    )
    repository.persist_observation(observation)
    updated = service.update_from_observation(observation)

    memory = updated[0]
    assert memory.last_seen_room == "Kitchen counter"
    assert memory.last_seen_room_id == "kitchen_node_zone"
    assert memory.last_seen_region_label is None
    assert memory.location_assignment_source == "node_profile"
