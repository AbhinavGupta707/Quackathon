"""add multimodal enrichment provenance

Revision ID: 20260621_0002
Revises: 20260621_0001
Create Date: 2026-06-21
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260621_0002"
down_revision: str | None = "20260621_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON()


def upgrade() -> None:
    op.create_table(
        "model_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("observation_id", sa.String(length=64), sa.ForeignKey("observations.id"), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("focus", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_model_runs_observation_id", "model_runs", ["observation_id"])
    op.create_index("ix_model_runs_provider", "model_runs", ["provider"])
    op.create_index("ix_model_runs_purpose", "model_runs", ["purpose"])
    op.create_index("ix_model_runs_focus", "model_runs", ["focus"])
    op.create_index("ix_model_runs_state", "model_runs", ["state"])
    op.create_index("ix_model_runs_started_at", "model_runs", ["started_at"])
    op.create_index("ix_model_runs_completed_at", "model_runs", ["completed_at"])

    op.create_table(
        "observation_enrichments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("observation_id", sa.String(length=64), sa.ForeignKey("observations.id"), nullable=False),
        sa.Column("model_run_id", sa.String(length=64), sa.ForeignKey("model_runs.id"), nullable=True),
        sa.Column("source_provider", sa.String(length=128), nullable=False),
        sa.Column("source_model", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("label_suggestions", json_type, nullable=False),
        sa.Column("safety_notes", json_type, nullable=False),
        sa.Column("spatial_notes", json_type, nullable=False),
        sa.Column("evidence_observation_ids", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_observation_enrichments_observation_id", "observation_enrichments", ["observation_id"])
    op.create_index("ix_observation_enrichments_model_run_id", "observation_enrichments", ["model_run_id"])
    op.create_index("ix_observation_enrichments_source_provider", "observation_enrichments", ["source_provider"])
    op.create_index("ix_observation_enrichments_created_at", "observation_enrichments", ["created_at"])


def downgrade() -> None:
    op.drop_table("observation_enrichments")
    op.drop_table("model_runs")
