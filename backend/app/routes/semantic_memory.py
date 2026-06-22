from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.routes.dependencies import get_semantic_memory_service
from app.schemas import (
    SemanticMemoryAskRequest,
    SemanticMemoryAskResponse,
    SemanticMemoryReindexRequest,
    SemanticMemoryReindexResponse,
    SemanticMemorySearchResponse,
    SemanticMemorySourceType,
)
from app.semantic_memory import SemanticMemoryService

router = APIRouter(tags=["semantic-memory"])


@router.get("/api/memory/semantic", response_model=SemanticMemorySearchResponse)
def semantic_memory(
    q: str | None = Query(default=None, max_length=1200),
    limit: int = Query(default=10, ge=1, le=50),
    source_type: list[SemanticMemorySourceType] | None = Query(default=None),
    service: SemanticMemoryService = Depends(get_semantic_memory_service),
) -> SemanticMemorySearchResponse:
    query = q.strip() if q and q.strip() else None
    return service.semantic(query=query, limit=limit, source_types=source_type)


@router.post("/api/memory/reindex", response_model=SemanticMemoryReindexResponse)
def reindex_memory(
    request: SemanticMemoryReindexRequest,
    service: SemanticMemoryService = Depends(get_semantic_memory_service),
) -> SemanticMemoryReindexResponse:
    return service.reindex(force=request.force, source_types=request.source_types)


@router.post("/api/memory/ask", response_model=SemanticMemoryAskResponse)
async def ask_memory(
    request: SemanticMemoryAskRequest,
    service: SemanticMemoryService = Depends(get_semantic_memory_service),
) -> SemanticMemoryAskResponse:
    return await service.ask(request)
