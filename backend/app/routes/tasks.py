from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.routes.dependencies import get_data_spine_service, get_task_resolution_service
from app.schemas import (
    TaskResolveRequest,
    TaskResolveResponse,
    TaskState,
    TaskType,
    TaskVerifyRequest,
    TaskVerifyResponse,
    TasksResponse,
)
from app.services import DataSpineService
from app.task_resolution import TaskResolutionService

router = APIRouter(tags=["tasks"])


@router.get("/api/tasks", response_model=TasksResponse)
async def tasks(
    state: TaskState | None = Query(default=None),
    type: TaskType | None = Query(default=None),
    service: DataSpineService = Depends(get_data_spine_service),
) -> TasksResponse:
    return TasksResponse(tasks=service.list_tasks(state=state, task_type=type))


@router.post("/api/tasks/{task_id}/verify", response_model=TaskVerifyResponse)
async def verify_task(
    task_id: str,
    request: TaskVerifyRequest,
    data_spine: DataSpineService = Depends(get_data_spine_service),
    service: TaskResolutionService = Depends(get_task_resolution_service),
) -> TaskVerifyResponse:
    task = data_spine.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )
    updated_task, verification = await service.verify(task, request)
    return TaskVerifyResponse(ok=True, task=updated_task, verification=verification)


@router.post("/api/tasks/{task_id}/resolve", response_model=TaskResolveResponse)
async def resolve_task(
    task_id: str,
    request: TaskResolveRequest,
    data_spine: DataSpineService = Depends(get_data_spine_service),
    service: TaskResolutionService = Depends(get_task_resolution_service),
) -> TaskResolveResponse:
    task = data_spine.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )
    resolved = service.resolve(task, request)
    return TaskResolveResponse(ok=True, task=resolved)
