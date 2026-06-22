from __future__ import annotations

from datetime import date as date_type
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


class AfferensModality(StrEnum):
    VISION = "VISION"
    SPATIAL = "SPATIAL"
    ACOUSTIC = "ACOUSTIC"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    MOLECULAR = "MOLECULAR"
    INTEROCEPTION = "INTEROCEPTION"


class ModalityReadinessState(StrEnum):
    AVAILABLE = "available"
    NO_LIVE_EVENTS = "no_live_events"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class ModalityStatus(BaseModel):
    modality: AfferensModality
    state: ModalityReadinessState
    message: str
    latest_event_id: str | None = None
    latest_timestamp_utc: datetime | None = None
    source_node_id: str | None = None
    checked_at: datetime = Field(default_factory=utc_now)


class PerceptionModalitiesResponse(BaseModel):
    modalities: list[ModalityStatus]


class ProviderReadinessState(StrEnum):
    CONFIGURED = "configured"
    MISSING_KEY = "missing_key"
    LIVE = "live"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    DEFERRED = "deferred"
    LEXICAL = "lexical"
    PGVECTOR_READY = "pgvector_ready"
    VECTOR_ENABLED = "vector_enabled"


class ProviderStatus(BaseModel):
    provider: str
    state: ProviderReadinessState
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ProvidersStatusResponse(BaseModel):
    ok: bool
    providers: list[ProviderStatus]


class HumanPresence(StrEnum):
    VISIBLE = "visible"
    NOT_VISIBLE = "not_visible"
    UNKNOWN = "unknown"


class LastSeenStatus(StrEnum):
    VISIBLE_NOW = "visible_now"
    VISIBLE_RECENTLY = "visible_recently"
    NOT_SEEN_RECENTLY = "not_seen_recently"
    UNKNOWN = "unknown"


class HomeRegionKind(StrEnum):
    QUADRANT = "quadrant"
    GRID_CELL = "grid_cell"
    POLYGON = "polygon"


class AmbientMonitorState(StrEnum):
    OFF = "off"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class AmbientMonitorMode(StrEnum):
    AMBIENT = "ambient"
    ACTIVE_RECOVERY = "active_recovery"


class RuntimeMonitorState(StrEnum):
    OFF = "off"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    COMPLETED = "completed"


class RuntimeMonitorMode(StrEnum):
    HOME_MEMORY = "home_memory"
    ACTIVE_RECOVERY = "active_recovery"


class QueryIntent(StrEnum):
    OBJECT_LOCATION = "object_location"
    RECENT_ACTIVITY = "recent_activity"
    SAFETY_STATUS = "safety_status"
    UNKNOWN = "unknown"


class AssistantIntent(StrEnum):
    OBJECT_LOCATION = "object_location"
    GUIDED_RECOVERY = "guided_recovery"
    SEMANTIC_MEMORY = "semantic_memory"
    DIARY = "diary"
    FAMILY_MESSAGE = "family_message"
    HYDRATION = "hydration"
    WELLNESS = "wellness"
    SETUP_STATUS = "setup_status"
    UNSUPPORTED = "unsupported"


class QueryConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActivityEventType(StrEnum):
    OBJECT_SEEN = "object_seen"
    TASK_OPENED = "task_opened"
    TASK_RESOLVED = "task_resolved"
    SAFETY_ALERT = "safety_alert"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    ACTUATION_ATTEMPTED = "actuation_attempted"
    FAMILY_PROMPT_DELIVERED = "family_prompt_delivered"
    FAMILY_PROMPT_ACKNOWLEDGED = "family_prompt_acknowledged"


class GeneratedSource(StrEnum):
    DETERMINISTIC = "deterministic"


class CareNoteAudience(StrEnum):
    FAMILY = "family"
    CARE_HOME = "care_home"


class FamilyMessagePriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class FamilyMessageStatus(StrEnum):
    ACTIVE = "active"
    SCHEDULED = "scheduled"
    ACKNOWLEDGED = "acknowledged"
    EXPIRED = "expired"


class HydrationEventType(StrEnum):
    WATER_VISIBLE = "water_visible"
    DRINK_CANDIDATE = "drink_candidate"
    CAREGIVER_REPORTED = "caregiver_reported"


class HydrationStatus(StrEnum):
    UNKNOWN = "unknown"
    OKAY = "okay"
    CONSIDER_PROMPTING = "consider_prompting"


class WellnessCheckType(StrEnum):
    HYDRATION_PROMPT = "hydration_prompt"
    POSSIBLE_FALL_CHECK = "possible_fall_check"
    UNUSUAL_STILLNESS_CHECK = "unusual_stillness_check"
    CAREGIVER_REVIEW = "caregiver_review"


class WellnessCheckStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"


class WellnessAckBy(StrEnum):
    CAREGIVER = "caregiver"
    FAMILY = "family"
    USER = "user"


class CaregiverNotificationType(StrEnum):
    POSSIBLE_FALL_CHECK = "possible_fall_check"
    HYDRATION_PROMPT = "hydration_prompt"
    FAMILY_PROMPT_DUE = "family_prompt_due"
    FAMILY_PROMPT_ACKNOWLEDGED = "family_prompt_acknowledged"
    UNRESOLVED_RECOVERY_TASK = "unresolved_recovery_task"
    ACTUATION_VERIFICATION_REQUIRED = "actuation_verification_required"


class CaregiverNotificationStatus(StrEnum):
    QUEUED = "queued"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ActionEventType(StrEnum):
    FALL_CANDIDATE = "fall_candidate"
    FALL_ESCALATED = "fall_escalated"
    DRINK_CANDIDATE = "drink_candidate"
    ACTION_INCONCLUSIVE = "action_inconclusive"


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


class VerificationState(StrEnum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    INCONCLUSIVE = "inconclusive"


class ActuationState(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class EnrichmentProvider(StrEnum):
    AUTO = "auto"
    FIREWORKS = "fireworks"
    GEMINI = "gemini"
    DETERMINISTIC = "deterministic"


class EnrichmentFocus(StrEnum):
    LABEL_QUALITY = "label_quality"
    SAFETY = "safety"
    SCENE_CONTEXT = "scene_context"
    ALL = "all"


class EnrichmentProviderState(StrEnum):
    USED = "used"
    FALLBACK = "fallback"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


class ModelRunState(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class SemanticMemorySourceType(StrEnum):
    OBSERVATION = "observation"
    OBJECT_MEMORY = "object_memory"
    DIARY_ENTRY = "diary_entry"
    CARE_NOTE = "care_note"
    FAMILY_MESSAGE = "family_message"
    HYDRATION_EVENT = "hydration_event"
    WELLNESS_CHECK = "wellness_check"


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
    last_seen_room_id: str | None = None
    last_seen_region_id: str | None = None
    last_seen_region_label: str | None = None
    last_seen_normalized_coords: dict[str, float] | None = None
    location_assignment_source: str = "observation_room"
    last_seen_relative_location: str | None = None
    last_seen_observation_id: str
    last_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: LastSeenStatus = LastSeenStatus.VISIBLE_NOW
    evidence_observation_ids: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class HomeRegion(BaseModel):
    id: str
    label: str
    kind: HomeRegionKind = HomeRegionKind.QUADRANT
    bounds: dict[str, float] | None = None
    polygon: list[dict[str, float]] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("label")
    @classmethod
    def normalize_region_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("region label must not be blank")
        return normalized


class HomeZone(BaseModel):
    id: str
    name: str
    room_type: str
    aliases: list[str] = Field(default_factory=list)
    is_default: bool = False
    source_node_id: str | None = None
    region_strategy: str = "none"
    regions: list[HomeRegion] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ActivityEvent(BaseModel):
    id: str
    type: ActivityEventType
    title: str
    body: str
    occurred_at: datetime
    source: str
    confidence: QueryConfidence = QueryConfidence.LOW
    zone_id: str | None = None
    zone_name: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DailyDiaryEntry(BaseModel):
    id: str
    date: date_type
    summary: str
    highlights: list[str] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)
    source: str = GeneratedSource.DETERMINISTIC.value


class CareNote(BaseModel):
    id: str
    date: date_type
    audience: CareNoteAudience
    summary: str
    bullets: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    source: str = GeneratedSource.DETERMINISTIC.value


class FamilyMessage(BaseModel):
    id: str
    title: str
    body: str
    priority: FamilyMessagePriority = FamilyMessagePriority.NORMAL
    status: FamilyMessageStatus = FamilyMessageStatus.ACTIVE
    trigger_object_key: str | None = None
    trigger_zone_id: str | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    acknowledged_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HydrationEvent(BaseModel):
    id: str
    type: HydrationEventType
    occurred_at: datetime
    confidence: QueryConfidence = QueryConfidence.LOW
    zone_id: str | None = None
    zone_name: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HydrationSummary(BaseModel):
    date: date_type
    status: HydrationStatus
    water_events: int
    latest_event_at: datetime | None = None
    message: str
    evidence_ids: list[str] = Field(default_factory=list)
    events: list[HydrationEvent] = Field(default_factory=list)


class WellnessCheck(BaseModel):
    id: str
    type: WellnessCheckType
    severity: AlertSeverity
    status: WellnessCheckStatus = WellnessCheckStatus.OPEN
    title: str
    body: str
    confidence: QueryConfidence = QueryConfidence.LOW
    occurred_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    acknowledged_at: datetime | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaregiverNotification(BaseModel):
    id: str
    type: CaregiverNotificationType
    status: CaregiverNotificationStatus = CaregiverNotificationStatus.QUEUED
    severity: AlertSeverity = AlertSeverity.LOW
    title: str
    body: str
    source: str
    source_id: str
    created_at: datetime
    due_at: datetime | None = None
    task_id: str | None = None
    alert_id: str | None = None
    wellness_check_id: str | None = None
    family_message_id: str | None = None
    actuation_attempt_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    requires_human_ack: bool = True
    requires_live_verification: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionEvent(BaseModel):
    id: str
    type: ActionEventType
    occurred_at: datetime
    confidence: QueryConfidence = QueryConfidence.LOW
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str
    source_node_id: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Task(BaseModel):
    id: str
    type: TaskType
    state: TaskState
    title: str
    body: str
    recommended_action: str
    evidence_observation_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
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
    zone_id: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("room_id")
    @classmethod
    def normalize_room_id(cls, value: str) -> str:
        normalized = value.strip()
        return normalized or "default_home_zone"

    @field_validator("zone_id")
    @classmethod
    def normalize_zone_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @property
    def effective_room_id(self) -> str:
        return self.zone_id or self.room_id


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


class HomeZonesResponse(BaseModel):
    zones: list[HomeZone] = Field(default_factory=list)


class HomeZoneCreateRequest(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    room_type: str = Field(min_length=1, max_length=64)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    is_default: bool = False
    source_node_id: str | None = Field(default=None, max_length=255)
    region_strategy: str = Field(default="none", max_length=64)
    regions: list[HomeRegion] = Field(default_factory=list, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "name", "room_type", "source_node_id", "region_strategy")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized and value is not None:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, value: list[str]) -> list[str]:
        aliases: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized and normalized not in aliases:
                aliases.append(normalized)
        return aliases


class HomeZoneCreateResponse(BaseModel):
    ok: bool
    zone: HomeZone


class ActivityTimelineResponse(BaseModel):
    date: date_type
    events: list[ActivityEvent] = Field(default_factory=list)


class DiaryResponse(BaseModel):
    date: date_type
    diary: DailyDiaryEntry | None = None


class DiaryGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date_type | None = None


class DiaryGenerateResponse(BaseModel):
    ok: bool
    diary: DailyDiaryEntry


class CareNotesResponse(BaseModel):
    date: date_type
    notes: list[CareNote] = Field(default_factory=list)


class CareNoteGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date_type | None = None
    audience: CareNoteAudience = CareNoteAudience.FAMILY


class CareNoteGenerateResponse(BaseModel):
    ok: bool
    note: CareNote


class FamilyMessagesResponse(BaseModel):
    messages: list[FamilyMessage] = Field(default_factory=list)


class FamilyMessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=2000)
    priority: FamilyMessagePriority = FamilyMessagePriority.NORMAL
    trigger_object_key: str | None = Field(default=None, max_length=255)
    trigger_zone_id: str | None = Field(default=None, max_length=120)
    starts_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("title", "body")
    @classmethod
    def normalize_required_message_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("trigger_object_key", "trigger_zone_id")
    @classmethod
    def normalize_optional_message_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class FamilyMessageCreateResponse(BaseModel):
    ok: bool
    message: FamilyMessage


class FamilyMessageAckResponse(BaseModel):
    ok: bool
    message: FamilyMessage


class HydrationSummaryResponse(BaseModel):
    date: date_type
    summary: HydrationSummary


class HydrationEventCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: HydrationEventType = HydrationEventType.CAREGIVER_REPORTED
    occurred_at: datetime | None = None
    confidence: QueryConfidence = QueryConfidence.LOW
    zone_id: str | None = Field(default=None, max_length=120)
    evidence_ids: list[str] = Field(default_factory=list, max_length=25)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("zone_id")
    @classmethod
    def normalize_hydration_zone_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("evidence_ids")
    @classmethod
    def normalize_hydration_evidence_ids(cls, value: list[str]) -> list[str]:
        evidence_ids: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized and normalized not in evidence_ids:
                evidence_ids.append(normalized)
        return evidence_ids


class HydrationEventCreateResponse(BaseModel):
    ok: bool
    event: HydrationEvent


class WellnessChecksResponse(BaseModel):
    date: date_type
    checks: list[WellnessCheck] = Field(default_factory=list)


class WellnessCheckGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date_type | None = None


class WellnessCheckGenerateResponse(BaseModel):
    ok: bool
    checks: list[WellnessCheck] = Field(default_factory=list)


class WellnessCheckAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledged_by: WellnessAckBy = WellnessAckBy.CAREGIVER
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note")
    @classmethod
    def normalize_wellness_ack_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WellnessCheckAckResponse(BaseModel):
    ok: bool
    check: WellnessCheck


class ActionEventCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ActionEventType
    occurred_at: datetime | None = None
    confidence: QueryConfidence = QueryConfidence.LOW
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str = Field(min_length=1, max_length=128)
    source_node_id: str | None = Field(default=None, max_length=255)
    zone_id: str | None = Field(default=None, max_length=120)
    evidence_ids: list[str] = Field(default_factory=list, max_length=25)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source")
    @classmethod
    def normalize_action_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source must not be blank")
        return normalized

    @field_validator("source_node_id", "zone_id")
    @classmethod
    def normalize_action_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("evidence_ids")
    @classmethod
    def normalize_action_evidence_ids(cls, value: list[str]) -> list[str]:
        evidence_ids: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized and normalized not in evidence_ids:
                evidence_ids.append(normalized)
        return evidence_ids


class ActionEventCreateResponse(BaseModel):
    ok: bool
    event: ActionEvent
    wellness_check_id: str | None = None
    hydration_event_id: str | None = None


class ActionEventsResponse(BaseModel):
    events: list[ActionEvent] = Field(default_factory=list)


class ActionRuntimeFallStatus(BaseModel):
    enabled: bool
    available: bool
    state: str = "unavailable"
    provider: str = "ultralytics"
    model_path_configured: bool
    model_file_exists: bool = False
    model_loaded: bool
    labels: list[str] = Field(default_factory=list)
    message: str
    unavailable_reason: str | None = None
    model_metadata: dict[str, Any] = Field(default_factory=dict)


class ActionRuntimeDrinkStatus(BaseModel):
    enabled: bool = True
    available: bool = True
    provider: str = "browser_mediapipe"
    message: str = "Drink detection runs in the browser after Action Node start."


class ActionRuntimePrivacyStatus(BaseModel):
    raw_video_storage_enabled: bool
    raw_frames_persisted: bool = False


class ActionRuntimeStatusResponse(BaseModel):
    ok: bool
    fall: ActionRuntimeFallStatus
    drink: ActionRuntimeDrinkStatus
    privacy: ActionRuntimePrivacyStatus


class FallEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurred_at: datetime | None = None
    source: str = Field(default="local_yolo_fall", min_length=1, max_length=128)
    source_node_id: str | None = Field(default=None, max_length=255)
    zone_id: str | None = Field(default=None, max_length=120)
    evidence_ids: list[str] = Field(default_factory=list, max_length=25)
    posture_state: str | None = Field(default=None, max_length=120)
    fallen: bool | None = None
    persistence_seconds: float = Field(default=0.0, ge=0.0, le=3600.0)
    confidence: QueryConfidence = QueryConfidence.LOW
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    require_model_runtime: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source", "source_node_id", "zone_id", "posture_state")
    @classmethod
    def normalize_fall_eval_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("evidence_ids")
    @classmethod
    def normalize_fall_evidence_ids(cls, value: list[str]) -> list[str]:
        evidence_ids: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized and normalized not in evidence_ids:
                evidence_ids.append(normalized)
        return evidence_ids


class DrinkEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurred_at: datetime | None = None
    source: str = Field(default="browser_mediapipe", min_length=1, max_length=128)
    source_node_id: str | None = Field(default=None, max_length=255)
    zone_id: str | None = Field(default=None, max_length=120)
    evidence_ids: list[str] = Field(default_factory=list, max_length=25)
    object_keys: list[str] = Field(default_factory=list, max_length=25)
    object_visible: bool = False
    hand_object_contact: bool = False
    hand_to_mouth_motion: bool = False
    object_near_mouth: bool = False
    explicit_action_telemetry: bool = False
    temporal_window_seconds: float = Field(default=0.0, ge=0.0, le=3600.0)
    confidence: QueryConfidence = QueryConfidence.LOW
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source", "source_node_id", "zone_id")
    @classmethod
    def normalize_drink_eval_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("evidence_ids", "object_keys")
    @classmethod
    def normalize_drink_string_lists(cls, value: list[str]) -> list[str]:
        values: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized and normalized not in values:
                values.append(normalized)
        return values


class ActionEvaluateResponse(BaseModel):
    ok: bool
    event: ActionEvent
    decision: ActionEventType
    wellness_check_id: str | None = None
    hydration_event_id: str | None = None
    message: str


class SemanticMemoryItem(BaseModel):
    id: str
    source_type: SemanticMemorySourceType
    source_id: str
    title: str
    text: str
    occurred_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class SemanticMemoryResult(SemanticMemoryItem):
    score: float = Field(ge=0.0)
    match_reasons: list[str] = Field(default_factory=list)


class SemanticMemorySearchResponse(BaseModel):
    ok: bool = True
    query: str | None = None
    provider: str = "deterministic_lexical"
    embedding_provider: str | None = None
    retrieval_mode: str = "lexical"
    reindex_recommended: bool = False
    items: list[SemanticMemoryResult] = Field(default_factory=list)


class SemanticMemoryReindexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force: bool = False
    source_types: list[SemanticMemorySourceType] | None = None


class SemanticMemoryReindexResponse(BaseModel):
    ok: bool
    provider: str = "deterministic_lexical"
    embedding_provider: str | None = None
    retrieval_mode: str = "lexical"
    indexed_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    message: str


class SemanticMemoryAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=1200)
    limit: int = Field(default=5, ge=1, le=20)
    source_types: list[SemanticMemorySourceType] | None = None

    @field_validator("question")
    @classmethod
    def normalize_semantic_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


class SemanticMemoryAskResponse(BaseModel):
    ok: bool
    answer: str
    confidence: QueryConfidence
    provider: str
    used_memory: bool
    needs_human_verification: bool = True
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    citations: list[SemanticMemoryResult] = Field(default_factory=list)
    safety_disclaimer: str = "This is an assistive prototype. Please verify important situations in person."


class TasksResponse(BaseModel):
    tasks: list[Task] = Field(default_factory=list)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=800)
    session_id: str | None = Field(default=None, max_length=255)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class QueryResponse(BaseModel):
    answer: str
    confidence: QueryConfidence
    intent: QueryIntent
    used_current_perception: bool
    used_memory: bool
    needs_human_verification: bool
    evidence_observation_ids: list[str] = Field(default_factory=list)
    task_id: str | None = None
    safety_disclaimer: str = "This is an assistive prototype. Please verify important items in person."


class AssistantAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1200)
    session_id: str | None = Field(default=None, max_length=255)
    voice: bool = False

    @field_validator("query")
    @classmethod
    def normalize_assistant_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @field_validator("session_id")
    @classmethod
    def normalize_assistant_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AssistantAskResponse(BaseModel):
    ok: bool = True
    intent: AssistantIntent
    answer: str
    next_step: str
    confidence: QueryConfidence
    provider: str
    used_current_perception: bool
    used_memory: bool
    needs_human_verification: bool = True
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    task_id: str | None = None
    route_metadata: dict[str, Any] = Field(default_factory=dict)


class VoiceQueryRequest(QueryRequest):
    model_config = ConfigDict(extra="forbid")

    speak: bool = True


class VoiceQueryResponse(BaseModel):
    ok: bool
    query_result: QueryResponse
    spoken_text: str


class GuidedRecoveryStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_key: str = Field(min_length=1, max_length=255)
    session_id: str | None = Field(default=None, max_length=255)

    @field_validator("object_key")
    @classmethod
    def normalize_object_key_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("object_key must not be blank")
        return normalized

    @field_validator("session_id")
    @classmethod
    def normalize_guidance_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class GuidedRecoveryStartResponse(BaseModel):
    ok: bool
    task: Task | None = None
    next_instruction: str


class AmbientStartRequest(BaseModel):
    mode: AmbientMonitorMode
    poll_interval_seconds: int = Field(ge=3, le=3600)
    duration_seconds: int | None = Field(default=None, ge=1, le=3600)
    target_object_key: str | None = Field(default=None, max_length=255)
    zone_id: str | None = Field(default=None, max_length=120)

    @field_validator("target_object_key", "zone_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AmbientMonitorStatus(BaseModel):
    state: AmbientMonitorState
    mode: AmbientMonitorMode | None = None
    poll_interval_seconds: int
    last_sync_at: datetime | None = None
    last_error: str | None = None
    estimated_afferens_tokens_per_call: int = 14
    target_object_key: str | None = None
    target_visible_now: bool | None = None
    zone_id: str | None = None
    started_at: datetime | None = None
    ends_at: datetime | None = None
    observations_synced: int = 0
    last_observation_id: str | None = None


class AmbientMonitorResponse(BaseModel):
    ok: bool = True
    monitor: AmbientMonitorStatus


class AmbientStatusResponse(BaseModel):
    monitor: AmbientMonitorStatus


class RuntimeMonitorTokenBudget(BaseModel):
    max_tokens_per_hour: int
    estimated_tokens_used_this_hour: int
    estimated_tokens_per_call: int = 14


class RuntimeMonitorStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: RuntimeMonitorMode = RuntimeMonitorMode.HOME_MEMORY
    poll_interval_seconds: int = Field(default=45, ge=3, le=3600)
    zone_id: str | None = Field(default=None, max_length=120)
    target_object_key: str | None = Field(default=None, max_length=255)
    duration_seconds: int | None = Field(default=None, ge=1, le=86400)
    max_tokens_per_hour: int = Field(default=420, ge=14, le=100_000)

    @field_validator("target_object_key", "zone_id")
    @classmethod
    def normalize_runtime_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RuntimeMonitorStatus(BaseModel):
    state: RuntimeMonitorState
    mode: RuntimeMonitorMode = RuntimeMonitorMode.HOME_MEMORY
    poll_interval_seconds: int = 45
    token_budget: RuntimeMonitorTokenBudget = Field(
        default_factory=lambda: RuntimeMonitorTokenBudget(
            max_tokens_per_hour=420,
            estimated_tokens_used_this_hour=0,
            estimated_tokens_per_call=14,
        )
    )
    last_tick_at: datetime | None = None
    next_tick_at: datetime | None = None
    observations_synced: int = 0
    last_observation_id: str | None = None
    last_error: str | None = None
    source: str = "background_supervisor"
    zone_id: str | None = None
    target_object_key: str | None = None
    started_at: datetime | None = None
    ends_at: datetime | None = None
    token_hour_started_at: datetime | None = None
    last_provider_event_id: str | None = None
    consecutive_errors: int = 0
    backoff_seconds: int = 0
    updated_at: datetime = Field(default_factory=utc_now)


class RuntimeMonitorResponse(BaseModel):
    ok: bool = True
    monitor: RuntimeMonitorStatus
    message: str | None = None


class QueryLog(BaseModel):
    id: str
    query_text: str
    session_id: str | None = None
    intent: QueryIntent | None = None
    answer: str | None = None
    confidence: QueryConfidence | None = None
    evidence_observation_ids: list[str] = Field(default_factory=list)
    task_id: str | None = None
    provider: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class VerificationCheck(BaseModel):
    id: str
    task_id: str
    observation_id: str | None = None
    state: VerificationState
    message: str
    evidence_observation_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ActuationAttempt(BaseModel):
    id: str
    task_id: str | None = None
    alert_id: str | None = None
    provider: str
    command_type: str
    state: ActuationState
    message: str
    request_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None
    evidence_observation_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class AfferensActuationResult(BaseModel):
    state: ActuationState
    message: str
    response_payload: dict[str, Any] | None = None


class TaskVerifyRequest(BaseModel):
    room_id: str = Field(default="default_home_zone", min_length=1, max_length=120)

    @field_validator("room_id")
    @classmethod
    def normalize_room_id(cls, value: str) -> str:
        normalized = value.strip()
        return normalized or "default_home_zone"


class TaskVerifyResponse(BaseModel):
    ok: bool
    task: Task
    verification: VerificationCheck


class TaskResolveRequest(BaseModel):
    resolution_note: str = Field(min_length=1, max_length=1000)
    resolved_by: str = Field(default="user", min_length=1, max_length=120)

    @field_validator("resolution_note", "resolved_by")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class TaskResolveResponse(BaseModel):
    ok: bool
    task: Task


class AlertsResponse(BaseModel):
    alerts: list[Alert] = Field(default_factory=list)


class CaregiverNotificationsResponse(BaseModel):
    ok: bool = True
    notifications: list[CaregiverNotification] = Field(default_factory=list)


class AlertAckRequest(BaseModel):
    acknowledged_by: str = Field(default="caregiver", min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("acknowledged_by")
    @classmethod
    def normalize_acknowledged_by(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("acknowledged_by must not be blank")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AlertAckResponse(BaseModel):
    ok: bool
    alert: Alert


class AlarmActuationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)
    severity: AlertSeverity = AlertSeverity.MEDIUM
    task_id: str = Field(min_length=1, max_length=120)
    alert_id: str | None = Field(default=None, max_length=120)
    target_node_id: str | None = Field(default=None, max_length=255)
    use_afferens: bool = True

    @field_validator("reason", "task_id")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("alert_id", "target_node_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CaptureFrameActuationRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=120)
    target_node_id: str | None = Field(default=None, max_length=255)
    reason: str = Field(default="guided_recovery_verification", min_length=1, max_length=255)
    alert_id: str | None = Field(default=None, max_length=120)

    @field_validator("task_id", "reason")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("target_node_id", "alert_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ActuationResponse(BaseModel):
    ok: bool
    attempt: ActuationAttempt


class EnrichmentLatestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: EnrichmentProvider = EnrichmentProvider.AUTO
    focus: EnrichmentFocus = EnrichmentFocus.ALL
    persist: bool = True


class EnrichmentLabelSuggestion(BaseModel):
    object_key: str
    afferens_label: str
    suggested_label: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str


class ModelRun(BaseModel):
    id: str
    provider: str
    model: str
    state: ModelRunState
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    error_message: str | None = None


class ObservationEnrichment(BaseModel):
    id: str
    observation_id: str
    source_provider: str
    source_model: str
    summary: str
    label_suggestions: list[EnrichmentLabelSuggestion] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    spatial_notes: list[str] = Field(default_factory=list)
    evidence_observation_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class EnrichmentLatestResponse(BaseModel):
    ok: bool
    observation_id: str | None = None
    provider: str
    provider_state: EnrichmentProviderState
    model_run: ModelRun
    enrichment: ObservationEnrichment | None = None
    message: str


class LatestEnrichmentResponse(BaseModel):
    enrichment: ObservationEnrichment | None = None
