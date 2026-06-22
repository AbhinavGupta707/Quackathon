from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.action_intelligence import ActionIntelligenceService
from app.alerts import CaregiverNotificationService
from app.actuation import ActuationService
from app.ambient import AmbientMonitorService
from app.afferens_adapter import AfferensAdapter
from app.assistant import AssistantService
from app.config import Settings, get_settings
from app.db import DatabaseUnavailable, create_session_factory
from app.diary import DailyCareService
from app.enrichment import ObservationEnrichmentService
from app.guidance import GuidedRecoveryService
from app.providers.fireworks import FireworksReasoningAdapter
from app.query_service import QueryAnswerService
from app.runtime_supervisor import RuntimeMonitorSupervisor
from app.semantic_memory import SemanticMemoryService
from app.services import DataSpineService
from app.task_resolution import TaskResolutionService
from app.wellness import HydrationWellnessService
from app.workflows.object_recovery import ObjectRecoveryWorkflow
from app.yolo_fall_adapter import UltralyticsFallAdapter


_ambient_monitor_service: AmbientMonitorService | None = None
_runtime_monitor_supervisor: RuntimeMonitorSupervisor | None = None
_yolo_fall_adapter: UltralyticsFallAdapter | None = None
_yolo_fall_adapter_key: tuple[object, ...] | None = None


def get_app_settings() -> Settings:
    return get_settings()


def get_afferens_adapter(settings: Settings = Depends(get_app_settings)) -> AfferensAdapter:
    return AfferensAdapter(settings)


def get_data_spine_service(settings: Settings = Depends(get_app_settings)) -> DataSpineService:
    try:
        session_factory = create_session_factory(settings)
        from app.sql_repository import SQLAlchemyDataRepository
    except DatabaseUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return DataSpineService(
        SQLAlchemyDataRepository(session_factory),
        recent_window_seconds=settings.object_recent_window_seconds,
    )


def get_ambient_monitor_service(
    settings: Settings = Depends(get_app_settings),
) -> AmbientMonitorService:
    global _ambient_monitor_service
    if _ambient_monitor_service is None:
        _ambient_monitor_service = AmbientMonitorService(
            default_poll_interval_seconds=settings.ambient_default_poll_interval_seconds,
        )
    return _ambient_monitor_service


def get_runtime_monitor_supervisor(
    settings: Settings = Depends(get_app_settings),
) -> RuntimeMonitorSupervisor:
    global _runtime_monitor_supervisor
    if _runtime_monitor_supervisor is None:
        _runtime_monitor_supervisor = RuntimeMonitorSupervisor(settings)
    return _runtime_monitor_supervisor


def get_fireworks_reasoning_adapter(
    settings: Settings = Depends(get_app_settings),
) -> FireworksReasoningAdapter:
    return FireworksReasoningAdapter(settings)


def get_object_recovery_workflow(
    settings: Settings = Depends(get_app_settings),
) -> ObjectRecoveryWorkflow:
    return ObjectRecoveryWorkflow(settings=settings)


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


def get_guided_recovery_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    workflow: ObjectRecoveryWorkflow = Depends(get_object_recovery_workflow),
) -> GuidedRecoveryService:
    return GuidedRecoveryService(data_spine, workflow=workflow)


def get_daily_care_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    fireworks: FireworksReasoningAdapter = Depends(get_fireworks_reasoning_adapter),
) -> DailyCareService:
    return DailyCareService(data_spine, fireworks=fireworks)


def get_hydration_wellness_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
) -> HydrationWellnessService:
    return HydrationWellnessService(data_spine)


def get_caregiver_notification_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
) -> CaregiverNotificationService:
    return CaregiverNotificationService(data_spine)


def get_yolo_fall_adapter(
    settings: Settings = Depends(get_app_settings),
) -> UltralyticsFallAdapter:
    global _yolo_fall_adapter, _yolo_fall_adapter_key
    key = (
        settings.action_yolo_fall_enabled,
        settings.action_yolo_fall_model_path,
        settings.action_yolo_fall_confidence_threshold,
        settings.action_yolo_fall_fallen_labels,
        settings.action_yolo_fall_non_fallen_labels,
    )
    if _yolo_fall_adapter is None or _yolo_fall_adapter_key != key:
        _yolo_fall_adapter = UltralyticsFallAdapter(settings)
        _yolo_fall_adapter_key = key
    return _yolo_fall_adapter


def get_action_intelligence_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    settings: Settings = Depends(get_app_settings),
    fall_adapter: UltralyticsFallAdapter = Depends(get_yolo_fall_adapter),
) -> ActionIntelligenceService:
    return ActionIntelligenceService(data_spine, settings=settings, fall_adapter=fall_adapter)


def get_task_resolution_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    adapter: AfferensAdapter = Depends(get_afferens_adapter),
) -> TaskResolutionService:
    return TaskResolutionService(data_spine, adapter=adapter)


def get_actuation_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    adapter: AfferensAdapter = Depends(get_afferens_adapter),
    settings: Settings = Depends(get_app_settings),
) -> ActuationService:
    return ActuationService(data_spine, adapter=adapter, settings=settings)


def get_observation_enrichment_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    settings: Settings = Depends(get_app_settings),
    fireworks: FireworksReasoningAdapter = Depends(get_fireworks_reasoning_adapter),
) -> ObservationEnrichmentService:
    return ObservationEnrichmentService(
        data_spine,
        settings=settings,
        fireworks=fireworks,
    )


def get_semantic_memory_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    fireworks: FireworksReasoningAdapter = Depends(get_fireworks_reasoning_adapter),
) -> SemanticMemoryService:
    return SemanticMemoryService(
        data_spine,
        fireworks=fireworks,
    )


def get_assistant_service(
    data_spine: DataSpineService = Depends(get_data_spine_service),
    query_service: QueryAnswerService = Depends(get_query_answer_service),
    semantic_memory: SemanticMemoryService = Depends(get_semantic_memory_service),
    daily_care: DailyCareService = Depends(get_daily_care_service),
    wellness: HydrationWellnessService = Depends(get_hydration_wellness_service),
    fireworks: FireworksReasoningAdapter = Depends(get_fireworks_reasoning_adapter),
    afferens: AfferensAdapter = Depends(get_afferens_adapter),
    settings: Settings = Depends(get_app_settings),
) -> AssistantService:
    return AssistantService(
        data_spine,
        query_service=query_service,
        semantic_memory=semantic_memory,
        daily_care=daily_care,
        wellness=wellness,
        fireworks=fireworks,
        afferens=afferens,
        settings=settings,
    )
