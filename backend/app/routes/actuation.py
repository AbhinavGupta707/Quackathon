from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.actuation import ActuationService
from app.routes.dependencies import get_actuation_service, get_data_spine_service
from app.schemas import (
    ActuationResponse,
    AlarmActuationRequest,
    CaptureFrameActuationRequest,
)
from app.services import DataSpineService

router = APIRouter(tags=["actuation"])


@router.post("/api/actuate/alarm", response_model=ActuationResponse)
async def actuate_alarm(
    request: AlarmActuationRequest,
    data_spine: DataSpineService = Depends(get_data_spine_service),
    service: ActuationService = Depends(get_actuation_service),
) -> ActuationResponse:
    task = _get_task_or_404(data_spine, request.task_id)
    _validate_alert_if_present(data_spine, alert_id=request.alert_id, task_id=task.id)
    _validate_evidence_linkage(task)
    attempt = await service.trigger_alarm(task=task, request=request)
    return ActuationResponse(ok=True, attempt=attempt)


@router.post("/api/actuate/capture-frame", response_model=ActuationResponse)
async def actuate_capture_frame(
    request: CaptureFrameActuationRequest,
    data_spine: DataSpineService = Depends(get_data_spine_service),
    service: ActuationService = Depends(get_actuation_service),
) -> ActuationResponse:
    task = _get_task_or_404(data_spine, request.task_id)
    _validate_alert_if_present(data_spine, alert_id=request.alert_id, task_id=task.id)
    _validate_evidence_linkage(task)
    attempt = await service.capture_frame(task=task, request=request)
    return ActuationResponse(ok=True, attempt=attempt)


def _get_task_or_404(data_spine: DataSpineService, task_id: str):
    task = data_spine.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )
    return task


def _validate_alert_if_present(
    data_spine: DataSpineService,
    *,
    alert_id: str | None,
    task_id: str,
) -> None:
    if alert_id is None:
        return
    alert = data_spine.get_alert(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found.",
        )
    if alert.task_id != task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is not linked to the requested task.",
        )


def _validate_evidence_linkage(task) -> None:
    if task.evidence_observation_ids:
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Actuation requires a task with linked live evidence.",
    )
