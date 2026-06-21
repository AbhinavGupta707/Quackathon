from __future__ import annotations

from app.afferens_adapter import AfferensAdapter
from app.ids import new_id
from app.schemas import (
    AfferensConnectionState,
    DetectedObject,
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

        return (
            VerificationState.INCONCLUSIVE,
            "This task type does not yet have deterministic live verification rules.",
        )

    @staticmethod
    def _find_visible_object(observation: Observation, object_key: str) -> DetectedObject | None:
        for detected in observation.objects:
            if detected.object_key == object_key and (
                detected.confidence is None or detected.confidence >= 0.5
            ):
                return detected
        return None

    @staticmethod
    def _no_live_message(state: AfferensConnectionState) -> str:
        if state == AfferensConnectionState.MISSING_KEY:
            return "Live verification is inconclusive because Afferens is not configured."
        if state == AfferensConnectionState.NO_LIVE_EVENTS:
            return "Live verification is inconclusive because no live Afferens events are available."
        return f"Live verification is inconclusive because Afferens returned {state.value}."
