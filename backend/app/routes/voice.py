from __future__ import annotations

from fastapi import APIRouter, Depends

from app.query_service import QueryAnswerService
from app.routes.dependencies import get_query_answer_service
from app.schemas import (
    QueryRequest,
    QueryResponse,
    VoiceQueryRequest,
    VoiceQueryResponse,
)

router = APIRouter(tags=["voice"])


@router.post("/api/voice/query", response_model=VoiceQueryResponse)
async def voice_query(
    request: VoiceQueryRequest,
    service: QueryAnswerService = Depends(get_query_answer_service),
) -> VoiceQueryResponse:
    query_result = await service.answer(
        QueryRequest(query=request.query, session_id=request.session_id)
    )
    return VoiceQueryResponse(
        ok=True,
        query_result=query_result,
        spoken_text=_spoken_text(query_result),
    )


def _spoken_text(query_result: QueryResponse) -> str:
    sentences = [
        sentence.strip()
        for sentence in query_result.answer.split(".")
        if sentence.strip()
    ]
    spoken = ". ".join(sentences[:2]).strip()
    if spoken and not spoken.endswith("."):
        spoken += "."
    if "verify" not in spoken.lower():
        spoken = f"{spoken} Please verify in person.".strip()
    return spoken or "I do not have enough evidence to answer. Please verify in person."
