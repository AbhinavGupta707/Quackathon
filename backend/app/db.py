from __future__ import annotations

from app.config import Settings
from app.schemas import ServiceHealthState, ServiceStatus


class DatabaseUnavailable(RuntimeError):
    pass


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
        from sqlalchemy import create_engine, text
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
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
        )
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
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.orm import sessionmaker
    except ModuleNotFoundError as exc:
        raise DatabaseUnavailable("SQLAlchemy is not installed in the backend environment.") from exc

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except ModuleNotFoundError as exc:
        raise DatabaseUnavailable(f"Database driver is not installed: {exc.name}.") from exc
    except SQLAlchemyError as exc:
        raise DatabaseUnavailable(f"Database connection check failed: {exc.__class__.__name__}.") from exc

    return sessionmaker(bind=engine, expire_on_commit=False)
