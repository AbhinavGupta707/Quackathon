from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routes.dependencies import get_runtime_monitor_supervisor
from app.runtime_supervisor import RuntimeMonitorSupervisor
from app.schemas import (
    AmbientMonitorMode,
    AmbientMonitorResponse,
    AmbientMonitorState,
    AmbientMonitorStatus,
    AmbientStartRequest,
    AmbientStatusResponse,
    RuntimeMonitorMode,
    RuntimeMonitorStartRequest,
    RuntimeMonitorState,
    RuntimeMonitorStatus,
)

router = APIRouter(tags=["ambient"])


@router.post("/api/ambient/start", response_model=AmbientMonitorResponse)
async def ambient_start(
    request: AmbientStartRequest,
    supervisor: RuntimeMonitorSupervisor = Depends(get_runtime_monitor_supervisor),
) -> AmbientMonitorResponse:
    runtime_request = RuntimeMonitorStartRequest(
        mode=(
            RuntimeMonitorMode.ACTIVE_RECOVERY
            if request.mode == AmbientMonitorMode.ACTIVE_RECOVERY
            else RuntimeMonitorMode.HOME_MEMORY
        ),
        poll_interval_seconds=request.poll_interval_seconds,
        zone_id=request.zone_id,
        target_object_key=request.target_object_key,
        duration_seconds=request.duration_seconds,
    )
    response = await supervisor.start_monitor(runtime_request)
    return AmbientMonitorResponse(ok=response.ok, monitor=_ambient_from_runtime(response.monitor))


@router.post("/api/ambient/stop", response_model=AmbientMonitorResponse)
async def ambient_stop(
    supervisor: RuntimeMonitorSupervisor = Depends(get_runtime_monitor_supervisor),
) -> AmbientMonitorResponse:
    response = await supervisor.stop_monitor()
    return AmbientMonitorResponse(ok=response.ok, monitor=_ambient_from_runtime(response.monitor))


@router.get("/api/ambient/status", response_model=AmbientStatusResponse)
async def ambient_status(
    supervisor: RuntimeMonitorSupervisor = Depends(get_runtime_monitor_supervisor),
) -> AmbientStatusResponse:
    return AmbientStatusResponse(monitor=_ambient_from_runtime(supervisor.current_status()))


def _ambient_from_runtime(status: RuntimeMonitorStatus) -> AmbientMonitorStatus:
    state = AmbientMonitorState.RUNNING
    if status.state == RuntimeMonitorState.OFF:
        state = AmbientMonitorState.OFF
    elif status.state == RuntimeMonitorState.COMPLETED:
        state = AmbientMonitorState.COMPLETED
    mode = (
        AmbientMonitorMode.ACTIVE_RECOVERY
        if status.mode == RuntimeMonitorMode.ACTIVE_RECOVERY
        else AmbientMonitorMode.AMBIENT
    )
    return AmbientMonitorStatus(
        state=state,
        mode=None if status.state == RuntimeMonitorState.OFF else mode,
        poll_interval_seconds=status.poll_interval_seconds,
        last_sync_at=status.last_tick_at,
        last_error=status.last_error,
        estimated_afferens_tokens_per_call=status.token_budget.estimated_tokens_per_call,
        target_object_key=status.target_object_key,
        target_visible_now=None,
        zone_id=status.zone_id,
        started_at=status.started_at,
        ends_at=status.ends_at,
        observations_synced=status.observations_synced,
        last_observation_id=status.last_observation_id,
    )
