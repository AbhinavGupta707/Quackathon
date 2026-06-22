from __future__ import annotations

from app.ids import new_id
from app.object_search import (
    infer_object_key_from_query,
    normalize_object_key,
    object_candidates,
)
from app.schemas import (
    DetectedObject,
    GuidedRecoveryStartRequest,
    GuidedRecoveryStartResponse,
    LastSeenObject,
    Observation,
    Task,
    TaskState,
    TaskType,
)
from app.services import DataSpineService
from app.workflows.object_recovery import ObjectRecoveryWorkflow


class GuidedRecoveryService:
    def __init__(
        self,
        data_spine: DataSpineService,
        *,
        workflow: ObjectRecoveryWorkflow,
    ) -> None:
        self._data_spine = data_spine
        self._workflow = workflow

    def start(self, request: GuidedRecoveryStartRequest) -> GuidedRecoveryStartResponse:
        latest_observation = self._data_spine.latest_observation()
        memories = self._data_spine.list_last_seen_objects()
        latest_objects = latest_observation.objects if latest_observation else []
        requested_key = self._resolve_requested_key(
            request.object_key,
            memories=memories,
            latest_objects=latest_objects,
        )

        current_object = self._find_visible_object(latest_observation, requested_key)
        if current_object is not None:
            return GuidedRecoveryStartResponse(
                ok=True,
                task=None,
                next_instruction=self._visible_instruction(current_object),
            )

        memory = {item.object_key: item for item in memories}.get(requested_key)
        if memory is None:
            return GuidedRecoveryStartResponse(
                ok=False,
                task=None,
                next_instruction=self._no_evidence_instruction(requested_key),
            )

        task = self._get_or_create_task(request=request, memory=memory)
        return GuidedRecoveryStartResponse(
            ok=True,
            task=task,
            next_instruction=self._next_instruction(memory),
        )

    def _get_or_create_task(
        self,
        *,
        request: GuidedRecoveryStartRequest,
        memory: LastSeenObject,
    ) -> Task:
        existing = self._data_spine.find_open_object_recovery_task(memory.object_key)
        if existing is not None:
            self._data_spine.add_task_event(
                task_id=existing.id,
                event_type="guided_recovery_reused",
                message=(
                    f"Reused an open guided recovery task for {memory.object_key}; "
                    "continue with live sync and task verification."
                ),
                evidence_observation_ids=existing.evidence_observation_ids,
            )
            return existing

        plan = self._workflow.plan_recovery(
            query=f"Find {memory.display_name}",
            object_key=memory.object_key,
            memory=memory,
            current_visible=False,
        )
        evidence_ids = list(
            dict.fromkeys(memory.evidence_observation_ids or [memory.last_seen_observation_id])
        )
        task = Task(
            id=new_id("task"),
            type=TaskType.OBJECT_RECOVERY,
            state=TaskState.OPEN,
            title=f"Find {memory.display_name}",
            body=self._task_body(memory),
            recommended_action=str(
                plan.get("recommended_action") or self._recommended_action(memory)
            ),
            evidence_observation_ids=evidence_ids,
            metadata={
                "object_key": memory.object_key,
                "display_name": memory.display_name,
                "last_seen_observation_id": memory.last_seen_observation_id,
                "opened_from_guided_recovery": True,
                "session_id": request.session_id,
            },
        )
        task = self._data_spine.create_task(task)
        self._data_spine.add_task_event(
            task_id=task.id,
            event_type="guided_recovery_started",
            message=f"Started guided recovery for {memory.object_key} from last-seen evidence.",
            evidence_observation_ids=evidence_ids,
        )
        return task

    @staticmethod
    def _resolve_requested_key(
        value: str,
        *,
        memories: list[LastSeenObject],
        latest_objects: list[DetectedObject],
    ) -> str:
        candidates = object_candidates(memories=memories, observation_objects=latest_objects)
        known_keys = {candidate.object_key for candidate in candidates}
        requested_key = normalize_object_key(value)
        if requested_key in known_keys:
            return requested_key
        return infer_object_key_from_query(value, candidates) or requested_key

    @staticmethod
    def _find_visible_object(
        observation: Observation | None,
        object_key: str,
    ) -> DetectedObject | None:
        if observation is None:
            return None
        for detected in observation.objects:
            if detected.object_key == object_key and (
                detected.confidence is None or detected.confidence >= 0.5
            ):
                return detected
        return None

    @staticmethod
    def _next_instruction(memory: LastSeenObject) -> str:
        if memory.last_seen_relative_location:
            area = f"{memory.last_seen_room} near {memory.last_seen_relative_location}"
        else:
            area = memory.last_seen_room
        return f"Point the Afferens Node at {area}, then sync live perception again."

    @staticmethod
    def _visible_instruction(detected: DetectedObject) -> str:
        if detected.relative_location:
            return (
                f"{detected.display_name} appears visible in the latest live observation "
                f"near {detected.relative_location}. Please verify in person."
            )
        return (
            f"{detected.display_name} appears visible in the latest live observation. "
            "Please verify in person."
        )

    @staticmethod
    def _no_evidence_instruction(object_key: str) -> str:
        display_name = object_key.replace("_", " ")
        return (
            f"I do not have live Afferens evidence for {display_name} yet. "
            "Start a live sync after it is visible once, then try guided recovery again "
            "if it goes missing."
        )

    @staticmethod
    def _task_body(memory: LastSeenObject) -> str:
        if memory.last_seen_relative_location:
            return (
                f"I last saw {memory.display_name} in {memory.last_seen_room} "
                f"near {memory.last_seen_relative_location}. Human verification is required."
            )
        return (
            f"I last saw {memory.display_name} in {memory.last_seen_room}. "
            "Human verification is required."
        )

    @staticmethod
    def _recommended_action(memory: LastSeenObject) -> str:
        if memory.last_seen_relative_location:
            return (
                f"Check {memory.last_seen_room} near {memory.last_seen_relative_location}, "
                "then place the object in view for live verification."
            )
        return (
            f"Check {memory.last_seen_room}, then place the object in view for live verification."
        )
