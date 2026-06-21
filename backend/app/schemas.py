from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ServiceHealthState(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"


class AfferensConnectionState(StrEnum):
    MISSING_KEY = "missing_key"
    INVALID_KEY = "invalid_key"
    INACTIVE_KEY = "inactive_key"
    NO_LIVE_EVENTS = "no_live_events"
    LIVE = "live"
    ERROR = "error"


class ServiceStatus(BaseModel):
    state: ServiceHealthState
    message: str
    checked_at: datetime = Field(default_factory=utc_now)


class HealthResponse(BaseModel):
    ok: bool
    version: str
    environment: str
    services: dict[str, ServiceStatus]


class AfferensStatus(BaseModel):
    configured: bool
    base_url: str
    state: AfferensConnectionState
    message: str
    latest_event_id: str | None = None
    latest_timestamp_utc: datetime | None = None
    source_node_id: str | None = None
    modality: str | None = None


class AfferensLatestResponse(BaseModel):
    ok: bool
    raw_event: dict[str, Any] | None = None
    status: AfferensStatus


class AfferensFetchResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: AfferensStatus
    raw_event: dict[str, Any] | None = None
    raw_payload: Any | None = None

    @property
    def is_live(self) -> bool:
        return self.status.state == AfferensConnectionState.LIVE
