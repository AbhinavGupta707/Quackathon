from __future__ import annotations

from functools import lru_cache

from app.config import Settings
from app.schemas import ServiceHealthState, ServiceStatus


class DatabaseUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=4)
def _get_engine(database_url: str, connect_timeout_seconds: int):
    from sqlalchemy import create_engine

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        connect_args={"connect_timeout": connect_timeout_seconds},
    )


@lru_cache(maxsize=4)
def _get_session_factory(database_url: str, connect_timeout_seconds: int):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(
        bind=_get_engine(database_url, connect_timeout_seconds),
        expire_on_commit=False,
    )


def get_database_status(settings: Settings) -> ServiceStatus:
    if not settings.database_enabled:
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="Database runtime is disabled.",
        )
    if not settings.database_configured:
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="DATABASE_URL is not configured; durable memory endpoints are unavailable.",
        )

    try:
        from sqlalchemy import text
        from sqlalchemy.exc import SQLAlchemyError
    except ModuleNotFoundError:
        return ServiceStatus(
            state=ServiceHealthState.ERROR,
            message="SQLAlchemy is not installed in the backend environment.",
        )

    database_url = settings.database_url_value()
    if database_url is None:
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="DATABASE_URL is not configured; durable memory endpoints are unavailable.",
        )

    try:
        engine = _get_engine(database_url, settings.database_connect_timeout_seconds)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except ModuleNotFoundError as exc:
        return ServiceStatus(
            state=ServiceHealthState.ERROR,
            message=f"Database driver is not installed: {exc.name}.",
        )
    except SQLAlchemyError as exc:
        return ServiceStatus(
            state=ServiceHealthState.ERROR,
            message=f"Database connection check failed: {exc.__class__.__name__}.",
        )

    return ServiceStatus(state=ServiceHealthState.OK, message="Connected.")


def create_session_factory(settings: Settings):
    if not settings.database_enabled:
        raise DatabaseUnavailable("Database runtime is disabled.")
    database_url = settings.database_url_value()
    if database_url is None:
        raise DatabaseUnavailable("DATABASE_URL is not configured; durable memory endpoints are unavailable.")

    try:
        from sqlalchemy import text
        from sqlalchemy.exc import SQLAlchemyError
    except ModuleNotFoundError as exc:
        raise DatabaseUnavailable("SQLAlchemy is not installed in the backend environment.") from exc

    engine = _get_engine(database_url, settings.database_connect_timeout_seconds)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except ModuleNotFoundError as exc:
        raise DatabaseUnavailable(f"Database driver is not installed: {exc.name}.") from exc
    except SQLAlchemyError as exc:
        raise DatabaseUnavailable(f"Database connection check failed: {exc.__class__.__name__}.") from exc

    return _get_session_factory(database_url, settings.database_connect_timeout_seconds)
