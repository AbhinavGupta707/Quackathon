"""add semantic memory records

Revision ID: 20260621_0006
Revises: 20260621_0005
Create Date: 2026-06-21
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models import Vector


revision: str = "20260621_0006"
down_revision: str | None = "20260621_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON()


def upgrade() -> None:
    op.create_table(
        "semantic_memory",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_ids", json_type, nullable=False),
        sa.Column("source_ids", json_type, nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_type", "source_id", name="uq_semantic_memory_source"),
    )
    op.create_index("ix_semantic_memory_source_type", "semantic_memory", ["source_type"])
    op.create_index("ix_semantic_memory_source_id", "semantic_memory", ["source_id"])
    op.create_index("ix_semantic_memory_occurred_at", "semantic_memory", ["occurred_at"])
    op.create_index("ix_semantic_memory_created_at", "semantic_memory", ["created_at"])
    op.create_index("ix_semantic_memory_updated_at", "semantic_memory", ["updated_at"])
    op.create_index(
        "ix_semantic_memory_source_type_occurred_at",
        "semantic_memory",
        ["source_type", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("semantic_memory")
