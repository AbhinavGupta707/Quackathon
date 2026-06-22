from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.diary import DailyCareService
from app.routes.dependencies import get_daily_care_service
from app.schemas import (
    ActivityTimelineResponse,
    CareNoteGenerateRequest,
    CareNoteGenerateResponse,
    CareNotesResponse,
    DiaryGenerateRequest,
    DiaryGenerateResponse,
    DiaryResponse,
    FamilyMessageAckResponse,
    FamilyMessageCreateRequest,
    FamilyMessageCreateResponse,
    FamilyMessagesResponse,
    utc_now,
)

router = APIRouter(tags=["daily-care"])


def _default_date(value: date | None) -> date:
    return value or utc_now().date()


@router.get("/api/activity/timeline", response_model=ActivityTimelineResponse)
async def activity_timeline(
    date: date = Query(...),
    service: DailyCareService = Depends(get_daily_care_service),
) -> ActivityTimelineResponse:
    return ActivityTimelineResponse(
        date=date,
        events=service.activity_timeline(date),
    )


@router.get("/api/diary", response_model=DiaryResponse)
async def diary_get(
    date: date = Query(...),
    service: DailyCareService = Depends(get_daily_care_service),
) -> DiaryResponse:
    return DiaryResponse(date=date, diary=service.get_diary(date))


@router.post("/api/diary/generate", response_model=DiaryGenerateResponse)
async def diary_generate(
    request: DiaryGenerateRequest,
    service: DailyCareService = Depends(get_daily_care_service),
) -> DiaryGenerateResponse:
    return DiaryGenerateResponse(
        ok=True,
        diary=await service.generate_diary_with_provider(_default_date(request.date)),
    )


@router.get("/api/care-notes", response_model=CareNotesResponse)
async def care_notes_get(
    date: date = Query(...),
    service: DailyCareService = Depends(get_daily_care_service),
) -> CareNotesResponse:
    return CareNotesResponse(date=date, notes=service.list_care_notes(date))


@router.post("/api/care-notes/generate", response_model=CareNoteGenerateResponse)
async def care_notes_generate(
    request: CareNoteGenerateRequest,
    service: DailyCareService = Depends(get_daily_care_service),
) -> CareNoteGenerateResponse:
    return CareNoteGenerateResponse(
        ok=True,
        note=await service.generate_care_note_with_provider(
            _default_date(request.date),
            request.audience,
        ),
    )


@router.get("/api/family-messages", response_model=FamilyMessagesResponse)
async def family_messages_get(
    include_acknowledged: bool = Query(default=False),
    service: DailyCareService = Depends(get_daily_care_service),
) -> FamilyMessagesResponse:
    return FamilyMessagesResponse(
        messages=service.list_family_messages(include_acknowledged=include_acknowledged)
    )


@router.get("/api/family-messages/active", response_model=FamilyMessagesResponse)
async def family_messages_active(
    service: DailyCareService = Depends(get_daily_care_service),
) -> FamilyMessagesResponse:
    return FamilyMessagesResponse(messages=service.active_family_messages())


@router.post("/api/family-messages", response_model=FamilyMessageCreateResponse)
async def family_messages_create(
    request: FamilyMessageCreateRequest,
    service: DailyCareService = Depends(get_daily_care_service),
) -> FamilyMessageCreateResponse:
    return FamilyMessageCreateResponse(
        ok=True,
        message=service.create_family_message(
            title=request.title,
            body=request.body,
            priority=request.priority,
            trigger_object_key=request.trigger_object_key,
            trigger_zone_id=request.trigger_zone_id,
            starts_at=request.starts_at,
            expires_at=request.expires_at,
        ),
    )


@router.post("/api/family-messages/{message_id}/ack", response_model=FamilyMessageAckResponse)
async def family_messages_ack(
    message_id: str,
    service: DailyCareService = Depends(get_daily_care_service),
) -> FamilyMessageAckResponse:
    message = service.acknowledge_family_message(message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family message not found.",
        )
    return FamilyMessageAckResponse(ok=True, message=message)
