"""add runtime monitor state

Revision ID: 20260622_0008
Revises: 20260621_0007
Create Date: 2026-06-22
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260622_0008"
down_revision: str | None = "20260621_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_monitor_state",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("poll_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("max_tokens_per_hour", sa.Integer(), nullable=False),
        sa.Column("estimated_tokens_used_this_hour", sa.Integer(), nullable=False),
        sa.Column("estimated_tokens_per_call", sa.Integer(), nullable=False),
        sa.Column("token_hour_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tick_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_tick_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observations_synced", sa.Integer(), nullable=False),
        sa.Column("last_observation_id", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("zone_id", sa.String(length=120), nullable=True),
        sa.Column("target_object_key", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("consecutive_errors", sa.Integer(), nullable=False),
        sa.Column("backoff_seconds", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runtime_monitor_state_state", "runtime_monitor_state", ["state"])
    op.create_index("ix_runtime_monitor_state_mode", "runtime_monitor_state", ["mode"])
    op.create_index(
        "ix_runtime_monitor_state_token_hour_started_at",
        "runtime_monitor_state",
        ["token_hour_started_at"],
    )
    op.create_index("ix_runtime_monitor_state_last_tick_at", "runtime_monitor_state", ["last_tick_at"])
    op.create_index("ix_runtime_monitor_state_next_tick_at", "runtime_monitor_state", ["next_tick_at"])
    op.create_index(
        "ix_runtime_monitor_state_last_observation_id",
        "runtime_monitor_state",
        ["last_observation_id"],
    )
    op.create_index("ix_runtime_monitor_state_zone_id", "runtime_monitor_state", ["zone_id"])
    op.create_index(
        "ix_runtime_monitor_state_target_object_key",
        "runtime_monitor_state",
        ["target_object_key"],
    )
    op.create_index("ix_runtime_monitor_state_started_at", "runtime_monitor_state", ["started_at"])
    op.create_index("ix_runtime_monitor_state_ends_at", "runtime_monitor_state", ["ends_at"])
    op.create_index(
        "ix_runtime_monitor_state_last_provider_event_id",
        "runtime_monitor_state",
        ["last_provider_event_id"],
    )
    op.create_index("ix_runtime_monitor_state_updated_at", "runtime_monitor_state", ["updated_at"])


def downgrade() -> None:
    op.drop_table("runtime_monitor_state")
