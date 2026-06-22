"""add hydration and wellness check records

Revision ID: 20260621_0005
Revises: 20260621_0004
Create Date: 2026-06-21
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260621_0005"
down_revision: str | None = "20260621_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON()


def upgrade() -> None:
    op.create_table(
        "hydration_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=120), nullable=True),
        sa.Column("zone_name", sa.String(length=120), nullable=True),
        sa.Column("evidence_ids", json_type, nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
    )
    op.create_index("ix_hydration_events_type", "hydration_events", ["type"])
    op.create_index("ix_hydration_events_occurred_at", "hydration_events", ["occurred_at"])
    op.create_index("ix_hydration_events_confidence", "hydration_events", ["confidence"])
    op.create_index("ix_hydration_events_zone_id", "hydration_events", ["zone_id"])

    op.create_table(
        "wellness_checks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("zone_id", sa.String(length=120), nullable=True),
        sa.Column("zone_name", sa.String(length=120), nullable=True),
        sa.Column("evidence_ids", json_type, nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
    )
    op.create_index("ix_wellness_checks_type", "wellness_checks", ["type"])
    op.create_index("ix_wellness_checks_severity", "wellness_checks", ["severity"])
    op.create_index("ix_wellness_checks_status", "wellness_checks", ["status"])
    op.create_index("ix_wellness_checks_confidence", "wellness_checks", ["confidence"])
    op.create_index("ix_wellness_checks_occurred_at", "wellness_checks", ["occurred_at"])
    op.create_index("ix_wellness_checks_created_at", "wellness_checks", ["created_at"])
    op.create_index(
        "ix_wellness_checks_acknowledged_at",
        "wellness_checks",
        ["acknowledged_at"],
    )
    op.create_index("ix_wellness_checks_zone_id", "wellness_checks", ["zone_id"])


def downgrade() -> None:
    op.drop_table("wellness_checks")
    op.drop_table("hydration_events")
