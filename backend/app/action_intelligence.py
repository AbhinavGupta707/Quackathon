from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Any

from app.config import Settings
from app.ids import new_id
from app.schemas import (
    ActionRuntimeDrinkStatus,
    ActionRuntimePrivacyStatus,
    ActionRuntimeStatusResponse,
    ActionEvent,
    ActionEventCreateRequest,
    ActionEventType,
    AlertSeverity,
    DrinkEvaluateRequest,
    FallEvaluateRequest,
    HydrationEvent,
    HydrationEventType,
    QueryConfidence,
    WellnessCheck,
    WellnessCheckStatus,
    WellnessCheckType,
    utc_now,
)
from app.services import DataSpineService
from app.yolo_fall_adapter import FallInferenceResult, UltralyticsFallAdapter


FALL_POSTURE_STATES = {
    "fall",
    "fallen",
    "fallen_person",
    "lying",
    "lying_down",
    "lying_on_floor",
    "horizontal_posture",
    "floor_posture",
}


class ActionIntelligenceService:
    def __init__(
        self,
        data_spine: DataSpineService,
        *,
        settings: Settings,
        fall_adapter: UltralyticsFallAdapter | None = None,
    ) -> None:
        self._data_spine = data_spine
        self._settings = settings
        self._fall_adapter = fall_adapter or UltralyticsFallAdapter(settings)

    def runtime_status(self) -> ActionRuntimeStatusResponse:
        return ActionRuntimeStatusResponse(
            ok=True,
            fall=self._fall_adapter.status(),
            drink=ActionRuntimeDrinkStatus(),
            privacy=ActionRuntimePrivacyStatus(
                raw_video_storage_enabled=self._settings.action_raw_video_storage_enabled,
                raw_frames_persisted=False,
            ),
        )

    @property
    def max_frame_bytes(self) -> int:
        return self._settings.action_max_frame_bytes

    def create_action_event(
        self,
        request: ActionEventCreateRequest,
    ) -> tuple[ActionEvent, str | None, str | None]:
        event = self._persist_event(
            event_type=request.type,
            occurred_at=request.occurred_at,
            confidence=request.confidence,
            score=request.score,
            source=request.source,
            source_node_id=request.source_node_id,
            zone_id=request.zone_id,
            evidence_ids=request.evidence_ids,
            metadata={
                "ingest_path": "direct_action_event",
                **request.metadata,
            },
        )
        wellness_check_id = None
        hydration_event_id = None
        if event.type in {ActionEventType.FALL_CANDIDATE, ActionEventType.FALL_ESCALATED}:
            wellness_check_id = self._ensure_fall_wellness_check(event).id
        if event.type == ActionEventType.DRINK_CANDIDATE:
            hydration_event_id = self._create_drink_hydration_event(event).id
        return event, wellness_check_id, hydration_event_id

    def list_action_events(
        self,
        *,
        event_date: date | None = None,
        event_type: ActionEventType | None = None,
        limit: int = 50,
    ) -> list[ActionEvent]:
        return self._data_spine.list_action_events(
            event_date=event_date,
            event_type=event_type,
            limit=limit,
        )

    def evaluate_fall(
        self,
        request: FallEvaluateRequest,
    ) -> tuple[ActionEvent, str | None, str]:
        occurred_at = _as_utc(request.occurred_at) or utc_now()
        model_status = self._fall_adapter_status(request)
        fallen_signal = self._is_fallen_signal(request)
        threshold = self._settings.action_fall_persistence_seconds

        if self._fall_model_runtime_required(request) and model_status != "configured":
            event = self._persist_event(
                event_type=ActionEventType.ACTION_INCONCLUSIVE,
                occurred_at=occurred_at,
                confidence=QueryConfidence.LOW,
                score=request.score,
                source=request.source,
                source_node_id=request.source_node_id,
                zone_id=request.zone_id,
                evidence_ids=request.evidence_ids,
                metadata={
                    "reason": "fall_model_runtime_unavailable",
                    "adapter_status": model_status,
                    "human_verification_required": True,
                    **self._fall_metadata(request),
                },
            )
            return event, None, "Fall adapter runtime is unavailable; telemetry was not escalated."

        if not fallen_signal or request.persistence_seconds < threshold:
            event = self._persist_event(
                event_type=ActionEventType.ACTION_INCONCLUSIVE,
                occurred_at=occurred_at,
                confidence=request.confidence,
                score=request.score,
                source=request.source,
                source_node_id=request.source_node_id,
                zone_id=request.zone_id,
                evidence_ids=request.evidence_ids,
                metadata={
                    "reason": "fall_persistence_threshold_not_met",
                    "required_persistence_seconds": threshold,
                    "adapter_status": model_status,
                    "human_verification_required": True,
                    **self._fall_metadata(request),
                },
            )
            return event, None, "Possible fall telemetry is inconclusive until persistence threshold is met."

        event = self._persist_event(
            event_type=ActionEventType.FALL_CANDIDATE,
            occurred_at=occurred_at,
            confidence=request.confidence,
            score=request.score,
            source=request.source,
            source_node_id=request.source_node_id,
            zone_id=request.zone_id,
            evidence_ids=request.evidence_ids,
            metadata={
                "reason": "fall_persistence_threshold_met",
                "required_persistence_seconds": threshold,
                "adapter_status": model_status,
                "human_verification_required": True,
                **self._fall_metadata(request),
            },
        )
        check = self._ensure_fall_wellness_check(event)
        return event, check.id, "Escalated notification to caregiver for a possible fall."

    def infer_fall_frame(
        self,
        *,
        frame_bytes: bytes,
        source_node_id: str | None,
        zone_id: str | None,
        evidence_ids: list[str],
        occurred_at: datetime | None,
        persist_inconclusive: bool = True,
    ) -> tuple[ActionEvent, str | None, str]:
        occurred_at = _as_utc(occurred_at) or utc_now()
        result = self._fall_adapter.infer_frame(frame_bytes)
        persistence_seconds = self._fall_persistence_seconds_for_inference(
            result=result,
            source_node_id=source_node_id,
            zone_id=zone_id,
            occurred_at=occurred_at,
        )
        confidence = _confidence_from_score(result.confidence)
        request = FallEvaluateRequest(
            occurred_at=occurred_at,
            source="local_yolo_fall",
            source_node_id=source_node_id,
            zone_id=zone_id,
            evidence_ids=evidence_ids,
            posture_state=result.label if result.fallen is True else None,
            fallen=result.fallen,
            persistence_seconds=persistence_seconds,
            confidence=confidence,
            score=result.confidence,
            require_model_runtime=True,
            metadata={
                "ingest_path": "fall_infer_frame",
                "model_provider": "ultralytics",
                "model_available": result.available,
                "model_label": result.label,
                "model_confidence": result.confidence,
                "model_message": result.message,
                "unavailable_reason": result.unavailable_reason,
                "raw_frame_persisted": False,
                **result.metadata,
            },
        )
        if not persist_inconclusive and self._would_be_inconclusive_fall(request):
            return (
                self._transient_inconclusive_fall_event(request),
                None,
                result.message
                if result.unavailable_reason
                else "Automatic fall scan did not meet the persistence threshold; no event was saved.",
            )
        event, wellness_check_id, message = self.evaluate_fall(request)
        if result.unavailable_reason:
            return event, wellness_check_id, result.message
        return event, wellness_check_id, message

    def evaluate_drink(
        self,
        request: DrinkEvaluateRequest,
    ) -> tuple[ActionEvent, str | None, str]:
        object_context = request.object_visible and bool(request.object_keys)
        explicit_action = request.explicit_action_telemetry
        temporal_action = (
            object_context
            and explicit_action
            and request.hand_object_contact
            and request.hand_to_mouth_motion
            and request.object_near_mouth
            and request.temporal_window_seconds >= self._settings.action_drink_min_window_seconds
        )
        metadata = {
            "object_keys": request.object_keys,
            "object_visible": request.object_visible,
            "object_context_met": object_context,
            "hand_object_contact": request.hand_object_contact,
            "hand_to_mouth_motion": request.hand_to_mouth_motion,
            "object_near_mouth": request.object_near_mouth,
            "explicit_action_telemetry": explicit_action,
            "temporal_window_seconds": request.temporal_window_seconds,
            "required_temporal_window_seconds": self._settings.action_drink_min_window_seconds,
            "human_verification_required": True,
            **request.metadata,
        }
        if not temporal_action:
            if not object_context:
                reason = "live_object_context_required"
            elif not explicit_action:
                reason = "object_visibility_only"
            else:
                reason = "drink_action_threshold_not_met"
            event = self._persist_event(
                event_type=ActionEventType.ACTION_INCONCLUSIVE,
                occurred_at=request.occurred_at,
                confidence=request.confidence,
                score=request.score,
                source=request.source,
                source_node_id=request.source_node_id,
                zone_id=request.zone_id,
                evidence_ids=request.evidence_ids,
                metadata={"reason": reason, **metadata},
            )
            if reason == "live_object_context_required":
                message = "Live Afferens cup, bottle, or water context is required before hydration can be logged."
            elif reason == "object_visibility_only":
                message = "Object visibility alone does not count as hydration."
            else:
                message = "Drink telemetry is inconclusive until hand/object/mouth temporal evidence passes threshold."
            return (
                event,
                None,
                message,
            )

        event = self._persist_event(
            event_type=ActionEventType.DRINK_CANDIDATE,
            occurred_at=request.occurred_at,
            confidence=request.confidence,
            score=request.score,
            source=request.source,
            source_node_id=request.source_node_id,
            zone_id=request.zone_id,
            evidence_ids=request.evidence_ids,
            metadata={"reason": "drink_action_threshold_met", **metadata},
        )
        hydration = self._create_drink_hydration_event(event)
        return event, hydration.id, "Possible drink action candidate recorded for hydration review."

    def _persist_event(
        self,
        *,
        event_type: ActionEventType,
        occurred_at: datetime | None,
        confidence: QueryConfidence,
        score: float | None,
        source: str,
        source_node_id: str | None,
        zone_id: str | None,
        evidence_ids: list[str],
        metadata: dict[str, Any],
    ) -> ActionEvent:
        zones = self._zone_names()
        event = ActionEvent(
            id=new_id("act"),
            type=event_type,
            occurred_at=_as_utc(occurred_at) or utc_now(),
            confidence=confidence,
            score=score,
            source=source,
            source_node_id=source_node_id,
            zone_id=zone_id,
            zone_name=zones.get(zone_id or ""),
            evidence_ids=evidence_ids,
            metadata={
                **metadata,
                "raw_video_stored": bool(
                    self._settings.action_raw_video_storage_enabled
                    and metadata.get("raw_video_stored") is True
                ),
                "human_verification_required": True,
            },
        )
        return self._data_spine.create_action_event(event)

    def _ensure_fall_wellness_check(self, event: ActionEvent) -> WellnessCheck:
        existing = self._recent_fall_check(event)
        if existing is not None:
            return existing
        severity = (
            AlertSeverity.HIGH
            if event.type == ActionEventType.FALL_ESCALATED
            else AlertSeverity.MEDIUM
        )
        check = WellnessCheck(
            id=new_id("well"),
            type=WellnessCheckType.POSSIBLE_FALL_CHECK,
            severity=severity,
            status=WellnessCheckStatus.OPEN,
            title="Possible fall candidate",
            body="This notification has been escalated to the caregiver for a possible fall.",
            confidence=event.confidence,
            occurred_at=event.occurred_at,
            created_at=utc_now(),
            zone_id=event.zone_id,
            zone_name=event.zone_name,
            evidence_ids=event.evidence_ids,
            metadata={
                "source": "action_event",
                "action_event_id": event.id,
                "action_event_type": event.type.value,
                "source_node_id": event.source_node_id,
                "reason": "action_fall_persistent",
                "notification_kind": "possible_fall_check",
                "notification_required": True,
                "requires_live_verification": True,
                "human_verification_required": True,
                "debounce_seconds": self._settings.action_fall_debounce_seconds,
            },
        )
        return self._data_spine.create_wellness_check(check)

    def _recent_fall_check(self, event: ActionEvent) -> WellnessCheck | None:
        cutoff = event.occurred_at - timedelta(seconds=self._settings.action_fall_debounce_seconds)
        for check in self._data_spine.list_wellness_checks_for_date(event.occurred_at.date()):
            if check.type != WellnessCheckType.POSSIBLE_FALL_CHECK:
                continue
            if check.metadata.get("reason") != "action_fall_persistent":
                continue
            if event.source_node_id and check.metadata.get("source_node_id") != event.source_node_id:
                continue
            if check.occurred_at >= cutoff:
                return check
        return None

    def _create_drink_hydration_event(self, event: ActionEvent) -> HydrationEvent:
        hydration = HydrationEvent(
            id=new_id("hyd"),
            type=HydrationEventType.DRINK_CANDIDATE,
            occurred_at=event.occurred_at,
            confidence=event.confidence,
            zone_id=event.zone_id,
            zone_name=event.zone_name,
            evidence_ids=event.evidence_ids,
            metadata={
                "source": "action_event",
                "action_event_id": event.id,
                "action_source": event.source,
                "notification_kind": "hydration_prompt",
                "notification_required": True,
                "human_verification_required": True,
                **event.metadata,
            },
        )
        return self._data_spine.create_hydration_event(hydration)

    def _fall_adapter_status(self, request: FallEvaluateRequest) -> str:
        if request.source != "local_yolo_fall":
            return "telemetry_input"
        status = self._fall_adapter.status()
        if not status.available:
            return status.unavailable_reason or "runtime_unavailable"
        return "configured"

    @staticmethod
    def _fall_model_runtime_required(request: FallEvaluateRequest) -> bool:
        return request.require_model_runtime or request.source == "local_yolo_fall"

    @staticmethod
    def _is_fallen_signal(request: FallEvaluateRequest) -> bool:
        if request.fallen is True:
            return True
        if request.posture_state is None:
            return False
        normalized = request.posture_state.strip().lower().replace("-", "_").replace(" ", "_")
        return normalized in FALL_POSTURE_STATES

    @staticmethod
    def _fall_metadata(request: FallEvaluateRequest) -> dict[str, Any]:
        return {
            "posture_state": request.posture_state,
            "fallen": request.fallen,
            "persistence_seconds": request.persistence_seconds,
            **request.metadata,
        }

    def _would_be_inconclusive_fall(self, request: FallEvaluateRequest) -> bool:
        model_status = self._fall_adapter_status(request)
        threshold = self._settings.action_fall_persistence_seconds
        if self._fall_model_runtime_required(request) and model_status != "configured":
            return True
        return not self._is_fallen_signal(request) or request.persistence_seconds < threshold

    def _transient_inconclusive_fall_event(self, request: FallEvaluateRequest) -> ActionEvent:
        zones = self._zone_names()
        model_status = self._fall_adapter_status(request)
        threshold = self._settings.action_fall_persistence_seconds
        return ActionEvent(
            id=new_id("act"),
            type=ActionEventType.ACTION_INCONCLUSIVE,
            occurred_at=_as_utc(request.occurred_at) or utc_now(),
            confidence=request.confidence,
            score=request.score,
            source=request.source,
            source_node_id=request.source_node_id,
            zone_id=request.zone_id,
            zone_name=zones.get(request.zone_id or ""),
            evidence_ids=request.evidence_ids,
            metadata={
                "persisted": False,
                "reason": "automatic_fall_scan_inconclusive",
                "required_persistence_seconds": threshold,
                "adapter_status": model_status,
                "human_verification_required": True,
                **self._fall_metadata(request),
            },
        )

    def _fall_persistence_seconds_for_inference(
        self,
        *,
        result: FallInferenceResult,
        source_node_id: str | None,
        zone_id: str | None,
        occurred_at: datetime,
    ) -> float:
        key = _fall_inference_key(source_node_id=source_node_id, zone_id=zone_id)
        if result.fallen is not True:
            _reset_fall_inference_state(key)
            return 0.0
        return _update_fall_inference_state(
            key=key,
            occurred_at=occurred_at,
            reset_gap_seconds=max(self._settings.action_fall_persistence_seconds * 2, 5.0),
        )

    def _zone_names(self) -> dict[str, str]:
        return {zone.id: zone.name for zone in self._data_spine.list_home_zones()}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _confidence_from_score(score: float | None) -> QueryConfidence:
    if score is None:
        return QueryConfidence.LOW
    if score >= 0.8:
        return QueryConfidence.HIGH
    if score >= 0.5:
        return QueryConfidence.MEDIUM
    return QueryConfidence.LOW


@dataclass
class _FallInferenceState:
    active_since: datetime
    last_seen_at: datetime


_fall_inference_states: dict[str, _FallInferenceState] = {}
_fall_inference_lock = Lock()


def _fall_inference_key(*, source_node_id: str | None, zone_id: str | None) -> str:
    source = (source_node_id or "unknown_source").strip() or "unknown_source"
    zone = (zone_id or "unknown_zone").strip() or "unknown_zone"
    return f"{source}:{zone}"


def _update_fall_inference_state(
    *,
    key: str,
    occurred_at: datetime,
    reset_gap_seconds: float,
) -> float:
    with _fall_inference_lock:
        state = _fall_inference_states.get(key)
        if (
            state is None
            or (occurred_at - state.last_seen_at).total_seconds() > reset_gap_seconds
        ):
            state = _FallInferenceState(active_since=occurred_at, last_seen_at=occurred_at)
            _fall_inference_states[key] = state
            return 0.0
        state.last_seen_at = occurred_at
        return max(0.0, (occurred_at - state.active_since).total_seconds())


def _reset_fall_inference_state(key: str) -> None:
    with _fall_inference_lock:
        _fall_inference_states.pop(key, None)
