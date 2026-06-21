from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings
from app.db import get_database_status
from app.routes.dependencies import get_app_settings
from app.schemas import (
    HealthResponse,
    ServiceHealthState,
    ServiceStatus,
)

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health(
    settings: Settings = Depends(get_app_settings),
) -> HealthResponse:
    afferens_service = _service_status_from_afferens_config(settings)

    services = {
        "database": get_database_status(settings),
        "afferens": afferens_service,
    }

    return HealthResponse(
        ok=all(service.state != ServiceHealthState.ERROR for service in services.values()),
        version=settings.version,
        environment=settings.environment,
        services=services,
    )


def _service_status_from_afferens_config(settings: Settings) -> ServiceStatus:
    if not settings.afferens_configured:
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="Afferens API key is not configured.",
        )

    return ServiceStatus(
        state=ServiceHealthState.DEGRADED,
        message="Afferens key is configured. Use /api/afferens/status for live node checks.",
    )
