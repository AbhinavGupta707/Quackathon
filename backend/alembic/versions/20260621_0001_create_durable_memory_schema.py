"""create durable memory schema

Revision ID: 20260621_0001
Revises:
Create Date: 2026-06-21
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models import Vector


revision: str = "20260621_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON()


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "afferens_raw_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_node_id", sa.String(length=255), nullable=True),
        sa.Column("modality", sa.String(length=64), nullable=True),
        sa.Column("classification", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("raw_payload", json_type, nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "provider_event_id",
            name="uq_afferens_raw_events_provider_event_id",
        ),
    )
    op.create_index("ix_afferens_raw_events_provider_event_id", "afferens_raw_events", ["provider_event_id"])
    op.create_index("ix_afferens_raw_events_timestamp_utc", "afferens_raw_events", ["timestamp_utc"])
    op.create_index("ix_afferens_raw_events_source_node_id", "afferens_raw_events", ["source_node_id"])
    op.create_index("ix_afferens_raw_events_modality", "afferens_raw_events", ["modality"])
    op.create_index("ix_afferens_raw_events_ingested_at", "afferens_raw_events", ["ingested_at"])

    op.create_table(
        "observations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("raw_event_id", sa.String(length=64), sa.ForeignKey("afferens_raw_events.id"), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_node_id", sa.String(length=255), nullable=True),
        sa.Column("modality", sa.String(length=64), nullable=False),
        sa.Column("classification", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("room_id", sa.String(length=255), nullable=False),
        sa.Column("scene_summary", sa.Text(), nullable=False),
        sa.Column("human_presence", sa.String(length=64), nullable=False),
        sa.Column("risk_signals", json_type, nullable=False),
        sa.Column("evidence_metadata", json_type, nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_observations_raw_event_id", "observations", ["raw_event_id"])
    op.create_index("ix_observations_provider_event_id", "observations", ["provider_event_id"])
    op.create_index("ix_observations_timestamp_utc", "observations", ["timestamp_utc"])
    op.create_index("ix_observations_source", "observations", ["source"])
    op.create_index("ix_observations_source_node_id", "observations", ["source_node_id"])
    op.create_index("ix_observations_modality", "observations", ["modality"])
    op.create_index("ix_observations_room_id", "observations", ["room_id"])
    op.create_index("ix_observations_human_presence", "observations", ["human_presence"])
    op.create_index("ix_observations_created_at", "observations", ["created_at"])

    op.create_table(
        "detected_objects",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("observation_id", sa.String(length=64), sa.ForeignKey("observations.id"), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("relative_location", sa.Text(), nullable=True),
        sa.Column("bbox", json_type, nullable=True),
        sa.Column("spatial_coords", json_type, nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("evidence_metadata", json_type, nullable=False),
    )
    op.create_index("ix_detected_objects_observation_id", "detected_objects", ["observation_id"])
    op.create_index("ix_detected_objects_object_key", "detected_objects", ["object_key"])
    op.create_index("ix_detected_objects_source", "detected_objects", ["source"])
    op.create_index(
        "ix_detected_objects_object_seen",
        "detected_objects",
        ["object_key", "observation_id"],
    )

    op.create_table(
        "last_seen_objects",
        sa.Column("object_key", sa.String(length=255), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_room", sa.String(length=255), nullable=False),
        sa.Column("last_seen_relative_location", sa.Text(), nullable=True),
        sa.Column("last_seen_observation_id", sa.String(length=64), sa.ForeignKey("observations.id"), nullable=False),
        sa.Column("last_confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("evidence_observation_ids", json_type, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_last_seen_objects_last_seen_at", "last_seen_objects", ["last_seen_at"])
    op.create_index("ix_last_seen_objects_last_seen_room", "last_seen_objects", ["last_seen_room"])
    op.create_index("ix_last_seen_objects_last_seen_observation_id", "last_seen_objects", ["last_seen_observation_id"])
    op.create_index("ix_last_seen_objects_status", "last_seen_objects", ["status"])
    op.create_index("ix_last_seen_objects_updated_at", "last_seen_objects", ["updated_at"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("type", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("evidence_observation_ids", json_type, nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_type", "tasks", ["type"])
    op.create_index("ix_tasks_state", "tasks", ["state"])
    op.create_index("ix_tasks_created_at", "tasks", ["created_at"])
    op.create_index("ix_tasks_updated_at", "tasks", ["updated_at"])

    op.create_table(
        "queries",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("intent", sa.String(length=128), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(length=64), nullable=True),
        sa.Column("evidence_observation_ids", json_type, nullable=False),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_queries_session_id", "queries", ["session_id"])
    op.create_index("ix_queries_intent", "queries", ["intent"])
    op.create_index("ix_queries_confidence", "queries", ["confidence"])
    op.create_index("ix_queries_task_id", "queries", ["task_id"])
    op.create_index("ix_queries_provider", "queries", ["provider"])
    op.create_index("ix_queries_created_at", "queries", ["created_at"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence_observation_ids", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])
    op.create_index("ix_task_events_event_type", "task_events", ["event_type"])
    op.create_index("ix_task_events_created_at", "task_events", ["created_at"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("hazard_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("evidence_observation_ids", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alerts_task_id", "alerts", ["task_id"])
    op.create_index("ix_alerts_hazard_type", "alerts", ["hazard_type"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])

    op.create_table(
        "actuation_attempts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("alert_id", sa.String(length=64), sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("request_payload", json_type, nullable=True),
        sa.Column("response_payload", json_type, nullable=True),
        sa.Column("evidence_observation_ids", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_actuation_attempts_task_id", "actuation_attempts", ["task_id"])
    op.create_index("ix_actuation_attempts_alert_id", "actuation_attempts", ["alert_id"])
    op.create_index("ix_actuation_attempts_provider", "actuation_attempts", ["provider"])
    op.create_index("ix_actuation_attempts_state", "actuation_attempts", ["state"])
    op.create_index("ix_actuation_attempts_created_at", "actuation_attempts", ["created_at"])

    op.create_table(
        "verification_checks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("observation_id", sa.String(length=64), sa.ForeignKey("observations.id"), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence_observation_ids", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verification_checks_task_id", "verification_checks", ["task_id"])
    op.create_index("ix_verification_checks_observation_id", "verification_checks", ["observation_id"])
    op.create_index("ix_verification_checks_state", "verification_checks", ["state"])
    op.create_index("ix_verification_checks_created_at", "verification_checks", ["created_at"])

    op.create_table(
        "system_status_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("service", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_system_status_events_service", "system_status_events", ["service"])
    op.create_index("ix_system_status_events_state", "system_status_events", ["state"])
    op.create_index("ix_system_status_events_created_at", "system_status_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("system_status_events")
    op.drop_table("verification_checks")
    op.drop_table("actuation_attempts")
    op.drop_table("alerts")
    op.drop_table("task_events")
    op.drop_table("queries")
    op.drop_table("tasks")
    op.drop_table("last_seen_objects")
    op.drop_table("detected_objects")
    op.drop_table("observations")
    op.drop_table("afferens_raw_events")
