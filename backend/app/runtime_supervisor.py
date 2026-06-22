from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.db import DatabaseUnavailable, create_session_factory
from app.models import RuntimeMonitorRecord
from app.repositories import InMemoryDataRepository
from app.schemas import (
    RuntimeMonitorMode,
    RuntimeMonitorResponse,
    RuntimeMonitorStartRequest,
    RuntimeMonitorState,
    RuntimeMonitorStatus,
    RuntimeMonitorTokenBudget,
    utc_now,
)
from app.services import DataSpineService


AFFERENS_VISION_TOKENS_PER_CALL = 14
RUNTIME_MONITOR_ID = "home_memory"
RUNTIME_SUPERVISOR_SOURCE = "background_supervisor"
RUNTIME_EVENT_BATCH_LIMIT = 5


class RuntimeMonitorStore(Protocol):
    def get_status(self) -> RuntimeMonitorStatus | None: ...

    def save_status(self, status: RuntimeMonitorStatus) -> RuntimeMonitorStatus: ...


class InMemoryRuntimeMonitorStore:
    def __init__(self) -> None:
        self._status: RuntimeMonitorStatus | None = None

    def get_status(self) -> RuntimeMonitorStatus | None:
        return self._status

    def save_status(self, status: RuntimeMonitorStatus) -> RuntimeMonitorStatus:
        self._status = status
        return status


class SQLAlchemyRuntimeMonitorStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_status(self) -> RuntimeMonitorStatus | None:
        with self._session_factory() as session:
            record = session.get(RuntimeMonitorRecord, RUNTIME_MONITOR_ID)
            return self._status_from_record(record) if record else None

    def save_status(self, status: RuntimeMonitorStatus) -> RuntimeMonitorStatus:
        with self._session_factory() as session:
            record = session.get(RuntimeMonitorRecord, RUNTIME_MONITOR_ID)
            if record is None:
                record = RuntimeMonitorRecord(id=RUNTIME_MONITOR_ID)
                session.add(record)
            self._apply_status(record, status)
            session.commit()
        return status

    def _apply_status(self, record: RuntimeMonitorRecord, status: RuntimeMonitorStatus) -> None:
        record.state = status.state.value
        record.mode = status.mode.value
        record.poll_interval_seconds = status.poll_interval_seconds
        record.max_tokens_per_hour = status.token_budget.max_tokens_per_hour
        record.estimated_tokens_used_this_hour = status.token_budget.estimated_tokens_used_this_hour
        record.estimated_tokens_per_call = status.token_budget.estimated_tokens_per_call
        record.token_hour_started_at = status.token_hour_started_at
        record.last_tick_at = status.last_tick_at
        record.next_tick_at = status.next_tick_at
        record.observations_synced = status.observations_synced
        record.last_observation_id = status.last_observation_id
        record.last_error = status.last_error
        record.source = status.source
        record.zone_id = status.zone_id
        record.target_object_key = status.target_object_key
        record.started_at = status.started_at
        record.ends_at = status.ends_at
        record.last_provider_event_id = status.last_provider_event_id
        record.consecutive_errors = status.consecutive_errors
        record.backoff_seconds = status.backoff_seconds
        record.updated_at = status.updated_at

    def _status_from_record(self, record: RuntimeMonitorRecord) -> RuntimeMonitorStatus:
        return RuntimeMonitorStatus(
            state=RuntimeMonitorState(record.state),
            mode=RuntimeMonitorMode(record.mode),
            poll_interval_seconds=record.poll_interval_seconds,
            token_budget=RuntimeMonitorTokenBudget(
                max_tokens_per_hour=record.max_tokens_per_hour,
                estimated_tokens_used_this_hour=record.estimated_tokens_used_this_hour,
                estimated_tokens_per_call=record.estimated_tokens_per_call,
            ),
            token_hour_started_at=record.token_hour_started_at,
            last_tick_at=record.last_tick_at,
            next_tick_at=record.next_tick_at,
            observations_synced=record.observations_synced,
            last_observation_id=record.last_observation_id,
            last_error=record.last_error,
            source=record.source,
            zone_id=record.zone_id,
            target_object_key=record.target_object_key,
            started_at=record.started_at,
            ends_at=record.ends_at,
            last_provider_event_id=record.last_provider_event_id,
            consecutive_errors=record.consecutive_errors,
            backoff_seconds=record.backoff_seconds,
            updated_at=record.updated_at,
        )


class RuntimeMonitorSupervisor:
    """Autonomous backend loop for live home-memory perception.

    The loop is intentionally bounded and token-aware. It polls live Afferens
    Vision only while monitor intent is running/degraded/paused, then syncs
    through the existing data spine.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        adapter: AfferensAdapter | None = None,
        store: RuntimeMonitorStore | None = None,
        data_spine: DataSpineService | None = None,
        idle_sleep_seconds: float = 30.0,
    ) -> None:
        self._settings = settings
        self._adapter = adapter or AfferensAdapter(settings)
        self._store = store or self._build_store(settings)
        self._data_spine = data_spine
        self._fallback_repository = InMemoryDataRepository()
        self._idle_sleep_seconds = idle_sleep_seconds
        self._wake_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None

    def start_background(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run_loop())

    async def stop_background(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._task is not None:
            await self._task

    def current_status(self) -> RuntimeMonitorStatus:
        return self._load_status()

    async def start_monitor(self, request: RuntimeMonitorStartRequest) -> RuntimeMonitorResponse:
        async with self._lock:
            now = utc_now()
            duration_seconds = request.duration_seconds
            if request.mode == RuntimeMonitorMode.ACTIVE_RECOVERY and duration_seconds is None:
                duration_seconds = 120
            status = RuntimeMonitorStatus(
                state=RuntimeMonitorState.RUNNING,
                mode=request.mode,
                poll_interval_seconds=request.poll_interval_seconds,
                token_budget=RuntimeMonitorTokenBudget(
                    max_tokens_per_hour=request.max_tokens_per_hour,
                    estimated_tokens_used_this_hour=0,
                    estimated_tokens_per_call=AFFERENS_VISION_TOKENS_PER_CALL,
                ),
                token_hour_started_at=_hour_start(now),
                last_tick_at=None,
                next_tick_at=now,
                observations_synced=0,
                last_observation_id=None,
                last_error=None,
                source=RUNTIME_SUPERVISOR_SOURCE,
                zone_id=request.zone_id,
                target_object_key=request.target_object_key,
                started_at=now,
                ends_at=now + timedelta(seconds=duration_seconds) if duration_seconds else None,
                last_provider_event_id=None,
                consecutive_errors=0,
                backoff_seconds=0,
                updated_at=now,
            )
            status = self._save_status(status)
            self._wake_event.set()
        return RuntimeMonitorResponse(
            ok=True,
            monitor=status,
            message="Home memory is running with a bounded token budget.",
        )

    async def stop_monitor(self) -> RuntimeMonitorResponse:
        async with self._lock:
            status = self._load_status()
            status = status.model_copy(
                update={
                    "state": RuntimeMonitorState.OFF,
                    "next_tick_at": None,
                    "last_error": None,
                    "updated_at": utc_now(),
                }
            )
            status = self._save_status(status)
            self._wake_event.set()
        return RuntimeMonitorResponse(ok=True, monitor=status, message="Home memory is off.")

    async def tick_once(self, *, force: bool = False) -> RuntimeMonitorStatus:
        async with self._lock:
            status = self._load_status()
            now = utc_now()
            status = self._roll_token_hour(status, now)

            if status.state == RuntimeMonitorState.OFF:
                return status
            if status.ends_at is not None and now >= status.ends_at:
                return self._save_status(
                    status.model_copy(
                        update={
                            "state": RuntimeMonitorState.COMPLETED,
                            "next_tick_at": None,
                            "updated_at": now,
                        }
                    )
                )
            if not force and status.next_tick_at is not None and now < status.next_tick_at:
                return status

            if (
                status.token_budget.estimated_tokens_used_this_hour
                + status.token_budget.estimated_tokens_per_call
                > status.token_budget.max_tokens_per_hour
            ):
                next_tick_at = (status.token_hour_started_at or _hour_start(now)) + timedelta(hours=1)
                return self._save_status(
                    status.model_copy(
                        update={
                            "state": RuntimeMonitorState.PAUSED,
                            "last_error": "Afferens Vision token budget is paused until the next hour.",
                            "next_tick_at": next_tick_at,
                            "updated_at": now,
                        }
                    )
                )

            status = status.model_copy(
                update={
                    "token_budget": status.token_budget.model_copy(
                        update={
                            "estimated_tokens_used_this_hour": (
                                status.token_budget.estimated_tokens_used_this_hour
                                + status.token_budget.estimated_tokens_per_call
                            )
                        }
                    )
                }
            )

            try:
                fetch_result = await self._adapter.fetch_events(limit=RUNTIME_EVENT_BATCH_LIMIT)
            except Exception as exc:  # pragma: no cover - defensive provider isolation
                return self._save_status(self._degraded_status(status, now, exc.__class__.__name__))

            if not fetch_result.is_live:
                return self._save_status(
                    self._degraded_status(status, now, fetch_result.status.message)
                )

            fetched_events = list(fetch_result.raw_events or ([fetch_result.raw_event] if fetch_result.raw_event else []))
            if not fetched_events:
                return self._save_status(
                    self._degraded_status(status, now, "Afferens returned no live event payload.")
                )

            next_tick_at = now + timedelta(seconds=status.poll_interval_seconds)
            newest_provider_event_id = _provider_event_id(fetched_events[0])
            events_to_sync = _new_events_since(fetched_events, status.last_provider_event_id)
            if not events_to_sync:
                return self._save_status(
                    status.model_copy(
                        update={
                            "state": RuntimeMonitorState.RUNNING,
                            "last_tick_at": now,
                            "next_tick_at": next_tick_at,
                            "last_error": None,
                            "consecutive_errors": 0,
                            "backoff_seconds": 0,
                            "updated_at": now,
                        }
                    )
                )

            try:
                sync_result = self._data_spine_service().sync_raw_events(
                    list(reversed(events_to_sync)),
                    room_id=status.zone_id or "default_home_zone",
                )
            except Exception as exc:  # pragma: no cover - defensive runtime isolation
                return self._save_status(self._degraded_status(status, now, exc.__class__.__name__))

            observations_synced = status.observations_synced + len(sync_result.observations)
            last_observation_id = (
                sync_result.observations[-1].id
                if sync_result.observations
                else status.last_observation_id
            )
            return self._save_status(
                status.model_copy(
                    update={
                        "state": RuntimeMonitorState.RUNNING,
                        "last_tick_at": now,
                        "next_tick_at": next_tick_at,
                        "observations_synced": observations_synced,
                        "last_observation_id": last_observation_id,
                        "last_error": None,
                        "last_provider_event_id": newest_provider_event_id,
                        "consecutive_errors": 0,
                        "backoff_seconds": 0,
                        "updated_at": now,
                    }
                )
            )

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                status = self._load_status()
                if status.state in {RuntimeMonitorState.RUNNING, RuntimeMonitorState.DEGRADED, RuntimeMonitorState.PAUSED}:
                    await self.tick_once()
                    status = self._load_status()
                sleep_seconds = self._sleep_seconds(status)
                await self._wait_for_wake(sleep_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._wait_for_wake(self._idle_sleep_seconds)

    async def _wait_for_wake(self, timeout_seconds: float) -> None:
        self._wake_event.clear()
        try:
            await asyncio.wait_for(self._wake_event.wait(), timeout=max(timeout_seconds, 0.1))
        except asyncio.TimeoutError:
            return

    def _sleep_seconds(self, status: RuntimeMonitorStatus) -> float:
        if status.state not in {
            RuntimeMonitorState.RUNNING,
            RuntimeMonitorState.DEGRADED,
            RuntimeMonitorState.PAUSED,
        }:
            return self._idle_sleep_seconds
        if status.next_tick_at is None:
            return self._idle_sleep_seconds
        return max((status.next_tick_at - utc_now()).total_seconds(), 0.1)

    def _load_status(self) -> RuntimeMonitorStatus:
        try:
            status = self._store.get_status()
        except Exception:
            status = None
        if status is None:
            status = RuntimeMonitorStatus(
                state=RuntimeMonitorState.OFF,
                mode=RuntimeMonitorMode.HOME_MEMORY,
                poll_interval_seconds=self._settings.ambient_default_poll_interval_seconds,
                token_budget=RuntimeMonitorTokenBudget(
                    max_tokens_per_hour=420,
                    estimated_tokens_used_this_hour=0,
                    estimated_tokens_per_call=AFFERENS_VISION_TOKENS_PER_CALL,
                ),
                source=RUNTIME_SUPERVISOR_SOURCE,
            )
            status = self._save_status(status)
        return status

    def _save_status(self, status: RuntimeMonitorStatus) -> RuntimeMonitorStatus:
        try:
            return self._store.save_status(status)
        except Exception:
            self._store = InMemoryRuntimeMonitorStore()
            return self._store.save_status(status)

    def _roll_token_hour(
        self,
        status: RuntimeMonitorStatus,
        now: datetime,
    ) -> RuntimeMonitorStatus:
        hour_start = _hour_start(now)
        if status.token_hour_started_at == hour_start:
            return status
        return status.model_copy(
            update={
                "state": (
                    RuntimeMonitorState.RUNNING
                    if status.state == RuntimeMonitorState.PAUSED
                    else status.state
                ),
                "token_hour_started_at": hour_start,
                "token_budget": status.token_budget.model_copy(
                    update={"estimated_tokens_used_this_hour": 0}
                ),
            }
        )

    def _degraded_status(
        self,
        status: RuntimeMonitorStatus,
        now: datetime,
        message: str,
    ) -> RuntimeMonitorStatus:
        consecutive_errors = status.consecutive_errors + 1
        backoff_seconds = min(
            max(status.poll_interval_seconds, 15) * (2 ** min(consecutive_errors - 1, 4)),
            300,
        )
        return status.model_copy(
            update={
                "state": RuntimeMonitorState.DEGRADED,
                "last_tick_at": now,
                "next_tick_at": now + timedelta(seconds=backoff_seconds),
                "last_error": message,
                "consecutive_errors": consecutive_errors,
                "backoff_seconds": backoff_seconds,
                "updated_at": now,
            }
        )

    def _data_spine_service(self) -> DataSpineService:
        if self._data_spine is not None:
            return self._data_spine
        try:
            from app.sql_repository import SQLAlchemyDataRepository

            session_factory = create_session_factory(self._settings)
            return DataSpineService(
                SQLAlchemyDataRepository(session_factory),
                recent_window_seconds=self._settings.object_recent_window_seconds,
            )
        except DatabaseUnavailable:
            return DataSpineService(
                self._fallback_repository,
                recent_window_seconds=self._settings.object_recent_window_seconds,
            )

    def _build_store(self, settings: Settings) -> RuntimeMonitorStore:
        try:
            session_factory = create_session_factory(settings)
            store = SQLAlchemyRuntimeMonitorStore(session_factory)
            store.get_status()
            return store
        except (DatabaseUnavailable, SQLAlchemyError):
            return InMemoryRuntimeMonitorStore()


def _hour_start(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.replace(minute=0, second=0, microsecond=0)


def _provider_event_id(raw_event: dict[str, Any]) -> str:
    for key in ("entity_id", "id", "event_id", "eventId"):
        value = raw_event.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    payload = json.dumps(raw_event, sort_keys=True, default=str)
    return f"event_hash_{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:24]}"


def _new_events_since(
    raw_events: list[dict[str, Any]],
    last_provider_event_id: str | None,
) -> list[dict[str, Any]]:
    if last_provider_event_id is None:
        return raw_events

    new_events: list[dict[str, Any]] = []
    for raw_event in raw_events:
        if _provider_event_id(raw_event) == last_provider_event_id:
            break
        new_events.append(raw_event)
    return new_events
