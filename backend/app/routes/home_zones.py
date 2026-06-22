from __future__ import annotations

from fastapi import APIRouter, Depends

from app.ids import new_id
from app.routes.dependencies import get_data_spine_service
from app.schemas import (
    HomeZone,
    HomeZoneCreateRequest,
    HomeZoneCreateResponse,
    HomeZonesResponse,
    utc_now,
)
from app.services import DataSpineService

router = APIRouter(tags=["home-zones"])


@router.get("/api/home-zones", response_model=HomeZonesResponse)
async def home_zones_list(
    service: DataSpineService = Depends(get_data_spine_service),
) -> HomeZonesResponse:
    return HomeZonesResponse(zones=service.list_home_zones())


@router.post("/api/home-zones", response_model=HomeZoneCreateResponse)
async def home_zones_create(
    request: HomeZoneCreateRequest,
    service: DataSpineService = Depends(get_data_spine_service),
) -> HomeZoneCreateResponse:
    zone = HomeZone(
        id=request.id or new_id("zone"),
        name=request.name,
        room_type=request.room_type,
        aliases=request.aliases,
        is_default=request.is_default,
        source_node_id=request.source_node_id,
        region_strategy=request.region_strategy,
        regions=request.regions,
        metadata=request.metadata,
        created_at=utc_now(),
    )
    return HomeZoneCreateResponse(ok=True, zone=service.create_home_zone(zone))
