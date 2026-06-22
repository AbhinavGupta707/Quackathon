from __future__ import annotations

import re
from datetime import timedelta

from app.afferens_adapter import AfferensAdapter
from app.schemas import (
    AmbientMonitorMode,
    AmbientMonitorState,
    AmbientMonitorStatus,
    AmbientStartRequest,
    LastSeenStatus,
    utc_now,
)
from app.services import DataSpineService


AFFERENS_VISION_TOKENS_PER_CALL = 14


class AmbientMonitorService:
    """Legacy bounded monitor seam retained for isolated tests and fallback wiring.

    Product routes use the autonomous runtime supervisor. This class must not
    be treated as the primary home-memory runtime.
    """

    def __init__(self, *, default_poll_interval_seconds: int = 45) -> None:
        self._status = AmbientMonitorStatus(
            state=AmbientMonitorState.OFF,
            mode=None,
            poll_interval_seconds=default_poll_interval_seconds,
            estimated_afferens_tokens_per_call=AFFERENS_VISION_TOKENS_PER_CALL,
        )

    def start(self, request: AmbientStartRequest) -> AmbientMonitorStatus:
        now = utc_now()
        duration_seconds = request.duration_seconds
        if request.mode == AmbientMonitorMode.ACTIVE_RECOVERY and duration_seconds is None:
            duration_seconds = 120

        self._status = AmbientMonitorStatus(
            state=AmbientMonitorState.RUNNING,
            mode=request.mode,
            poll_interval_seconds=request.poll_interval_seconds,
            last_sync_at=None,
            last_error=None,
            estimated_afferens_tokens_per_call=AFFERENS_VISION_TOKENS_PER_CALL,
            target_object_key=request.target_object_key,
            target_visible_now=None if request.target_object_key else None,
            zone_id=request.zone_id,
            started_at=now,
            ends_at=now + timedelta(seconds=duration_seconds) if duration_seconds else None,
            observations_synced=0,
            last_observation_id=None,
        )
        return self._status

    def stop(self) -> AmbientMonitorStatus:
        self._status = self._status.model_copy(
            update={
                "state": AmbientMonitorState.OFF,
                "mode": None,
                "target_visible_now": None,
            }
        )
        return self._status

    async def tick_if_due(
        self,
        *,
        data_spine: DataSpineService,
        adapter: AfferensAdapter,
        force: bool = False,
    ) -> AmbientMonitorStatus:
        now = utc_now()
        if self._status.state != AmbientMonitorState.RUNNING:
            return self._status

        if self._status.ends_at is not None and now >= self._status.ends_at:
            self._status = self._status.model_copy(update={"state": AmbientMonitorState.COMPLETED})
            return self._status

        if not force and self._status.last_sync_at is not None:
            elapsed = (now - self._status.last_sync_at).total_seconds()
            if elapsed < self._status.poll_interval_seconds:
                return self._status

        fetch_result = await adapter.fetch_events(limit=1)
        if not fetch_result.is_live:
            self._status = self._status.model_copy(
                update={
                    "last_sync_at": now,
                    "last_error": fetch_result.status.message,
                    "target_visible_now": self._target_visible_now(data_spine),
                }
            )
            return self._status

        sync_result = data_spine.sync_raw_events(
            fetch_result.raw_events,
            room_id=self._status.zone_id or "default_home_zone",
        )
        observations_synced = self._status.observations_synced + len(sync_result.observations)
        last_observation_id = (
            sync_result.observations[-1].id
            if sync_result.observations
            else self._status.last_observation_id
        )
        target_visible = self._target_visible_now(data_spine)
        state = self._status.state
        if (
            self._status.mode == AmbientMonitorMode.ACTIVE_RECOVERY
            and self._status.target_object_key
            and target_visible is True
        ):
            state = AmbientMonitorState.COMPLETED

        self._status = self._status.model_copy(
            update={
                "state": state,
                "last_sync_at": now,
                "last_error": None,
                "target_visible_now": target_visible,
                "observations_synced": observations_synced,
                "last_observation_id": last_observation_id,
            }
        )
        return self._status

    def status(self, data_spine: DataSpineService | None = None) -> AmbientMonitorStatus:
        if data_spine is not None and self._status.target_object_key:
            self._status = self._status.model_copy(
                update={"target_visible_now": self._target_visible_now(data_spine)}
            )
        if (
            self._status.state == AmbientMonitorState.RUNNING
            and self._status.ends_at is not None
            and utc_now() >= self._status.ends_at
        ):
            self._status = self._status.model_copy(update={"state": AmbientMonitorState.COMPLETED})
        return self._status

    def _target_visible_now(self, data_spine: DataSpineService) -> bool | None:
        target = self._status.target_object_key
        if not target:
            return None
        normalized_target = re.sub(r"[^a-z0-9]+", "_", target.strip().lower()).strip("_")
        for memory in data_spine.list_last_seen_objects():
            if memory.object_key == normalized_target:
                return memory.status == LastSeenStatus.VISIBLE_NOW
        return False
