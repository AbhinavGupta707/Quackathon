from __future__ import annotations

from fastapi import APIRouter, Depends

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.routes.dependencies import get_afferens_adapter, get_app_settings
from app.schemas import (
    AfferensConnectionState,
    HealthResponse,
    ServiceHealthState,
    ServiceStatus,
)

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health(
    settings: Settings = Depends(get_app_settings),
    adapter: AfferensAdapter = Depends(get_afferens_adapter),
) -> HealthResponse:
    afferens_result = await adapter.fetch_latest()
    afferens_service = _service_status_from_afferens(afferens_result.status.state)
    afferens_service.message = afferens_result.status.message

    services = {
        "database": ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="Database is not configured in Checkpoint 1.",
        ),
        "afferens": afferens_service,
    }

    return HealthResponse(
        ok=all(service.state != ServiceHealthState.ERROR for service in services.values()),
        version=settings.version,
        environment=settings.environment,
        services=services,
    )


def _service_status_from_afferens(state: AfferensConnectionState) -> ServiceStatus:
    if state == AfferensConnectionState.LIVE:
        return ServiceStatus(state=ServiceHealthState.OK, message="Live")
    if state in {
        AfferensConnectionState.MISSING_KEY,
        AfferensConnectionState.NO_LIVE_EVENTS,
    }:
        return ServiceStatus(state=ServiceHealthState.DEGRADED, message="Not live")
    return ServiceStatus(state=ServiceHealthState.ERROR, message="Afferens error")
