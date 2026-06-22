from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.ids import new_id
from app.models import (
    ActuationAttemptRecord,
    ActionEventRecord,
    AfferensRawEvent,
    AlertRecord,
    CareNoteRecord,
    DailyDiaryEntryRecord,
    DetectedObjectRecord,
    FamilyMessageRecord,
    HydrationEventRecord,
    HomeZoneRecord,
    LastSeenObjectRecord,
    ModelRunRecord,
    ObservationEnrichmentRecord,
    ObservationRecord,
    QueryRecord as QueryRecordModel,
    SemanticMemoryRecord,
    TaskEventRecord,
    TaskRecord,
    VerificationCheckRecord,
    WellnessCheckRecord,
)
from app.repositories import (
    DEFAULT_HOME_ZONE,
    DataRepository,
    _filter_semantic_items,
    _semantic_source_items,
    normalize_home_zone,
    object_location_assignment,
    reconcile_last_seen_status,
)
from app.schemas import (
    ActuationAttempt,
    ActuationState,
    ActionEvent,
    ActionEventType,
    Alert,
    AlertSeverity,
    AlertStatus,
    CareNote,
    CareNoteAudience,
    DailyDiaryEntry,
    DetectedObject,
    FamilyMessage,
    FamilyMessagePriority,
    FamilyMessageStatus,
    HydrationEvent,
    HydrationEventType,
    HomeRegion,
    HomeZone,
    HumanPresence,
    LastSeenObject,
    LastSeenStatus,
    ModelRun,
    ModelRunState,
    Observation,
    ObservationEnrichment,
    QueryConfidence,
    QueryLog,
    SemanticMemoryItem,
    SemanticMemorySourceType,
    Task,
    TaskState,
    TaskType,
    VerificationCheck,
    WellnessCheck,
    WellnessCheckStatus,
    WellnessCheckType,
    utc_now,
)


class SQLAlchemyDataRepository(DataRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def persist_raw_event(self, raw_event: dict[str, Any]) -> str:
        provider_event_id = self._first_text(raw_event, "entity_id", "id", "event_id", "eventId")
        if provider_event_id is not None:
            with self._session_factory() as session:
                existing = session.scalars(
                    select(AfferensRawEvent).where(
                        AfferensRawEvent.provider_event_id == provider_event_id
                    )
                ).first()
                if existing is not None:
                    return existing.id

        raw_event_id = new_id("aff")
        record = AfferensRawEvent(
            id=raw_event_id,
            provider_event_id=provider_event_id,
            timestamp_utc=self._first_datetime(raw_event, "timestamp_utc", "timestampUtc", "timestamp"),
            source_node_id=self._first_text(raw_event, "source_node_id", "sourceNodeId", "node_id", "nodeId"),
            modality=self._first_text(raw_event, "modality", "type", "sensor_modality"),
            classification=self._first_text(raw_event, "classification", "classifier"),
            confidence=self._first_float(raw_event, "confidence", "score"),
            raw_payload=raw_event,
            ingested_at=utc_now(),
        )
        with self._session_factory() as session:
            session.add(record)
            session.commit()
        return raw_event_id

    def persist_observation(self, observation: Observation) -> Observation:
        record = ObservationRecord(
            id=observation.id,
            raw_event_id=observation.raw_event_id,
            provider_event_id=observation.provider_event_id,
            timestamp_utc=observation.timestamp_utc,
            source=observation.source,
            source_node_id=observation.source_node_id,
            modality=observation.modality,
            classification=observation.classification,
            confidence=observation.confidence,
            room_id=observation.room_id,
            scene_summary=observation.scene_summary,
            human_presence=observation.human_presence.value,
            risk_signals=observation.risk_signals,
            evidence_metadata=observation.evidence_metadata,
            parser_version=str(observation.evidence_metadata.get("normalizer_version", "afferens-v1")),
            created_at=observation.created_at,
        )
        record.objects = [
            DetectedObjectRecord(
                id=detected.id or new_id("obj"),
                observation_id=observation.id,
                object_key=detected.object_key,
                label=detected.label,
                display_name=detected.display_name,
                confidence=detected.confidence,
                relative_location=detected.relative_location,
                bbox=detected.bbox,
                spatial_coords=detected.spatial_coords,
                source=detected.source,
                evidence_metadata=detected.evidence_metadata,
            )
            for detected in observation.objects
        ]
        with self._session_factory() as session:
            session.add(record)
            session.commit()
        return observation

    def upsert_last_seen_objects(
        self,
        observation: Observation,
        *,
        recent_window_seconds: int,
    ) -> list[LastSeenObject]:
        updated: list[LastSeenObject] = []
        seen_keys: set[str] = set()
        with self._session_factory() as session:
            for detected in observation.objects:
                seen_keys.add(detected.object_key)
                existing = session.get(LastSeenObjectRecord, detected.object_key)
                if existing and existing.last_seen_at > observation.timestamp_utc:
                    continue
                assignment = object_location_assignment(
                    detected=detected,
                    observation=observation,
                    zone=self._zone_for_observation(session, observation),
                )

                evidence_ids = list(existing.evidence_observation_ids) if existing else []
                if observation.id not in evidence_ids:
                    evidence_ids.append(observation.id)

                record = existing or LastSeenObjectRecord(object_key=detected.object_key)
                record.display_name = detected.display_name
                record.last_seen_at = observation.timestamp_utc
                record.last_seen_room = assignment.room_label
                record.last_seen_room_id = assignment.room_id
                record.last_seen_region_id = assignment.region_id
                record.last_seen_region_label = assignment.region_label
                record.last_seen_normalized_coords = assignment.normalized_coords
                record.location_assignment_source = assignment.source
                record.last_seen_relative_location = assignment.relative_location
                record.last_seen_observation_id = observation.id
                record.last_confidence = detected.confidence
                record.status = LastSeenStatus.VISIBLE_NOW.value
                record.evidence_observation_ids = evidence_ids
                record.updated_at = utc_now()
                session.add(record)
                updated.append(self._last_seen_from_record(record))

            latest_record = session.scalars(
                select(ObservationRecord)
                .order_by(desc(ObservationRecord.timestamp_utc))
                .limit(1)
            ).first()
            if latest_record is None or latest_record.id == observation.id:
                records = session.scalars(select(LastSeenObjectRecord)).all()
                for record in records:
                    if record.object_key in seen_keys:
                        continue
                    memory = self._last_seen_from_record(record)
                    next_status = reconcile_last_seen_status(
                        memory,
                        latest_observation=observation,
                        recent_window_seconds=recent_window_seconds,
                        reference_time=observation.timestamp_utc,
                    )
                    if record.status != next_status.value:
                        record.status = next_status.value
                        record.updated_at = utc_now()
                        updated.append(self._last_seen_from_record(record))
            session.commit()
        return updated

    def list_home_zones(self) -> list[HomeZone]:
        with self._session_factory() as session:
            self._ensure_default_home_zone(session)
            records = session.scalars(
                select(HomeZoneRecord).order_by(
                    HomeZoneRecord.is_default.desc(),
                    HomeZoneRecord.created_at,
                    HomeZoneRecord.name,
                )
            ).all()
            return [self._home_zone_from_record(record) for record in records]

    def create_home_zone(self, zone: HomeZone) -> HomeZone:
        zone = normalize_home_zone(zone)
        with self._session_factory() as session:
            self._ensure_default_home_zone(session)
            if zone.is_default:
                for existing in session.scalars(select(HomeZoneRecord)).all():
                    existing.is_default = False
            record = session.get(HomeZoneRecord, zone.id)
            if record is None:
                record = HomeZoneRecord(id=zone.id, created_at=zone.created_at)
            record.name = zone.name
            record.room_type = zone.room_type
            record.aliases = zone.aliases
            record.is_default = zone.is_default
            record.source_node_id = zone.source_node_id
            record.region_strategy = zone.region_strategy
            record.regions = [region.model_dump(mode="json") for region in zone.regions]
            record.metadata_json = zone.metadata
            session.add(record)
            session.flush()
            if not session.scalars(
                select(HomeZoneRecord).where(HomeZoneRecord.is_default.is_(True))
            ).first():
                record.is_default = True
            session.commit()
            return self._home_zone_from_record(record)

    def list_observations_for_date(self, activity_date: date) -> list[Observation]:
        start_at, end_at = self._day_bounds(activity_date)
        stmt = (
            select(ObservationRecord)
            .options(selectinload(ObservationRecord.objects))
            .where(ObservationRecord.timestamp_utc >= start_at)
            .where(ObservationRecord.timestamp_utc < end_at)
            .order_by(desc(ObservationRecord.timestamp_utc))
        )
        with self._session_factory() as session:
            return [self._observation_from_record(record) for record in session.scalars(stmt).all()]

    def create_task(self, task: Task) -> Task:
        with self._session_factory() as session:
            session.add(
                TaskRecord(
                    id=task.id,
                    type=task.type.value,
                    state=task.state.value,
                    title=task.title,
                    body=task.body,
                    recommended_action=task.recommended_action,
                    evidence_observation_ids=task.evidence_observation_ids,
                    metadata_json=task.metadata,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    resolved_at=task.resolved_at,
                )
            )
            session.commit()
        return task

    def create_query(self, query: QueryLog) -> QueryLog:
        with self._session_factory() as session:
            session.add(
                QueryRecordModel(
                    id=query.id,
                    query_text=query.query_text,
                    session_id=query.session_id,
                    intent=query.intent.value if query.intent else None,
                    answer=query.answer,
                    confidence=query.confidence.value if query.confidence else None,
                    evidence_observation_ids=query.evidence_observation_ids,
                    task_id=query.task_id,
                    provider=query.provider,
                    created_at=query.created_at,
                )
            )
            session.commit()
        return query

    def create_alert(self, alert: Alert) -> Alert:
        with self._session_factory() as session:
            session.add(
                AlertRecord(
                    id=alert.id,
                    task_id=alert.task_id,
                    hazard_type=alert.hazard_type,
                    severity=alert.severity.value,
                    title=alert.title,
                    body=alert.body,
                    recommended_action=alert.recommended_action,
                    status=alert.status.value,
                    evidence_observation_ids=alert.evidence_observation_ids,
                    created_at=alert.created_at,
                    acknowledged_at=alert.acknowledged_at,
                )
            )
            session.commit()
        return alert

    def create_actuation_attempt(self, attempt: ActuationAttempt) -> ActuationAttempt:
        with self._session_factory() as session:
            session.add(
                ActuationAttemptRecord(
                    id=attempt.id,
                    task_id=attempt.task_id,
                    alert_id=attempt.alert_id,
                    provider=attempt.provider,
                    state=attempt.state.value,
                    message=attempt.message,
                    request_payload=attempt.request_payload,
                    response_payload=attempt.response_payload,
                    evidence_observation_ids=attempt.evidence_observation_ids,
                    created_at=attempt.created_at,
                )
            )
            session.commit()
        return attempt

    def list_actuation_attempts_for_date(self, activity_date: date) -> list[ActuationAttempt]:
        start_at, end_at = self._day_bounds(activity_date)
        stmt = (
            select(ActuationAttemptRecord)
            .where(ActuationAttemptRecord.created_at >= start_at)
            .where(ActuationAttemptRecord.created_at < end_at)
            .order_by(desc(ActuationAttemptRecord.created_at))
        )
        with self._session_factory() as session:
            return [self._actuation_from_record(record) for record in session.scalars(stmt).all()]

    def get_daily_diary(self, entry_date: date) -> DailyDiaryEntry | None:
        stmt = (
            select(DailyDiaryEntryRecord)
            .where(DailyDiaryEntryRecord.entry_date == entry_date)
            .order_by(desc(DailyDiaryEntryRecord.generated_at))
            .limit(1)
        )
        with self._session_factory() as session:
            record = session.scalars(stmt).first()
            return self._diary_from_record(record) if record else None

    def upsert_daily_diary(self, diary: DailyDiaryEntry) -> DailyDiaryEntry:
        with self._session_factory() as session:
            record = session.scalars(
                select(DailyDiaryEntryRecord)
                .where(DailyDiaryEntryRecord.entry_date == diary.date)
                .where(DailyDiaryEntryRecord.source == diary.source)
            ).first()
            if record is None:
                record = DailyDiaryEntryRecord(
                    id=diary.id,
                    entry_date=diary.date,
                    summary=diary.summary,
                    highlights=diary.highlights,
                    needs_review=diary.needs_review,
                    evidence_ids=diary.evidence_ids,
                    generated_at=diary.generated_at,
                    source=diary.source,
                )
                session.add(record)
            else:
                record.summary = diary.summary
                record.highlights = diary.highlights
                record.needs_review = diary.needs_review
                record.evidence_ids = diary.evidence_ids
                record.generated_at = diary.generated_at
            session.commit()
        return diary

    def list_care_notes(self, note_date: date) -> list[CareNote]:
        stmt = (
            select(CareNoteRecord)
            .where(CareNoteRecord.note_date == note_date)
            .order_by(desc(CareNoteRecord.created_at))
        )
        with self._session_factory() as session:
            return [self._care_note_from_record(record) for record in session.scalars(stmt).all()]

    def create_care_note(self, note: CareNote) -> CareNote:
        with self._session_factory() as session:
            session.add(
                CareNoteRecord(
                    id=note.id,
                    note_date=note.date,
                    audience=note.audience.value,
                    summary=note.summary,
                    bullets=note.bullets,
                    risks=note.risks,
                    follow_ups=note.follow_ups,
                    evidence_ids=note.evidence_ids,
                    created_at=note.created_at,
                    source=note.source,
                )
            )
            session.commit()
        return note

    def list_family_messages(
        self,
        *,
        include_acknowledged: bool = False,
    ) -> list[FamilyMessage]:
        stmt = select(FamilyMessageRecord).order_by(desc(FamilyMessageRecord.created_at))
        if not include_acknowledged:
            stmt = stmt.where(FamilyMessageRecord.status != FamilyMessageStatus.ACKNOWLEDGED.value)
        with self._session_factory() as session:
            return [self._family_message_from_record(record) for record in session.scalars(stmt).all()]

    def create_family_message(self, message: FamilyMessage) -> FamilyMessage:
        with self._session_factory() as session:
            session.add(
                FamilyMessageRecord(
                    id=message.id,
                    title=message.title,
                    body=message.body,
                    priority=message.priority.value,
                    status=message.status.value,
                    trigger_object_key=message.trigger_object_key,
                    trigger_zone_id=message.trigger_zone_id,
                    starts_at=message.starts_at,
                    expires_at=message.expires_at,
                    created_at=message.created_at,
                    acknowledged_at=message.acknowledged_at,
                    metadata_json=message.metadata,
                )
            )
            session.commit()
        return message

    def get_family_message(self, message_id: str) -> FamilyMessage | None:
        with self._session_factory() as session:
            record = session.get(FamilyMessageRecord, message_id)
            return self._family_message_from_record(record) if record else None

    def update_family_message(self, message: FamilyMessage) -> FamilyMessage:
        with self._session_factory() as session:
            record = session.get(FamilyMessageRecord, message.id)
            if record is None:
                session.add(
                    FamilyMessageRecord(
                        id=message.id,
                        title=message.title,
                        body=message.body,
                        priority=message.priority.value,
                        status=message.status.value,
                        trigger_object_key=message.trigger_object_key,
                        trigger_zone_id=message.trigger_zone_id,
                        starts_at=message.starts_at,
                        expires_at=message.expires_at,
                        created_at=message.created_at,
                        acknowledged_at=message.acknowledged_at,
                        metadata_json=message.metadata,
                    )
                )
            else:
                record.title = message.title
                record.body = message.body
                record.priority = message.priority.value
                record.status = message.status.value
                record.trigger_object_key = message.trigger_object_key
                record.trigger_zone_id = message.trigger_zone_id
                record.starts_at = message.starts_at
                record.expires_at = message.expires_at
                record.acknowledged_at = message.acknowledged_at
                record.metadata_json = message.metadata
            session.commit()
        return message

    def list_hydration_events_for_date(self, event_date: date) -> list[HydrationEvent]:
        start_at, end_at = self._day_bounds(event_date)
        stmt = (
            select(HydrationEventRecord)
            .where(HydrationEventRecord.occurred_at >= start_at)
            .where(HydrationEventRecord.occurred_at < end_at)
            .order_by(desc(HydrationEventRecord.occurred_at))
        )
        with self._session_factory() as session:
            return [
                self._hydration_event_from_record(record)
                for record in session.scalars(stmt).all()
            ]

    def create_hydration_event(self, event: HydrationEvent) -> HydrationEvent:
        with self._session_factory() as session:
            session.add(
                HydrationEventRecord(
                    id=event.id,
                    type=event.type.value,
                    occurred_at=event.occurred_at,
                    confidence=event.confidence.value,
                    zone_id=event.zone_id,
                    zone_name=event.zone_name,
                    evidence_ids=event.evidence_ids,
                    metadata_json=event.metadata,
                )
            )
            session.commit()
        return event

    def create_action_event(self, event: ActionEvent) -> ActionEvent:
        with self._session_factory() as session:
            session.add(
                ActionEventRecord(
                    id=event.id,
                    type=event.type.value,
                    occurred_at=event.occurred_at,
                    confidence=event.confidence.value,
                    score=event.score,
                    source=event.source,
                    source_node_id=event.source_node_id,
                    zone_id=event.zone_id,
                    zone_name=event.zone_name,
                    evidence_ids=event.evidence_ids,
                    metadata_json=event.metadata,
                    created_at=event.created_at,
                )
            )
            session.commit()
        return event

    def list_action_events(
        self,
        *,
        event_date: date | None = None,
        event_type: ActionEventType | None = None,
        limit: int = 50,
    ) -> list[ActionEvent]:
        stmt: Select[tuple[ActionEventRecord]] = select(ActionEventRecord).order_by(
            desc(ActionEventRecord.occurred_at)
        )
        if event_date is not None:
            start_at, end_at = self._day_bounds(event_date)
            stmt = stmt.where(ActionEventRecord.occurred_at >= start_at).where(
                ActionEventRecord.occurred_at < end_at
            )
        if event_type is not None:
            stmt = stmt.where(ActionEventRecord.type == event_type.value)
        stmt = stmt.limit(limit)
        with self._session_factory() as session:
            return [
                self._action_event_from_record(record)
                for record in session.scalars(stmt).all()
            ]

    def list_wellness_checks_for_date(self, check_date: date) -> list[WellnessCheck]:
        start_at, end_at = self._day_bounds(check_date)
        stmt = (
            select(WellnessCheckRecord)
            .where(WellnessCheckRecord.occurred_at >= start_at)
            .where(WellnessCheckRecord.occurred_at < end_at)
            .order_by(desc(WellnessCheckRecord.created_at))
        )
        with self._session_factory() as session:
            return [
                self._wellness_check_from_record(record)
                for record in session.scalars(stmt).all()
            ]

    def create_wellness_check(self, check: WellnessCheck) -> WellnessCheck:
        with self._session_factory() as session:
            session.add(
                WellnessCheckRecord(
                    id=check.id,
                    type=check.type.value,
                    severity=check.severity.value,
                    status=check.status.value,
                    title=check.title,
                    body=check.body,
                    confidence=check.confidence.value,
                    occurred_at=check.occurred_at,
                    created_at=check.created_at,
                    acknowledged_at=check.acknowledged_at,
                    zone_id=check.zone_id,
                    zone_name=check.zone_name,
                    evidence_ids=check.evidence_ids,
                    metadata_json=check.metadata,
                )
            )
            session.commit()
        return check

    def get_wellness_check(self, check_id: str) -> WellnessCheck | None:
        with self._session_factory() as session:
            record = session.get(WellnessCheckRecord, check_id)
            return self._wellness_check_from_record(record) if record else None

    def update_wellness_check(self, check: WellnessCheck) -> WellnessCheck:
        with self._session_factory() as session:
            record = session.get(WellnessCheckRecord, check.id)
            if record is None:
                session.add(
                    WellnessCheckRecord(
                        id=check.id,
                        type=check.type.value,
                        severity=check.severity.value,
                        status=check.status.value,
                        title=check.title,
                        body=check.body,
                        confidence=check.confidence.value,
                        occurred_at=check.occurred_at,
                        created_at=check.created_at,
                        acknowledged_at=check.acknowledged_at,
                        zone_id=check.zone_id,
                        zone_name=check.zone_name,
                        evidence_ids=check.evidence_ids,
                        metadata_json=check.metadata,
                    )
                )
            else:
                record.type = check.type.value
                record.severity = check.severity.value
                record.status = check.status.value
                record.title = check.title
                record.body = check.body
                record.confidence = check.confidence.value
                record.occurred_at = check.occurred_at
                record.created_at = check.created_at
                record.acknowledged_at = check.acknowledged_at
                record.zone_id = check.zone_id
                record.zone_name = check.zone_name
                record.evidence_ids = check.evidence_ids
                record.metadata_json = check.metadata
            session.commit()
        return check

    def list_semantic_source_items(
        self,
        *,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> list[SemanticMemoryItem]:
        with self._session_factory() as session:
            observations = [
                self._observation_from_record(record)
                for record in session.scalars(
                    select(ObservationRecord).options(selectinload(ObservationRecord.objects))
                ).all()
            ]
            last_seen = [
                self._last_seen_from_record(record)
                for record in session.scalars(select(LastSeenObjectRecord)).all()
            ]
            diary_entries = [
                self._diary_from_record(record)
                for record in session.scalars(select(DailyDiaryEntryRecord)).all()
            ]
            care_notes = [
                self._care_note_from_record(record)
                for record in session.scalars(select(CareNoteRecord)).all()
            ]
            family_messages = [
                self._family_message_from_record(record)
                for record in session.scalars(select(FamilyMessageRecord)).all()
            ]
            hydration_events = [
                self._hydration_event_from_record(record)
                for record in session.scalars(select(HydrationEventRecord)).all()
            ]
            wellness_checks = [
                self._wellness_check_from_record(record)
                for record in session.scalars(select(WellnessCheckRecord)).all()
            ]
        items = _semantic_source_items(
            observations=observations,
            last_seen=last_seen,
            diary_entries=diary_entries,
            care_notes=care_notes,
            family_messages=family_messages,
            hydration_events=hydration_events,
            wellness_checks=wellness_checks,
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
        with self._session_factory() as session:
            for item in items:
                record = session.get(SemanticMemoryRecord, item.id)
                if record is None:
                    session.add(self._semantic_record_from_item(item))
                    created += 1
                    continue
                if not force and self._semantic_record_matches(record, item):
                    skipped += 1
                    continue
                record.source_type = item.source_type.value
                record.source_id = item.source_id
                record.title = item.title
                record.text = item.text
                record.occurred_at = item.occurred_at
                record.evidence_ids = item.evidence_ids
                record.source_ids = item.source_ids
                record.metadata_json = item.metadata
                record.embedding = item.embedding
                record.updated_at = utc_now()
                updated += 1
            session.commit()
        return created, updated, skipped

    def list_semantic_memory_items(
        self,
        *,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> list[SemanticMemoryItem]:
        stmt: Select[tuple[SemanticMemoryRecord]] = select(SemanticMemoryRecord).order_by(
            desc(SemanticMemoryRecord.occurred_at),
            desc(SemanticMemoryRecord.created_at),
        )
        if source_types:
            stmt = stmt.where(
                SemanticMemoryRecord.source_type.in_([source_type.value for source_type in source_types])
            )
        with self._session_factory() as session:
            return [
                self._semantic_item_from_record(record)
                for record in session.scalars(stmt).all()
            ]

    def create_model_run(
        self,
        model_run: ModelRun,
        *,
        observation_id: str | None,
        purpose: str,
        focus: str,
    ) -> ModelRun:
        with self._session_factory() as session:
            session.add(
                ModelRunRecord(
                    id=model_run.id,
                    observation_id=observation_id,
                    provider=model_run.provider,
                    model=model_run.model,
                    purpose=purpose,
                    focus=focus,
                    state=model_run.state.value,
                    started_at=model_run.started_at,
                    completed_at=model_run.completed_at,
                    latency_ms=model_run.latency_ms,
                    error_message=model_run.error_message,
                )
            )
            session.commit()
        return model_run

    def create_observation_enrichment(
        self,
        enrichment: ObservationEnrichment,
        *,
        model_run_id: str | None = None,
    ) -> ObservationEnrichment:
        with self._session_factory() as session:
            session.add(
                ObservationEnrichmentRecord(
                    id=enrichment.id,
                    observation_id=enrichment.observation_id,
                    model_run_id=model_run_id,
                    source_provider=enrichment.source_provider,
                    source_model=enrichment.source_model,
                    summary=enrichment.summary,
                    label_suggestions=[
                        item.model_dump(mode="json") for item in enrichment.label_suggestions
                    ],
                    safety_notes=enrichment.safety_notes,
                    spatial_notes=enrichment.spatial_notes,
                    evidence_observation_ids=enrichment.evidence_observation_ids,
                    created_at=enrichment.created_at,
                )
            )
            session.commit()
        return enrichment

    def get_task(self, task_id: str) -> Task | None:
        with self._session_factory() as session:
            record = session.get(TaskRecord, task_id)
            return self._task_from_record(record) if record else None

    def update_task(self, task: Task) -> Task:
        with self._session_factory() as session:
            record = session.get(TaskRecord, task.id)
            if record is None:
                session.add(
                    TaskRecord(
                        id=task.id,
                        type=task.type.value,
                        state=task.state.value,
                        title=task.title,
                        body=task.body,
                        recommended_action=task.recommended_action,
                        evidence_observation_ids=task.evidence_observation_ids,
                        metadata_json=task.metadata,
                        created_at=task.created_at,
                        updated_at=task.updated_at,
                        resolved_at=task.resolved_at,
                    )
                )
            else:
                record.type = task.type.value
                record.state = task.state.value
                record.title = task.title
                record.body = task.body
                record.recommended_action = task.recommended_action
                record.evidence_observation_ids = task.evidence_observation_ids
                record.metadata_json = task.metadata
                record.updated_at = task.updated_at
                record.resolved_at = task.resolved_at
            session.commit()
        return task

    def add_task_event(
        self,
        *,
        task_id: str,
        event_type: str,
        message: str,
        evidence_observation_ids: list[str] | None = None,
    ) -> None:
        with self._session_factory() as session:
            session.add(
                TaskEventRecord(
                    id=new_id("taskevt"),
                    task_id=task_id,
                    event_type=event_type,
                    message=message,
                    evidence_observation_ids=list(evidence_observation_ids or []),
                    created_at=utc_now(),
                )
            )
            session.commit()

    def find_open_object_recovery_task(self, object_key: str) -> Task | None:
        open_states = {
            TaskState.OPEN.value,
            TaskState.WAITING_FOR_HUMAN.value,
            TaskState.VERIFICATION_PENDING.value,
            TaskState.FAILED_VERIFICATION.value,
        }
        stmt = (
            select(TaskRecord)
            .where(TaskRecord.type == TaskType.OBJECT_RECOVERY.value)
            .where(TaskRecord.state.in_(open_states))
            .order_by(desc(TaskRecord.created_at))
        )
        with self._session_factory() as session:
            for record in session.scalars(stmt).all():
                if (record.metadata_json or {}).get("object_key") == object_key:
                    return self._task_from_record(record)
        return None

    def create_verification_check(self, check: VerificationCheck) -> VerificationCheck:
        with self._session_factory() as session:
            session.add(
                VerificationCheckRecord(
                    id=check.id,
                    task_id=check.task_id,
                    observation_id=check.observation_id,
                    state=check.state.value,
                    message=check.message,
                    evidence_observation_ids=check.evidence_observation_ids,
                    created_at=check.created_at,
                )
            )
            session.commit()
        return check

    def list_alerts(self, *, status: AlertStatus | None = None) -> list[Alert]:
        stmt: Select[tuple[AlertRecord]] = select(AlertRecord).order_by(desc(AlertRecord.created_at))
        if status is not None:
            stmt = stmt.where(AlertRecord.status == status.value)
        with self._session_factory() as session:
            return [self._alert_from_record(record) for record in session.scalars(stmt).all()]

    def get_alert(self, alert_id: str) -> Alert | None:
        with self._session_factory() as session:
            record = session.get(AlertRecord, alert_id)
            return self._alert_from_record(record) if record else None

    def update_alert(self, alert: Alert) -> Alert:
        with self._session_factory() as session:
            record = session.get(AlertRecord, alert.id)
            if record is None:
                session.add(
                    AlertRecord(
                        id=alert.id,
                        task_id=alert.task_id,
                        hazard_type=alert.hazard_type,
                        severity=alert.severity.value,
                        title=alert.title,
                        body=alert.body,
                        recommended_action=alert.recommended_action,
                        status=alert.status.value,
                        evidence_observation_ids=alert.evidence_observation_ids,
                        created_at=alert.created_at,
                        acknowledged_at=alert.acknowledged_at,
                    )
                )
            else:
                record.task_id = alert.task_id
                record.hazard_type = alert.hazard_type
                record.severity = alert.severity.value
                record.title = alert.title
                record.body = alert.body
                record.recommended_action = alert.recommended_action
                record.status = alert.status.value
                record.evidence_observation_ids = alert.evidence_observation_ids
                record.acknowledged_at = alert.acknowledged_at
            session.commit()
        return alert

    def latest_observation(self) -> Observation | None:
        stmt = (
            select(ObservationRecord)
            .options(selectinload(ObservationRecord.objects))
            .order_by(desc(ObservationRecord.timestamp_utc))
            .limit(1)
        )
        with self._session_factory() as session:
            record = session.scalars(stmt).first()
            return self._observation_from_record(record) if record else None

    def latest_enrichment(self) -> ObservationEnrichment | None:
        stmt = (
            select(ObservationEnrichmentRecord)
            .order_by(desc(ObservationEnrichmentRecord.created_at))
            .limit(1)
        )
        with self._session_factory() as session:
            record = session.scalars(stmt).first()
            return self._enrichment_from_record(record) if record else None

    def list_last_seen_objects(
        self,
        *,
        recent_window_seconds: int = 300,
    ) -> list[LastSeenObject]:
        with self._session_factory() as session:
            latest_record = session.scalars(
                select(ObservationRecord)
                .options(selectinload(ObservationRecord.objects))
                .order_by(desc(ObservationRecord.timestamp_utc))
                .limit(1)
            ).first()
            latest = self._observation_from_record(latest_record) if latest_record else None
            records = session.scalars(
                select(LastSeenObjectRecord).order_by(desc(LastSeenObjectRecord.last_seen_at))
            ).all()
            objects: list[LastSeenObject] = []
            for record in records:
                memory = self._last_seen_from_record(record)
                next_status = reconcile_last_seen_status(
                    memory,
                    latest_observation=latest,
                    recent_window_seconds=recent_window_seconds,
                )
                if record.status != next_status.value:
                    record.status = next_status.value
                    record.updated_at = utc_now()
                    memory = memory.model_copy(
                        update={"status": next_status, "updated_at": record.updated_at}
                    )
                else:
                    memory = memory.model_copy(update={"status": next_status})
                objects.append(memory)
            session.commit()
            return objects

    def list_tasks(
        self,
        *,
        state: TaskState | None = None,
        task_type: TaskType | None = None,
    ) -> list[Task]:
        stmt: Select[tuple[TaskRecord]] = select(TaskRecord).order_by(desc(TaskRecord.created_at))
        if state is not None:
            stmt = stmt.where(TaskRecord.state == state.value)
        if task_type is not None:
            stmt = stmt.where(TaskRecord.type == task_type.value)
        with self._session_factory() as session:
            return [self._task_from_record(record) for record in session.scalars(stmt).all()]

    @staticmethod
    def _observation_from_record(record: ObservationRecord) -> Observation:
        return Observation(
            id=record.id,
            raw_event_id=record.raw_event_id,
            provider_event_id=record.provider_event_id,
            timestamp_utc=record.timestamp_utc,
            source=record.source,
            source_node_id=record.source_node_id,
            modality=record.modality,
            classification=record.classification,
            confidence=record.confidence,
            room_id=record.room_id,
            scene_summary=record.scene_summary,
            human_presence=HumanPresence(record.human_presence),
            objects=[
                DetectedObject(
                    id=obj.id,
                    object_key=obj.object_key,
                    label=obj.label,
                    display_name=obj.display_name,
                    confidence=obj.confidence,
                    relative_location=obj.relative_location,
                    bbox=obj.bbox,
                    spatial_coords=obj.spatial_coords,
                    source=obj.source,
                    evidence_metadata=obj.evidence_metadata,
                )
                for obj in record.objects
            ],
            risk_signals=record.risk_signals,
            evidence_metadata=record.evidence_metadata,
            created_at=record.created_at,
        )

    @staticmethod
    def _last_seen_from_record(record: LastSeenObjectRecord) -> LastSeenObject:
        return LastSeenObject(
            object_key=record.object_key,
            display_name=record.display_name,
            last_seen_at=record.last_seen_at,
            last_seen_room=record.last_seen_room,
            last_seen_room_id=record.last_seen_room_id,
            last_seen_region_id=record.last_seen_region_id,
            last_seen_region_label=record.last_seen_region_label,
            last_seen_normalized_coords=record.last_seen_normalized_coords,
            location_assignment_source=record.location_assignment_source or "observation_room",
            last_seen_relative_location=record.last_seen_relative_location,
            last_seen_observation_id=record.last_seen_observation_id,
            last_confidence=record.last_confidence,
            status=LastSeenStatus(record.status),
            evidence_observation_ids=record.evidence_observation_ids,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _home_zone_from_record(record: HomeZoneRecord) -> HomeZone:
        regions = [HomeRegion.model_validate(region) for region in (record.regions or [])]
        return normalize_home_zone(
            HomeZone(
                id=record.id,
                name=record.name,
                room_type=record.room_type,
                aliases=record.aliases,
                is_default=record.is_default,
                source_node_id=record.source_node_id,
                region_strategy=record.region_strategy or "none",
                regions=regions,
                metadata=record.metadata_json or {},
                created_at=record.created_at,
            )
        )

    @staticmethod
    def _diary_from_record(record: DailyDiaryEntryRecord) -> DailyDiaryEntry:
        return DailyDiaryEntry(
            id=record.id,
            date=record.entry_date,
            summary=record.summary,
            highlights=record.highlights,
            needs_review=record.needs_review,
            evidence_ids=record.evidence_ids,
            generated_at=record.generated_at,
            source=record.source,
        )

    @staticmethod
    def _care_note_from_record(record: CareNoteRecord) -> CareNote:
        return CareNote(
            id=record.id,
            date=record.note_date,
            audience=CareNoteAudience(record.audience),
            summary=record.summary,
            bullets=record.bullets,
            risks=record.risks,
            follow_ups=record.follow_ups,
            evidence_ids=record.evidence_ids,
            created_at=record.created_at,
            source=record.source,
        )

    @staticmethod
    def _family_message_from_record(record: FamilyMessageRecord) -> FamilyMessage:
        return FamilyMessage(
            id=record.id,
            title=record.title,
            body=record.body,
            priority=FamilyMessagePriority(record.priority),
            status=FamilyMessageStatus(record.status),
            trigger_object_key=record.trigger_object_key,
            trigger_zone_id=record.trigger_zone_id,
            starts_at=record.starts_at,
            expires_at=record.expires_at,
            created_at=record.created_at,
            acknowledged_at=record.acknowledged_at,
            metadata=record.metadata_json or {},
        )

    @staticmethod
    def _hydration_event_from_record(record: HydrationEventRecord) -> HydrationEvent:
        return HydrationEvent(
            id=record.id,
            type=HydrationEventType(record.type),
            occurred_at=record.occurred_at,
            confidence=QueryConfidence(record.confidence),
            zone_id=record.zone_id,
            zone_name=record.zone_name,
            evidence_ids=record.evidence_ids,
            metadata=record.metadata_json or {},
        )

    @staticmethod
    def _action_event_from_record(record: ActionEventRecord) -> ActionEvent:
        return ActionEvent(
            id=record.id,
            type=ActionEventType(record.type),
            occurred_at=record.occurred_at,
            confidence=QueryConfidence(record.confidence),
            score=record.score,
            source=record.source,
            source_node_id=record.source_node_id,
            zone_id=record.zone_id,
            zone_name=record.zone_name,
            evidence_ids=record.evidence_ids,
            metadata=record.metadata_json or {},
            created_at=record.created_at,
        )

    @staticmethod
    def _wellness_check_from_record(record: WellnessCheckRecord) -> WellnessCheck:
        return WellnessCheck(
            id=record.id,
            type=WellnessCheckType(record.type),
            severity=AlertSeverity(record.severity),
            status=WellnessCheckStatus(record.status),
            title=record.title,
            body=record.body,
            confidence=QueryConfidence(record.confidence),
            occurred_at=record.occurred_at,
            created_at=record.created_at,
            acknowledged_at=record.acknowledged_at,
            zone_id=record.zone_id,
            zone_name=record.zone_name,
            evidence_ids=record.evidence_ids,
            metadata=record.metadata_json or {},
        )

    def _zone_for_observation(
        self,
        session: Session,
        observation: Observation,
    ) -> HomeZone | None:
        direct = session.get(HomeZoneRecord, observation.room_id)
        if direct is not None and direct.id != DEFAULT_HOME_ZONE.id:
            return self._home_zone_from_record(direct)
        if observation.source_node_id:
            node_record = session.scalars(
                select(HomeZoneRecord)
                .where(HomeZoneRecord.source_node_id == observation.source_node_id)
                .limit(1)
            ).first()
            if node_record is not None:
                return self._home_zone_from_record(node_record)
        if direct is not None:
            return self._home_zone_from_record(direct)
        return None

    @staticmethod
    def _ensure_default_home_zone(session: Session) -> None:
        existing_default = session.scalars(
            select(HomeZoneRecord).where(HomeZoneRecord.is_default.is_(True))
        ).first()
        existing_builtin = session.get(HomeZoneRecord, DEFAULT_HOME_ZONE.id)
        if existing_default is not None:
            return
        if existing_builtin is not None:
            existing_builtin.is_default = True
            session.flush()
            return
        session.add(
            HomeZoneRecord(
                id=DEFAULT_HOME_ZONE.id,
                name=DEFAULT_HOME_ZONE.name,
                room_type=DEFAULT_HOME_ZONE.room_type,
                aliases=DEFAULT_HOME_ZONE.aliases,
                is_default=True,
                source_node_id=DEFAULT_HOME_ZONE.source_node_id,
                region_strategy=DEFAULT_HOME_ZONE.region_strategy,
                regions=[region.model_dump(mode="json") for region in DEFAULT_HOME_ZONE.regions],
                metadata_json=DEFAULT_HOME_ZONE.metadata,
                created_at=DEFAULT_HOME_ZONE.created_at,
            )
        )
        session.flush()

    @staticmethod
    def _task_from_record(record: TaskRecord) -> Task:
        return Task(
            id=record.id,
            type=TaskType(record.type),
            state=TaskState(record.state),
            title=record.title,
            body=record.body,
            recommended_action=record.recommended_action,
            evidence_observation_ids=record.evidence_observation_ids,
            metadata=record.metadata_json or {},
            created_at=record.created_at,
            updated_at=record.updated_at,
            resolved_at=record.resolved_at,
        )

    @staticmethod
    def _alert_from_record(record: AlertRecord) -> Alert:
        return Alert(
            id=record.id,
            task_id=record.task_id,
            hazard_type=record.hazard_type,
            severity=AlertSeverity(record.severity),
            title=record.title,
            body=record.body,
            recommended_action=record.recommended_action,
            status=AlertStatus(record.status),
            evidence_observation_ids=record.evidence_observation_ids,
            created_at=record.created_at,
            acknowledged_at=record.acknowledged_at,
        )

    @staticmethod
    def _actuation_from_record(record: ActuationAttemptRecord) -> ActuationAttempt:
        request_payload = record.request_payload or {}
        return ActuationAttempt(
            id=record.id,
            task_id=record.task_id,
            alert_id=record.alert_id,
            provider=record.provider,
            command_type=str(request_payload.get("command_type", "UNKNOWN")),
            state=ActuationState(record.state),
            message=record.message,
            request_payload=record.request_payload,
            response_payload=record.response_payload,
            evidence_observation_ids=record.evidence_observation_ids,
            created_at=record.created_at,
        )

    @staticmethod
    def _model_run_from_record(record: ModelRunRecord) -> ModelRun:
        return ModelRun(
            id=record.id,
            provider=record.provider,
            model=record.model,
            state=ModelRunState(record.state),
            started_at=record.started_at,
            completed_at=record.completed_at,
            latency_ms=record.latency_ms,
            error_message=record.error_message,
        )

    @staticmethod
    def _enrichment_from_record(record: ObservationEnrichmentRecord) -> ObservationEnrichment:
        return ObservationEnrichment(
            id=record.id,
            observation_id=record.observation_id,
            source_provider=record.source_provider,
            source_model=record.source_model,
            summary=record.summary,
            label_suggestions=record.label_suggestions,
            safety_notes=record.safety_notes,
            spatial_notes=record.spatial_notes,
            evidence_observation_ids=record.evidence_observation_ids,
            created_at=record.created_at,
        )

    @staticmethod
    def _semantic_item_from_record(record: SemanticMemoryRecord) -> SemanticMemoryItem:
        return SemanticMemoryItem(
            id=record.id,
            source_type=SemanticMemorySourceType(record.source_type),
            source_id=record.source_id,
            title=record.title,
            text=record.text,
            occurred_at=record.occurred_at,
            created_at=record.created_at,
            evidence_ids=record.evidence_ids,
            source_ids=record.source_ids,
            metadata=record.metadata_json or {},
            embedding=record.embedding,
        )

    @staticmethod
    def _semantic_record_from_item(item: SemanticMemoryItem) -> SemanticMemoryRecord:
        now = utc_now()
        return SemanticMemoryRecord(
            id=item.id,
            source_type=item.source_type.value,
            source_id=item.source_id,
            title=item.title,
            text=item.text,
            occurred_at=item.occurred_at,
            created_at=item.created_at,
            evidence_ids=item.evidence_ids,
            source_ids=item.source_ids,
            metadata_json=item.metadata,
            embedding=item.embedding,
            updated_at=now,
        )

    @staticmethod
    def _semantic_record_matches(
        record: SemanticMemoryRecord,
        item: SemanticMemoryItem,
    ) -> bool:
        return (
            record.source_type == item.source_type.value
            and record.source_id == item.source_id
            and record.title == item.title
            and record.text == item.text
            and record.occurred_at == item.occurred_at
            and record.evidence_ids == item.evidence_ids
            and record.source_ids == item.source_ids
            and (record.metadata_json or {}) == item.metadata
            and record.embedding == item.embedding
        )

    @staticmethod
    def _day_bounds(activity_date: date) -> tuple[datetime, datetime]:
        start_at = datetime.combine(activity_date, time.min, tzinfo=timezone.utc)
        end_at = start_at + timedelta(days=1)
        return start_at, end_at

    @staticmethod
    def _first_text(payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _first_float(payload: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool) or value is None:
                continue
            try:
                return max(0.0, min(float(value), 1.0))
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _first_datetime(payload: dict[str, Any], *keys: str) -> datetime | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, datetime):
                return value
            if isinstance(value, str) and value.strip():
                normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
                try:
                    return datetime.fromisoformat(normalized)
                except ValueError:
                    continue
        return None
