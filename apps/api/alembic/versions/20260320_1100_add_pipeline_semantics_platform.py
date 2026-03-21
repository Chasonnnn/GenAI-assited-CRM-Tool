"""add pipeline semantics platform fields

Revision ID: 20260320_1100
Revises: 20260315_1900
Create Date: 2026-03-20 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core.stage_definitions import canonicalize_stage_key
from app.schemas.pipeline_semantics import (
    default_pipeline_feature_config,
    default_stage_semantics,
)


# revision identifiers, used by Alembic.
revision: str = "20260320_1100"
down_revision: str | Sequence[str] | None = "20260315_1900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize_stage_key(value: Any) -> str:
    return canonicalize_stage_key(str(value or "").strip())


def upgrade() -> None:
    op.add_column(
        "pipelines",
        sa.Column(
            "feature_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "pipeline_stages",
        sa.Column(
            "semantics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    conn = op.get_bind()
    update_pipeline_stmt = sa.text(
        """
        UPDATE pipelines
        SET feature_config = :feature_config
        WHERE id = :pipeline_id
        """
    ).bindparams(sa.bindparam("feature_config", type_=postgresql.JSONB()))
    update_stage_stmt = sa.text(
        """
        UPDATE pipeline_stages
        SET semantics = :semantics
        WHERE id = :stage_id
        """
    ).bindparams(sa.bindparam("semantics", type_=postgresql.JSONB()))

    default_feature_config = default_pipeline_feature_config()
    pipeline_rows = conn.execute(sa.text("SELECT id FROM pipelines")).mappings().all()
    for row in pipeline_rows:
        conn.execute(
            update_pipeline_stmt,
            {
                "pipeline_id": row["id"],
                "feature_config": default_feature_config,
            },
        )

    stage_rows = conn.execute(
        sa.text(
            """
            SELECT id, stage_key, slug, stage_type
            FROM pipeline_stages
            """
        )
    ).mappings()
    for row in stage_rows:
        stage_key = _normalize_stage_key(row["stage_key"] or row["slug"])
        semantics = default_stage_semantics(stage_key, row["stage_type"] or "intake")
        conn.execute(
            update_stage_stmt,
            {
                "stage_id": row["id"],
                "semantics": semantics,
            },
        )


def downgrade() -> None:
    op.drop_column("pipeline_stages", "semantics")
    op.drop_column("pipelines", "feature_config")
