from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from app.ids import new_id
from app.schemas import DetectedObject, HumanPresence, Observation, utc_now

NORMALIZER_VERSION = "afferens-v1"

MEDICINE_OBJECT_KEYS = {
    "medicine",
    "medicine_bottle",
    "medication",
    "medication_bottle",
    "meds",
    "pill",
    "pill_bottle",
    "pills",
}
COOKING_OBJECT_KEYS = {
    "burner",
    "cooktop",
    "electric_stove",
    "gas_stove",
    "hob",
    "oven",
    "pan",
    "pot",
    "range",
    "skillet",
    "stove",
    "stove_burner",
    "stove_top",
}


class AfferensObservationNormalizer:
    """Derives internal observations from live Afferens event payloads."""

    def normalize(
        self,
        raw_event: dict[str, Any],
        *,
        raw_event_id: str,
        room_id: str = "default_home_zone",
    ) -> Observation:
        timestamp = self._first_datetime(
            raw_event,
            "timestamp_utc",
            "timestampUtc",
            "timestamp",
            "created_at",
            "createdAt",
            "ingested_at_utc",
            "ingested_at",
        )
        provider_event_id = self._first_text(
            raw_event,
            "entity_id",
            "id",
            "event_id",
            "eventId",
        )
        modality = self._first_text(raw_event, "modality", "type", "sensor_modality")
        objects = self._extract_objects(raw_event)
        human_presence = self._human_presence(raw_event, objects)

        return Observation(
            id=new_id("obs"),
            raw_event_id=raw_event_id,
            provider_event_id=provider_event_id,
            timestamp_utc=timestamp or utc_now(),
            source="afferens",
            source_node_id=self._first_text(
                raw_event,
                "source_node_id",
                "sourceNodeId",
                "node_id",
                "nodeId",
                "device_id",
                "deviceId",
            ),
            modality=(modality or "VISION").upper(),
            classification=self._first_text(raw_event, "classification", "classifier"),
            confidence=self._first_float(raw_event, "confidence", "score"),
            room_id=room_id,
            scene_summary=self._scene_summary(objects),
            human_presence=human_presence,
            objects=objects,
            risk_signals=self._risk_signals(objects, human_presence),
            evidence_metadata={
                "normalizer_version": NORMALIZER_VERSION,
                "provider_event_id": provider_event_id,
                "raw_keys": sorted(raw_event.keys()),
                "object_labels_available": bool(objects),
                "spatial_object_count": self._spatial_object_count(raw_event),
            },
        )

    def _extract_objects(self, raw_event: dict[str, Any]) -> list[DetectedObject]:
        objects: list[DetectedObject] = []
        seen: set[tuple[str, str | None]] = set()

        for candidate in self._object_candidates(raw_event):
            detected = self._detected_object(candidate)
            if detected is None:
                continue
            dedupe_key = (detected.object_key, detected.relative_location)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            objects.append(detected)

        return objects

    def _object_candidates(self, raw_event: dict[str, Any]) -> Iterable[dict[str, Any]]:
        direct_keys = (
            "objects",
            "detected_objects",
            "detectedObjects",
            "detections",
            "items",
            "entities",
            "labels",
        )
        for key in direct_keys:
            yield from self._candidate_mappings(raw_event.get(key))

        spatial = raw_event.get("spatial_coords")
        if isinstance(spatial, dict):
            for key in direct_keys + ("classes", "classifications"):
                yield from self._candidate_mappings(spatial.get(key))

    def _detected_object(self, candidate: dict[str, Any]) -> DetectedObject | None:
        label = self._first_text(
            candidate,
            "label",
            "display_name",
            "displayName",
            "name",
            "class_name",
            "className",
            "class",
            "object",
            "category",
        )
        if label is None:
            return None

        object_key = self._object_key(label)
        if not object_key:
            return None

        spatial_coords = candidate.get("spatial_coords")
        if not isinstance(spatial_coords, dict):
            spatial_coords = candidate.get("spatialCoords")
        if not isinstance(spatial_coords, dict):
            spatial_coords = None

        return DetectedObject(
            id=new_id("obj"),
            object_key=object_key,
            label=label,
            display_name=label,
            confidence=self._first_float(candidate, "confidence", "score", "probability"),
            relative_location=self._first_text(
                candidate,
                "relative_location",
                "relativeLocation",
                "location",
                "position",
                "description",
            ),
            bbox=self._first_present(candidate, "bbox", "bounding_box", "boundingBox", "box"),
            spatial_coords=spatial_coords,
            source="afferens",
            evidence_metadata={"normalizer_version": NORMALIZER_VERSION},
        )

    @staticmethod
    def _candidate_mappings(value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item
                elif isinstance(item, str) and item.strip():
                    yield {"label": item.strip()}
        elif isinstance(value, dict):
            yield value
        elif isinstance(value, str) and value.strip():
            yield {"label": value.strip()}

    @staticmethod
    def _object_key(label: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", label.strip().lower())
        return normalized.strip("_")

    @staticmethod
    def _scene_summary(objects: list[DetectedObject]) -> str:
        if not objects:
            return "Live Afferens event did not include object labels."
        names = ", ".join(obj.display_name for obj in objects[:5])
        suffix = " are visible." if len(objects) != 1 else " is visible."
        return f"{names}{suffix}"

    @staticmethod
    def _risk_signals(
        objects: list[DetectedObject],
        human_presence: HumanPresence,
    ) -> list[str]:
        risk_signals: list[str] = []
        labels = {obj.object_key for obj in objects}
        if labels & MEDICINE_OBJECT_KEYS:
            risk_signals.append("medicine_visible_human_verification_required")
        if labels & COOKING_OBJECT_KEYS and human_presence != HumanPresence.VISIBLE:
            risk_signals.append("unattended_cooking_possible_human_verification_required")
        return risk_signals

    def _human_presence(
        self,
        raw_event: dict[str, Any],
        objects: list[DetectedObject],
    ) -> HumanPresence:
        explicit = self._first_present(raw_event, "human_presence", "humanPresence", "person_visible")
        if isinstance(explicit, bool):
            return HumanPresence.VISIBLE if explicit else HumanPresence.NOT_VISIBLE
        if isinstance(explicit, str):
            lowered = explicit.strip().lower()
            if lowered in {"visible", "present", "true", "yes"}:
                return HumanPresence.VISIBLE
            if lowered in {"not_visible", "absent", "false", "no"}:
                return HumanPresence.NOT_VISIBLE
        if any(obj.object_key in {"person", "human"} for obj in objects):
            return HumanPresence.VISIBLE
        return HumanPresence.UNKNOWN

    @staticmethod
    def _spatial_object_count(raw_event: dict[str, Any]) -> int | None:
        spatial = raw_event.get("spatial_coords")
        if not isinstance(spatial, dict):
            return None
        value = spatial.get("object_count")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return None

    @staticmethod
    def _first_text(payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _first_float(payload: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool) or value is None:
                continue
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            return max(0.0, min(parsed, 1.0))
        return None

    @staticmethod
    def _first_present(payload: dict[str, Any], *keys: str) -> Any | None:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

    @staticmethod
    def _first_datetime(payload: dict[str, Any], *keys: str) -> datetime | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, datetime):
                return value.astimezone(timezone.utc)
            if isinstance(value, str) and value.strip():
                parsed = AfferensObservationNormalizer._parse_datetime(value.strip())
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
