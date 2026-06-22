from __future__ import annotations

from datetime import date

from app.schemas import (
    ActuationState,
    AlertSeverity,
    CaregiverNotification,
    CaregiverNotificationStatus,
    CaregiverNotificationType,
    FamilyMessage,
    FamilyMessageStatus,
    TaskState,
    TaskType,
    WellnessCheck,
    WellnessCheckStatus,
    WellnessCheckType,
    utc_now,
)
from app.services import DataSpineService


class CaregiverNotificationService:
    def __init__(self, data_spine: DataSpineService) -> None:
        self._data_spine = data_spine

    def list_notifications(
        self,
        *,
        notification_date: date | None = None,
        include_acknowledged: bool = False,
        limit: int = 100,
    ) -> list[CaregiverNotification]:
        notifications: list[CaregiverNotification] = []
        check_dates = self._notification_dates(notification_date)
        for check_date in check_dates:
            for check in self._data_spine.list_wellness_checks_for_date(check_date):
                notification = self._notification_from_wellness_check(check)
                if notification is not None:
                    notifications.append(notification)
            for attempt in self._data_spine.list_actuation_attempts_for_date(check_date):
                if attempt.state in {
                    ActuationState.SUCCEEDED,
                    ActuationState.SKIPPED,
                    ActuationState.FAILED,
                }:
                    notifications.append(
                        CaregiverNotification(
                            id=f"notif_actuation_{attempt.id}",
                            type=CaregiverNotificationType.ACTUATION_VERIFICATION_REQUIRED,
                            status=CaregiverNotificationStatus.QUEUED,
                            severity=AlertSeverity.MEDIUM,
                            title="Actuation verification required",
                            body=(
                                "An Afferens actuation attempt was logged. Please verify the "
                                "physical situation live or acknowledge the outcome before resolving it."
                            ),
                            source="actuation_attempt",
                            source_id=attempt.id,
                            created_at=attempt.created_at,
                            task_id=attempt.task_id,
                            alert_id=attempt.alert_id,
                            actuation_attempt_id=attempt.id,
                            evidence_ids=attempt.evidence_observation_ids,
                            requires_human_ack=True,
                            requires_live_verification=True,
                            metadata={
                                "command_type": attempt.command_type,
                                "actuation_state": attempt.state.value,
                                "verification_requirement": "live_verification_or_human_ack",
                            },
                        )
                    )

        notifications.extend(
            self._family_notifications(
                include_acknowledged=include_acknowledged,
                notification_date=notification_date,
            )
        )
        notifications.extend(self._recovery_task_notifications())

        if not include_acknowledged:
            notifications = [
                item
                for item in notifications
                if item.status != CaregiverNotificationStatus.ACKNOWLEDGED
            ]
        return sorted(notifications, key=lambda item: item.created_at, reverse=True)[:limit]

    def _notification_dates(self, notification_date: date | None) -> list[date]:
        if notification_date is not None:
            return [notification_date]
        dates = {utc_now().date()}
        for task in self._data_spine.list_tasks():
            dates.add(task.created_at.date())
        return sorted(dates, reverse=True)

    @staticmethod
    def _notification_from_wellness_check(check: WellnessCheck) -> CaregiverNotification | None:
        if check.status != WellnessCheckStatus.OPEN:
            status = CaregiverNotificationStatus.ACKNOWLEDGED
        else:
            status = CaregiverNotificationStatus.QUEUED

        if check.type == WellnessCheckType.POSSIBLE_FALL_CHECK:
            if not _is_action_backed_or_manual_fall_check(check):
                return None
            return CaregiverNotification(
                id=f"notif_wellness_{check.id}",
                type=CaregiverNotificationType.POSSIBLE_FALL_CHECK,
                status=status,
                severity=check.severity,
                title="Possible fall candidate",
                body="This notification has been escalated to the caregiver for a possible fall.",
                source="wellness_check",
                source_id=check.id,
                created_at=check.created_at,
                due_at=check.occurred_at,
                wellness_check_id=check.id,
                evidence_ids=check.evidence_ids,
                requires_human_ack=True,
                requires_live_verification=True,
                metadata={
                    "confidence": check.confidence.value,
                    "source_metadata": check.metadata,
                },
            )

        if check.type == WellnessCheckType.HYDRATION_PROMPT:
            return CaregiverNotification(
                id=f"notif_wellness_{check.id}",
                type=CaregiverNotificationType.HYDRATION_PROMPT,
                status=status,
                severity=check.severity,
                title="Hydration prompt",
                body=(
                    "Hydration may need a gentle check-in. Bottle, cup, or water "
                    "visibility alone is context only and does not count as intake."
                ),
                source="wellness_check",
                source_id=check.id,
                created_at=check.created_at,
                due_at=check.occurred_at,
                wellness_check_id=check.id,
                evidence_ids=check.evidence_ids,
                requires_human_ack=True,
                requires_live_verification=False,
                metadata={
                    "confidence": check.confidence.value,
                    "source_metadata": check.metadata,
                },
            )
        return None

    def _family_notifications(
        self,
        *,
        include_acknowledged: bool,
        notification_date: date | None,
    ) -> list[CaregiverNotification]:
        notifications: list[CaregiverNotification] = []
        now = utc_now()
        for message in self._data_spine.list_family_messages(include_acknowledged=True):
            if message.status == FamilyMessageStatus.ACKNOWLEDGED:
                if not include_acknowledged:
                    continue
                if notification_date is not None and (
                    message.acknowledged_at is None
                    or message.acknowledged_at.date() != notification_date
                ):
                    continue
                notifications.append(self._family_ack_notification(message))
                continue
            if message.status == FamilyMessageStatus.EXPIRED:
                continue
            if message.starts_at and message.starts_at > now:
                continue
            if message.expires_at and message.expires_at <= now:
                continue
            if notification_date is not None and _family_due_at(message).date() != notification_date:
                continue
            notifications.append(self._family_due_notification(message))
        return notifications

    @staticmethod
    def _family_due_notification(message: FamilyMessage) -> CaregiverNotification:
        return CaregiverNotification(
            id=f"notif_family_due_{message.id}",
            type=CaregiverNotificationType.FAMILY_PROMPT_DUE,
            status=CaregiverNotificationStatus.QUEUED,
            severity=_severity_from_family_priority(message.priority.value),
            title="Family prompt due",
            body="A family prompt is available for the patient context.",
            source="family_message",
            source_id=message.id,
            created_at=_family_due_at(message),
            due_at=_family_due_at(message),
            family_message_id=message.id,
            requires_human_ack=True,
            metadata={
                "family_message_status": message.status.value,
                "priority": message.priority.value,
                "trigger_object_key": message.trigger_object_key,
                "trigger_zone_id": message.trigger_zone_id,
            },
        )

    @staticmethod
    def _family_ack_notification(message: FamilyMessage) -> CaregiverNotification:
        acknowledged_at = message.acknowledged_at or message.created_at
        return CaregiverNotification(
            id=f"notif_family_ack_{message.id}",
            type=CaregiverNotificationType.FAMILY_PROMPT_ACKNOWLEDGED,
            status=CaregiverNotificationStatus.ACKNOWLEDGED,
            severity=_severity_from_family_priority(message.priority.value),
            title="Family prompt acknowledged",
            body="A family prompt was acknowledged.",
            source="family_message",
            source_id=message.id,
            created_at=acknowledged_at,
            due_at=message.starts_at,
            family_message_id=message.id,
            requires_human_ack=False,
            metadata={
                "family_message_status": message.status.value,
                "priority": message.priority.value,
            },
        )

    def _recovery_task_notifications(self) -> list[CaregiverNotification]:
        notifications: list[CaregiverNotification] = []
        unresolved_states = {
            TaskState.OPEN,
            TaskState.WAITING_FOR_HUMAN,
            TaskState.ACTUATION_ATTEMPTED,
            TaskState.VERIFICATION_PENDING,
            TaskState.FAILED_VERIFICATION,
        }
        for task in self._data_spine.list_tasks(task_type=TaskType.OBJECT_RECOVERY):
            if task.state not in unresolved_states:
                continue
            notifications.append(
                CaregiverNotification(
                    id=f"notif_task_{task.id}",
                    type=CaregiverNotificationType.UNRESOLVED_RECOVERY_TASK,
                    status=CaregiverNotificationStatus.QUEUED,
                    severity=AlertSeverity.LOW,
                    title="Unresolved recovery task",
                    body=(
                        "An object recovery task is still open. Please continue live "
                        "verification or acknowledge the outcome if it has been resolved."
                    ),
                    source="task",
                    source_id=task.id,
                    created_at=task.updated_at,
                    task_id=task.id,
                    evidence_ids=task.evidence_observation_ids,
                    requires_human_ack=True,
                    requires_live_verification=task.state
                    in {TaskState.ACTUATION_ATTEMPTED, TaskState.VERIFICATION_PENDING},
                    metadata={
                        "task_state": task.state.value,
                        "task_type": task.type.value,
                        "verification_requirement": task.metadata.get(
                            "actuation_resolution_required"
                        ),
                    },
                )
            )
        return notifications


def _is_action_backed_or_manual_fall_check(check: WellnessCheck) -> bool:
    source = str(check.metadata.get("source", "")).lower()
    reason = str(check.metadata.get("reason", "")).lower()
    return (
        source in {"action_event", "caregiver_manual", "manual", "caregiver_or_api_report"}
        or bool(check.metadata.get("action_event_id"))
        or reason in {"action_fall_persistent", "manual_fall_check", "caregiver_fall_check"}
    )


def _family_due_at(message: FamilyMessage):
    return message.starts_at or message.created_at


def _severity_from_family_priority(priority: str) -> AlertSeverity:
    if priority == "high":
        return AlertSeverity.MEDIUM
    return AlertSeverity.LOW
