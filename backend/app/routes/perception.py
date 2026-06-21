from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.afferens_adapter import AfferensAdapter
from app.routes.dependencies import get_afferens_adapter, get_data_spine_service
from app.schemas import (
    LatestObservationResponse,
    ObjectsLastSeenResponse,
    PerceptionSyncRequest,
    PerceptionSyncResponse,
    TaskState,
    TaskType,
    TasksResponse,
)
from app.services import DataSpineService

router = APIRouter(tags=["perception"])


@router.post("/api/perception/sync", response_model=PerceptionSyncResponse)
async def perception_sync(
    request: PerceptionSyncRequest,
    adapter: AfferensAdapter = Depends(get_afferens_adapter),
    service: DataSpineService = Depends(get_data_spine_service),
) -> PerceptionSyncResponse:
    fetch_result = await adapter.fetch_events(limit=request.limit)
    if not fetch_result.is_live:
        return PerceptionSyncResponse(
            ok=False,
            status=fetch_result.status,
            message=fetch_result.status.message,
        )

    sync_result = service.sync_raw_events(fetch_result.raw_events, room_id=request.room_id)
    return PerceptionSyncResponse(
        ok=True,
        observations=sync_result.observations,
        objects_updated=sync_result.objects_updated,
        tasks_created=sync_result.tasks_created,
        alerts_created=sync_result.alerts_created,
        status=fetch_result.status,
    )


@router.get("/api/observations/latest", response_model=LatestObservationResponse)
async def observations_latest(
    service: DataSpineService = Depends(get_data_spine_service),
) -> LatestObservationResponse:
    return LatestObservationResponse(observation=service.latest_observation())


@router.get("/api/objects/last-seen", response_model=ObjectsLastSeenResponse)
async def objects_last_seen(
    service: DataSpineService = Depends(get_data_spine_service),
) -> ObjectsLastSeenResponse:
    return ObjectsLastSeenResponse(objects=service.list_last_seen_objects())


@router.get("/api/tasks", response_model=TasksResponse)
async def tasks(
    state: TaskState | None = Query(default=None),
    type: TaskType | None = Query(default=None),
    service: DataSpineService = Depends(get_data_spine_service),
) -> TasksResponse:
    return TasksResponse(tasks=service.list_tasks(state=state, task_type=type))
