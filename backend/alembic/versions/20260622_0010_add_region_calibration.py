"""add region calibration metadata

Revision ID: 20260622_0010
Revises: 20260622_0009
Create Date: 2026-06-22
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260622_0010"
down_revision: str | None = "20260622_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON()


def upgrade() -> None:
    op.add_column("home_zones", sa.Column("source_node_id", sa.String(length=255), nullable=True))
    op.add_column(
        "home_zones",
        sa.Column("region_strategy", sa.String(length=64), nullable=False, server_default="none"),
    )
    op.add_column("home_zones", sa.Column("regions", json_type, nullable=False, server_default="[]"))
    op.add_column(
        "home_zones",
        sa.Column("metadata_json", json_type, nullable=False, server_default="{}"),
    )
    op.create_index("ix_home_zones_source_node_id", "home_zones", ["source_node_id"])
    op.create_index("ix_home_zones_region_strategy", "home_zones", ["region_strategy"])

    op.add_column("last_seen_objects", sa.Column("last_seen_room_id", sa.String(length=255), nullable=True))
    op.add_column("last_seen_objects", sa.Column("last_seen_region_id", sa.String(length=255), nullable=True))
    op.add_column(
        "last_seen_objects",
        sa.Column("last_seen_region_label", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "last_seen_objects",
        sa.Column("last_seen_normalized_coords", json_type, nullable=True),
    )
    op.add_column(
        "last_seen_objects",
        sa.Column(
            "location_assignment_source",
            sa.String(length=64),
            nullable=False,
            server_default="observation_room",
        ),
    )
    op.execute("UPDATE last_seen_objects SET last_seen_room_id = last_seen_room WHERE last_seen_room_id IS NULL")
    op.create_index("ix_last_seen_objects_last_seen_room_id", "last_seen_objects", ["last_seen_room_id"])
    op.create_index("ix_last_seen_objects_last_seen_region_id", "last_seen_objects", ["last_seen_region_id"])
    op.create_index(
        "ix_last_seen_objects_last_seen_region_label",
        "last_seen_objects",
        ["last_seen_region_label"],
    )
    op.create_index(
        "ix_last_seen_objects_location_assignment_source",
        "last_seen_objects",
        ["location_assignment_source"],
    )
    op.alter_column("home_zones", "region_strategy", server_default=None)
    op.alter_column("home_zones", "regions", server_default=None)
    op.alter_column("home_zones", "metadata_json", server_default=None)
    op.alter_column("last_seen_objects", "location_assignment_source", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_last_seen_objects_location_assignment_source", table_name="last_seen_objects")
    op.drop_index("ix_last_seen_objects_last_seen_region_label", table_name="last_seen_objects")
    op.drop_index("ix_last_seen_objects_last_seen_region_id", table_name="last_seen_objects")
    op.drop_index("ix_last_seen_objects_last_seen_room_id", table_name="last_seen_objects")
    op.drop_column("last_seen_objects", "location_assignment_source")
    op.drop_column("last_seen_objects", "last_seen_normalized_coords")
    op.drop_column("last_seen_objects", "last_seen_region_label")
    op.drop_column("last_seen_objects", "last_seen_region_id")
    op.drop_column("last_seen_objects", "last_seen_room_id")

    op.drop_index("ix_home_zones_region_strategy", table_name="home_zones")
    op.drop_index("ix_home_zones_source_node_id", table_name="home_zones")
    op.drop_column("home_zones", "metadata_json")
    op.drop_column("home_zones", "regions")
    op.drop_column("home_zones", "region_strategy")
    op.drop_column("home_zones", "source_node_id")
