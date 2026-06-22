from __future__ import annotations

import importlib.util

from fastapi import APIRouter, Depends

from app.config import ConfigIssueSeverity, Settings
from app.db import get_database_status
from app.observability import langsmith_status
from app.providers.fireworks import FireworksReasoningAdapter
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
        "configuration": _service_status_from_config_validation(settings),
        "database": get_database_status(settings),
        "afferens": afferens_service,
        "fireworks": FireworksReasoningAdapter(settings).status(),
        "langgraph": _service_status_from_langgraph_install(),
        "langsmith": langsmith_status(settings),
    }

    return HealthResponse(
        ok=all(service.state != ServiceHealthState.ERROR for service in services.values()),
        version=settings.version,
        environment=settings.environment,
        services=services,
    )


def _service_status_from_config_validation(settings: Settings) -> ServiceStatus:
    issues = settings.validate_startup_environment()
    errors = [issue for issue in issues if issue.severity == ConfigIssueSeverity.ERROR]
    warnings = [issue for issue in issues if issue.severity == ConfigIssueSeverity.WARNING]

    if errors:
        return ServiceStatus(
            state=ServiceHealthState.ERROR,
            message=(
                "Startup configuration has blocking deployment issues: "
                + ", ".join(issue.code for issue in errors)
            ),
        )
    if warnings:
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message=(
                "Startup configuration has non-blocking issues: "
                + ", ".join(issue.code for issue in warnings)
            ),
        )
    return ServiceStatus(
        state=ServiceHealthState.OK,
        message="Startup configuration passed required validation for this profile.",
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


def _service_status_from_langgraph_install() -> ServiceStatus:
    if importlib.util.find_spec("langgraph") is None:
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="LangGraph is not installed; deterministic workflow fallback is available.",
        )
    return ServiceStatus(
        state=ServiceHealthState.OK,
        message="LangGraph is installed for workflow orchestration.",
    )
