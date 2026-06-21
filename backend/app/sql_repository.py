from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.ids import new_id
from app.models import (
    AfferensRawEvent,
    AlertRecord,
    DetectedObjectRecord,
    LastSeenObjectRecord,
    ObservationRecord,
    TaskRecord,
)
from app.repositories import DataRepository
from app.schemas import (
    Alert,
    AlertSeverity,
    AlertStatus,
    DetectedObject,
    HumanPresence,
    LastSeenObject,
    LastSeenStatus,
    Observation,
    Task,
    TaskState,
    TaskType,
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

    def upsert_last_seen_objects(self, observation: Observation) -> list[LastSeenObject]:
        updated: list[LastSeenObject] = []
        with self._session_factory() as session:
            for detected in observation.objects:
                existing = session.get(LastSeenObjectRecord, detected.object_key)
                if existing and existing.last_seen_at > observation.timestamp_utc:
                    continue

                evidence_ids = list(existing.evidence_observation_ids) if existing else []
                if observation.id not in evidence_ids:
                    evidence_ids.append(observation.id)

                record = existing or LastSeenObjectRecord(object_key=detected.object_key)
                record.display_name = detected.display_name
                record.last_seen_at = observation.timestamp_utc
                record.last_seen_room = observation.room_id
                record.last_seen_relative_location = detected.relative_location
                record.last_seen_observation_id = observation.id
                record.last_confidence = detected.confidence
                record.status = LastSeenStatus.VISIBLE_NOW.value
                record.evidence_observation_ids = evidence_ids
                record.updated_at = utc_now()
                session.add(record)
                updated.append(self._last_seen_from_record(record))
            session.commit()
        return updated

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
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    resolved_at=task.resolved_at,
                )
            )
            session.commit()
        return task

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

    def list_last_seen_objects(self) -> list[LastSeenObject]:
        with self._session_factory() as session:
            records = session.scalars(
                select(LastSeenObjectRecord).order_by(desc(LastSeenObjectRecord.last_seen_at))
            ).all()
            return [self._last_seen_from_record(record) for record in records]

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
            last_seen_relative_location=record.last_seen_relative_location,
            last_seen_observation_id=record.last_seen_observation_id,
            last_confidence=record.last_confidence,
            status=LastSeenStatus(record.status),
            evidence_observation_ids=record.evidence_observation_ids,
            updated_at=record.updated_at,
        )

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
            created_at=record.created_at,
            updated_at=record.updated_at,
            resolved_at=record.resolved_at,
        )

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
