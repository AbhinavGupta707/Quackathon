from __future__ import annotations

from dataclasses import dataclass

from app.ids import new_id
from app.normalizer import COOKING_OBJECT_KEYS, MEDICINE_OBJECT_KEYS
from app.repositories import DataRepository
from app.schemas import (
    Alert,
    AlertSeverity,
    AlertStatus,
    HumanPresence,
    Observation,
    Task,
    TaskState,
    TaskType,
    utc_now,
)


ACTIVE_SAFETY_TASK_STATES = {
    TaskState.OPEN,
    TaskState.WAITING_FOR_HUMAN,
    TaskState.ACTUATION_ATTEMPTED,
    TaskState.VERIFICATION_PENDING,
    TaskState.FAILED_VERIFICATION,
}


@dataclass(frozen=True)
class SafetyCandidate:
    hazard_type: str
    severity: AlertSeverity
    rule_id: str
    task_title: str
    task_body: str
    task_action: str
    alert_title: str
    alert_body: str
    alert_action: str
    object_keys: list[str]


class TaskCreationService:
    def __init__(self, repository: DataRepository) -> None:
        self._repository = repository

    def create_from_observation(self, observation: Observation) -> tuple[list[Task], list[Alert]]:
        tasks: list[Task] = []
        alerts: list[Alert] = []

        self._resolve_cleared_safety_tasks(observation)
        for candidate in self._safety_candidates(observation):
            existing = self._find_active_safety_task(
                hazard_type=candidate.hazard_type,
                room_id=observation.room_id,
            )
            if existing is not None:
                self._append_safety_evidence(existing, candidate, observation)
                continue

            task = self._repository.create_task(
                Task(
                    id=new_id("task"),
                    type=TaskType.SAFETY_ALERT,
                    state=TaskState.OPEN,
                    title=candidate.task_title,
                    body=candidate.task_body,
                    recommended_action=candidate.task_action,
                    evidence_observation_ids=[observation.id],
                    metadata={
                        "hazard_type": candidate.hazard_type,
                        "safety_rule": candidate.rule_id,
                        "room_id": observation.room_id,
                        "object_keys": candidate.object_keys,
                        "human_presence": observation.human_presence.value,
                        "human_verification_required": True,
                        "last_candidate_observation_id": observation.id,
                    },
                )
            )
            alert = self._repository.create_alert(
                Alert(
                    id=new_id("alert"),
                    task_id=task.id,
                    hazard_type=candidate.hazard_type,
                    severity=candidate.severity,
                    title=candidate.alert_title,
                    body=candidate.alert_body,
                    recommended_action=candidate.alert_action,
                    evidence_observation_ids=[observation.id],
                )
            )
            self._repository.add_task_event(
                task_id=task.id,
                event_type="safety_candidate_created",
                message=f"{candidate.hazard_type} candidate created from live Afferens observation.",
                evidence_observation_ids=[observation.id],
            )
            tasks.append(task)
            alerts.append(alert)

        return tasks, alerts

    def _safety_candidates(self, observation: Observation) -> list[SafetyCandidate]:
        candidates: list[SafetyCandidate] = []

        if "medicine_visible_human_verification_required" in observation.risk_signals:
            candidates.append(
                SafetyCandidate(
                    hazard_type="medicine_left_out",
                    severity=AlertSeverity.MEDIUM,
                    rule_id="medicine_visible_v1",
                    task_title="Check possible medicine left out",
                    task_body=(
                        "Medicine appears visible in the home zone. "
                        "Human verification is required."
                    ),
                    task_action="Please verify in person and move medicine to a safe place if needed.",
                    alert_title="Possible medicine left out",
                    alert_body="Medicine appears visible in the home zone. Please verify in person.",
                    alert_action="Move medicine to the safe zone or acknowledge if intentional.",
                    object_keys=self._matched_object_keys(observation, MEDICINE_OBJECT_KEYS),
                )
            )

        if "unattended_cooking_possible_human_verification_required" in observation.risk_signals:
            person_context = self._person_context_message(observation.human_presence)
            candidates.append(
                SafetyCandidate(
                    hazard_type="unattended_cooking_possible",
                    severity=AlertSeverity.MEDIUM,
                    rule_id="cooking_object_without_visible_person_v1",
                    task_title="Check possible unattended cooking",
                    task_body=(
                        "A stove, burner, oven, pan, or similar cooking object appears visible, "
                        f"and {person_context}. Human verification is required."
                    ),
                    task_action=(
                        "Please check the cooking area in person and confirm whether it is safe."
                    ),
                    alert_title="Possible unattended cooking",
                    alert_body=(
                        "A cooking-related object appears visible without nearby person context. "
                        "Please verify in person."
                    ),
                    alert_action="Check the cooking area and acknowledge if it is intentional.",
                    object_keys=self._matched_object_keys(observation, COOKING_OBJECT_KEYS),
                )
            )

        return candidates

    def _resolve_cleared_safety_tasks(self, observation: Observation) -> None:
        if not self._observation_has_labels(observation):
            return

        for task in self._repository.list_tasks(task_type=TaskType.SAFETY_ALERT):
            if task.state not in ACTIVE_SAFETY_TASK_STATES:
                continue
            if task.metadata.get("room_id") not in {None, observation.room_id}:
                continue
            hazard_type = str(task.metadata.get("hazard_type", ""))
            message = self._clearance_message(hazard_type, observation)
            if message is None:
                continue

            now = utc_now()
            resolved = task.model_copy(
                update={
                    "state": TaskState.VERIFIED_RESOLVED,
                    "updated_at": now,
                    "resolved_at": now,
                    "metadata": {
                        **task.metadata,
                        "resolution_source": "live_afferens_safety_clear",
                        "resolution_observation_id": observation.id,
                    },
                }
            )
            self._repository.update_task(resolved)
            self._repository.add_task_event(
                task_id=task.id,
                event_type="live_safety_condition_cleared",
                message=message,
                evidence_observation_ids=[observation.id],
            )
            self._resolve_linked_alerts(task.id, observation)

    def _append_safety_evidence(
        self,
        task: Task,
        candidate: SafetyCandidate,
        observation: Observation,
    ) -> None:
        if observation.id in task.evidence_observation_ids:
            return

        evidence_ids = [*task.evidence_observation_ids, observation.id]
        existing_object_keys = task.metadata.get("object_keys", [])
        if not isinstance(existing_object_keys, list):
            existing_object_keys = []
        updated = task.model_copy(
            update={
                "evidence_observation_ids": evidence_ids,
                "updated_at": utc_now(),
                "metadata": {
                    **task.metadata,
                    "object_keys": sorted(set(existing_object_keys) | set(candidate.object_keys)),
                    "human_presence": observation.human_presence.value,
                    "last_candidate_observation_id": observation.id,
                },
            }
        )
        self._repository.update_task(updated)
        for alert in self._repository.list_alerts(status=AlertStatus.OPEN):
            if alert.task_id != task.id or observation.id in alert.evidence_observation_ids:
                continue
            self._repository.update_alert(
                alert.model_copy(
                    update={
                        "evidence_observation_ids": [*alert.evidence_observation_ids, observation.id]
                    }
                )
            )
        self._repository.add_task_event(
            task_id=task.id,
            event_type="safety_candidate_reobserved",
            message=f"{candidate.hazard_type} candidate was observed again in live Afferens data.",
            evidence_observation_ids=[observation.id],
        )

    def _resolve_linked_alerts(self, task_id: str, observation: Observation) -> None:
        for alert in self._repository.list_alerts():
            if alert.task_id != task_id or alert.status not in {
                AlertStatus.OPEN,
                AlertStatus.ACKNOWLEDGED,
            }:
                continue
            evidence_ids = list(alert.evidence_observation_ids)
            if observation.id not in evidence_ids:
                evidence_ids.append(observation.id)
            self._repository.update_alert(
                alert.model_copy(
                    update={
                        "status": AlertStatus.RESOLVED,
                        "evidence_observation_ids": evidence_ids,
                    }
                )
            )

    def _find_active_safety_task(self, *, hazard_type: str, room_id: str) -> Task | None:
        candidates = [
            task
            for task in self._repository.list_tasks(task_type=TaskType.SAFETY_ALERT)
            if task.state in ACTIVE_SAFETY_TASK_STATES
            and task.metadata.get("hazard_type") == hazard_type
            and task.metadata.get("room_id") in {None, room_id}
        ]
        return max(candidates, key=lambda item: item.created_at) if candidates else None

    def _clearance_message(self, hazard_type: str, observation: Observation) -> str | None:
        if hazard_type == "medicine_left_out" and not self._has_any_object(
            observation,
            MEDICINE_OBJECT_KEYS,
        ):
            return (
                "Medicine is no longer visible in the latest labeled live Afferens "
                "observation. Human verification is still recommended."
            )

        if hazard_type == "unattended_cooking_possible":
            if observation.human_presence == HumanPresence.VISIBLE:
                return (
                    "A person appears visible in the latest live Afferens observation, "
                    "so the possible unattended-cooking condition appears cleared. "
                    "Human verification is still recommended."
                )
            if not self._has_any_object(observation, COOKING_OBJECT_KEYS):
                return (
                    "The cooking-related object is no longer visible in the latest labeled "
                    "live Afferens observation. Human verification is still recommended."
                )

        return None

    @staticmethod
    def _has_any_object(observation: Observation, object_keys: set[str]) -> bool:
        return any(obj.object_key in object_keys for obj in observation.objects)

    @staticmethod
    def _matched_object_keys(observation: Observation, object_keys: set[str]) -> list[str]:
        return sorted({obj.object_key for obj in observation.objects if obj.object_key in object_keys})

    @staticmethod
    def _observation_has_labels(observation: Observation) -> bool:
        return bool(observation.objects) or bool(
            observation.evidence_metadata.get("object_labels_available")
        )

    @staticmethod
    def _person_context_message(human_presence: HumanPresence) -> str:
        if human_presence == HumanPresence.NOT_VISIBLE:
            return "no person appears visible nearby in the live observation"
        return "the live observation did not provide nearby person context"
