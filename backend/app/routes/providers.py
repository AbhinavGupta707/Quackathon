from __future__ import annotations

from fastapi import APIRouter, Depends

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.provider_status import ProviderStatusService
from app.routes.dependencies import (
    get_afferens_adapter,
    get_app_settings,
    get_yolo_fall_adapter,
)
from app.schemas import ProvidersStatusResponse
from app.yolo_fall_adapter import UltralyticsFallAdapter

router = APIRouter(tags=["providers"])


@router.get("/api/providers/status", response_model=ProvidersStatusResponse)
@router.get("/api/provider-status", response_model=ProvidersStatusResponse, include_in_schema=False)
async def providers_status(
    settings: Settings = Depends(get_app_settings),
    afferens: AfferensAdapter = Depends(get_afferens_adapter),
    fall_adapter: UltralyticsFallAdapter = Depends(get_yolo_fall_adapter),
) -> ProvidersStatusResponse:
    return await ProviderStatusService(
        settings,
        afferens=afferens,
        fall_adapter=fall_adapter,
    ).status()
