from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from app.ids import new_id
from app.schemas import (
    ActuationAttempt,
    ActionEvent,
    ActionEventType,
    Alert,
    AlertStatus,
    CareNote,
    DailyDiaryEntry,
    DetectedObject,
    FamilyMessage,
    FamilyMessageStatus,
    HydrationEvent,
    HomeRegion,
    HomeRegionKind,
    HomeZone,
    LastSeenObject,
    LastSeenStatus,
    ModelRun,
    ObservationEnrichment,
    Observation,
    QueryLog,
    SemanticMemoryItem,
    SemanticMemorySourceType,
    Task,
    TaskState,
    TaskType,
    VerificationCheck,
    WellnessCheck,
    utc_now,
)


DEFAULT_HOME_ZONE = HomeZone(
    id="default_home_zone",
    name="Home area",
    room_type="other",
    aliases=["home", "main room"],
    is_default=True,
)


@dataclass(frozen=True)
class ObjectLocationAssignment:
    room_id: str
    room_label: str
    region_id: str | None = None
    region_label: str | None = None
    normalized_coords: dict[str, float] | None = None
    relative_location: str | None = None
    source: str = "observation_room"


DEFAULT_QUADRANT_REGIONS = [
    HomeRegion(
        id="top_left",
        label="top left area",
        kind=HomeRegionKind.QUADRANT,
        bounds={"x_min": 0.0, "y_min": 0.0, "x_max": 0.5, "y_max": 0.5},
    ),
    HomeRegion(
        id="top_right",
        label="top right area",
        kind=HomeRegionKind.QUADRANT,
        bounds={"x_min": 0.5, "y_min": 0.0, "x_max": 1.0, "y_max": 0.5},
    ),
    HomeRegion(
        id="bottom_left",
        label="bottom left area",
        kind=HomeRegionKind.QUADRANT,
        bounds={"x_min": 0.0, "y_min": 0.5, "x_max": 0.5, "y_max": 1.0},
    ),
    HomeRegion(
        id="bottom_right",
        label="bottom right area",
        kind=HomeRegionKind.QUADRANT,
        bounds={"x_min": 0.5, "y_min": 0.5, "x_max": 1.0, "y_max": 1.0},
    ),
]


class DataRepository(Protocol):
    def persist_raw_event(self, raw_event: dict[str, Any]) -> str: ...

    def persist_observation(self, observation: Observation) -> Observation: ...

    def upsert_last_seen_objects(
        self,
        observation: Observation,
        *,
        recent_window_seconds: int,
    ) -> list[LastSeenObject]: ...

    def list_home_zones(self) -> list[HomeZone]: ...

    def create_home_zone(self, zone: HomeZone) -> HomeZone: ...

    def list_observations_for_date(self, activity_date: date) -> list[Observation]: ...

    def create_task(self, task: Task) -> Task: ...

    def create_alert(self, alert: Alert) -> Alert: ...

    def create_actuation_attempt(self, attempt: ActuationAttempt) -> ActuationAttempt: ...

    def list_actuation_attempts_for_date(self, activity_date: date) -> list[ActuationAttempt]: ...

    def get_daily_diary(self, entry_date: date) -> DailyDiaryEntry | None: ...

    def upsert_daily_diary(self, diary: DailyDiaryEntry) -> DailyDiaryEntry: ...

    def list_care_notes(self, note_date: date) -> list[CareNote]: ...

    def create_care_note(self, note: CareNote) -> CareNote: ...

    def list_family_messages(
        self,
        *,
        include_acknowledged: bool = False,
    ) -> list[FamilyMessage]: ...

    def create_family_message(self, message: FamilyMessage) -> FamilyMessage: ...

    def get_family_message(self, message_id: str) -> FamilyMessage | None: ...

    def update_family_message(self, message: FamilyMessage) -> FamilyMessage: ...

    def list_hydration_events_for_date(self, event_date: date) -> list[HydrationEvent]: ...

    def create_hydration_event(self, event: HydrationEvent) -> HydrationEvent: ...

    def create_action_event(self, event: ActionEvent) -> ActionEvent: ...

    def list_action_events(
        self,
        *,
        event_date: date | None = None,
        event_type: ActionEventType | None = None,
        limit: int = 50,
    ) -> list[ActionEvent]: ...

    def list_wellness_checks_for_date(self, check_date: date) -> list[WellnessCheck]: ...

    def create_wellness_check(self, check: WellnessCheck) -> WellnessCheck: ...

    def get_wellness_check(self, check_id: str) -> WellnessCheck | None: ...

    def update_wellness_check(self, check: WellnessCheck) -> WellnessCheck: ...

    def list_semantic_source_items(
        self,
        *,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> list[SemanticMemoryItem]: ...

    def upsert_semantic_memory_items(
        self,
        items: list[SemanticMemoryItem],
        *,
        force: bool = False,
    ) -> tuple[int, int, int]: ...

    def list_semantic_memory_items(
        self,
        *,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> list[SemanticMemoryItem]: ...

    def create_model_run(
        self,
        model_run: ModelRun,
        *,
        observation_id: str | None,
        purpose: str,
        focus: str,
    ) -> ModelRun: ...

    def create_observation_enrichment(
        self,
        enrichment: ObservationEnrichment,
        *,
        model_run_id: str | None = None,
    ) -> ObservationEnrichment: ...

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

    def latest_enrichment(self) -> ObservationEnrichment | None: ...

    def list_last_seen_objects(
        self,
        *,
        recent_window_seconds: int = 300,
    ) -> list[LastSeenObject]: ...

    def list_tasks(
        self,
        *,
        state: TaskState | None = None,
        task_type: TaskType | None = None,
    ) -> list[Task]: ...


def reconcile_last_seen_status(
    memory: LastSeenObject,
    *,
    latest_observation: Observation | None,
    recent_window_seconds: int,
    reference_time: datetime | None = None,
) -> LastSeenStatus:
    reference = reference_time or utc_now()
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=utc_now().tzinfo)
    last_seen_at = memory.last_seen_at
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=reference.tzinfo)

    if last_seen_at < reference - timedelta(seconds=recent_window_seconds):
        return LastSeenStatus.NOT_SEEN_RECENTLY
    if latest_observation is None:
        return LastSeenStatus.UNKNOWN

    latest_keys = {detected.object_key for detected in latest_observation.objects}
    if (
        memory.last_seen_observation_id == latest_observation.id
        and memory.object_key in latest_keys
    ):
        return LastSeenStatus.VISIBLE_NOW
    return LastSeenStatus.VISIBLE_RECENTLY


def normalize_home_zone(zone: HomeZone) -> HomeZone:
    region_strategy = (zone.region_strategy or "none").strip().lower() or "none"
    regions = zone.regions
    if region_strategy in {"quadrants", "grid_2x2"} and not regions:
        regions = DEFAULT_QUADRANT_REGIONS
        region_strategy = "quadrants"
    return zone.model_copy(update={"region_strategy": region_strategy, "regions": regions})


def object_location_assignment(
    *,
    detected: DetectedObject,
    observation: Observation,
    zone: HomeZone | None,
) -> ObjectLocationAssignment:
    normalized_zone = normalize_home_zone(zone) if zone is not None else None
    room_id = normalized_zone.id if normalized_zone is not None else observation.room_id
    room_label = normalized_zone.name if normalized_zone is not None else observation.room_id
    source = "node_profile" if (
        normalized_zone is not None
        and observation.room_id == DEFAULT_HOME_ZONE.id
        and observation.source_node_id
        and normalized_zone.source_node_id == observation.source_node_id
    ) else "observation_room"

    coords = normalized_object_center(detected)
    region = find_region_for_coords(normalized_zone.regions if normalized_zone else [], coords)
    if region is not None:
        source = "calibrated_region"
        relative_location = detected.relative_location
        if not relative_location:
            relative_location = region.label
    else:
        relative_location = detected.relative_location

    return ObjectLocationAssignment(
        room_id=room_id,
        room_label=room_label,
        region_id=region.id if region else None,
        region_label=region.label if region else None,
        normalized_coords=coords,
        relative_location=relative_location,
        source=source,
    )


def normalized_object_center(detected: DetectedObject) -> dict[str, float] | None:
    spatial = detected.spatial_coords or {}
    for x_key, y_key in (("x", "y"), ("cx", "cy"), ("center_x", "center_y")):
        point = _normalized_pair(spatial.get(x_key), spatial.get(y_key))
        if point is not None:
            return point

    bbox = detected.bbox
    if isinstance(bbox, dict):
        for x_key, y_key in (("center_x", "center_y"), ("cx", "cy")):
            point = _normalized_pair(bbox.get(x_key), bbox.get(y_key))
            if point is not None:
                return point
        x = _coerce_float(_first_present_value(bbox, "x", "left", "xmin", "x_min"))
        y = _coerce_float(_first_present_value(bbox, "y", "top", "ymin", "y_min"))
        width = _coerce_float(_first_present_value(bbox, "width", "w"))
        height = _coerce_float(_first_present_value(bbox, "height", "h"))
        right = _coerce_float(_first_present_value(bbox, "right", "xmax", "x_max"))
        bottom = _coerce_float(_first_present_value(bbox, "bottom", "ymax", "y_max"))
        if x is not None and y is not None:
            if width is not None and height is not None:
                return _normalized_pair(x + width / 2, y + height / 2)
            if right is not None and bottom is not None:
                return _normalized_pair((x + right) / 2, (y + bottom) / 2)
    elif isinstance(bbox, list) and len(bbox) >= 4:
        values = [_coerce_float(item) for item in bbox[:4]]
        if all(item is not None for item in values):
            x1, y1, x2_or_w, y2_or_h = values  # type: ignore[misc]
            if x2_or_w <= 1.0 and y2_or_h <= 1.0:
                return _normalized_pair((x1 + x2_or_w) / 2, (y1 + y2_or_h) / 2)
            return _normalized_pair(x1 + x2_or_w / 2, y1 + y2_or_h / 2)
    return None


def find_region_for_coords(
    regions: list[HomeRegion],
    coords: dict[str, float] | None,
) -> HomeRegion | None:
    if coords is None:
        return None
    x = coords["x"]
    y = coords["y"]
    for region in regions:
        bounds = region.bounds or {}
        x_min = _coerce_float(bounds.get("x_min"))
        y_min = _coerce_float(bounds.get("y_min"))
        x_max = _coerce_float(bounds.get("x_max"))
        y_max = _coerce_float(bounds.get("y_max"))
        if None in {x_min, y_min, x_max, y_max}:
            continue
        if x_min <= x <= x_max and y_min <= y <= y_max:
            return region
    return None


def _normalized_pair(x_value: Any, y_value: Any) -> dict[str, float] | None:
    x = _coerce_float(x_value)
    y = _coerce_float(y_value)
    if x is None or y is None:
        return None
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return {"x": round(x, 4), "y": round(y, 4)}


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_present_value(payload: dict[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


class InMemoryDataRepository:
    """Test repository. Product runtime uses the SQLAlchemy repository."""

    def __init__(self) -> None:
        self.raw_events: dict[str, dict[str, Any]] = {}
        self.observations: dict[str, Observation] = {}
        self.last_seen: dict[str, LastSeenObject] = {}
        self.tasks: dict[str, Task] = {}
        self.alerts: dict[str, Alert] = {}
        self.actuation_attempts: dict[str, ActuationAttempt] = {}
        self.diary_entries: dict[date, DailyDiaryEntry] = {}
        self.care_notes: dict[str, CareNote] = {}
        self.family_messages: dict[str, FamilyMessage] = {}
        self.hydration_events: dict[str, HydrationEvent] = {}
        self.action_events: dict[str, ActionEvent] = {}
        self.wellness_checks: dict[str, WellnessCheck] = {}
        self.semantic_memory: dict[str, SemanticMemoryItem] = {}
        self.model_runs: dict[str, ModelRun] = {}
        self.enrichments: dict[str, ObservationEnrichment] = {}
        self.enrichment_model_runs: dict[str, str | None] = {}
        self.home_zones: dict[str, HomeZone] = {DEFAULT_HOME_ZONE.id: DEFAULT_HOME_ZONE}
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

    def upsert_last_seen_objects(
        self,
        observation: Observation,
        *,
        recent_window_seconds: int,
    ) -> list[LastSeenObject]:
        updated: list[LastSeenObject] = []
        seen_keys: set[str] = set()
        for detected in observation.objects:
            seen_keys.add(detected.object_key)
            existing = self.last_seen.get(detected.object_key)
            if existing and existing.last_seen_at > observation.timestamp_utc:
                continue
            assignment = object_location_assignment(
                detected=detected,
                observation=observation,
                zone=self._zone_for_observation(observation),
            )
            evidence_ids = list(existing.evidence_observation_ids) if existing else []
            if observation.id not in evidence_ids:
                evidence_ids.append(observation.id)
            memory = LastSeenObject(
                object_key=detected.object_key,
                display_name=detected.display_name,
                last_seen_at=observation.timestamp_utc,
                last_seen_room=assignment.room_label,
                last_seen_room_id=assignment.room_id,
                last_seen_region_id=assignment.region_id,
                last_seen_region_label=assignment.region_label,
                last_seen_normalized_coords=assignment.normalized_coords,
                location_assignment_source=assignment.source,
                last_seen_relative_location=assignment.relative_location,
                last_seen_observation_id=observation.id,
                last_confidence=detected.confidence,
                status=LastSeenStatus.VISIBLE_NOW,
                evidence_observation_ids=evidence_ids,
            )
            self.last_seen[detected.object_key] = memory
            updated.append(memory)

        latest_observation = self.latest_observation()
        if latest_observation is None or latest_observation.id == observation.id:
            for object_key, memory in list(self.last_seen.items()):
                if object_key in seen_keys:
                    continue
                reconciled = memory.model_copy(
                    update={
                        "status": reconcile_last_seen_status(
                            memory,
                            latest_observation=observation,
                            recent_window_seconds=recent_window_seconds,
                            reference_time=observation.timestamp_utc,
                        ),
                        "updated_at": utc_now(),
                    }
                )
                self.last_seen[object_key] = reconciled
                if reconciled.status != memory.status:
                    updated.append(reconciled)
        return updated

    def list_home_zones(self) -> list[HomeZone]:
        if not self.home_zones:
            self.home_zones[DEFAULT_HOME_ZONE.id] = DEFAULT_HOME_ZONE
        return sorted(
            self.home_zones.values(),
            key=lambda item: (not item.is_default, item.created_at, item.name.lower()),
        )

    def create_home_zone(self, zone: HomeZone) -> HomeZone:
        zone = normalize_home_zone(zone)
        if zone.is_default:
            for existing_id, existing in list(self.home_zones.items()):
                self.home_zones[existing_id] = existing.model_copy(update={"is_default": False})
        self.home_zones[zone.id] = zone
        if not any(item.is_default for item in self.home_zones.values()):
            self.home_zones[zone.id] = zone.model_copy(update={"is_default": True})
        return self.home_zones[zone.id]

    def _zone_for_observation(self, observation: Observation) -> HomeZone | None:
        direct = self.home_zones.get(observation.room_id)
        if direct is not None and direct.id != DEFAULT_HOME_ZONE.id:
            return normalize_home_zone(direct)
        if observation.source_node_id:
            for zone in self.home_zones.values():
                if zone.source_node_id and zone.source_node_id == observation.source_node_id:
                    return normalize_home_zone(zone)
        if direct is not None:
            return normalize_home_zone(direct)
        return None

    def list_observations_for_date(self, activity_date: date) -> list[Observation]:
        return sorted(
            [
                observation
                for observation in self.observations.values()
                if observation.timestamp_utc.date() == activity_date
            ],
            key=lambda item: item.timestamp_utc,
            reverse=True,
        )

    def create_task(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task

    def create_alert(self, alert: Alert) -> Alert:
        self.alerts[alert.id] = alert
        return alert

    def create_actuation_attempt(self, attempt: ActuationAttempt) -> ActuationAttempt:
        self.actuation_attempts[attempt.id] = attempt
        return attempt

    def list_actuation_attempts_for_date(self, activity_date: date) -> list[ActuationAttempt]:
        return sorted(
            [
                attempt
                for attempt in self.actuation_attempts.values()
                if attempt.created_at.date() == activity_date
            ],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get_daily_diary(self, entry_date: date) -> DailyDiaryEntry | None:
        return self.diary_entries.get(entry_date)

    def upsert_daily_diary(self, diary: DailyDiaryEntry) -> DailyDiaryEntry:
        self.diary_entries[diary.date] = diary
        return diary

    def list_care_notes(self, note_date: date) -> list[CareNote]:
        return sorted(
            [note for note in self.care_notes.values() if note.date == note_date],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def create_care_note(self, note: CareNote) -> CareNote:
        self.care_notes[note.id] = note
        return note

    def list_family_messages(
        self,
        *,
        include_acknowledged: bool = False,
    ) -> list[FamilyMessage]:
        messages = list(self.family_messages.values())
        if not include_acknowledged:
            messages = [
                message
                for message in messages
                if message.status != FamilyMessageStatus.ACKNOWLEDGED
            ]
        return sorted(messages, key=lambda item: item.created_at, reverse=True)

    def create_family_message(self, message: FamilyMessage) -> FamilyMessage:
        self.family_messages[message.id] = message
        return message

    def get_family_message(self, message_id: str) -> FamilyMessage | None:
        return self.family_messages.get(message_id)

    def update_family_message(self, message: FamilyMessage) -> FamilyMessage:
        self.family_messages[message.id] = message
        return message

    def list_hydration_events_for_date(self, event_date: date) -> list[HydrationEvent]:
        return sorted(
            [
                event
                for event in self.hydration_events.values()
                if event.occurred_at.date() == event_date
            ],
            key=lambda item: item.occurred_at,
            reverse=True,
        )

    def create_hydration_event(self, event: HydrationEvent) -> HydrationEvent:
        self.hydration_events[event.id] = event
        return event

    def create_action_event(self, event: ActionEvent) -> ActionEvent:
        self.action_events[event.id] = event
        return event

    def list_action_events(
        self,
        *,
        event_date: date | None = None,
        event_type: ActionEventType | None = None,
        limit: int = 50,
    ) -> list[ActionEvent]:
        events = list(self.action_events.values())
        if event_date is not None:
            events = [event for event in events if event.occurred_at.date() == event_date]
        if event_type is not None:
            events = [event for event in events if event.type == event_type]
        return sorted(events, key=lambda item: item.occurred_at, reverse=True)[:limit]

    def list_wellness_checks_for_date(self, check_date: date) -> list[WellnessCheck]:
        return sorted(
            [
                check
                for check in self.wellness_checks.values()
                if check.occurred_at.date() == check_date
            ],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def create_wellness_check(self, check: WellnessCheck) -> WellnessCheck:
        self.wellness_checks[check.id] = check
        return check

    def get_wellness_check(self, check_id: str) -> WellnessCheck | None:
        return self.wellness_checks.get(check_id)

    def update_wellness_check(self, check: WellnessCheck) -> WellnessCheck:
        self.wellness_checks[check.id] = check
        return check

    def list_semantic_source_items(
        self,
        *,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> list[SemanticMemoryItem]:
        items = _semantic_source_items(
            observations=list(self.observations.values()),
            last_seen=list(self.last_seen.values()),
            diary_entries=list(self.diary_entries.values()),
            care_notes=list(self.care_notes.values()),
            family_messages=list(self.family_messages.values()),
            hydration_events=list(self.hydration_events.values()),
            wellness_checks=list(self.wellness_checks.values()),
        )
        return _filter_semantic_items(items, source_types)

    def upsert_semantic_memory_items(
        self,
        items: list[SemanticMemoryItem],
        *,
        force: bool = False,
    ) -> tuple[int, int, int]:
        created = 0
        updated = 0
        skipped = 0
        for item in items:
            existing = self.semantic_memory.get(item.id)
            if existing is None:
                self.semantic_memory[item.id] = item
                created += 1
                continue
            comparable = item.model_copy(update={"created_at": existing.created_at})
            if not force and existing.model_dump(mode="json") == comparable.model_dump(mode="json"):
                skipped += 1
                continue
            self.semantic_memory[item.id] = comparable
            updated += 1
        return created, updated, skipped

    def list_semantic_memory_items(
        self,
        *,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> list[SemanticMemoryItem]:
        return _filter_semantic_items(
            sorted(
                self.semantic_memory.values(),
                key=lambda item: item.occurred_at or item.created_at,
                reverse=True,
            ),
            source_types,
        )

    def create_model_run(
        self,
        model_run: ModelRun,
        *,
        observation_id: str | None,
        purpose: str,
        focus: str,
    ) -> ModelRun:
        self.model_runs[model_run.id] = model_run
        return model_run

    def create_observation_enrichment(
        self,
        enrichment: ObservationEnrichment,
        *,
        model_run_id: str | None = None,
    ) -> ObservationEnrichment:
        self.enrichments[enrichment.id] = enrichment
        self.enrichment_model_runs[enrichment.id] = model_run_id
        return enrichment

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

    def latest_enrichment(self) -> ObservationEnrichment | None:
        if not self.enrichments:
            return None
        return max(self.enrichments.values(), key=lambda item: item.created_at)

    def list_last_seen_objects(
        self,
        *,
        recent_window_seconds: int = 300,
    ) -> list[LastSeenObject]:
        latest = self.latest_observation()
        reconciled = [
            item.model_copy(
                update={
                    "status": reconcile_last_seen_status(
                        item,
                        latest_observation=latest,
                        recent_window_seconds=recent_window_seconds,
                    )
                }
            )
            for item in self.last_seen.values()
        ]
        return sorted(
            reconciled,
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


def _semantic_source_items(
    *,
    observations: list[Observation],
    last_seen: list[LastSeenObject],
    diary_entries: list[DailyDiaryEntry],
    care_notes: list[CareNote],
    family_messages: list[FamilyMessage],
    hydration_events: list[HydrationEvent],
    wellness_checks: list[WellnessCheck],
) -> list[SemanticMemoryItem]:
    items: list[SemanticMemoryItem] = []
    for observation in observations:
        labels = ", ".join(obj.display_name for obj in observation.objects[:8])
        text = observation.scene_summary
        if labels:
            text = f"{text} Objects: {labels}."
        items.append(
            _semantic_item(
                source_type=SemanticMemorySourceType.OBSERVATION,
                source_id=observation.id,
                title="Live observation",
                text=text,
                occurred_at=observation.timestamp_utc,
                evidence_ids=[observation.id],
                source_ids=[observation.id, observation.raw_event_id],
                metadata={
                    "room_id": observation.room_id,
                    "source": observation.source,
                    "source_node_id": observation.source_node_id,
                    "object_keys": [obj.object_key for obj in observation.objects],
                    "human_presence": observation.human_presence.value,
                },
            )
        )

    for memory in last_seen:
        location = memory.last_seen_relative_location or "an unspecified location"
        items.append(
            _semantic_item(
                source_type=SemanticMemorySourceType.OBJECT_MEMORY,
                source_id=memory.object_key,
                title=f"Object memory: {memory.display_name}",
                text=(
                    f"{memory.display_name} was last seen in {memory.last_seen_room} "
                    f"at {location}. Current memory status is {memory.status.value}."
                ),
                occurred_at=memory.last_seen_at,
                evidence_ids=memory.evidence_observation_ids or [memory.last_seen_observation_id],
                source_ids=[memory.object_key, memory.last_seen_observation_id],
                metadata={
                    "object_key": memory.object_key,
                    "display_name": memory.display_name,
                    "room": memory.last_seen_room,
                    "room_id": memory.last_seen_room_id or memory.last_seen_room,
                    "region_id": memory.last_seen_region_id,
                    "region_label": memory.last_seen_region_label,
                    "normalized_coords": memory.last_seen_normalized_coords,
                    "location_assignment_source": memory.location_assignment_source,
                    "status": memory.status.value,
                    "confidence": memory.last_confidence,
                },
            )
        )

    for diary in diary_entries:
        items.append(
            _semantic_item(
                source_type=SemanticMemorySourceType.DIARY_ENTRY,
                source_id=diary.id,
                title=f"Daily diary for {diary.date.isoformat()}",
                text=" ".join(
                    [diary.summary, *_prefixed("Highlight", diary.highlights), *_prefixed("Review", diary.needs_review)]
                ),
                occurred_at=diary.generated_at,
                evidence_ids=diary.evidence_ids,
                source_ids=[diary.id],
                metadata={"date": diary.date.isoformat(), "source": diary.source},
            )
        )

    for note in care_notes:
        items.append(
            _semantic_item(
                source_type=SemanticMemorySourceType.CARE_NOTE,
                source_id=note.id,
                title=f"Care note for {note.date.isoformat()}",
                text=" ".join(
                    [
                        note.summary,
                        *_prefixed("Note", note.bullets),
                        *_prefixed("Risk", note.risks),
                        *_prefixed("Follow-up", note.follow_ups),
                    ]
                ),
                occurred_at=note.created_at,
                evidence_ids=note.evidence_ids,
                source_ids=[note.id],
                metadata={
                    "date": note.date.isoformat(),
                    "audience": note.audience.value,
                    "source": note.source,
                },
            )
        )

    for message in family_messages:
        occurred_at = message.acknowledged_at or message.starts_at or message.created_at
        items.append(
            _semantic_item(
                source_type=SemanticMemorySourceType.FAMILY_MESSAGE,
                source_id=message.id,
                title=f"Family message: {message.title}",
                text=f"{message.title}. {message.body} Status: {message.status.value}.",
                occurred_at=occurred_at,
                evidence_ids=[],
                source_ids=[message.id],
                metadata={
                    "priority": message.priority.value,
                    "status": message.status.value,
                    "trigger_object_key": message.trigger_object_key,
                    "trigger_zone_id": message.trigger_zone_id,
                },
            )
        )

    for event in hydration_events:
        object_keys = event.metadata.get("object_keys") if isinstance(event.metadata, dict) else None
        object_text = f" Objects: {', '.join(object_keys)}." if isinstance(object_keys, list) and object_keys else ""
        items.append(
            _semantic_item(
                source_type=SemanticMemorySourceType.HYDRATION_EVENT,
                source_id=event.id,
                title="Hydration event",
                text=(
                    f"Hydration candidate {event.type.value} in {event.zone_name or event.zone_id or 'an unknown zone'} "
                    f"with {event.confidence.value} confidence.{object_text}"
                ),
                occurred_at=event.occurred_at,
                evidence_ids=event.evidence_ids,
                source_ids=[event.id, *event.evidence_ids],
                metadata={
                    "type": event.type.value,
                    "confidence": event.confidence.value,
                    "zone_id": event.zone_id,
                    "zone_name": event.zone_name,
                    **event.metadata,
                },
            )
        )

    for check in wellness_checks:
        items.append(
            _semantic_item(
                source_type=SemanticMemorySourceType.WELLNESS_CHECK,
                source_id=check.id,
                title=check.title,
                text=(
                    f"{check.title}. {check.body} Status: {check.status.value}. "
                    f"Human verification required."
                ),
                occurred_at=check.occurred_at,
                evidence_ids=check.evidence_ids,
                source_ids=[check.id, *check.evidence_ids],
                metadata={
                    "type": check.type.value,
                    "severity": check.severity.value,
                    "status": check.status.value,
                    "confidence": check.confidence.value,
                    "zone_id": check.zone_id,
                    "zone_name": check.zone_name,
                    **check.metadata,
                },
            )
        )

    return sorted(items, key=lambda item: item.occurred_at or item.created_at, reverse=True)


def _semantic_item(
    *,
    source_type: SemanticMemorySourceType,
    source_id: str,
    title: str,
    text: str,
    occurred_at: datetime | None,
    evidence_ids: list[str],
    source_ids: list[str],
    metadata: dict[str, Any],
) -> SemanticMemoryItem:
    return SemanticMemoryItem(
        id=_semantic_memory_id(source_type, source_id),
        source_type=source_type,
        source_id=source_id,
        title=title.strip(),
        text=" ".join(text.split()),
        occurred_at=occurred_at,
        created_at=utc_now(),
        evidence_ids=list(dict.fromkeys(evidence_ids)),
        source_ids=list(dict.fromkeys(source_ids)),
        metadata={key: value for key, value in metadata.items() if value is not None},
    )


def _semantic_memory_id(source_type: SemanticMemorySourceType, source_id: str) -> str:
    digest = hashlib.sha1(f"{source_type.value}:{source_id}".encode("utf-8")).hexdigest()[:24]
    return f"semmem_{digest}"


def _filter_semantic_items(
    items: list[SemanticMemoryItem],
    source_types: list[SemanticMemorySourceType] | None,
) -> list[SemanticMemoryItem]:
    if not source_types:
        return items
    allowed = set(source_types)
    return [item for item in items if item.source_type in allowed]


def _prefixed(prefix: str, values: list[str]) -> list[str]:
    return [f"{prefix}: {value}" for value in values if value.strip()]
