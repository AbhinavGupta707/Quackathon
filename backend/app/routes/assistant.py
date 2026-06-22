from __future__ import annotations

from fastapi import APIRouter, Depends

from app.assistant import AssistantService
from app.routes.dependencies import get_assistant_service
from app.schemas import AssistantAskRequest, AssistantAskResponse

router = APIRouter(tags=["assistant"])


@router.post("/api/assistant/ask", response_model=AssistantAskResponse)
async def assistant_ask(
    request: AssistantAskRequest,
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantAskResponse:
    return await service.ask(request)
