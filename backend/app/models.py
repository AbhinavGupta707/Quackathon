from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: Any) -> str:
        return f"vector({self.dimensions})"


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
    last_seen_relative_location: Mapped[str | None] = mapped_column(Text)
    last_seen_observation_id: Mapped[str] = mapped_column(ForeignKey("observations.id"), index=True)
    last_confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(64), index=True)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class QueryRecord(Base):
    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(128), index=True)
    answer: Mapped[str | None] = mapped_column(Text)
    evidence_observation_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
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


class SystemStatusEventRecord(Base):
    __tablename__ = "system_status_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    service: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(json_type)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
