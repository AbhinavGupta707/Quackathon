"""add semantic memory vector index

Revision ID: 20260622_0009
Revises: 20260622_0008
Create Date: 2026-06-22
"""

from __future__ import annotations

from typing import Sequence

from alembic import op


revision: str = "20260622_0009"
down_revision: str | None = "20260622_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            BEGIN
                CREATE INDEX IF NOT EXISTS ix_semantic_memory_embedding_hnsw
                ON semantic_memory
                USING hnsw (embedding vector_cosine_ops)
                WHERE embedding IS NOT NULL;
            EXCEPTION WHEN undefined_object THEN
                BEGIN
                    CREATE INDEX IF NOT EXISTS ix_semantic_memory_embedding_ivfflat
                    ON semantic_memory
                    USING ivfflat (embedding vector_cosine_ops)
                    WHERE embedding IS NOT NULL;
                EXCEPTION WHEN undefined_object THEN
                    RAISE NOTICE 'pgvector ANN index access method is unavailable; semantic_memory.embedding remains queryable without ANN index';
                END;
            END;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_semantic_memory_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_semantic_memory_embedding_ivfflat")
