from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routes.dependencies import get_runtime_monitor_supervisor
from app.runtime_supervisor import RuntimeMonitorSupervisor
from app.schemas import RuntimeMonitorResponse, RuntimeMonitorStartRequest

router = APIRouter(tags=["runtime"])


@router.get("/api/runtime/monitor/status", response_model=RuntimeMonitorResponse)
async def runtime_monitor_status(
    supervisor: RuntimeMonitorSupervisor = Depends(get_runtime_monitor_supervisor),
) -> RuntimeMonitorResponse:
    return RuntimeMonitorResponse(ok=True, monitor=supervisor.current_status())


@router.post("/api/runtime/monitor/start", response_model=RuntimeMonitorResponse)
async def runtime_monitor_start(
    request: RuntimeMonitorStartRequest,
    supervisor: RuntimeMonitorSupervisor = Depends(get_runtime_monitor_supervisor),
) -> RuntimeMonitorResponse:
    return await supervisor.start_monitor(request)


@router.post("/api/runtime/monitor/stop", response_model=RuntimeMonitorResponse)
async def runtime_monitor_stop(
    supervisor: RuntimeMonitorSupervisor = Depends(get_runtime_monitor_supervisor),
) -> RuntimeMonitorResponse:
    return await supervisor.stop_monitor()
