from __future__ import annotations

from datetime import datetime, timezone

from app.memory import ObjectMemoryService
from app.repositories import InMemoryDataRepository
from app.schemas import DetectedObject, LastSeenStatus, Observation


def _observation(observation_id: str, timestamp: str, location: str) -> Observation:
    return Observation(
        id=observation_id,
        raw_event_id=f"aff_{observation_id}",
        timestamp_utc=datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc),
        scene_summary="keys is visible.",
        objects=[
            DetectedObject(
                object_key="keys",
                label="keys",
                display_name="keys",
                confidence=0.8,
                relative_location=location,
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
