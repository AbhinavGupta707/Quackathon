from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import get_data_spine_service
from app.services import DataSpineService


def test_home_zones_returns_default_and_can_create_new_default() -> None:
    app = create_app()
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    app.dependency_overrides[get_data_spine_service] = lambda: service
    client = TestClient(app)

    default_response = client.get("/api/home-zones")
    default_payload = default_response.json()

    assert default_response.status_code == 200
    assert default_payload["zones"][0]["id"] == "default_home_zone"
    assert default_payload["zones"][0]["is_default"] is True

    create_response = client.post(
        "/api/home-zones",
        json={
            "name": "Study desk",
            "room_type": "study",
            "aliases": ["desk", "computer table", "desk"],
            "is_default": True,
            "source_node_id": "LAPTOP-CAM-1",
            "region_strategy": "quadrants",
        },
    )
    created = create_response.json()["zone"]

    assert create_response.status_code == 200
    assert create_response.json()["ok"] is True
    assert created["id"].startswith("zone_")
    assert created["aliases"] == ["desk", "computer table"]
    assert created["is_default"] is True
    assert created["source_node_id"] == "LAPTOP-CAM-1"
    assert created["region_strategy"] == "quadrants"
    assert [region["id"] for region in created["regions"]] == [
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
    ]

    zones = client.get("/api/home-zones").json()["zones"]
    assert [zone for zone in zones if zone["is_default"]][0]["id"] == created["id"]
    assert any(zone["id"] == "default_home_zone" and not zone["is_default"] for zone in zones)


def test_home_zones_accepts_custom_grid_regions_and_updates_by_id() -> None:
    app = create_app()
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    app.dependency_overrides[get_data_spine_service] = lambda: service
    client = TestClient(app)

    create_response = client.post(
        "/api/home-zones",
        json={
            "id": "living_room_camera",
            "name": "Living room",
            "room_type": "living_room",
            "source_node_id": "USB-CAM-2",
            "region_strategy": "grid",
            "regions": [
                {
                    "id": "sofa_area",
                    "label": "sofa area",
                    "kind": "grid_cell",
                    "bounds": {"x_min": 0.0, "y_min": 0.0, "x_max": 0.5, "y_max": 1.0},
                }
            ],
            "metadata": {"calibration_note": "caregiver selected room"},
        },
    )
    update_response = client.post(
        "/api/home-zones",
        json={
            "id": "living_room_camera",
            "name": "Living room camera",
            "room_type": "living_room",
            "region_strategy": "grid",
            "regions": [
                {
                    "id": "sofa_area",
                    "label": "sofa area",
                    "kind": "grid_cell",
                    "bounds": {"x_min": 0.0, "y_min": 0.0, "x_max": 0.5, "y_max": 1.0},
                }
            ],
        },
    )

    assert create_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["zone"]["id"] == "living_room_camera"
    assert update_response.json()["zone"]["name"] == "Living room camera"
    zones = client.get("/api/home-zones").json()["zones"]
    assert len([zone for zone in zones if zone["id"] == "living_room_camera"]) == 1
