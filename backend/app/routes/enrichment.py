from __future__ import annotations

from fastapi import APIRouter, Depends

from app.enrichment import ObservationEnrichmentService
from app.routes.dependencies import get_observation_enrichment_service
from app.schemas import (
    EnrichmentLatestRequest,
    EnrichmentLatestResponse,
    LatestEnrichmentResponse,
)

router = APIRouter(tags=["enrichment"])


@router.post("/api/enrichment/latest", response_model=EnrichmentLatestResponse)
async def enrich_latest_observation(
    request: EnrichmentLatestRequest | None = None,
    service: ObservationEnrichmentService = Depends(get_observation_enrichment_service),
) -> EnrichmentLatestResponse:
    return await service.enrich_latest(request or EnrichmentLatestRequest())


@router.get("/api/enrichment/latest", response_model=LatestEnrichmentResponse)
async def latest_enrichment(
    service: ObservationEnrichmentService = Depends(get_observation_enrichment_service),
) -> LatestEnrichmentResponse:
    return LatestEnrichmentResponse(enrichment=service.latest_enrichment())
