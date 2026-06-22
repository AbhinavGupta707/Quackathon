"""add home zone calibration

Revision ID: 20260621_0003
Revises: 20260621_0002
Create Date: 2026-06-21
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260621_0003"
down_revision: str | None = "20260621_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON()


def upgrade() -> None:
    op.create_table(
        "home_zones",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("room_type", sa.String(length=64), nullable=False),
        sa.Column("aliases", json_type, nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_home_zones_room_type", "home_zones", ["room_type"])
    op.create_index("ix_home_zones_is_default", "home_zones", ["is_default"])
    op.create_index("ix_home_zones_created_at", "home_zones", ["created_at"])

    home_zones = sa.table(
        "home_zones",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("room_type", sa.String),
        sa.column("aliases", json_type),
        sa.column("is_default", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        home_zones,
        [
            {
                "id": "default_home_zone",
                "name": "Home area",
                "room_type": "other",
                "aliases": ["home", "main room"],
                "is_default": True,
                "created_at": datetime(2026, 6, 21, tzinfo=timezone.utc),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("home_zones")
