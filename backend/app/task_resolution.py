from __future__ import annotations

from app.afferens_adapter import AfferensAdapter
from app.ids import new_id
from app.normalizer import COOKING_OBJECT_KEYS, MEDICINE_OBJECT_KEYS
from app.schemas import (
    AfferensConnectionState,
    AlertStatus,
    DetectedObject,
    HumanPresence,
    Observation,
    Task,
    TaskResolveRequest,
    TaskState,
    TaskType,
    TaskVerifyRequest,
    VerificationCheck,
    VerificationState,
    utc_now,
)
from app.services import DataSpineService


class TaskResolutionService:
    def __init__(
        self,
        data_spine: DataSpineService,
        *,
        adapter: AfferensAdapter,
    ) -> None:
        self._data_spine = data_spine
        self._adapter = adapter

    async def verify(self, task: Task, request: TaskVerifyRequest) -> tuple[Task, VerificationCheck]:
        fetch_result = await self._adapter.fetch_events(limit=1)
        if not fetch_result.is_live:
            check = self._record_verification(
                task=task,
                state=VerificationState.INCONCLUSIVE,
                observation=None,
                message=self._no_live_message(fetch_result.status.state),
            )
            return task, check

        sync_result = self._data_spine.sync_raw_events(
            fetch_result.raw_events,
            room_id=request.room_id,
        )
        observation = sync_result.observations[0] if sync_result.observations else None
        if observation is None:
            check = self._record_verification(
                task=task,
                state=VerificationState.INCONCLUSIVE,
                observation=None,
                message="A live Afferens response arrived, but no normalized observation was created.",
            )
            return task, check

        state, message = self._evaluate_task(task, observation)
        if state == VerificationState.VERIFIED:
            task = task.model_copy(
                update={
                    "state": TaskState.VERIFIED_RESOLVED,
                    "updated_at": utc_now(),
                    "resolved_at": utc_now(),
                    "metadata": {
                        **task.metadata,
                        "resolution_source": "live_afferens_verification",
                    },
                }
            )
            task = self._data_spine.update_task(task)
            self._data_spine.add_task_event(
                task_id=task.id,
                event_type="live_verification_succeeded",
                message=message,
                evidence_observation_ids=[observation.id],
            )
            self._resolve_linked_alerts(task.id, observation)
        elif state == VerificationState.NOT_VERIFIED:
            task = task.model_copy(
                update={
                    "state": TaskState.FAILED_VERIFICATION,
                    "updated_at": utc_now(),
                    "metadata": {
                        **task.metadata,
                        "last_failed_verification_observation_id": observation.id,
                    },
                }
            )
            task = self._data_spine.update_task(task)
            self._data_spine.add_task_event(
                task_id=task.id,
                event_type="live_verification_failed",
                message=message,
                evidence_observation_ids=[observation.id],
            )

        check = self._record_verification(
            task=task,
            state=state,
            observation=observation,
            message=message,
        )
        return task, check

    def resolve(self, task: Task, request: TaskResolveRequest) -> Task:
        now = utc_now()
        resolved = task.model_copy(
            update={
                "state": TaskState.VERIFIED_RESOLVED,
                "updated_at": now,
                "resolved_at": now,
                "metadata": {
                    **task.metadata,
                    "resolution_source": "human_reported",
                    "resolved_by": request.resolved_by,
                    "resolution_note": request.resolution_note,
                },
            }
        )
        resolved = self._data_spine.update_task(resolved)
        self._data_spine.add_task_event(
            task_id=resolved.id,
            event_type="human_resolved",
            message=f"{request.resolved_by} reported resolution: {request.resolution_note}",
            evidence_observation_ids=resolved.evidence_observation_ids,
        )
        return resolved

    def _record_verification(
        self,
        *,
        task: Task,
        state: VerificationState,
        observation: Observation | None,
        message: str,
    ) -> VerificationCheck:
        evidence_ids = [observation.id] if observation is not None else []
        return self._data_spine.create_verification_check(
            VerificationCheck(
                id=new_id("verify"),
                task_id=task.id,
                observation_id=observation.id if observation is not None else None,
                state=state,
                message=message,
                evidence_observation_ids=evidence_ids,
            )
        )

    def _evaluate_task(
        self,
        task: Task,
        observation: Observation,
    ) -> tuple[VerificationState, str]:
        if task.type == TaskType.OBJECT_RECOVERY:
            object_key = task.metadata.get("object_key")
            if not object_key:
                return (
                    VerificationState.INCONCLUSIVE,
                    "This recovery task does not include an object key, so live verification is inconclusive.",
                )
            detected = self._find_visible_object(observation, object_key)
            if detected is not None:
                return (
                    VerificationState.VERIFIED,
                    (
                        f"{detected.display_name} appears visible in the latest live Afferens "
                        "observation. Human verification is still recommended."
                    ),
                )
            return (
                VerificationState.NOT_VERIFIED,
                (
                    f"{object_key} was not confidently visible in the latest live Afferens "
                    "observation. Human verification is required."
                ),
            )

        if task.type == TaskType.SAFETY_ALERT:
            return self._evaluate_safety_task(task, observation)

        return (
            VerificationState.INCONCLUSIVE,
            "This task type does not yet have deterministic live verification rules.",
        )

    def _evaluate_safety_task(
        self,
        task: Task,
        observation: Observation,
    ) -> tuple[VerificationState, str]:
        if not self._observation_has_labels(observation):
            return (
                VerificationState.INCONCLUSIVE,
                "The latest live Afferens observation did not include labels for safety verification.",
            )

        hazard_type = task.metadata.get("hazard_type")
        if hazard_type == "medicine_left_out":
            if self._has_any_object(observation, MEDICINE_OBJECT_KEYS):
                return (
                    VerificationState.NOT_VERIFIED,
                    (
                        "Medicine still appears visible in the latest live Afferens observation. "
                        "Human verification is required."
                    ),
                )
            return (
                VerificationState.VERIFIED,
                (
                    "Medicine is no longer visible in the latest labeled live Afferens observation. "
                    "Human verification is still recommended."
                ),
            )

        if hazard_type == "unattended_cooking_possible":
            cooking_visible = self._has_any_object(observation, COOKING_OBJECT_KEYS)
            if cooking_visible and observation.human_presence != HumanPresence.VISIBLE:
                return (
                    VerificationState.NOT_VERIFIED,
                    (
                        "A cooking-related object still appears visible without nearby person "
                        "context. Human verification is required."
                    ),
                )
            if observation.human_presence == HumanPresence.VISIBLE:
                return (
                    VerificationState.VERIFIED,
                    (
                        "A person appears visible in the latest live Afferens observation, "
                        "so the possible unattended-cooking condition appears cleared. "
                        "Human verification is still recommended."
                    ),
                )
            return (
                VerificationState.VERIFIED,
                (
                    "The cooking-related object is no longer visible in the latest labeled live "
                    "Afferens observation. Human verification is still recommended."
                ),
            )

        return (
            VerificationState.INCONCLUSIVE,
            "This safety task does not include a recognized hazard type.",
        )

    @staticmethod
    def _find_visible_object(observation: Observation, object_key: str) -> DetectedObject | None:
        for detected in observation.objects:
            if detected.object_key == object_key and (
                detected.confidence is None or detected.confidence >= 0.5
            ):
                return detected
        return None

    def _resolve_linked_alerts(self, task_id: str, observation: Observation) -> None:
        for alert in self._data_spine.list_alerts():
            if alert.task_id != task_id or alert.status not in {
                AlertStatus.OPEN,
                AlertStatus.ACKNOWLEDGED,
            }:
                continue
            evidence_ids = list(alert.evidence_observation_ids)
            if observation.id not in evidence_ids:
                evidence_ids.append(observation.id)
            self._data_spine.update_alert(
                alert.model_copy(
                    update={
                        "status": AlertStatus.RESOLVED,
                        "evidence_observation_ids": evidence_ids,
                    }
                )
            )

    @staticmethod
    def _has_any_object(observation: Observation, object_keys: set[str]) -> bool:
        return any(detected.object_key in object_keys for detected in observation.objects)

    @staticmethod
    def _observation_has_labels(observation: Observation) -> bool:
        return bool(observation.objects) or bool(
            observation.evidence_metadata.get("object_labels_available")
        )

    @staticmethod
    def _no_live_message(state: AfferensConnectionState) -> str:
        if state == AfferensConnectionState.MISSING_KEY:
            return "Live verification is inconclusive because Afferens is not configured."
        if state == AfferensConnectionState.NO_LIVE_EVENTS:
            return "Live verification is inconclusive because no live Afferens events are available."
        return f"Live verification is inconclusive because Afferens returned {state.value}."
