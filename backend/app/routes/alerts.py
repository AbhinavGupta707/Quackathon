from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas import AlertAckRequest, AlertAckResponse, AlertStatus, AlertsResponse, utc_now
from app.services import DataSpineService
from app.routes.dependencies import get_data_spine_service

router = APIRouter(tags=["alerts"])


@router.get("/api/alerts", response_model=AlertsResponse)
async def alerts(
    status_filter: AlertStatus | None = Query(default=None, alias="status"),
    service: DataSpineService = Depends(get_data_spine_service),
) -> AlertsResponse:
    return AlertsResponse(alerts=service.list_alerts(status=status_filter))


@router.post("/api/alerts/{alert_id}/ack", response_model=AlertAckResponse)
async def acknowledge_alert(
    alert_id: str,
    request: AlertAckRequest,
    service: DataSpineService = Depends(get_data_spine_service),
) -> AlertAckResponse:
    alert = service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found.",
        )

    updated = alert.model_copy(
        update={
            "status": AlertStatus.ACKNOWLEDGED,
            "acknowledged_at": utc_now(),
        }
    )
    updated = service.update_alert(updated)
    if updated.task_id is not None:
        service.add_task_event(
            task_id=updated.task_id,
            event_type="alert_acknowledged",
            message=f"{request.acknowledged_by} acknowledged alert {updated.id}."
            + (f" Note: {request.note}" if request.note else ""),
            evidence_observation_ids=updated.evidence_observation_ids,
        )
    return AlertAckResponse(ok=True, alert=updated)
