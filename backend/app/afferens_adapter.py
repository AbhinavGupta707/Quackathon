from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings
from app.schemas import AfferensConnectionState, AfferensFetchResult, AfferensStatus


class AfferensAdapter:
    """Live-only adapter for Afferens perception.

    Product code must call the live Afferens perception endpoint. Tests can
    inject an HTTPX transport, but runtime code does not provide replay/demo
    fixture paths.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def fetch_latest(self) -> AfferensFetchResult:
        return await self.fetch_events(limit=1)

    async def fetch_events(self, *, limit: int = 1) -> AfferensFetchResult:
        key = self._settings.afferens_key_value()
        if key is None:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.MISSING_KEY,
                    message="Afferens API key is not configured.",
                )
            )

        try:
            async with httpx.AsyncClient(
                base_url=str(self._settings.afferens_base_url).rstrip("/"),
                timeout=self._settings.afferens_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    "/api/perception",
                    headers={"X-API-KEY": key},
                    params={"modality": "vision", "limit": min(max(limit, 1), 10)},
                )
        except httpx.HTTPError as exc:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.ERROR,
                    message=f"Afferens perception request failed: {exc.__class__.__name__}.",
                )
            )

        if response.status_code == 401:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.INVALID_KEY,
                    message="Afferens API key was rejected.",
                )
            )
        if response.status_code == 403:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.INACTIVE_KEY,
                    message="Afferens API key is not active.",
                )
            )
        if response.status_code == 404:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.NO_LIVE_EVENTS,
                    message="No live Afferens Vision events are available.",
                )
            )
        if response.is_error:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.ERROR,
                    message=f"Afferens perception returned HTTP {response.status_code}.",
                )
            )

        try:
            payload = response.json()
        except ValueError:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.ERROR,
                    message="Afferens perception returned non-JSON data.",
                )
            )

        events = self._extract_events(payload)
        if not events:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.NO_LIVE_EVENTS,
                    message="No live Afferens Vision events are available.",
                ),
                raw_payload=payload,
            )

        return AfferensFetchResult(
            status=self._status_from_event(events[0]),
            raw_event=events[0],
            raw_events=events,
            raw_payload=payload,
        )

    def _status(
        self,
        *,
        state: AfferensConnectionState,
        message: str,
        latest_event_id: str | None = None,
        latest_timestamp_utc: datetime | None = None,
        source_node_id: str | None = None,
        modality: str | None = None,
    ) -> AfferensStatus:
        return AfferensStatus(
            configured=self._settings.afferens_configured,
            base_url=str(self._settings.afferens_base_url).rstrip("/"),
            state=state,
            message=message,
            latest_event_id=latest_event_id,
            latest_timestamp_utc=latest_timestamp_utc,
            source_node_id=source_node_id,
            modality=modality,
        )

    def _status_from_event(self, event: dict[str, Any]) -> AfferensStatus:
        modality = self._first_text(event, "modality", "type", "sensor_modality")
        return self._status(
            state=AfferensConnectionState.LIVE,
            message="Live Afferens Vision event available.",
            latest_event_id=self._first_text(event, "entity_id", "id", "event_id", "eventId"),
            latest_timestamp_utc=self._first_datetime(
                event,
                "timestamp_utc",
                "timestamp",
                "timestampUtc",
                "created_at",
                "createdAt",
            ),
            source_node_id=self._first_text(
                event,
                "source_node_id",
                "sourceNodeId",
                "node_id",
                "nodeId",
                "device_id",
                "deviceId",
            ),
            modality=modality.upper() if modality else "VISION",
        )

    def _extract_latest_event(self, payload: Any) -> dict[str, Any] | None:
        events = self._extract_events(payload)
        return events[0] if events else None

    def _extract_events(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return self._mappings(payload)

        if not isinstance(payload, dict):
            return []

        for key in ("event", "latest_event", "latestEvent", "raw_event", "rawEvent"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return [candidate]

        for key in ("events", "data", "items", "results", "perception"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return self._mappings(candidate)
            if isinstance(candidate, dict):
                return [candidate]

        if self._looks_like_event(payload):
            return [payload]

        return []

    @staticmethod
    def _first_mapping(items: list[Any]) -> dict[str, Any] | None:
        for item in items:
            if isinstance(item, dict):
                return item
        return None

    @staticmethod
    def _mappings(items: list[Any]) -> list[dict[str, Any]]:
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def _looks_like_event(payload: dict[str, Any]) -> bool:
        event_keys = {
            "id",
            "event_id",
            "eventId",
            "timestamp",
            "timestamp_utc",
            "timestampUtc",
            "modality",
            "source_node_id",
            "sourceNodeId",
        }
        return any(key in payload for key in event_keys)

    @staticmethod
    def _first_text(payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _first_datetime(payload: dict[str, Any], *keys: str) -> datetime | None:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            if isinstance(value, datetime):
                return value.astimezone(timezone.utc)
            if isinstance(value, str) and value.strip():
                parsed = AfferensAdapter._parse_datetime(value.strip())
                if parsed is not None:
                    return parsed
        return None

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
