from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ServiceHealthState(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"


class AfferensConnectionState(StrEnum):
    MISSING_KEY = "missing_key"
    INVALID_KEY = "invalid_key"
    INACTIVE_KEY = "inactive_key"
    NO_LIVE_EVENTS = "no_live_events"
    LIVE = "live"
    ERROR = "error"


class ServiceStatus(BaseModel):
    state: ServiceHealthState
    message: str
    checked_at: datetime = Field(default_factory=utc_now)


class HealthResponse(BaseModel):
    ok: bool
    version: str
    environment: str
    services: dict[str, ServiceStatus]


class AfferensStatus(BaseModel):
    configured: bool
    base_url: str
    state: AfferensConnectionState
    message: str
    latest_event_id: str | None = None
    latest_timestamp_utc: datetime | None = None
    source_node_id: str | None = None
    modality: str | None = None


class AfferensLatestResponse(BaseModel):
    ok: bool
    raw_event: dict[str, Any] | None = None
    status: AfferensStatus


class AfferensFetchResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: AfferensStatus
    raw_event: dict[str, Any] | None = None
    raw_events: list[dict[str, Any]] = Field(default_factory=list)
    raw_payload: Any | None = None

    @property
    def is_live(self) -> bool:
        return self.status.state == AfferensConnectionState.LIVE


class HumanPresence(StrEnum):
    VISIBLE = "visible"
    NOT_VISIBLE = "not_visible"
    UNKNOWN = "unknown"


class LastSeenStatus(StrEnum):
    VISIBLE_NOW = "visible_now"
    VISIBLE_RECENTLY = "visible_recently"
    NOT_SEEN_RECENTLY = "not_seen_recently"
    UNKNOWN = "unknown"


class TaskType(StrEnum):
    OBJECT_RECOVERY = "object_recovery"
    SAFETY_ALERT = "safety_alert"


class TaskState(StrEnum):
    OPEN = "open"
    WAITING_FOR_HUMAN = "waiting_for_human"
    ACTUATION_ATTEMPTED = "actuation_attempted"
    VERIFICATION_PENDING = "verification_pending"
    VERIFIED_RESOLVED = "verified_resolved"
    ESCALATED = "escalated"
    DISMISSED = "dismissed"
    FAILED_VERIFICATION = "failed_verification"


class AlertSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class DetectedObject(BaseModel):
    id: str | None = None
    object_key: str
    label: str
    display_name: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    relative_location: str | None = None
    bbox: dict[str, Any] | list[Any] | None = None
    spatial_coords: dict[str, Any] | None = None
    source: str = "afferens"
    evidence_metadata: dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):
    id: str
    raw_event_id: str
    provider_event_id: str | None = None
    timestamp_utc: datetime
    source: str = "afferens"
    source_node_id: str | None = None
    modality: str = "VISION"
    classification: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    room_id: str = "default_home_zone"
    scene_summary: str
    human_presence: HumanPresence = HumanPresence.UNKNOWN
    objects: list[DetectedObject] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    evidence_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class LastSeenObject(BaseModel):
    object_key: str
    display_name: str
    last_seen_at: datetime
    last_seen_room: str
    last_seen_relative_location: str | None = None
    last_seen_observation_id: str
    last_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: LastSeenStatus = LastSeenStatus.VISIBLE_NOW
    evidence_observation_ids: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class Task(BaseModel):
    id: str
    type: TaskType
    state: TaskState
    title: str
    body: str
    recommended_action: str
    evidence_observation_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None


class Alert(BaseModel):
    id: str
    task_id: str | None = None
    hazard_type: str
    severity: AlertSeverity
    title: str
    body: str
    recommended_action: str
    status: AlertStatus = AlertStatus.OPEN
    evidence_observation_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    acknowledged_at: datetime | None = None


class PerceptionSyncRequest(BaseModel):
    limit: int = Field(default=1, ge=1, le=10)
    room_id: str = Field(default="default_home_zone", min_length=1, max_length=120)

    @field_validator("room_id")
    @classmethod
    def normalize_room_id(cls, value: str) -> str:
        normalized = value.strip()
        return normalized or "default_home_zone"


class PerceptionSyncResponse(BaseModel):
    ok: bool
    observations: list[Observation] = Field(default_factory=list)
    objects_updated: list[LastSeenObject] = Field(default_factory=list)
    tasks_created: list[Task] = Field(default_factory=list)
    alerts_created: list[Alert] = Field(default_factory=list)
    status: AfferensStatus | None = None
    message: str | None = None


class LatestObservationResponse(BaseModel):
    observation: Observation | None = None


class ObjectsLastSeenResponse(BaseModel):
    objects: list[LastSeenObject] = Field(default_factory=list)


class TasksResponse(BaseModel):
    tasks: list[Task] = Field(default_factory=list)
