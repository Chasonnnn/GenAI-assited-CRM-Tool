"""Restore donor handoff and Matched stages before protecting their identities.

Existing stage IDs, donor references, labels, colors, order and semantics survive.
Missing stages are inserted after approval/handoff; inactive or deleted stages
are restored in place. Protection itself is derived from stage definitions.
Downgrade leaves the restored stages intact so donor references remain valid.

Revision ID: 20260926_1200_donor_match_stages
Revises: 20260925_1200_match_status_model
"""

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.db.migration_steps.donor_pipelines import _stage_semantics

revision = "20260926_1200_donor_match_stages"
down_revision = "20260925_1200_match_status_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    connection = op.get_bind()
    pipelines = connection.execute(
        sa.text(
            "SELECT id, entity_type FROM pipelines WHERE entity_type IN ('egg_donor', 'sperm_donor') ORDER BY id"
        )
    ).all()
    for pipeline in pipelines:
        handoff = "available" if pipeline.entity_type == "sperm_donor" else "ready_to_match"
        previous_key = "approved"
        for key, label, color in (
            (handoff, "Available" if handoff == "available" else "Ready to Match", "#0EA5E9"),
            ("matched", "Matched", "#6366F1"),
        ):
            existing = connection.execute(
                sa.text(
                    "SELECT id FROM pipeline_stages WHERE pipeline_id=:pipeline AND stage_key=:key"
                ),
                {"pipeline": pipeline.id, "key": key},
            ).scalar_one_or_none()
            if existing:
                connection.execute(
                    sa.text(
                        "UPDATE pipeline_stages SET is_active=TRUE, deleted_at=NULL WHERE id=:id AND (NOT is_active OR deleted_at IS NOT NULL)"
                    ),
                    {"id": existing},
                )
            else:
                order = connection.execute(
                    sa.text(
                        'SELECT "order" FROM pipeline_stages WHERE pipeline_id=:pipeline AND stage_key=:key'
                    ),
                    {"pipeline": pipeline.id, "key": previous_key},
                ).scalar_one_or_none()
                if order is None:
                    order = connection.execute(
                        sa.text(
                            'SELECT coalesce(max("order"), 0) FROM pipeline_stages WHERE pipeline_id=:pipeline'
                        ),
                        {"pipeline": pipeline.id},
                    ).scalar_one()
                order += 1
                connection.execute(
                    sa.text(
                        'UPDATE pipeline_stages SET "order"="order"+1 WHERE pipeline_id=:pipeline AND "order">=:order'
                    ),
                    {"pipeline": pipeline.id, "order": order},
                )
                stage_id = uuid4()
                slug_taken = connection.execute(
                    sa.text(
                        "SELECT 1 FROM pipeline_stages WHERE pipeline_id=:pipeline AND slug=:key"
                    ),
                    {"pipeline": pipeline.id, "key": key},
                ).scalar_one_or_none()
                connection.execute(
                    sa.text("""
                    INSERT INTO pipeline_stages (id, pipeline_id, stage_key, slug, label, color,
                        "order", stage_type, semantics, is_active, is_intake_stage)
                    VALUES (:id, :pipeline, :key, :slug, :label, :color, :order,
                        'post_approval', :semantics, TRUE, FALSE)
                """).bindparams(sa.bindparam("semantics", type_=JSONB())),
                    {
                        "id": stage_id,
                        "pipeline": pipeline.id,
                        "key": key,
                        "slug": f"{key}_{stage_id.hex[:8]}" if slug_taken else key,
                        "label": label,
                        "color": color,
                        "order": order,
                        "semantics": _stage_semantics(pipeline.entity_type, key),
                    },
                )
            previous_key = key


def downgrade() -> None:
    pass
