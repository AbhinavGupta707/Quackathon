"""add daily care and family message records

Revision ID: 20260621_0004
Revises: 20260621_0003
Create Date: 2026-06-21
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260621_0004"
down_revision: str | None = "20260621_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON()


def upgrade() -> None:
    op.create_table(
        "daily_diary_entries",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("highlights", json_type, nullable=False),
        sa.Column("needs_review", json_type, nullable=False),
        sa.Column("evidence_ids", json_type, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("entry_date", "source", name="uq_daily_diary_entries_date_source"),
    )
    op.create_index("ix_daily_diary_entries_entry_date", "daily_diary_entries", ["entry_date"])
    op.create_index("ix_daily_diary_entries_generated_at", "daily_diary_entries", ["generated_at"])
    op.create_index("ix_daily_diary_entries_source", "daily_diary_entries", ["source"])

    op.create_table(
        "care_notes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("note_date", sa.Date(), nullable=False),
        sa.Column("audience", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("bullets", json_type, nullable=False),
        sa.Column("risks", json_type, nullable=False),
        sa.Column("follow_ups", json_type, nullable=False),
        sa.Column("evidence_ids", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
    )
    op.create_index("ix_care_notes_note_date", "care_notes", ["note_date"])
    op.create_index("ix_care_notes_audience", "care_notes", ["audience"])
    op.create_index("ix_care_notes_created_at", "care_notes", ["created_at"])
    op.create_index("ix_care_notes_source", "care_notes", ["source"])

    op.create_table(
        "family_messages",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("trigger_object_key", sa.String(length=255), nullable=True),
        sa.Column("trigger_zone_id", sa.String(length=120), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", json_type, nullable=False),
    )
    op.create_index("ix_family_messages_priority", "family_messages", ["priority"])
    op.create_index("ix_family_messages_status", "family_messages", ["status"])
    op.create_index("ix_family_messages_trigger_object_key", "family_messages", ["trigger_object_key"])
    op.create_index("ix_family_messages_trigger_zone_id", "family_messages", ["trigger_zone_id"])
    op.create_index("ix_family_messages_starts_at", "family_messages", ["starts_at"])
    op.create_index("ix_family_messages_expires_at", "family_messages", ["expires_at"])
    op.create_index("ix_family_messages_created_at", "family_messages", ["created_at"])
    op.create_index("ix_family_messages_acknowledged_at", "family_messages", ["acknowledged_at"])


def downgrade() -> None:
    op.drop_table("family_messages")
    op.drop_table("care_notes")
    op.drop_table("daily_diary_entries")
