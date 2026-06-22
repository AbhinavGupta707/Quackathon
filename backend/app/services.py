from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.memory import ObjectMemoryService
from app.normalizer import AfferensObservationNormalizer
from app.repositories import DataRepository
from app.schemas import (
    ActuationAttempt,
    ActionEvent,
    ActionEventType,
    Alert,
    AlertStatus,
    CareNote,
    DailyDiaryEntry,
    FamilyMessage,
    HydrationEvent,
    HomeZone,
    LastSeenObject,
    ModelRun,
    Observation,
    ObservationEnrichment,
    QueryLog,
    SemanticMemoryItem,
    SemanticMemorySourceType,
    Task,
    TaskState,
    TaskType,
    VerificationCheck,
    WellnessCheck,
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
        recent_window_seconds: int = 300,
    ) -> None:
        self._repository = repository
        self._recent_window_seconds = recent_window_seconds
        self._normalizer = normalizer or AfferensObservationNormalizer()
        self._memory = ObjectMemoryService(
            repository,
            recent_window_seconds=recent_window_seconds,
        )
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
        return self._repository.list_last_seen_objects(
            recent_window_seconds=self._recent_window_seconds,
        )

    def list_home_zones(self) -> list[HomeZone]:
        return self._repository.list_home_zones()

    def create_home_zone(self, zone: HomeZone) -> HomeZone:
        return self._repository.create_home_zone(zone)

    def list_observations_for_date(self, activity_date: date) -> list[Observation]:
        return self._repository.list_observations_for_date(activity_date)

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

    def create_actuation_attempt(self, attempt: ActuationAttempt) -> ActuationAttempt:
        return self._repository.create_actuation_attempt(attempt)

    def list_actuation_attempts_for_date(self, activity_date: date) -> list[ActuationAttempt]:
        return self._repository.list_actuation_attempts_for_date(activity_date)

    def get_daily_diary(self, entry_date: date) -> DailyDiaryEntry | None:
        return self._repository.get_daily_diary(entry_date)

    def upsert_daily_diary(self, diary: DailyDiaryEntry) -> DailyDiaryEntry:
        return self._repository.upsert_daily_diary(diary)

    def list_care_notes(self, note_date: date) -> list[CareNote]:
        return self._repository.list_care_notes(note_date)

    def create_care_note(self, note: CareNote) -> CareNote:
        return self._repository.create_care_note(note)

    def list_family_messages(
        self,
        *,
        include_acknowledged: bool = False,
    ) -> list[FamilyMessage]:
        return self._repository.list_family_messages(include_acknowledged=include_acknowledged)

    def create_family_message(self, message: FamilyMessage) -> FamilyMessage:
        return self._repository.create_family_message(message)

    def get_family_message(self, message_id: str) -> FamilyMessage | None:
        return self._repository.get_family_message(message_id)

    def update_family_message(self, message: FamilyMessage) -> FamilyMessage:
        return self._repository.update_family_message(message)

    def list_hydration_events_for_date(self, event_date: date) -> list[HydrationEvent]:
        return self._repository.list_hydration_events_for_date(event_date)

    def create_hydration_event(self, event: HydrationEvent) -> HydrationEvent:
        return self._repository.create_hydration_event(event)

    def create_action_event(self, event: ActionEvent) -> ActionEvent:
        return self._repository.create_action_event(event)

    def list_action_events(
        self,
        *,
        event_date: date | None = None,
        event_type: ActionEventType | None = None,
        limit: int = 50,
    ) -> list[ActionEvent]:
        return self._repository.list_action_events(
            event_date=event_date,
            event_type=event_type,
            limit=limit,
        )

    def list_wellness_checks_for_date(self, check_date: date) -> list[WellnessCheck]:
        return self._repository.list_wellness_checks_for_date(check_date)

    def create_wellness_check(self, check: WellnessCheck) -> WellnessCheck:
        return self._repository.create_wellness_check(check)

    def get_wellness_check(self, check_id: str) -> WellnessCheck | None:
        return self._repository.get_wellness_check(check_id)

    def update_wellness_check(self, check: WellnessCheck) -> WellnessCheck:
        return self._repository.update_wellness_check(check)

    def list_semantic_source_items(
        self,
        *,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> list[SemanticMemoryItem]:
        return self._repository.list_semantic_source_items(source_types=source_types)

    def upsert_semantic_memory_items(
        self,
        items: list[SemanticMemoryItem],
        *,
        force: bool = False,
    ) -> tuple[int, int, int]:
        return self._repository.upsert_semantic_memory_items(items, force=force)

    def list_semantic_memory_items(
        self,
        *,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> list[SemanticMemoryItem]:
        return self._repository.list_semantic_memory_items(source_types=source_types)

    def create_model_run(
        self,
        model_run: ModelRun,
        *,
        observation_id: str | None,
        purpose: str,
        focus: str,
    ) -> ModelRun:
        return self._repository.create_model_run(
            model_run,
            observation_id=observation_id,
            purpose=purpose,
            focus=focus,
        )

    def create_observation_enrichment(
        self,
        enrichment: ObservationEnrichment,
        *,
        model_run_id: str | None = None,
    ) -> ObservationEnrichment:
        return self._repository.create_observation_enrichment(
            enrichment,
            model_run_id=model_run_id,
        )

    def latest_enrichment(self) -> ObservationEnrichment | None:
        return self._repository.latest_enrichment()

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
