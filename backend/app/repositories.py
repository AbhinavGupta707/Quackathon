from __future__ import annotations

from typing import Any, Protocol

from app.ids import new_id
from app.schemas import (
    Alert,
    AlertStatus,
    LastSeenObject,
    LastSeenStatus,
    Observation,
    QueryLog,
    Task,
    TaskState,
    TaskType,
    VerificationCheck,
)


class DataRepository(Protocol):
    def persist_raw_event(self, raw_event: dict[str, Any]) -> str: ...

    def persist_observation(self, observation: Observation) -> Observation: ...

    def upsert_last_seen_objects(self, observation: Observation) -> list[LastSeenObject]: ...

    def create_task(self, task: Task) -> Task: ...

    def create_alert(self, alert: Alert) -> Alert: ...

    def create_query(self, query: QueryLog) -> QueryLog: ...

    def get_task(self, task_id: str) -> Task | None: ...

    def update_task(self, task: Task) -> Task: ...

    def add_task_event(
        self,
        *,
        task_id: str,
        event_type: str,
        message: str,
        evidence_observation_ids: list[str] | None = None,
    ) -> None: ...

    def find_open_object_recovery_task(self, object_key: str) -> Task | None: ...

    def create_verification_check(self, check: VerificationCheck) -> VerificationCheck: ...

    def list_alerts(self, *, status: AlertStatus | None = None) -> list[Alert]: ...

    def get_alert(self, alert_id: str) -> Alert | None: ...

    def update_alert(self, alert: Alert) -> Alert: ...

    def latest_observation(self) -> Observation | None: ...

    def list_last_seen_objects(self) -> list[LastSeenObject]: ...

    def list_tasks(
        self,
        *,
        state: TaskState | None = None,
        task_type: TaskType | None = None,
    ) -> list[Task]: ...


class InMemoryDataRepository:
    """Test repository. Product runtime uses the SQLAlchemy repository."""

    def __init__(self) -> None:
        self.raw_events: dict[str, dict[str, Any]] = {}
        self.observations: dict[str, Observation] = {}
        self.last_seen: dict[str, LastSeenObject] = {}
        self.tasks: dict[str, Task] = {}
        self.alerts: dict[str, Alert] = {}
        self.queries: dict[str, QueryLog] = {}
        self.task_events: list[dict[str, Any]] = []
        self.verification_checks: dict[str, VerificationCheck] = {}

    def persist_raw_event(self, raw_event: dict[str, Any]) -> str:
        provider_event_id = self._provider_event_id(raw_event)
        if provider_event_id is not None:
            for raw_event_id, stored_event in self.raw_events.items():
                if self._provider_event_id(stored_event) == provider_event_id:
                    return raw_event_id

        raw_event_id = new_id("aff")
        self.raw_events[raw_event_id] = raw_event
        return raw_event_id

    def persist_observation(self, observation: Observation) -> Observation:
        self.observations[observation.id] = observation
        return observation

    def upsert_last_seen_objects(self, observation: Observation) -> list[LastSeenObject]:
        updated: list[LastSeenObject] = []
        for detected in observation.objects:
            existing = self.last_seen.get(detected.object_key)
            if existing and existing.last_seen_at > observation.timestamp_utc:
                continue
            evidence_ids = list(existing.evidence_observation_ids) if existing else []
            if observation.id not in evidence_ids:
                evidence_ids.append(observation.id)
            memory = LastSeenObject(
                object_key=detected.object_key,
                display_name=detected.display_name,
                last_seen_at=observation.timestamp_utc,
                last_seen_room=observation.room_id,
                last_seen_relative_location=detected.relative_location,
                last_seen_observation_id=observation.id,
                last_confidence=detected.confidence,
                status=LastSeenStatus.VISIBLE_NOW,
                evidence_observation_ids=evidence_ids,
            )
            self.last_seen[detected.object_key] = memory
            updated.append(memory)
        return updated

    def create_task(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task

    def create_alert(self, alert: Alert) -> Alert:
        self.alerts[alert.id] = alert
        return alert

    def create_query(self, query: QueryLog) -> QueryLog:
        self.queries[query.id] = query
        return query

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def update_task(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task

    def add_task_event(
        self,
        *,
        task_id: str,
        event_type: str,
        message: str,
        evidence_observation_ids: list[str] | None = None,
    ) -> None:
        self.task_events.append(
            {
                "task_id": task_id,
                "event_type": event_type,
                "message": message,
                "evidence_observation_ids": list(evidence_observation_ids or []),
            }
        )

    def find_open_object_recovery_task(self, object_key: str) -> Task | None:
        open_states = {
            TaskState.OPEN,
            TaskState.WAITING_FOR_HUMAN,
            TaskState.VERIFICATION_PENDING,
            TaskState.FAILED_VERIFICATION,
        }
        candidates = [
            task
            for task in self.tasks.values()
            if task.type == TaskType.OBJECT_RECOVERY
            and task.state in open_states
            and task.metadata.get("object_key") == object_key
        ]
        return max(candidates, key=lambda item: item.created_at) if candidates else None

    def create_verification_check(self, check: VerificationCheck) -> VerificationCheck:
        self.verification_checks[check.id] = check
        return check

    def list_alerts(self, *, status: AlertStatus | None = None) -> list[Alert]:
        alerts = list(self.alerts.values())
        if status is not None:
            alerts = [alert for alert in alerts if alert.status == status]
        return sorted(alerts, key=lambda item: item.created_at, reverse=True)

    def get_alert(self, alert_id: str) -> Alert | None:
        return self.alerts.get(alert_id)

    def update_alert(self, alert: Alert) -> Alert:
        self.alerts[alert.id] = alert
        return alert

    def latest_observation(self) -> Observation | None:
        if not self.observations:
            return None
        return max(self.observations.values(), key=lambda item: item.timestamp_utc)

    def list_last_seen_objects(self) -> list[LastSeenObject]:
        return sorted(
            self.last_seen.values(),
            key=lambda item: item.last_seen_at,
            reverse=True,
        )

    def list_tasks(
        self,
        *,
        state: TaskState | None = None,
        task_type: TaskType | None = None,
    ) -> list[Task]:
        tasks = list(self.tasks.values())
        if state is not None:
            tasks = [task for task in tasks if task.state == state]
        if task_type is not None:
            tasks = [task for task in tasks if task.type == task_type]
        return sorted(tasks, key=lambda item: item.created_at, reverse=True)

    @staticmethod
    def _provider_event_id(raw_event: dict[str, Any]) -> str | None:
        for key in ("entity_id", "id", "event_id", "eventId"):
            value = raw_event.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None
