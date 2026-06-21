from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.memory import ObjectMemoryService
from app.normalizer import AfferensObservationNormalizer
from app.repositories import DataRepository
from app.schemas import (
    Alert,
    AlertStatus,
    LastSeenObject,
    Observation,
    QueryLog,
    Task,
    TaskState,
    TaskType,
    VerificationCheck,
)
from app.tasks import TaskCreationService


@dataclass
class SyncResult:
    observations: list[Observation] = field(default_factory=list)
    objects_updated: list[LastSeenObject] = field(default_factory=list)
    tasks_created: list[Task] = field(default_factory=list)
    alerts_created: list[Alert] = field(default_factory=list)


class DataSpineService:
    def __init__(
        self,
        repository: DataRepository,
        *,
        normalizer: AfferensObservationNormalizer | None = None,
    ) -> None:
        self._repository = repository
        self._normalizer = normalizer or AfferensObservationNormalizer()
        self._memory = ObjectMemoryService(repository)
        self._tasks = TaskCreationService(repository)

    def sync_raw_events(
        self,
        raw_events: list[dict[str, Any]],
        *,
        room_id: str,
    ) -> SyncResult:
        result = SyncResult()
        for raw_event in raw_events:
            raw_event_id = self._repository.persist_raw_event(raw_event)
            observation = self._normalizer.normalize(
                raw_event,
                raw_event_id=raw_event_id,
                room_id=room_id,
            )
            observation = self._repository.persist_observation(observation)
            result.observations.append(observation)
            result.objects_updated.extend(self._memory.update_from_observation(observation))

            tasks, alerts = self._tasks.create_from_observation(observation)
            result.tasks_created.extend(tasks)
            result.alerts_created.extend(alerts)

        return result

    def latest_observation(self) -> Observation | None:
        return self._repository.latest_observation()

    def list_last_seen_objects(self) -> list[LastSeenObject]:
        return self._repository.list_last_seen_objects()

    def list_tasks(
        self,
        *,
        state: TaskState | None = None,
        task_type: TaskType | None = None,
    ) -> list[Task]:
        return self._repository.list_tasks(state=state, task_type=task_type)

    def create_query(self, query: QueryLog) -> QueryLog:
        return self._repository.create_query(query)

    def create_task(self, task: Task) -> Task:
        return self._repository.create_task(task)

    def get_task(self, task_id: str) -> Task | None:
        return self._repository.get_task(task_id)

    def update_task(self, task: Task) -> Task:
        return self._repository.update_task(task)

    def add_task_event(
        self,
        *,
        task_id: str,
        event_type: str,
        message: str,
        evidence_observation_ids: list[str] | None = None,
    ) -> None:
        self._repository.add_task_event(
            task_id=task_id,
            event_type=event_type,
            message=message,
            evidence_observation_ids=evidence_observation_ids,
        )

    def find_open_object_recovery_task(self, object_key: str) -> Task | None:
        return self._repository.find_open_object_recovery_task(object_key)

    def create_verification_check(self, check: VerificationCheck) -> VerificationCheck:
        return self._repository.create_verification_check(check)

    def list_alerts(self, *, status: AlertStatus | None = None) -> list[Alert]:
        return self._repository.list_alerts(status=status)

    def get_alert(self, alert_id: str) -> Alert | None:
        return self._repository.get_alert(alert_id)

    def update_alert(self, alert: Alert) -> Alert:
        return self._repository.update_alert(alert)
