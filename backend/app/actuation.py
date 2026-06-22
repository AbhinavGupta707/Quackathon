from __future__ import annotations

from typing import Any

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.ids import new_id
from app.schemas import (
    ActuationAttempt,
    ActuationState,
    AlertStatus,
    AlarmActuationRequest,
    CaptureFrameActuationRequest,
    Task,
    TaskState,
    utc_now,
)
from app.services import DataSpineService


SAFE_AFFERENS_COMMANDS = {"TRIGGER_ALARM", "CAPTURE_FRAME"}


class ActuationService:
    def __init__(
        self,
        data_spine: DataSpineService,
        *,
        adapter: AfferensAdapter,
        settings: Settings,
    ) -> None:
        self._data_spine = data_spine
        self._adapter = adapter
        self._settings = settings

    async def trigger_alarm(
        self,
        *,
        task: Task,
        request: AlarmActuationRequest,
    ) -> ActuationAttempt:
        alert_id = request.alert_id or self._latest_open_alert_id(task.id)
        attempt = await self._attempt_afferens(
            command_type="TRIGGER_ALARM",
            task=task,
            alert_id=alert_id,
            target_node_id=request.target_node_id,
            parameters={
                "reason": request.reason,
                "severity": request.severity.value,
                "task_id": task.id,
                "source": "afferens_memory_guardian",
            },
            requested=request.use_afferens,
        )
        self._record_task_outcome(task, attempt)
        return attempt

    async def capture_frame(
        self,
        *,
        task: Task,
        request: CaptureFrameActuationRequest,
    ) -> ActuationAttempt:
        alert_id = request.alert_id or self._latest_open_alert_id(task.id)
        attempt = await self._attempt_afferens(
            command_type="CAPTURE_FRAME",
            task=task,
            alert_id=alert_id,
            target_node_id=request.target_node_id,
            parameters={
                "reason": request.reason,
                "task_id": task.id,
                "source": "afferens_memory_guardian",
            },
            requested=True,
        )
        self._record_task_outcome(task, attempt)
        return attempt

    async def _attempt_afferens(
        self,
        *,
        command_type: str,
        task: Task,
        alert_id: str | None,
        target_node_id: str | None,
        parameters: dict[str, Any],
        requested: bool,
    ) -> ActuationAttempt:
        request_payload = self._request_payload(
            command_type=command_type,
            target_node_id=target_node_id,
            parameters=parameters,
            requested=requested,
        )
        if not requested:
            return self._persist_attempt(
                task=task,
                alert_id=alert_id,
                command_type=command_type,
                state=ActuationState.SKIPPED,
                message="Afferens actuation was not requested for this alarm.",
                request_payload=request_payload,
            )

        if command_type not in SAFE_AFFERENS_COMMANDS:
            return self._persist_attempt(
                task=task,
                alert_id=alert_id,
                command_type=command_type,
                state=ActuationState.SKIPPED,
                message=f"{command_type} is not in the safe Afferens command allowlist.",
                request_payload=request_payload,
            )

        if not self._settings.afferens_actuation_enabled:
            return self._persist_attempt(
                task=task,
                alert_id=alert_id,
                command_type=command_type,
                state=ActuationState.SKIPPED,
                message=(
                    "Afferens actuation is disabled; enable AFFERENS_ACTUATION_ENABLED "
                    "before sending node commands."
                ),
                request_payload=request_payload,
            )

        supported = self._settings.afferens_supported_actuation_commands
        if command_type not in supported:
            return self._persist_attempt(
                task=task,
                alert_id=alert_id,
                command_type=command_type,
                state=ActuationState.SKIPPED,
                message=f"{command_type} is not configured as a supported Afferens command.",
                request_payload=request_payload,
            )

        provider_result = await self._adapter.actuate(
            command_type=command_type,
            target_node_id=target_node_id,
            parameters=parameters,
        )
        return self._persist_attempt(
            task=task,
            alert_id=alert_id,
            command_type=command_type,
            state=provider_result.state,
            message=provider_result.message,
            request_payload=request_payload,
            response_payload=provider_result.response_payload,
        )

    def _persist_attempt(
        self,
        *,
        task: Task,
        alert_id: str | None,
        command_type: str,
        state: ActuationState,
        message: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any] | None = None,
    ) -> ActuationAttempt:
        attempt = ActuationAttempt(
            id=new_id("act"),
            task_id=task.id,
            alert_id=alert_id,
            provider="afferens",
            command_type=command_type,
            state=state,
            message=message,
            request_payload=request_payload,
            response_payload=response_payload,
            evidence_observation_ids=list(task.evidence_observation_ids),
        )
        return self._data_spine.create_actuation_attempt(attempt)

    def _record_task_outcome(self, task: Task, attempt: ActuationAttempt) -> None:
        now = utc_now()
        next_state = task.state
        if attempt.state == ActuationState.SUCCEEDED and task.state not in {
            TaskState.VERIFIED_RESOLVED,
            TaskState.DISMISSED,
            TaskState.ESCALATED,
        }:
            next_state = TaskState.ACTUATION_ATTEMPTED

        updated = task.model_copy(
            update={
                "state": next_state,
                "updated_at": now,
                "metadata": {
                    **task.metadata,
                    "last_actuation_attempt_id": attempt.id,
                    "last_actuation_command": attempt.command_type,
                    "last_actuation_state": attempt.state.value,
                    "last_actuation_message": attempt.message,
                    "actuation_verification_required": True,
                    "actuation_resolution_required": "live_verification_or_human_ack",
                    "last_actuation_requires_live_verification": attempt.state
                    == ActuationState.SUCCEEDED,
                },
            }
        )
        self._data_spine.update_task(updated)
        self._data_spine.add_task_event(
            task_id=task.id,
            event_type=f"actuation_attempt_{attempt.state.value}",
            message=f"{attempt.command_type} via Afferens: {attempt.message}",
            evidence_observation_ids=attempt.evidence_observation_ids,
        )

    def _latest_open_alert_id(self, task_id: str) -> str | None:
        for alert in self._data_spine.list_alerts(status=AlertStatus.OPEN):
            if alert.task_id == task_id:
                return alert.id
        return None

    @staticmethod
    def _request_payload(
        *,
        command_type: str,
        target_node_id: str | None,
        parameters: dict[str, Any],
        requested: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "command_type": command_type,
            "parameters": parameters,
            "requested": requested,
        }
        if target_node_id:
            payload["target_node_id"] = target_node_id
        return payload
