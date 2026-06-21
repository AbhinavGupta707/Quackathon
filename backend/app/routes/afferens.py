from __future__ import annotations

from fastapi import APIRouter, Depends

from app.afferens_adapter import AfferensAdapter
from app.routes.dependencies import get_afferens_adapter
from app.schemas import AfferensLatestResponse, AfferensStatus

router = APIRouter(prefix="/api/afferens", tags=["afferens"])


@router.get("/status", response_model=AfferensStatus)
async def afferens_status(
    adapter: AfferensAdapter = Depends(get_afferens_adapter),
) -> AfferensStatus:
    result = await adapter.fetch_latest()
    return result.status


@router.get("/latest", response_model=AfferensLatestResponse)
async def afferens_latest(
    adapter: AfferensAdapter = Depends(get_afferens_adapter),
) -> AfferensLatestResponse:
    result = await adapter.fetch_latest()
    return AfferensLatestResponse(
        ok=result.is_live,
        raw_event=result.raw_event if result.is_live else None,
        status=result.status,
    )
