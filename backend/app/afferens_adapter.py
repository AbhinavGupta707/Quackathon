from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings
from app.schemas import (
    ActuationState,
    AfferensActuationResult,
    AfferensConnectionState,
    AfferensFetchResult,
    AfferensModality,
    AfferensStatus,
    ModalityReadinessState,
    ModalityStatus,
)

DOCUMENTED_AFFERENS_MODALITIES: tuple[AfferensModality, ...] = (
    AfferensModality.VISION,
    AfferensModality.SPATIAL,
    AfferensModality.ACOUSTIC,
    AfferensModality.ENVIRONMENTAL,
    AfferensModality.MOLECULAR,
    AfferensModality.INTEROCEPTION,
)


class AfferensAdapter:
    """Live-only adapter for Afferens perception.

    Product code must call the live Afferens perception endpoint. Tests can
    inject an HTTPX transport, but runtime code does not provide replay or fixture
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

    async def fetch_events(
        self,
        *,
        limit: int = 1,
        modality: AfferensModality | str = AfferensModality.VISION,
    ) -> AfferensFetchResult:
        normalized_modality = self._normalize_modality(modality)
        key = self._settings.afferens_key_value()
        if key is None:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.MISSING_KEY,
                    message="Afferens API key is not configured.",
                    modality=normalized_modality.value,
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
                    params={
                        "modality": normalized_modality.value.lower(),
                        "limit": min(max(limit, 1), 10),
                    },
                )
        except httpx.HTTPError as exc:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.ERROR,
                    message=f"Afferens perception request failed: {exc.__class__.__name__}.",
                    modality=normalized_modality.value,
                )
            )

        if response.status_code == 401:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.INVALID_KEY,
                    message="Afferens API key was rejected.",
                    modality=normalized_modality.value,
                )
            )
        if response.status_code == 403:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.INACTIVE_KEY,
                    message="Afferens API key is not active.",
                    modality=normalized_modality.value,
                )
            )
        if response.status_code == 404:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.NO_LIVE_EVENTS,
                    message=f"No live Afferens {self._display_modality(normalized_modality)} events are available.",
                    modality=normalized_modality.value,
                )
            )
        if response.is_error:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.ERROR,
                    message=f"Afferens perception returned HTTP {response.status_code}.",
                    modality=normalized_modality.value,
                )
            )

        try:
            payload = response.json()
        except ValueError:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.ERROR,
                    message="Afferens perception returned non-JSON data.",
                    modality=normalized_modality.value,
                )
            )

        events = self._extract_events(payload)
        if not events:
            return AfferensFetchResult(
                status=self._status(
                    state=AfferensConnectionState.NO_LIVE_EVENTS,
                    message=f"No live Afferens {self._display_modality(normalized_modality)} events are available.",
                    modality=normalized_modality.value,
                ),
                raw_payload=payload,
            )

        return AfferensFetchResult(
            status=self._status_from_event(events[0], requested_modality=normalized_modality),
            raw_event=events[0],
            raw_events=events,
            raw_payload=payload,
        )

    async def probe_modalities(self) -> list[ModalityStatus]:
        checked_at = datetime.now(timezone.utc)
        if not self._settings.afferens_configured:
            return [
                ModalityStatus(
                    modality=modality,
                    state=ModalityReadinessState.UNAVAILABLE,
                    message="Afferens API key is not configured.",
                    checked_at=checked_at,
                )
                for modality in DOCUMENTED_AFFERENS_MODALITIES
            ]

        statuses: list[ModalityStatus] = []
        for modality in DOCUMENTED_AFFERENS_MODALITIES:
            result = await self.fetch_events(limit=1, modality=modality)
            statuses.append(self._modality_status_from_fetch_result(result, modality, checked_at))
        return statuses

    async def actuate(
        self,
        *,
        command_type: str,
        target_node_id: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> AfferensActuationResult:
        key = self._settings.afferens_key_value()
        if key is None:
            return AfferensActuationResult(
                state=ActuationState.SKIPPED,
                message="Afferens actuation is unavailable because the API key is not configured.",
            )

        payload: dict[str, Any] = {"command_type": command_type}
        if target_node_id:
            payload["target_node_id"] = target_node_id
        if parameters:
            payload["parameters"] = parameters

        try:
            async with httpx.AsyncClient(
                base_url=str(self._settings.afferens_base_url).rstrip("/"),
                timeout=self._settings.afferens_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    "/api/actuation",
                    headers={"X-API-KEY": key},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            return AfferensActuationResult(
                state=ActuationState.FAILED,
                message=f"Afferens actuation request failed: {exc.__class__.__name__}.",
            )

        response_payload = self._safe_response_payload(response)
        if response.status_code == 401:
            return AfferensActuationResult(
                state=ActuationState.FAILED,
                message="Afferens actuation rejected the API key.",
                response_payload=response_payload,
            )
        if response.status_code == 403:
            return AfferensActuationResult(
                state=ActuationState.FAILED,
                message="Afferens actuation is not active for this key.",
                response_payload=response_payload,
            )
        if response.status_code == 404:
            return AfferensActuationResult(
                state=ActuationState.SKIPPED,
                message="Afferens actuation is unavailable for the requested node or command.",
                response_payload=response_payload,
            )
        if response.is_error:
            return AfferensActuationResult(
                state=ActuationState.FAILED,
                message=f"Afferens actuation returned HTTP {response.status_code}.",
                response_payload=response_payload,
            )

        return AfferensActuationResult(
            state=ActuationState.SUCCEEDED,
            message="Afferens actuation command accepted.",
            response_payload=response_payload,
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

    def _status_from_event(
        self,
        event: dict[str, Any],
        *,
        requested_modality: AfferensModality = AfferensModality.VISION,
    ) -> AfferensStatus:
        modality = self._first_text(event, "modality", "type", "sensor_modality")
        resolved_modality = modality.upper() if modality else requested_modality.value
        return self._status(
            state=AfferensConnectionState.LIVE,
            message=f"Live Afferens {self._display_modality(resolved_modality)} event available.",
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
            modality=resolved_modality,
        )

    def _modality_status_from_fetch_result(
        self,
        result: AfferensFetchResult,
        modality: AfferensModality,
        checked_at: datetime,
    ) -> ModalityStatus:
        status = result.status
        if status.state == AfferensConnectionState.LIVE:
            return ModalityStatus(
                modality=modality,
                state=ModalityReadinessState.AVAILABLE,
                message=f"Live Afferens {self._display_modality(modality)} events are available.",
                latest_event_id=status.latest_event_id,
                latest_timestamp_utc=status.latest_timestamp_utc,
                source_node_id=status.source_node_id,
                checked_at=checked_at,
            )
        if status.state == AfferensConnectionState.NO_LIVE_EVENTS:
            return ModalityStatus(
                modality=modality,
                state=ModalityReadinessState.NO_LIVE_EVENTS,
                message=f"No live Afferens {self._display_modality(modality)} events are available for this account/node.",
                checked_at=checked_at,
            )
        if status.state == AfferensConnectionState.ERROR:
            return ModalityStatus(
                modality=modality,
                state=ModalityReadinessState.ERROR,
                message=status.message,
                checked_at=checked_at,
            )
        return ModalityStatus(
            modality=modality,
            state=ModalityReadinessState.UNAVAILABLE,
            message=status.message,
            checked_at=checked_at,
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
    def _safe_response_payload(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            return {"status_code": response.status_code}
        if isinstance(payload, dict):
            sanitized = AfferensAdapter._redact_sensitive_values(payload)
            if isinstance(sanitized, dict):
                sanitized.setdefault("status_code", response.status_code)
                return sanitized
        return {"status_code": response.status_code, "body": str(payload)[:500]}

    @staticmethod
    def _redact_sensitive_values(value: Any) -> Any:
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered == "key" or any(
                    marker in lowered
                    for marker in ("api_key", "apikey", "x-api-key", "authorization", "secret", "token")
                ):
                    redacted[key] = "[redacted]"
                else:
                    redacted[key] = AfferensAdapter._redact_sensitive_values(item)
            return redacted
        if isinstance(value, list):
            return [AfferensAdapter._redact_sensitive_values(item) for item in value]
        return value

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

    @staticmethod
    def _normalize_modality(modality: AfferensModality | str) -> AfferensModality:
        if isinstance(modality, AfferensModality):
            return modality
        normalized = str(modality).strip().upper()
        try:
            return AfferensModality(normalized)
        except ValueError:
            return AfferensModality.VISION

    @staticmethod
    def _display_modality(modality: AfferensModality | str) -> str:
        value = modality.value if isinstance(modality, AfferensModality) else str(modality)
        return value.strip().replace("_", " ").title()
