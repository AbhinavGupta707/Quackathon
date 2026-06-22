from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.routes.dependencies import get_hydration_wellness_service
from app.schemas import (
    HydrationEventCreateRequest,
    HydrationEventCreateResponse,
    HydrationSummaryResponse,
    WellnessCheckAckRequest,
    WellnessCheckAckResponse,
    WellnessCheckGenerateRequest,
    WellnessCheckGenerateResponse,
    WellnessChecksResponse,
    utc_now,
)
from app.wellness import HydrationWellnessService

router = APIRouter(tags=["wellness"])


def _default_date(value: date | None) -> date:
    return value or utc_now().date()


@router.get("/api/hydration/summary", response_model=HydrationSummaryResponse)
async def hydration_summary(
    date: date = Query(...),
    service: HydrationWellnessService = Depends(get_hydration_wellness_service),
) -> HydrationSummaryResponse:
    return HydrationSummaryResponse(
        date=date,
        summary=service.hydration_summary(date),
    )


@router.post("/api/hydration/events", response_model=HydrationEventCreateResponse)
async def hydration_event_create(
    request: HydrationEventCreateRequest,
    service: HydrationWellnessService = Depends(get_hydration_wellness_service),
) -> HydrationEventCreateResponse:
    return HydrationEventCreateResponse(
        ok=True,
        event=service.create_hydration_event(
            event_type=request.type,
            occurred_at=request.occurred_at,
            confidence=request.confidence,
            zone_id=request.zone_id,
            evidence_ids=request.evidence_ids,
            metadata=request.metadata,
        ),
    )


@router.get("/api/wellness/checks", response_model=WellnessChecksResponse)
async def wellness_checks_get(
    date: date = Query(...),
    service: HydrationWellnessService = Depends(get_hydration_wellness_service),
) -> WellnessChecksResponse:
    return WellnessChecksResponse(date=date, checks=service.list_wellness_checks(date))


@router.post("/api/wellness/checks/generate", response_model=WellnessCheckGenerateResponse)
async def wellness_checks_generate(
    request: WellnessCheckGenerateRequest,
    service: HydrationWellnessService = Depends(get_hydration_wellness_service),
) -> WellnessCheckGenerateResponse:
    return WellnessCheckGenerateResponse(
        ok=True,
        checks=service.generate_wellness_checks(_default_date(request.date)),
    )


@router.post("/api/wellness/checks/{check_id}/ack", response_model=WellnessCheckAckResponse)
async def wellness_check_ack(
    check_id: str,
    request: WellnessCheckAckRequest,
    service: HydrationWellnessService = Depends(get_hydration_wellness_service),
) -> WellnessCheckAckResponse:
    check = service.acknowledge_wellness_check(
        check_id,
        acknowledged_by=request.acknowledged_by,
        note=request.note,
    )
    if check is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wellness check not found.",
        )
    return WellnessCheckAckResponse(ok=True, check=check)
