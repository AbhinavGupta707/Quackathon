from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.afferens_adapter import AfferensAdapter
from app.config import Settings, get_settings
from app.db import DatabaseUnavailable, create_session_factory
from app.services import DataSpineService


def get_afferens_adapter() -> AfferensAdapter:
    return AfferensAdapter(get_settings())


def get_app_settings() -> Settings:
    return get_settings()


def get_data_spine_service(settings: Settings = Depends(get_app_settings)) -> DataSpineService:
    try:
        session_factory = create_session_factory(settings)
        from app.sql_repository import SQLAlchemyDataRepository
    except DatabaseUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return DataSpineService(SQLAlchemyDataRepository(session_factory))
