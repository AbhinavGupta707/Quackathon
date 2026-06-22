"""add action events

Revision ID: 20260621_0007
Revises: 20260621_0006
Create Date: 2026-06-21
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260621_0007"
down_revision: str | None = "20260621_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON()


def upgrade() -> None:
    op.create_table(
        "action_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_node_id", sa.String(length=255), nullable=True),
        sa.Column("zone_id", sa.String(length=120), nullable=True),
        sa.Column("zone_name", sa.String(length=120), nullable=True),
        sa.Column("evidence_ids", json_type, nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_action_events_type", "action_events", ["type"])
    op.create_index("ix_action_events_occurred_at", "action_events", ["occurred_at"])
    op.create_index("ix_action_events_confidence", "action_events", ["confidence"])
    op.create_index("ix_action_events_source", "action_events", ["source"])
    op.create_index("ix_action_events_source_node_id", "action_events", ["source_node_id"])
    op.create_index("ix_action_events_zone_id", "action_events", ["zone_id"])
    op.create_index("ix_action_events_created_at", "action_events", ["created_at"])
    op.create_index(
        "ix_action_events_type_occurred_at",
        "action_events",
        ["type", "occurred_at"],
    )
    op.create_index(
        "ix_action_events_source_node_occurred_at",
        "action_events",
        ["source_node_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("action_events")
