from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable

from app.ids import new_id
from app.schemas import (
    Alert,
    AlertSeverity,
    HydrationEvent,
    HydrationEventType,
    HydrationStatus,
    HydrationSummary,
    HumanPresence,
    Observation,
    QueryConfidence,
    Task,
    WellnessAckBy,
    WellnessCheck,
    WellnessCheckStatus,
    WellnessCheckType,
    utc_now,
)
from app.services import DataSpineService


WATER_OBJECT_KEYS = {
    "bottle",
    "cup",
    "drinking_glass",
    "faucet",
    "glass",
    "mug",
    "sink",
    "tap",
    "water",
    "water_bottle",
}

FALL_SIGNAL_WORDS = {
    "collapse",
    "collapsed",
    "fall",
    "fallen",
    "floor_posture",
    "horizontal_posture",
    "lying_on_floor",
}

STILLNESS_SIGNAL_WORDS = {
    "immobile",
    "motionless",
    "no_movement",
    "prolonged_lack_of_movement",
    "stillness",
    "unusual_stillness",
}


class HydrationWellnessService:
    def __init__(self, data_spine: DataSpineService) -> None:
        self._data_spine = data_spine

    def hydration_summary(self, summary_date: date) -> HydrationSummary:
        events = self._hydration_events(summary_date)
        intake_events = self._intake_events(events)
        evidence_ids = self._unique_evidence_ids(events)
        latest = max((event.occurred_at for event in intake_events), default=None)
        observations = self._data_spine.list_observations_for_date(summary_date)
        status = self._hydration_status(intake_events, observations)
        return HydrationSummary(
            date=summary_date,
            status=status,
            water_events=len(intake_events),
            latest_event_at=latest,
            message=self._hydration_message(
                status,
                len(intake_events),
                has_observations=bool(observations),
                has_context=bool(events),
            ),
            evidence_ids=evidence_ids,
            events=events,
        )

    def create_hydration_event(
        self,
        *,
        event_type: HydrationEventType,
        occurred_at: datetime | None,
        confidence: QueryConfidence,
        zone_id: str | None,
        evidence_ids: list[str],
        metadata: dict[str, Any],
    ) -> HydrationEvent:
        zones = self._zone_names()
        event = HydrationEvent(
            id=new_id("hyd"),
            type=event_type,
            occurred_at=_as_utc(occurred_at) or utc_now(),
            confidence=confidence,
            zone_id=zone_id,
            zone_name=zones.get(zone_id or ""),
            evidence_ids=evidence_ids,
            metadata={
                "source": "caregiver_or_api_report",
                "human_verification_required": True,
                **metadata,
            },
        )
        return self._data_spine.create_hydration_event(event)

    def list_wellness_checks(self, check_date: date) -> list[WellnessCheck]:
        return self._data_spine.list_wellness_checks_for_date(check_date)

    def generate_wellness_checks(self, check_date: date) -> list[WellnessCheck]:
        existing = self._data_spine.list_wellness_checks_for_date(check_date)
        candidates = [
            *self._hydration_check_candidates(check_date),
            *self._observation_wellness_candidates(check_date),
            *self._task_alert_wellness_candidates(check_date),
        ]
        for candidate in candidates:
            if self._has_equivalent_check(existing, candidate):
                continue
            created = self._data_spine.create_wellness_check(candidate)
            existing.append(created)
        return sorted(existing, key=lambda item: item.created_at, reverse=True)

    def acknowledge_wellness_check(
        self,
        check_id: str,
        *,
        acknowledged_by: WellnessAckBy,
        note: str | None,
    ) -> WellnessCheck | None:
        check = self._data_spine.get_wellness_check(check_id)
        if check is None:
            return None
        if check.status == WellnessCheckStatus.ACKNOWLEDGED:
            return check
        acknowledged = check.model_copy(
            update={
                "status": WellnessCheckStatus.ACKNOWLEDGED,
                "acknowledged_at": utc_now(),
                "metadata": {
                    **check.metadata,
                    "acknowledged_by": acknowledged_by.value,
                    "acknowledgement_note": note,
                },
            }
        )
        return self._data_spine.update_wellness_check(acknowledged)

    def _hydration_events(self, summary_date: date) -> list[HydrationEvent]:
        stored = self._data_spine.list_hydration_events_for_date(summary_date)
        derived = self._derived_water_visible_events(summary_date, stored)
        return sorted([*stored, *derived], key=lambda item: item.occurred_at, reverse=True)

    def _derived_water_visible_events(
        self,
        summary_date: date,
        stored: list[HydrationEvent],
    ) -> list[HydrationEvent]:
        zones = self._zone_names()
        linked_observation_ids = {
            evidence_id
            for event in stored
            if event.type == HydrationEventType.WATER_VISIBLE
            for evidence_id in event.evidence_ids
        }
        events: list[HydrationEvent] = []
        for observation in self._data_spine.list_observations_for_date(summary_date):
            if observation.id in linked_observation_ids:
                continue
            matches = [
                obj
                for obj in observation.objects
                if self._is_water_candidate(obj.object_key, obj.display_name, obj.label)
            ]
            if not matches:
                continue
            object_keys = sorted({obj.object_key for obj in matches})
            events.append(
                HydrationEvent(
                    id=f"hyd_obs_{observation.id}",
                    type=HydrationEventType.WATER_VISIBLE,
                    occurred_at=observation.timestamp_utc,
                    confidence=self._confidence_from_values(
                        [obj.confidence for obj in matches],
                        observation.confidence,
                    ),
                    zone_id=observation.room_id,
                    zone_name=zones.get(observation.room_id),
                    evidence_ids=[observation.id],
                    metadata={
                        "source": "afferens_observation",
                        "object_keys": object_keys,
                        "human_presence": observation.human_presence.value,
                        "candidate_only": True,
                    },
                )
            )
        return events

    def _hydration_check_candidates(self, check_date: date) -> list[WellnessCheck]:
        summary = self.hydration_summary(check_date)
        if summary.status == HydrationStatus.OKAY:
            return []

        now = utc_now()
        if summary.status == HydrationStatus.UNKNOWN:
            severity = AlertSeverity.LOW
            confidence = QueryConfidence.LOW
            title = "Hydration check-in"
            body = (
                "No hydration-related live evidence is available for this date. "
                "Consider a gentle check-in if hydration matters."
            )
            reason = "no_hydration_evidence"
        elif summary.water_events == 0:
            severity = AlertSeverity.MEDIUM
            confidence = QueryConfidence.MEDIUM
            title = "Hydration check"
            body = (
                "No drink action or caregiver-confirmed hydration has been recorded today. "
                "Water or cup visibility alone is context only; consider checking in."
            )
            reason = "no_drink_action_or_confirmation"
        else:
            severity = AlertSeverity.LOW
            confidence = QueryConfidence.LOW
            title = "Hydration reminder"
            body = (
                "Only limited water-nearby evidence has appeared today. "
                "Consider a gentle reminder if hydration is important."
            )
            reason = "limited_water_candidate_evidence"

        return [
            WellnessCheck(
                id=new_id("well"),
                type=WellnessCheckType.HYDRATION_PROMPT,
                severity=severity,
                status=WellnessCheckStatus.OPEN,
                title=title,
                body=body,
                confidence=confidence,
                occurred_at=summary.latest_event_at or _start_of_day_utc(check_date),
                created_at=now,
                evidence_ids=summary.evidence_ids,
                metadata={
                    "generated_for_date": check_date.isoformat(),
                    "reason": reason,
                    "hydration_status": summary.status.value,
                    "water_events": summary.water_events,
                    "notification_kind": "hydration_prompt",
                    "notification_required": True,
                    "human_verification_required": True,
                },
            )
        ]

    def _observation_wellness_candidates(self, check_date: date) -> list[WellnessCheck]:
        zones = self._zone_names()
        checks: list[WellnessCheck] = []
        for observation in self._data_spine.list_observations_for_date(check_date):
            signals = self._observation_signal_words(observation)
            if signals & STILLNESS_SIGNAL_WORDS:
                checks.append(
                    self._wellness_candidate_from_observation(
                        observation,
                        zones,
                        check_type=WellnessCheckType.UNUSUAL_STILLNESS_CHECK,
                        severity=AlertSeverity.MEDIUM,
                        title="Unusual stillness check",
                        body=(
                            "A possible prolonged-stillness cue appears in evidence. "
                            "Please check in; human verification is required."
                        ),
                        reason="possible_stillness_signal",
                    )
                )
        return checks

    def _task_alert_wellness_candidates(self, check_date: date) -> list[WellnessCheck]:
        checks: list[WellnessCheck] = []
        for task in self._data_spine.list_tasks():
            if task.created_at.date() != check_date:
                continue
            signal = self._task_signal(task)
            candidate = self._wellness_candidate_from_task(task, signal)
            if candidate is not None:
                checks.append(candidate)
        for alert in self._data_spine.list_alerts():
            if alert.created_at.date() != check_date:
                continue
            signal = self._alert_signal(alert)
            candidate = self._wellness_candidate_from_alert(alert, signal)
            if candidate is not None:
                checks.append(candidate)
        return checks

    def _wellness_candidate_from_observation(
        self,
        observation: Observation,
        zones: dict[str, str],
        *,
        check_type: WellnessCheckType,
        severity: AlertSeverity,
        title: str,
        body: str,
        reason: str,
    ) -> WellnessCheck:
        return WellnessCheck(
            id=new_id("well"),
            type=check_type,
            severity=severity,
            status=WellnessCheckStatus.OPEN,
            title=title,
            body=body,
            confidence=QueryConfidence.MEDIUM,
            occurred_at=observation.timestamp_utc,
            created_at=utc_now(),
            zone_id=observation.room_id,
            zone_name=zones.get(observation.room_id),
            evidence_ids=[observation.id],
            metadata={
                "generated_for_date": observation.timestamp_utc.date().isoformat(),
                "source": "afferens_observation",
                "reason": reason,
                "risk_signals": observation.risk_signals,
                "human_presence": observation.human_presence.value,
                "human_verification_required": True,
            },
        )

    def _wellness_candidate_from_task(
        self,
        task: Task,
        signal: str,
    ) -> WellnessCheck | None:
        check_type = self._wellness_type_from_signal(signal)
        if check_type is None:
            return None
        return WellnessCheck(
            id=new_id("well"),
            type=check_type,
            severity=AlertSeverity.MEDIUM,
            status=WellnessCheckStatus.OPEN,
            title="Caregiver review",
            body=(
                "An existing task includes a possible wellness cue. "
                "Please check in and verify the situation in person."
            ),
            confidence=QueryConfidence.MEDIUM,
            occurred_at=task.created_at,
            created_at=utc_now(),
            zone_id=task.metadata.get("room_id"),
            evidence_ids=task.evidence_observation_ids,
            metadata={
                "generated_for_date": task.created_at.date().isoformat(),
                "source": "task",
                "task_id": task.id,
                "reason": signal,
                "human_verification_required": True,
            },
        )

    def _wellness_candidate_from_alert(
        self,
        alert: Alert,
        signal: str,
    ) -> WellnessCheck | None:
        check_type = self._wellness_type_from_signal(signal)
        if check_type is None:
            return None
        return WellnessCheck(
            id=new_id("well"),
            type=check_type,
            severity=alert.severity,
            status=WellnessCheckStatus.OPEN,
            title="Caregiver review",
            body=(
                "An existing alert includes a possible wellness cue. "
                "Please check in and verify the situation in person."
            ),
            confidence=self._confidence_from_severity(alert.severity),
            occurred_at=alert.created_at,
            created_at=utc_now(),
            evidence_ids=alert.evidence_observation_ids,
            metadata={
                "generated_for_date": alert.created_at.date().isoformat(),
                "source": "alert",
                "alert_id": alert.id,
                "task_id": alert.task_id,
                "reason": signal,
                "human_verification_required": True,
            },
        )

    @staticmethod
    def _hydration_status(
        events: list[HydrationEvent],
        observations: list[Observation],
    ) -> HydrationStatus:
        if len(events) >= 2:
            return HydrationStatus.OKAY
        if events or observations:
            return HydrationStatus.CONSIDER_PROMPTING
        return HydrationStatus.UNKNOWN

    @staticmethod
    def _hydration_message(
        status: HydrationStatus,
        water_events: int,
        has_observations: bool,
        has_context: bool,
    ) -> str:
        if status == HydrationStatus.OKAY:
            return (
                f"I saw {water_events} possible drink action or caregiver-confirmed hydration events today. "
                "Please verify in person if hydration is important."
            )
        if status == HydrationStatus.CONSIDER_PROMPTING and water_events:
            return (
                "I saw limited possible drink action or caregiver-confirmed hydration evidence today. "
                "This still needs human context; consider a gentle check-in."
            )
        if status == HydrationStatus.CONSIDER_PROMPTING and has_context:
            return (
                "Water, cup, or bottle context may be visible, but no drink action or caregiver "
                "confirmation is recorded. Object visibility alone does not count as hydration."
            )
        if status == HydrationStatus.CONSIDER_PROMPTING and has_observations:
            return (
                "Live evidence was available today, but no drink action or caregiver-confirmed "
                "hydration is recorded. Consider checking in."
            )
        return (
            "No live hydration evidence is available for this date. "
            "If hydration matters, please use in-person context."
        )

    @staticmethod
    def _intake_events(events: list[HydrationEvent]) -> list[HydrationEvent]:
        return [
            event
            for event in events
            if event.type
            in {HydrationEventType.DRINK_CANDIDATE, HydrationEventType.CAREGIVER_REPORTED}
        ]

    @staticmethod
    def _is_water_candidate(*values: str) -> bool:
        for value in values:
            normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
            if normalized in WATER_OBJECT_KEYS:
                return True
            tokens = {token for token in normalized.split("_") if token}
            if tokens & WATER_OBJECT_KEYS:
                return True
        return False

    @staticmethod
    def _confidence_from_values(
        confidences: Iterable[float | None],
        fallback: float | None,
    ) -> QueryConfidence:
        values = [value for value in confidences if value is not None]
        confidence = sum(values) / len(values) if values else fallback
        if confidence is None or confidence < 0.5:
            return QueryConfidence.LOW
        if confidence < 0.8:
            return QueryConfidence.MEDIUM
        return QueryConfidence.HIGH

    @staticmethod
    def _confidence_from_severity(severity: AlertSeverity) -> QueryConfidence:
        if severity == AlertSeverity.HIGH:
            return QueryConfidence.HIGH
        if severity == AlertSeverity.MEDIUM:
            return QueryConfidence.MEDIUM
        return QueryConfidence.LOW

    @staticmethod
    def _observation_signal_words(observation: Observation) -> set[str]:
        signals = set(_signal_tokens(observation.risk_signals))
        signals |= set(_signal_tokens(observation.evidence_metadata.values()))
        if observation.human_presence == HumanPresence.VISIBLE:
            signals.add("human_visible")
        return signals

    @staticmethod
    def _task_signal(task: Task) -> str:
        values = [
            task.title,
            task.body,
            task.metadata.get("hazard_type"),
            task.metadata.get("wellness_signal"),
            task.metadata.get("reason"),
        ]
        return " ".join(_signal_tokens(values))

    @staticmethod
    def _alert_signal(alert: Alert) -> str:
        return " ".join(_signal_tokens([alert.hazard_type, alert.title, alert.body]))

    @staticmethod
    def _wellness_type_from_signal(signal: str) -> WellnessCheckType | None:
        tokens = set(_signal_tokens([signal]))
        if tokens & FALL_SIGNAL_WORDS:
            return WellnessCheckType.POSSIBLE_FALL_CHECK
        if tokens & STILLNESS_SIGNAL_WORDS:
            return WellnessCheckType.UNUSUAL_STILLNESS_CHECK
        return None

    @staticmethod
    def _has_equivalent_check(
        existing: list[WellnessCheck],
        candidate: WellnessCheck,
    ) -> bool:
        candidate_reason = candidate.metadata.get("reason")
        candidate_date = candidate.metadata.get("generated_for_date")
        candidate_evidence = set(candidate.evidence_ids)
        for check in existing:
            if check.type != candidate.type:
                continue
            if check.metadata.get("generated_for_date") != candidate_date:
                continue
            if check.metadata.get("reason") != candidate_reason:
                continue
            if not candidate_evidence or candidate_evidence & set(check.evidence_ids):
                return True
        return False

    def _zone_names(self) -> dict[str, str]:
        return {zone.id: zone.name for zone in self._data_spine.list_home_zones()}

    @staticmethod
    def _unique_evidence_ids(events: list[HydrationEvent]) -> list[str]:
        evidence_ids: list[str] = []
        for event in events:
            for evidence_id in event.evidence_ids:
                if evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)
        return evidence_ids


def _signal_tokens(values: Iterable[Any]) -> list[str]:
    tokens: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            tokens.extend(_signal_tokens([*value.keys(), *value.values()]))
            continue
        if isinstance(value, (list, tuple, set)):
            tokens.extend(_signal_tokens(value))
            continue
        for part in str(value).lower().replace("-", "_").replace(" ", "_").split("_"):
            if part:
                tokens.append(part)
        joined = str(value).lower().replace("-", "_").replace(" ", "_")
        if joined:
            tokens.append(joined)
    return tokens


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _start_of_day_utc(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
