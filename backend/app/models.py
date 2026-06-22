from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: Any) -> str:
        return f"vector({self.dimensions})"

    def bind_processor(self, dialect: Any):
        if dialect.name == "postgresql":
            return None

        def process(value: Any) -> str | None:
            if value is None:
                return None
            return json.dumps(value)

        return process

    def result_processor(self, dialect: Any, coltype: Any):
        if dialect.name == "postgresql":
            return None

        def process(value: Any) -> Any:
            if value is None or not isinstance(value, str):
                return value
            return json.loads(value)

        return process


json_type = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class AfferensRawEvent(Base):
    __tablename__ = "afferens_raw_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), index=True)
    timestamp_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    source_node_id: Mapped[str | None] = mapped_column(String(255), index=True)
    modality: Mapped[str | None] = mapped_column(String(64), index=True)
    classification: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[float | None] = mapped_column(Float)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    observations: Mapped[list[ObservationRecord]] = relationship(back_populates="raw_event")

    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_afferens_raw_events_provider_event_id"),
    )


class ObservationRecord(Base):
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    raw_event_id: Mapped[str] = mapped_column(ForeignKey("afferens_raw_events.id"), index=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), index=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(64), default="afferens", index=True)
    source_node_id: Mapped[str | None] = mapped_column(String(255), index=True)
    modality: Mapped[str] = mapped_column(String(64), index=True)
    classification: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[float | None] = mapped_column(Float)
    room_id: Mapped[str] = mapped_column(String(255), index=True)
    scene_summary: Mapped[str] = mapped_column(Text)
    human_presence: Mapped[str] = mapped_column(String(64), index=True)
    risk_signals: Mapped[list[str]] = mapped_column(json_type, default=list)
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    parser_version: Mapped[str] = mapped_column(String(64), default="afferens-v1")
    embedding: Mapped[Any | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    raw_event: Mapped[AfferensRawEvent] = relationship(back_populates="observations")
    objects: Mapped[list[DetectedObjectRecord]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
    )
    enrichments: Mapped[list[ObservationEnrichmentRecord]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
    )
    model_runs: Mapped[list[ModelRunRecord]] = relationship(back_populates="observation")


class DetectedObjectRecord(Base):
    __tablename__ = "detected_objects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    observation_id: Mapped[str] = mapped_column(ForeignKey("observations.id"), index=True)
    object_key: Mapped[str] = mapped_column(String(255), index=True)
    label: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    confidence: Mapped[float | None] = mapped_column(Float)
    relative_location: Mapped[str | None] = mapped_column(Text)
    bbox: Mapped[Any | None] = mapped_column(json_type)
    spatial_coords: Mapped[dict[str, Any] | None] = mapped_column(json_type)
    source: Mapped[str] = mapped_column(String(64), default="afferens", index=True)
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)

    observation: Mapped[ObservationRecord] = relationship(back_populates="objects")

    __table_args__ = (
        Index("ix_detected_objects_object_seen", "object_key", "observation_id"),
    )


class LastSeenObjectRecord(Base):
    __tablename__ = "last_seen_objects"

    object_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_room: Mapped[str] = mapped_column(String(255), index=True)
    last_seen_room_id: Mapped[str | None] = mapped_column(String(255), index=True)
    last_seen_region_id: Mapped[str | None] = mapped_column(String(255), index=True)
    last_seen_region_label: Mapped[str | None] = mapped_column(String(255), index=True)
    last_seen_normalized_coords: Mapped[dict[str, float] | None] = mapped_column(json_type)
    location_assignment_source: Mapped[str] = mapped_column(
        String(64),
        default="observation_room",
        index=True,
    )
    last_seen_relative_location: Mapped[str | None] = mapped_column(Text)
    last_seen_observation_id: Mapped[str] = mapped_column(ForeignKey("observations.id"), index=True)
    last_confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(64), index=True)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class HomeZoneRecord(Base):
    __tablename__ = "home_zones"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    room_type: Mapped[str] = mapped_column(String(64), index=True)
    aliases: Mapped[list[str]] = mapped_column(json_type, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_node_id: Mapped[str | None] = mapped_column(String(255), index=True)
    region_strategy: Mapped[str] = mapped_column(String(64), default="none", index=True)
    regions: Mapped[list[dict[str, Any]]] = mapped_column(json_type, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DailyDiaryEntryRecord(Base):
    __tablename__ = "daily_diary_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date(), index=True)
    summary: Mapped[str] = mapped_column(Text)
    highlights: Mapped[list[str]] = mapped_column(json_type, default=list)
    needs_review: Mapped[list[str]] = mapped_column(json_type, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(128), index=True)

    __table_args__ = (
        UniqueConstraint("entry_date", "source", name="uq_daily_diary_entries_date_source"),
    )


class CareNoteRecord(Base):
    __tablename__ = "care_notes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    note_date: Mapped[date] = mapped_column(Date(), index=True)
    audience: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text)
    bullets: Mapped[list[str]] = mapped_column(json_type, default=list)
    risks: Mapped[list[str]] = mapped_column(json_type, default=list)
    follow_ups: Mapped[list[str]] = mapped_column(json_type, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(128), index=True)


class FamilyMessageRecord(Base):
    __tablename__ = "family_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    trigger_object_key: Mapped[str | None] = mapped_column(String(255), index=True)
    trigger_zone_id: Mapped[str | None] = mapped_column(String(120), index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)


class HydrationEventRecord(Base):
    __tablename__ = "hydration_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    confidence: Mapped[str] = mapped_column(String(64), index=True)
    zone_id: Mapped[str | None] = mapped_column(String(120), index=True)
    zone_name: Mapped[str | None] = mapped_column(String(120))
    evidence_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)


class WellnessCheckRecord(Base):
    __tablename__ = "wellness_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    zone_id: Mapped[str | None] = mapped_column(String(120), index=True)
    zone_name: Mapped[str | None] = mapped_column(String(120))
    evidence_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)


class ActionEventRecord(Base):
    __tablename__ = "action_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    confidence: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(128), index=True)
    source_node_id: Mapped[str | None] = mapped_column(String(255), index=True)
    zone_id: Mapped[str | None] = mapped_column(String(120), index=True)
    zone_name: Mapped[str | None] = mapped_column(String(120))
    evidence_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        Index("ix_action_events_type_occurred_at", "type", "occurred_at"),
        Index("ix_action_events_source_node_occurred_at", "source_node_id", "occurred_at"),
    )


class SemanticMemoryRecord(Base):
    __tablename__ = "semantic_memory"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    evidence_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    source_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    embedding: Mapped[Any | None] = mapped_column(Vector(1536), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_semantic_memory_source"),
        Index("ix_semantic_memory_source_type_occurred_at", "source_type", "occurred_at"),
    )


class QueryRecord(Base):
    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_text: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(String(255), index=True)
    intent: Mapped[str | None] = mapped_column(String(128), index=True)
    answer: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(String(64), index=True)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    provider: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    alerts: Mapped[list[AlertRecord]] = relationship(back_populates="task")
    events: Mapped[list[TaskEventRecord]] = relationship(back_populates="task")


class TaskEventRecord(Base):
    __tablename__ = "task_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    message: Mapped[str] = mapped_column(Text)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    task: Mapped[TaskRecord] = relationship(back_populates="events")


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    hazard_type: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), index=True)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[TaskRecord | None] = relationship(back_populates="alerts")


class ActuationAttemptRecord(Base):
    __tablename__ = "actuation_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    alert_id: Mapped[str | None] = mapped_column(ForeignKey("alerts.id"), index=True)
    provider: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(json_type)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(json_type)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class VerificationCheckRecord(Base):
    __tablename__ = "verification_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id"), index=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ModelRunRecord(Base):
    __tablename__ = "model_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id"), index=True)
    provider: Mapped[str] = mapped_column(String(128), index=True)
    model: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(String(128), index=True)
    focus: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    latency_ms: Mapped[int] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text)

    observation: Mapped[ObservationRecord | None] = relationship(back_populates="model_runs")
    enrichments: Mapped[list[ObservationEnrichmentRecord]] = relationship(back_populates="model_run")


class ObservationEnrichmentRecord(Base):
    __tablename__ = "observation_enrichments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    observation_id: Mapped[str] = mapped_column(ForeignKey("observations.id"), index=True)
    model_run_id: Mapped[str | None] = mapped_column(ForeignKey("model_runs.id"), index=True)
    source_provider: Mapped[str] = mapped_column(String(128), index=True)
    source_model: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    label_suggestions: Mapped[list[dict[str, Any]]] = mapped_column(json_type, default=list)
    safety_notes: Mapped[list[str]] = mapped_column(json_type, default=list)
    spatial_notes: Mapped[list[str]] = mapped_column(json_type, default=list)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    observation: Mapped[ObservationRecord] = relationship(back_populates="enrichments")
    model_run: Mapped[ModelRunRecord | None] = relationship(back_populates="enrichments")


class RuntimeMonitorRecord(Base):
    __tablename__ = "runtime_monitor_state"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    mode: Mapped[str] = mapped_column(String(64), index=True)
    poll_interval_seconds: Mapped[int] = mapped_column()
    max_tokens_per_hour: Mapped[int] = mapped_column()
    estimated_tokens_used_this_hour: Mapped[int] = mapped_column(default=0)
    estimated_tokens_per_call: Mapped[int] = mapped_column(default=14)
    token_hour_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_tick_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_tick_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    observations_synced: Mapped[int] = mapped_column(default=0)
    last_observation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128), default="background_supervisor")
    zone_id: Mapped[str | None] = mapped_column(String(120), index=True)
    target_object_key: Mapped[str | None] = mapped_column(String(255), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_provider_event_id: Mapped[str | None] = mapped_column(String(255), index=True)
    consecutive_errors: Mapped[int] = mapped_column(default=0)
    backoff_seconds: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SystemStatusEventRecord(Base):
    __tablename__ = "system_status_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    service: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(json_type)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
