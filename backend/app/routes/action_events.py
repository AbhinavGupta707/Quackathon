from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.action_intelligence import ActionIntelligenceService
from app.routes.dependencies import get_action_intelligence_service
from app.schemas import (
    ActionEvaluateResponse,
    ActionEventCreateRequest,
    ActionEventCreateResponse,
    ActionEventsResponse,
    ActionEventType,
    ActionRuntimeStatusResponse,
    DrinkEvaluateRequest,
    FallEvaluateRequest,
)

router = APIRouter(tags=["action-events"])


@router.post("/api/action-events", response_model=ActionEventCreateResponse)
async def action_event_create(
    request: ActionEventCreateRequest,
    service: ActionIntelligenceService = Depends(get_action_intelligence_service),
) -> ActionEventCreateResponse:
    if request.type == ActionEventType.DRINK_CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Drink candidates must be submitted through /api/action-events/drink/evaluate "
                "with live object context and browser action telemetry."
            ),
        )
    event, wellness_check_id, hydration_event_id = service.create_action_event(request)
    return ActionEventCreateResponse(
        ok=True,
        event=event,
        wellness_check_id=wellness_check_id,
        hydration_event_id=hydration_event_id,
    )


@router.get("/api/action-events", response_model=ActionEventsResponse)
async def action_events_get(
    date: date | None = Query(default=None),
    type: ActionEventType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    service: ActionIntelligenceService = Depends(get_action_intelligence_service),
) -> ActionEventsResponse:
    return ActionEventsResponse(
        events=service.list_action_events(
            event_date=date,
            event_type=type,
            limit=limit,
        )
    )


@router.get("/api/action-events/runtime/status", response_model=ActionRuntimeStatusResponse)
async def action_event_runtime_status(
    service: ActionIntelligenceService = Depends(get_action_intelligence_service),
) -> ActionRuntimeStatusResponse:
    return service.runtime_status()


@router.post("/api/action-events/fall/evaluate", response_model=ActionEvaluateResponse)
async def action_event_fall_evaluate(
    request: FallEvaluateRequest,
    service: ActionIntelligenceService = Depends(get_action_intelligence_service),
) -> ActionEvaluateResponse:
    event, wellness_check_id, message = service.evaluate_fall(request)
    return ActionEvaluateResponse(
        ok=True,
        event=event,
        decision=event.type,
        wellness_check_id=wellness_check_id,
        message=message,
    )


@router.post("/api/action-events/fall/infer-frame", response_model=ActionEvaluateResponse)
async def action_event_fall_infer_frame(
    frame: Annotated[UploadFile, File()],
    source_node_id: Annotated[str | None, Form()] = None,
    zone_id: Annotated[str | None, Form()] = None,
    evidence_ids: Annotated[str | None, Form()] = None,
    occurred_at: Annotated[str | None, Form()] = None,
    persist_inconclusive: Annotated[bool, Form()] = True,
    service: ActionIntelligenceService = Depends(get_action_intelligence_service),
) -> ActionEvaluateResponse:
    if frame.size is not None and frame.size > service.max_frame_bytes:
        await frame.close()
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"frame upload must be {service.max_frame_bytes} bytes or smaller",
        )
    frame_bytes = await frame.read()
    await frame.close()
    if not frame_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="frame upload must not be empty",
        )
    if len(frame_bytes) > service.max_frame_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"frame upload must be {service.max_frame_bytes} bytes or smaller",
        )
    event, wellness_check_id, message = service.infer_fall_frame(
        frame_bytes=frame_bytes,
        source_node_id=_normalize_optional_form_text(source_node_id),
        zone_id=_normalize_optional_form_text(zone_id),
        evidence_ids=_parse_evidence_ids(evidence_ids),
        occurred_at=_parse_occurred_at(occurred_at),
        persist_inconclusive=persist_inconclusive,
    )
    return ActionEvaluateResponse(
        ok=True,
        event=event,
        decision=event.type,
        wellness_check_id=wellness_check_id,
        message=message,
    )


@router.post("/api/action-events/drink/evaluate", response_model=ActionEvaluateResponse)
async def action_event_drink_evaluate(
    request: DrinkEvaluateRequest,
    service: ActionIntelligenceService = Depends(get_action_intelligence_service),
) -> ActionEvaluateResponse:
    event, hydration_event_id, message = service.evaluate_drink(request)
    return ActionEvaluateResponse(
        ok=True,
        event=event,
        decision=event.type,
        hydration_event_id=hydration_event_id,
        message=message,
    )


def _normalize_optional_form_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_evidence_ids(value: str | None) -> list[str]:
    if value is None:
        return []
    parsed: list[str] = []
    for item in value.split(","):
        normalized = item.strip()
        if normalized and normalized not in parsed:
            parsed.append(normalized)
    return parsed


def _parse_occurred_at(value: str | None):
    normalized = _normalize_optional_form_text(value)
    if normalized is None:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="occurred_at must be an ISO timestamp",
        ) from exc
