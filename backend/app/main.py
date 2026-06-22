from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import ConfigIssueSeverity, Settings, get_settings
from app.routes import (
    actuation,
    action_events,
    afferens,
    alerts,
    ambient,
    assistant,
    diary,
    enrichment,
    guidance,
    health,
    home_zones,
    perception,
    providers,
    query,
    runtime,
    semantic_memory,
    tasks,
    voice,
    wellness,
)
from app.routes.dependencies import get_app_settings, get_runtime_monitor_supervisor


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = getattr(app.state, "settings", get_settings())
    supervisor = get_runtime_monitor_supervisor(settings)
    app.state.runtime_monitor_supervisor = supervisor
    supervisor.start_background()
    try:
        yield
    finally:
        await supervisor.stop_background()


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    _validate_startup_or_raise(active_settings)

    app = FastAPI(
        title="Afferens Memory Guardian API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = active_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_allowed_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings is not None:
        app.dependency_overrides[get_app_settings] = lambda: active_settings

    app.include_router(health.router)
    app.include_router(afferens.router)
    app.include_router(perception.router)
    app.include_router(providers.router)
    app.include_router(query.router)
    app.include_router(runtime.router)
    app.include_router(assistant.router)
    app.include_router(semantic_memory.router)
    app.include_router(tasks.router)
    app.include_router(alerts.router)
    app.include_router(actuation.router)
    app.include_router(action_events.router)
    app.include_router(enrichment.router)
    app.include_router(voice.router)
    app.include_router(guidance.router)
    app.include_router(home_zones.router)
    app.include_router(ambient.router)
    app.include_router(diary.router)
    app.include_router(wellness.router)

    return app


def _validate_startup_or_raise(settings: Settings) -> None:
    if not settings.strict_startup_validation:
        return

    errors = [
        issue
        for issue in settings.validate_startup_environment()
        if issue.severity == ConfigIssueSeverity.ERROR
    ]
    if errors:
        codes = ", ".join(issue.code for issue in errors)
        raise RuntimeError(f"Startup environment validation failed: {codes}")


app = create_app()
