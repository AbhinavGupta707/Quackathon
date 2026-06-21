from __future__ import annotations

from fastapi import APIRouter, Depends

from app.query_service import QueryAnswerService
from app.routes.dependencies import get_query_answer_service
from app.schemas import QueryRequest, QueryResponse

router = APIRouter(tags=["query"])


@router.post("/api/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    service: QueryAnswerService = Depends(get_query_answer_service),
) -> QueryResponse:
    return await service.answer(request)
