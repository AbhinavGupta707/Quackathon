from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.afferens_adapter import AfferensAdapter
from app.config import Settings, get_settings
from app.db import DatabaseUnavailable, create_session_factory
from app.providers.fireworks import FireworksReasoningAdapter
from app.query_service import QueryAnswerService
from app.services import DataSpineService
from app.task_resolution import TaskResolutionService
from app.workflows.object_recovery import ObjectRecoveryWorkflow


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


def get_fireworks_reasoning_adapter(
    settings: Settings = Depends(get_app_settings),
) -> FireworksReasoningAdapter:
    return FireworksReasoningAdapter(settings)


def get_object_recovery_workflow() -> ObjectRecoveryWorkflow:
    return ObjectRecoveryWorkflow()


def get_query_answer_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    reasoning: FireworksReasoningAdapter = Depends(get_fireworks_reasoning_adapter),
    workflow: ObjectRecoveryWorkflow = Depends(get_object_recovery_workflow),
) -> QueryAnswerService:
    return QueryAnswerService(
        data_spine,
        reasoning=reasoning,
        workflow=workflow,
    )


def get_task_resolution_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    adapter: AfferensAdapter = Depends(get_afferens_adapter),
) -> TaskResolutionService:
    return TaskResolutionService(data_spine, adapter=adapter)
