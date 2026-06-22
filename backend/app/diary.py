from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.ids import new_id
from app.providers.fireworks import (
    FireworksProviderError,
    FireworksProviderUnavailable,
    FireworksReasoningAdapter,
)
from app.schemas import (
    ActuationAttempt,
    ActionEvent,
    ActionEventType,
    ActivityEvent,
    ActivityEventType,
    Alert,
    AlertSeverity,
    CareNote,
    CareNoteAudience,
    DailyDiaryEntry,
    FamilyMessage,
    FamilyMessagePriority,
    FamilyMessageStatus,
    HydrationEvent,
    HydrationEventType,
    Observation,
    QueryConfidence,
    Task,
    TaskState,
    WellnessCheck,
    WellnessCheckStatus,
    WellnessCheckType,
    utc_now,
)
from app.services import DataSpineService


RESOLVED_TASK_STATES = {
    TaskState.VERIFIED_RESOLVED,
    TaskState.DISMISSED,
}


class DailyCareService:
    def __init__(
        self,
        data_spine: DataSpineService,
        *,
        fireworks: FireworksReasoningAdapter | None = None,
    ) -> None:
        self._data_spine = data_spine
        self._fireworks = fireworks

    def activity_timeline(self, activity_date: date) -> list[ActivityEvent]:
        zones = {zone.id: zone.name for zone in self._data_spine.list_home_zones()}
        observations = self._data_spine.list_observations_for_date(activity_date)
        tasks = self._data_spine.list_tasks()
        alerts = self._data_spine.list_alerts()
        attempts = self._data_spine.list_actuation_attempts_for_date(activity_date)
        messages = self._data_spine.list_family_messages(include_acknowledged=True)
        hydration_events = self._data_spine.list_hydration_events_for_date(activity_date)
        action_events = self._data_spine.list_action_events(event_date=activity_date, limit=100)
        wellness_checks = self._data_spine.list_wellness_checks_for_date(activity_date)
        care_notes = self._data_spine.list_care_notes(activity_date)

        events: list[ActivityEvent] = []
        for observation in observations:
            events.extend(self._events_from_observation(observation, zones))
        for hydration_event in hydration_events:
            events.append(self._event_from_hydration_event(hydration_event, zones))
        for action_event in action_events:
            events.append(self._event_from_action_event(action_event, zones))
        for wellness_check in wellness_checks:
            events.extend(self._events_from_wellness_check(wellness_check, zones, activity_date))
        for task in tasks:
            events.extend(self._events_from_task(task, activity_date))
        for alert in alerts:
            events.extend(self._events_from_alert(alert, activity_date))
        for attempt in attempts:
            events.append(self._event_from_actuation_attempt(attempt))
        for message in messages:
            events.extend(self._events_from_family_message(message, activity_date))
        for care_note in care_notes:
            events.append(self._event_from_care_note(care_note))

        return sorted(
            self._dedupe_activity_events(events),
            key=lambda event: event.occurred_at,
            reverse=True,
        )

    def get_diary(self, entry_date: date) -> DailyDiaryEntry | None:
        return self._data_spine.get_daily_diary(entry_date)

    def generate_diary(self, entry_date: date) -> DailyDiaryEntry:
        events = list(reversed(self.activity_timeline(entry_date)))
        evidence_ids = self._unique_evidence_ids(events)
        highlights = self._diary_highlights(events)
        needs_review = self._review_items(events)
        summary = self._diary_summary(entry_date, events, highlights, needs_review)
        diary = DailyDiaryEntry(
            id=new_id("diary"),
            date=entry_date,
            summary=summary,
            highlights=highlights,
            needs_review=needs_review,
            evidence_ids=evidence_ids,
            generated_at=utc_now(),
            source="deterministic",
        )
        return self._data_spine.upsert_daily_diary(diary)

    async def generate_diary_with_provider(self, entry_date: date) -> DailyDiaryEntry:
        events = list(reversed(self.activity_timeline(entry_date)))
        evidence_ids = self._unique_evidence_ids(events)
        highlights = self._diary_highlights(events)
        needs_review = self._review_items(events)
        summary = self._diary_summary(entry_date, events, highlights, needs_review)
        source = "deterministic"
        synthesized = await self._synthesize_diary_if_available(
            entry_date=entry_date,
            events=events,
            deterministic={
                "summary": summary,
                "highlights": highlights,
                "needs_review": needs_review,
            },
        )
        if synthesized is not None:
            summary = synthesized.get("summary") or summary
            highlights = synthesized.get("highlights") or highlights
            needs_review = synthesized.get("needs_review") or needs_review
            source = "fireworks"

        diary = DailyDiaryEntry(
            id=new_id("diary"),
            date=entry_date,
            summary=summary,
            highlights=highlights,
            needs_review=needs_review,
            evidence_ids=evidence_ids,
            generated_at=utc_now(),
            source=source,
        )
        return self._data_spine.upsert_daily_diary(diary)

    def list_care_notes(self, note_date: date) -> list[CareNote]:
        return self._data_spine.list_care_notes(note_date)

    def generate_care_note(self, note_date: date, audience: CareNoteAudience) -> CareNote:
        events = list(reversed(self.activity_timeline(note_date)))
        evidence_ids = self._unique_evidence_ids(events)
        bullets = self._care_bullets(events)
        risks = self._care_risks(events)
        follow_ups = self._care_follow_ups(events, risks)
        summary = self._care_summary(note_date, audience, events, risks)
        note = CareNote(
            id=new_id("carenote"),
            date=note_date,
            audience=audience,
            summary=summary,
            bullets=bullets,
            risks=risks,
            follow_ups=follow_ups,
            evidence_ids=evidence_ids,
            created_at=utc_now(),
            source="deterministic",
        )
        return self._data_spine.create_care_note(note)

    async def generate_care_note_with_provider(
        self,
        note_date: date,
        audience: CareNoteAudience,
    ) -> CareNote:
        events = list(reversed(self.activity_timeline(note_date)))
        evidence_ids = self._unique_evidence_ids(events)
        bullets = self._care_bullets(events)
        risks = self._care_risks(events)
        follow_ups = self._care_follow_ups(events, risks)
        summary = self._care_summary(note_date, audience, events, risks)
        source = "deterministic"
        synthesized = await self._synthesize_care_note_if_available(
            note_date=note_date,
            audience=audience,
            events=events,
            deterministic={
                "summary": summary,
                "bullets": bullets,
                "risks": risks,
                "follow_ups": follow_ups,
            },
        )
        if synthesized is not None:
            summary = synthesized.get("summary") or summary
            bullets = synthesized.get("bullets") or bullets
            risks = synthesized.get("risks") or risks
            follow_ups = synthesized.get("follow_ups") or follow_ups
            source = "fireworks"

        note = CareNote(
            id=new_id("carenote"),
            date=note_date,
            audience=audience,
            summary=summary,
            bullets=bullets,
            risks=risks,
            follow_ups=follow_ups,
            evidence_ids=evidence_ids,
            created_at=utc_now(),
            source=source,
        )
        return self._data_spine.create_care_note(note)

    def list_family_messages(
        self,
        *,
        include_acknowledged: bool = False,
    ) -> list[FamilyMessage]:
        return self._data_spine.list_family_messages(
            include_acknowledged=include_acknowledged,
        )

    def active_family_messages(self) -> list[FamilyMessage]:
        now = utc_now()
        active: list[FamilyMessage] = []
        for message in self._data_spine.list_family_messages(include_acknowledged=False):
            starts_at = _as_utc(message.starts_at)
            expires_at = _as_utc(message.expires_at)
            if message.acknowledged_at is not None:
                continue
            if expires_at is not None and expires_at <= now:
                continue
            if starts_at is not None and starts_at > now:
                continue
            if message.status == FamilyMessageStatus.ACKNOWLEDGED:
                continue
            if message.status == FamilyMessageStatus.SCHEDULED:
                message = message.model_copy(update={"status": FamilyMessageStatus.ACTIVE})
            active.append(message)
        return sorted(active, key=lambda item: (self._priority_rank(item.priority), item.created_at), reverse=True)

    def create_family_message(
        self,
        *,
        title: str,
        body: str,
        priority: FamilyMessagePriority,
        trigger_object_key: str | None,
        trigger_zone_id: str | None,
        starts_at: datetime | None,
        expires_at: datetime | None,
    ) -> FamilyMessage:
        now = utc_now()
        starts_at = _as_utc(starts_at)
        expires_at = _as_utc(expires_at)
        status = FamilyMessageStatus.ACTIVE
        if expires_at is not None and expires_at <= now:
            status = FamilyMessageStatus.EXPIRED
        elif starts_at is not None and starts_at > now:
            status = FamilyMessageStatus.SCHEDULED
        message = FamilyMessage(
            id=new_id("fammsg"),
            title=title,
            body=body,
            priority=priority,
            status=status,
            trigger_object_key=trigger_object_key,
            trigger_zone_id=trigger_zone_id,
            starts_at=starts_at,
            expires_at=expires_at,
            created_at=now,
            metadata={"created_by": "caregiver"},
        )
        return self._data_spine.create_family_message(message)

    def acknowledge_family_message(self, message_id: str) -> FamilyMessage | None:
        message = self._data_spine.get_family_message(message_id)
        if message is None:
            return None
        acknowledged = message.model_copy(
            update={
                "status": FamilyMessageStatus.ACKNOWLEDGED,
                "acknowledged_at": utc_now(),
                "metadata": {**message.metadata, "acknowledged_by": "caregiver"},
            }
        )
        return self._data_spine.update_family_message(acknowledged)

    def _events_from_observation(
        self,
        observation: Observation,
        zones: dict[str, str],
    ) -> list[ActivityEvent]:
        if not observation.objects:
            return []
        labels = [obj.display_name for obj in observation.objects]
        label_text = self._join_human(labels[:4])
        zone_name = zones.get(observation.room_id)
        location_text = f" in {zone_name}" if zone_name else ""
        context_labels = self._observation_context_labels(observation)
        title = "Objects noted"
        if "breakfast_like_activity" in context_labels:
            title = "Breakfast-like activity"
        elif "meal_like_activity" in context_labels:
            title = "Meal-like activity"
        elif "water_nearby" in context_labels:
            title = "Water nearby"
        body = f"{label_text} appeared in live Afferens evidence{location_text}."
        if "water_nearby" in context_labels:
            body += " This is water-nearby context only and does not count as drinking."
        return [
            ActivityEvent(
                id=f"actevt_obs_{observation.id}",
                type=ActivityEventType.OBJECT_SEEN,
                title=f"{title}{location_text}",
                body=body,
                occurred_at=observation.timestamp_utc,
                source="afferens_observation",
                confidence=self._confidence_from_observation(observation),
                zone_id=observation.room_id,
                zone_name=zone_name,
                evidence_ids=[observation.id],
                metadata={
                    "object_keys": [obj.object_key for obj in observation.objects],
                    "object_labels": [obj.label for obj in observation.objects],
                    "source_ids": [observation.id],
                    "conservative_labels": context_labels,
                    "human_presence": observation.human_presence.value,
                },
            )
        ]

    def _event_from_hydration_event(
        self,
        hydration_event: HydrationEvent,
        zones: dict[str, str],
    ) -> ActivityEvent:
        zone_name = hydration_event.zone_name or zones.get(hydration_event.zone_id or "")
        title_by_type = {
            HydrationEventType.WATER_VISIBLE: "Water nearby",
            HydrationEventType.DRINK_CANDIDATE: "Possible drink action",
            HydrationEventType.CAREGIVER_REPORTED: "Caregiver-confirmed hydration note",
        }
        body_by_type = {
            HydrationEventType.WATER_VISIBLE: (
                "Water, a cup, or a bottle was visible as context only. "
                "This does not count as drinking by itself."
            ),
            HydrationEventType.DRINK_CANDIDATE: (
                "A possible drink action candidate was recorded from action evidence. "
                "Please treat it as a candidate, not certainty."
            ),
            HydrationEventType.CAREGIVER_REPORTED: (
                "A caregiver or trusted reporter recorded hydration context. "
                "Please keep ordinary verification for important decisions."
            ),
        }
        return ActivityEvent(
            id=f"actevt_hydration_{hydration_event.id}",
            type=ActivityEventType.OBJECT_SEEN,
            title=title_by_type[hydration_event.type],
            body=body_by_type[hydration_event.type],
            occurred_at=hydration_event.occurred_at,
            source="hydration_event",
            confidence=hydration_event.confidence,
            zone_id=hydration_event.zone_id,
            zone_name=zone_name,
            evidence_ids=hydration_event.evidence_ids,
            metadata={
                **hydration_event.metadata,
                "hydration_event_id": hydration_event.id,
                "hydration_type": hydration_event.type.value,
                "source_ids": [hydration_event.id],
                "conservative_labels": [self._hydration_label(hydration_event.type)],
            },
        )

    def _event_from_action_event(
        self,
        action_event: ActionEvent,
        zones: dict[str, str],
    ) -> ActivityEvent:
        zone_name = action_event.zone_name or zones.get(action_event.zone_id or "")
        if action_event.type == ActionEventType.DRINK_CANDIDATE:
            title = "Possible drink action"
            body = (
                "Action telemetry recorded a possible drink action candidate. "
                "This remains a candidate and should be verified if important."
            )
            event_type = ActivityEventType.OBJECT_SEEN
            labels = ["possible_drink_action"]
        elif action_event.type in {ActionEventType.FALL_CANDIDATE, ActionEventType.FALL_ESCALATED}:
            title = "Possible fall candidate"
            body = "This notification has been escalated to the caregiver for a possible fall."
            event_type = ActivityEventType.SAFETY_ALERT
            labels = ["possible_fall_check"]
        else:
            title = "Action telemetry inconclusive"
            body = (
                "Action telemetry was recorded as inconclusive. "
                "No drink or fall conclusion should be inferred from this item."
            )
            event_type = ActivityEventType.OBJECT_SEEN
            labels = ["action_inconclusive"]
        return ActivityEvent(
            id=f"actevt_action_{action_event.id}",
            type=event_type,
            title=title,
            body=body,
            occurred_at=action_event.occurred_at,
            source="action_event",
            confidence=action_event.confidence,
            zone_id=action_event.zone_id,
            zone_name=zone_name,
            evidence_ids=action_event.evidence_ids,
            metadata={
                **action_event.metadata,
                "action_event_id": action_event.id,
                "action_event_type": action_event.type.value,
                "action_source": action_event.source,
                "source_ids": [action_event.id],
                "conservative_labels": labels,
            },
        )

    def _events_from_wellness_check(
        self,
        check: WellnessCheck,
        zones: dict[str, str],
        activity_date: date,
    ) -> list[ActivityEvent]:
        zone_name = check.zone_name or zones.get(check.zone_id or "")
        labels = [self._wellness_label(check.type)]
        events: list[ActivityEvent] = []
        if check.occurred_at.date() == activity_date:
            events.append(
                ActivityEvent(
                    id=f"actevt_wellness_{check.id}",
                    type=ActivityEventType.SAFETY_ALERT,
                    title=check.title,
                    body=f"{check.body} Please verify in person; no medical conclusion is implied.",
                    occurred_at=check.occurred_at,
                    source="wellness_check",
                    confidence=check.confidence,
                    zone_id=check.zone_id,
                    zone_name=zone_name,
                    evidence_ids=check.evidence_ids,
                    metadata={
                        **check.metadata,
                        "wellness_check_id": check.id,
                        "wellness_type": check.type.value,
                        "status": check.status.value,
                        "source_ids": [check.id],
                        "conservative_labels": labels,
                    },
                )
            )
        if check.acknowledged_at is not None and check.acknowledged_at.date() == activity_date:
            events.append(
                ActivityEvent(
                    id=f"actevt_wellness_ack_{check.id}",
                    type=ActivityEventType.ALERT_ACKNOWLEDGED,
                    title=f"Acknowledged: {check.title}",
                    body="A caregiver acknowledged this wellness check. Continue ordinary verification for important details.",
                    occurred_at=check.acknowledged_at,
                    source="wellness_check",
                    confidence=check.confidence,
                    zone_id=check.zone_id,
                    zone_name=zone_name,
                    evidence_ids=check.evidence_ids,
                    metadata={
                        "wellness_check_id": check.id,
                        "wellness_type": check.type.value,
                        "status": WellnessCheckStatus.ACKNOWLEDGED.value,
                        "source_ids": [check.id],
                        "conservative_labels": labels,
                    },
                )
            )
        return events

    def _events_from_task(self, task: Task, activity_date: date) -> list[ActivityEvent]:
        events: list[ActivityEvent] = []
        if task.created_at.date() == activity_date:
            events.append(
                ActivityEvent(
                    id=f"actevt_task_opened_{task.id}",
                    type=ActivityEventType.TASK_OPENED,
                    title=task.title,
                    body=f"{task.body} Please verify important changes in person.",
                    occurred_at=task.created_at,
                    source="task",
                    confidence=QueryConfidence.MEDIUM,
                    zone_id=task.metadata.get("room_id"),
                    evidence_ids=task.evidence_observation_ids,
                    metadata={
                        "task_id": task.id,
                        "state": task.state.value,
                        "source_ids": [task.id],
                        "conservative_labels": ["task_opened"],
                    },
                )
            )
        if task.resolved_at is not None and task.resolved_at.date() == activity_date:
            events.append(
                ActivityEvent(
                    id=f"actevt_task_resolved_{task.id}",
                    type=ActivityEventType.TASK_RESOLVED,
                    title=f"Resolved: {task.title}",
                    body="A task was marked resolved with evidence or a human report.",
                    occurred_at=task.resolved_at,
                    source="task",
                    confidence=QueryConfidence.MEDIUM,
                    zone_id=task.metadata.get("room_id"),
                    evidence_ids=task.evidence_observation_ids,
                    metadata={
                        "task_id": task.id,
                        "state": task.state.value,
                        "source_ids": [task.id],
                        "conservative_labels": ["task_resolved"],
                    },
                )
            )
        return events

    def _events_from_alert(self, alert: Alert, activity_date: date) -> list[ActivityEvent]:
        events: list[ActivityEvent] = []
        if alert.created_at.date() == activity_date:
            events.append(
                ActivityEvent(
                    id=f"actevt_alert_{alert.id}",
                    type=ActivityEventType.SAFETY_ALERT,
                    title=alert.title,
                    body=f"{alert.body} Human verification is required.",
                    occurred_at=alert.created_at,
                    source="alert",
                    confidence=self._confidence_from_alert(alert.severity),
                    evidence_ids=alert.evidence_observation_ids,
                    metadata={
                        "alert_id": alert.id,
                        "status": alert.status.value,
                        "source_ids": [alert.id],
                        "conservative_labels": ["possible_safety_item"],
                    },
                )
            )
        if alert.acknowledged_at is not None and alert.acknowledged_at.date() == activity_date:
            events.append(
                ActivityEvent(
                    id=f"actevt_alert_ack_{alert.id}",
                    type=ActivityEventType.ALERT_ACKNOWLEDGED,
                    title=f"Acknowledged: {alert.title}",
                    body="A caregiver acknowledged this review item. Please continue to verify important changes in person.",
                    occurred_at=alert.acknowledged_at,
                    source="alert",
                    confidence=QueryConfidence.MEDIUM,
                    evidence_ids=alert.evidence_observation_ids,
                    metadata={
                        "alert_id": alert.id,
                        "status": alert.status.value,
                        "source_ids": [alert.id],
                        "conservative_labels": ["alert_acknowledged"],
                    },
                )
            )
        return events

    def _event_from_actuation_attempt(self, attempt: ActuationAttempt) -> ActivityEvent:
        return ActivityEvent(
            id=f"actevt_actuation_{attempt.id}",
            type=ActivityEventType.ACTUATION_ATTEMPTED,
            title="Assistive action attempted",
            body=f"{attempt.message} This does not confirm resolution by itself.",
            occurred_at=attempt.created_at,
            source="actuation_attempt",
            confidence=QueryConfidence.LOW,
            evidence_ids=attempt.evidence_observation_ids,
            metadata={
                "attempt_id": attempt.id,
                "task_id": attempt.task_id,
                "alert_id": attempt.alert_id,
                "state": attempt.state.value,
                "command_type": attempt.command_type,
                "source_ids": [attempt.id],
                "conservative_labels": ["assistive_action_attempted"],
            },
        )

    def _events_from_family_message(
        self,
        message: FamilyMessage,
        activity_date: date,
    ) -> list[ActivityEvent]:
        events: list[ActivityEvent] = []
        prompt_at = message.starts_at or message.created_at
        if prompt_at.date() == activity_date:
            events.append(
                ActivityEvent(
                    id=f"actevt_family_message_{message.id}",
                    type=ActivityEventType.FAMILY_PROMPT_DELIVERED,
                    title=message.title,
                    body="A family prompt became available for the patient context.",
                    occurred_at=prompt_at,
                    source="family_message",
                    confidence=QueryConfidence.MEDIUM,
                    zone_id=message.trigger_zone_id,
                    evidence_ids=[],
                    metadata={
                        "message_id": message.id,
                        "priority": message.priority.value,
                        "trigger_object_key": message.trigger_object_key,
                        "source_ids": [message.id],
                        "conservative_labels": ["family_prompt_delivered"],
                    },
                )
            )
        if message.acknowledged_at is not None and message.acknowledged_at.date() == activity_date:
            events.append(
                ActivityEvent(
                    id=f"actevt_family_message_ack_{message.id}",
                    type=ActivityEventType.FAMILY_PROMPT_ACKNOWLEDGED,
                    title=f"Acknowledged: {message.title}",
                    body="A family prompt was acknowledged.",
                    occurred_at=message.acknowledged_at,
                    source="family_message",
                    confidence=QueryConfidence.MEDIUM,
                    zone_id=message.trigger_zone_id,
                    metadata={
                        "message_id": message.id,
                        "source_ids": [message.id],
                        "conservative_labels": ["family_prompt_acknowledged"],
                    },
                )
            )
        return events

    def _event_from_care_note(self, note: CareNote) -> ActivityEvent:
        return ActivityEvent(
            id=f"actevt_care_note_{note.id}",
            type=ActivityEventType.OBJECT_SEEN,
            title="Caregiver note recorded",
            body=(
                "A caregiver-facing note was recorded from cited activity evidence. "
                "Please treat it as observational context, not diagnosis."
            ),
            occurred_at=note.created_at,
            source="care_note",
            confidence=QueryConfidence.MEDIUM if note.evidence_ids else QueryConfidence.LOW,
            evidence_ids=note.evidence_ids,
            metadata={
                "care_note_id": note.id,
                "audience": note.audience.value,
                "source_ids": [note.id],
                "conservative_labels": ["caregiver_note_recorded"],
            },
        )

    def _diary_highlights(self, events: list[ActivityEvent]) -> list[str]:
        if not events:
            return []
        highlights: list[str] = []
        object_event_count = sum(
            1
            for event in events
            if event.source == "afferens_observation"
            and event.type == ActivityEventType.OBJECT_SEEN
        )
        if object_event_count:
            highlights.append(f"{object_event_count} evidence-backed object activity event(s) were noted.")
        breakfast_count = sum(
            1
            for event in events
            if "breakfast_like_activity" in event.metadata.get("conservative_labels", [])
        )
        if breakfast_count:
            highlights.append(f"{breakfast_count} breakfast-like activity event(s) appeared in cited evidence.")
        water_context_count = sum(
            1
            for event in events
            if "water_nearby" in event.metadata.get("conservative_labels", [])
        )
        if water_context_count:
            highlights.append(f"{water_context_count} water-nearby context event(s) were noted without counting intake.")
        drink_count = sum(
            1
            for event in events
            if "possible_drink_action" in event.metadata.get("conservative_labels", [])
        )
        if drink_count:
            highlights.append(f"{drink_count} possible drink action candidate(s) were recorded.")
        wellness_count = sum(1 for event in events if event.source == "wellness_check")
        if wellness_count:
            highlights.append(f"{wellness_count} wellness check timeline item(s) may need review.")
        resolved_count = sum(1 for event in events if event.type == ActivityEventType.TASK_RESOLVED)
        if resolved_count:
            highlights.append(f"{resolved_count} task(s) were marked resolved.")
        message_count = sum(
            1 for event in events if event.type == ActivityEventType.FAMILY_PROMPT_DELIVERED
        )
        if message_count:
            highlights.append(f"{message_count} family prompt(s) were available.")
        if not highlights:
            highlights = [event.title for event in events[:3]]
        return highlights[:5]

    def _review_items(self, events: list[ActivityEvent]) -> list[str]:
        needs_review: list[str] = []
        for event in events:
            if event.type == ActivityEventType.SAFETY_ALERT:
                needs_review.append(f"Possible safety item: {event.title}. Please verify in person.")
            if event.source == "wellness_check" and event.metadata.get("status") == WellnessCheckStatus.OPEN.value:
                needs_review.append(f"Open wellness check: {event.title}.")
            if event.type == ActivityEventType.TASK_OPENED and event.metadata.get("state") not in {
                state.value for state in RESOLVED_TASK_STATES
            }:
                needs_review.append(f"Open task: {event.title}.")
        return self._dedupe(needs_review)[:6]

    def _diary_summary(
        self,
        entry_date: date,
        events: list[ActivityEvent],
        highlights: list[str],
        needs_review: list[str],
    ) -> str:
        if not events:
            return (
                f"No evidence-backed activity events were available for {entry_date.isoformat()}. "
                "If anything important is uncertain, please check in person."
            )
        review_text = (
            f" {len(needs_review)} item(s) may need human review."
            if needs_review
            else " No review items were generated from the available evidence."
        )
        return (
            f"{len(events)} evidence-backed activity event(s) were summarized for "
            f"{entry_date.isoformat()}. {self._join_human(highlights) if highlights else 'Activity was limited.'}"
            f"{review_text}"
        )

    def _care_bullets(self, events: list[ActivityEvent]) -> list[str]:
        if not events:
            return ["No evidence-backed activity events were available for this date."]
        return [f"{event.occurred_at.strftime('%H:%M')}: {event.title}." for event in events[:8]]

    def _care_risks(self, events: list[ActivityEvent]) -> list[str]:
        risks = [
            f"{event.title}: {event.body}"
            for event in events
            if event.type == ActivityEventType.SAFETY_ALERT or event.source == "wellness_check"
        ]
        return self._dedupe(risks)[:6]

    def _care_follow_ups(self, events: list[ActivityEvent], risks: list[str]) -> list[str]:
        follow_ups: list[str] = []
        if risks:
            follow_ups.append("Please verify possible safety items in person.")
        open_tasks = [
            event.title
            for event in events
            if event.type == ActivityEventType.TASK_OPENED
            and event.metadata.get("state") not in {state.value for state in RESOLVED_TASK_STATES}
        ]
        for title in open_tasks[:4]:
            follow_ups.append(f"Follow up on open task: {title}.")
        open_wellness = [
            event.title
            for event in events
            if event.source == "wellness_check"
            and event.metadata.get("status") == WellnessCheckStatus.OPEN.value
        ]
        for title in open_wellness[:4]:
            follow_ups.append(f"Check in on wellness item: {title}.")
        if not follow_ups:
            follow_ups.append("Continue ordinary check-ins; no medical conclusion is implied.")
        return self._dedupe(follow_ups)

    def _care_summary(
        self,
        note_date: date,
        audience: CareNoteAudience,
        events: list[ActivityEvent],
        risks: list[str],
    ) -> str:
        audience_text = "care-home" if audience == CareNoteAudience.CARE_HOME else "family"
        if not events:
            return (
                f"{audience_text.title()} note for {note_date.isoformat()}: no evidence-backed "
                "activity events were available. Please rely on in-person context for important decisions."
            )
        risk_text = (
            f" {len(risks)} possible safety item(s) need human verification."
            if risks
            else " No possible safety items were generated from the available evidence."
        )
        return (
            f"{audience_text.title()} note for {note_date.isoformat()}: "
            f"{len(events)} evidence-backed event(s) reviewed.{risk_text}"
        )

    async def _synthesize_diary_if_available(
        self,
        *,
        entry_date: date,
        events: list[ActivityEvent],
        deterministic: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self._fireworks is None:
            return None
        try:
            result = await self._fireworks.synthesize_daily_diary(
                diary_date=entry_date.isoformat(),
                events=self._provider_event_payload(events),
                deterministic=deterministic,
            )
        except (FireworksProviderUnavailable, FireworksProviderError, ValueError):
            return None
        return {
            "summary": self._safe_text(result.summary),
            "highlights": self._safe_list(result.highlights, limit=5),
            "needs_review": self._safe_list(result.needs_review, limit=6),
        }

    async def _synthesize_care_note_if_available(
        self,
        *,
        note_date: date,
        audience: CareNoteAudience,
        events: list[ActivityEvent],
        deterministic: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self._fireworks is None:
            return None
        try:
            result = await self._fireworks.synthesize_care_note(
                note_date=note_date.isoformat(),
                audience=audience.value,
                events=self._provider_event_payload(events),
                deterministic=deterministic,
            )
        except (FireworksProviderUnavailable, FireworksProviderError, ValueError):
            return None
        return {
            "summary": self._safe_text(result.summary),
            "bullets": self._safe_list(result.bullets, limit=8),
            "risks": self._safe_list(result.risks, limit=6),
            "follow_ups": self._safe_list(result.follow_ups, limit=6),
        }

    @staticmethod
    def _provider_event_payload(events: list[ActivityEvent]) -> list[dict[str, Any]]:
        return [
            {
                "id": event.id,
                "type": event.type.value,
                "title": event.title,
                "body": event.body,
                "occurred_at": event.occurred_at.isoformat(),
                "source": event.source,
                "confidence": event.confidence.value,
                "zone_name": event.zone_name,
                "evidence_ids": event.evidence_ids,
                "source_ids": event.metadata.get("source_ids", []),
                "conservative_labels": event.metadata.get("conservative_labels", []),
                "metadata": event.metadata,
            }
            for event in events[:40]
        ]

    @staticmethod
    def _safe_text(value: str) -> str | None:
        normalized = value.strip()
        return normalized if normalized else None

    @staticmethod
    def _safe_list(values: list[str], *, limit: int) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned[:limit]

    @staticmethod
    def _confidence_from_observation(observation: Observation) -> QueryConfidence:
        confidences = [obj.confidence for obj in observation.objects if obj.confidence is not None]
        confidence = observation.confidence
        if confidences:
            confidence = sum(confidences) / len(confidences)
        if confidence is None or confidence < 0.5:
            return QueryConfidence.LOW
        if confidence < 0.8:
            return QueryConfidence.MEDIUM
        return QueryConfidence.HIGH

    @staticmethod
    def _confidence_from_alert(severity: AlertSeverity) -> QueryConfidence:
        if severity == AlertSeverity.HIGH:
            return QueryConfidence.HIGH
        if severity == AlertSeverity.MEDIUM:
            return QueryConfidence.MEDIUM
        return QueryConfidence.LOW

    @staticmethod
    def _observation_context_labels(observation: Observation) -> list[str]:
        labels: list[str] = []
        object_words = {
            _normalize_label(value)
            for obj in observation.objects
            for value in (obj.object_key, obj.display_name, obj.label)
        }
        if object_words & {
            "bottle",
            "cup",
            "drinking_glass",
            "glass",
            "mug",
            "water",
            "water_bottle",
        }:
            labels.append("water_nearby")
        meal_words = {
            "banana",
            "bowl",
            "bread",
            "cereal",
            "coffee",
            "cup",
            "fork",
            "fruit",
            "mug",
            "plate",
            "sandwich",
            "spoon",
            "toast",
        }
        if object_words & meal_words:
            labels.append("meal_like_activity")
            if 5 <= observation.timestamp_utc.hour < 11:
                labels.append("breakfast_like_activity")
        return labels

    @staticmethod
    def _hydration_label(event_type: HydrationEventType) -> str:
        if event_type == HydrationEventType.DRINK_CANDIDATE:
            return "possible_drink_action"
        if event_type == HydrationEventType.CAREGIVER_REPORTED:
            return "caregiver_confirmed_hydration_context"
        return "water_nearby"

    @staticmethod
    def _wellness_label(check_type: WellnessCheckType) -> str:
        if check_type == WellnessCheckType.POSSIBLE_FALL_CHECK:
            return "possible_fall_check"
        if check_type == WellnessCheckType.UNUSUAL_STILLNESS_CHECK:
            return "possible_stillness_check"
        if check_type == WellnessCheckType.HYDRATION_PROMPT:
            return "hydration_check"
        return "caregiver_review"

    @staticmethod
    def _dedupe_activity_events(events: list[ActivityEvent]) -> list[ActivityEvent]:
        deduped: list[ActivityEvent] = []
        seen: set[tuple[str, str, str]] = set()
        for event in events:
            key = (event.source, event.id, event.occurred_at.isoformat())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)
        return deduped

    @staticmethod
    def _unique_evidence_ids(events: list[ActivityEvent]) -> list[str]:
        evidence: list[str] = []
        for event in events:
            for evidence_id in event.evidence_ids:
                if evidence_id not in evidence:
                    evidence.append(evidence_id)
        return evidence

    @staticmethod
    def _join_human(values: list[str]) -> str:
        cleaned = [value for value in values if value]
        if not cleaned:
            return "Activity"
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} and {cleaned[1]}"
        return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        return deduped

    @staticmethod
    def _priority_rank(priority: FamilyMessagePriority) -> int:
        if priority == FamilyMessagePriority.HIGH:
            return 3
        if priority == FamilyMessagePriority.NORMAL:
            return 2
        return 1


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_label(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower().replace("-", "_").replace(" ", "_")
