from __future__ import annotations

from app.repositories import InMemoryDataRepository
from app.schemas import AlertStatus, TaskState
from app.services import DataSpineService


def test_cooking_candidate_is_evidence_backed_deduped_and_live_clearable() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)

    first = service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-STOVE-1",
                "timestamp_utc": "2026-06-21T16:00:00Z",
                "person_visible": False,
                "objects": [
                    {
                        "label": "stove",
                        "confidence": 0.84,
                        "relative_location": "back counter",
                    }
                ],
            }
        ],
        room_id="kitchen",
    )

    assert first.observations[0].risk_signals == [
        "unattended_cooking_possible_human_verification_required"
    ]
    assert len(first.tasks_created) == 1
    assert len(first.alerts_created) == 1
    task = first.tasks_created[0]
    alert = first.alerts_created[0]
    assert task.type == "safety_alert"
    assert task.metadata["hazard_type"] == "unattended_cooking_possible"
    assert task.evidence_observation_ids == [first.observations[0].id]
    assert alert.hazard_type == "unattended_cooking_possible"
    assert "Please verify in person" in alert.body

    second = service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-STOVE-2",
                "timestamp_utc": "2026-06-21T16:01:00Z",
                "human_presence": "unknown",
                "objects": [{"label": "oven", "confidence": 0.8}],
            }
        ],
        room_id="kitchen",
    )

    assert second.tasks_created == []
    assert second.alerts_created == []
    assert len(repository.tasks) == 1
    assert repository.tasks[task.id].evidence_observation_ids == [
        first.observations[0].id,
        second.observations[0].id,
    ]
    assert repository.task_events[-1]["event_type"] == "safety_candidate_reobserved"

    cleared = service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-STOVE-CLEAR",
                "timestamp_utc": "2026-06-21T16:02:00Z",
                "objects": [{"label": "person", "confidence": 0.91}],
            }
        ],
        room_id="kitchen",
    )

    assert repository.tasks[task.id].state == TaskState.VERIFIED_RESOLVED
    assert repository.tasks[task.id].metadata["resolution_source"] == "live_afferens_safety_clear"
    assert repository.alerts[alert.id].status == AlertStatus.RESOLVED
    assert cleared.observations[0].id in repository.alerts[alert.id].evidence_observation_ids
    assert repository.task_events[-1]["event_type"] == "live_safety_condition_cleared"


def test_visible_person_context_prevents_unattended_cooking_candidate() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)

    result = service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-STOVE-WITH-PERSON",
                "timestamp_utc": "2026-06-21T16:00:00Z",
                "objects": [
                    {"label": "stove", "confidence": 0.82},
                    {"label": "person", "confidence": 0.88},
                ],
            }
        ],
        room_id="kitchen",
    )

    assert result.observations[0].risk_signals == []
    assert result.tasks_created == []
    assert result.alerts_created == []
