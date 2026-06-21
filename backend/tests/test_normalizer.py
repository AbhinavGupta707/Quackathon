from __future__ import annotations

from app.normalizer import AfferensObservationNormalizer
from app.schemas import HumanPresence


def test_normalizer_extracts_official_nested_objects() -> None:
    raw_event = {
        "entity_id": "LIVE-VIS-123",
        "timestamp_utc": "2026-06-21T16:00:00Z",
        "modality": "vision",
        "classification": "iphone_camera_coco",
        "confidence": 0.94,
        "source_node_id": "LAPTOP-WEBCAM-01",
        "spatial_coords": {
            "objects": [
                {
                    "label": "Keys",
                    "confidence": 0.82,
                    "relative_location": "left side of the table",
                    "bbox": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
                },
                {"label": "person", "confidence": 0.9},
            ]
        },
    }

    observation = AfferensObservationNormalizer().normalize(
        raw_event,
        raw_event_id="aff_123",
    )

    assert observation.raw_event_id == "aff_123"
    assert observation.provider_event_id == "LIVE-VIS-123"
    assert observation.modality == "VISION"
    assert observation.classification == "iphone_camera_coco"
    assert observation.human_presence == HumanPresence.VISIBLE
    assert [item.object_key for item in observation.objects] == ["keys", "person"]
    assert observation.objects[0].relative_location == "left side of the table"


def test_normalizer_does_not_invent_objects_when_labels_are_absent() -> None:
    raw_event = {
        "entity_id": "LIVE-VIS-NO-LABELS",
        "timestamp_utc": "2026-06-21T16:00:00Z",
        "type": "VISION",
        "source_node_id": "USB-CAM-01",
        "spatial_coords": {"object_count": 2},
    }

    observation = AfferensObservationNormalizer().normalize(
        raw_event,
        raw_event_id="aff_456",
    )

    assert observation.objects == []
    assert observation.human_presence == HumanPresence.UNKNOWN
    assert observation.scene_summary == "Live Afferens event did not include object labels."
    assert observation.evidence_metadata["object_labels_available"] is False
    assert observation.evidence_metadata["spatial_object_count"] == 2
