from __future__ import annotations

from fastapi import APIRouter, Depends

from app.guidance import GuidedRecoveryService
from app.routes.dependencies import get_guided_recovery_service
from app.schemas import GuidedRecoveryStartRequest, GuidedRecoveryStartResponse

router = APIRouter(tags=["guidance"])


@router.post("/api/guidance/recovery/start", response_model=GuidedRecoveryStartResponse)
async def start_guided_recovery(
    request: GuidedRecoveryStartRequest,
    service: GuidedRecoveryService = Depends(get_guided_recovery_service),
) -> GuidedRecoveryStartResponse:
    return service.start(request)
