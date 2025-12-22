"""Add org timezone and insert matched pipeline stage.

Revision ID: 0045_add_org_timezone_and_matched_stage
Revises: 0044_fix_appointment_types
Create Date: 2025-01-06
"""
from alembic import op
import sqlalchemy as sa


revision = '0045_add_org_timezone_and_matched_stage'
down_revision = '0044_fix_appointment_types'
branch_labels = None
depends_on = None


MATCHED_COLOR = "#6366F1"


def upgrade():
    op.add_column(
        "organizations",
        sa.Column(
            "timezone",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'America/Los_Angeles'"),
        ),
    )

    conn = op.get_bind()
    pipelines = conn.execute(sa.text("SELECT id FROM pipelines")).fetchall()

    for row in pipelines:
        pipeline_id = row[0]

        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM pipeline_stages "
                "WHERE pipeline_id = :pid AND slug = 'matched'"
            ),
            {"pid": pipeline_id},
        ).first()
        if exists:
            continue

        pending = conn.execute(
            sa.text(
                "SELECT \"order\" FROM pipeline_stages "
                "WHERE pipeline_id = :pid AND slug = 'pending_match' AND deleted_at IS NULL"
            ),
            {"pid": pipeline_id},
        ).first()

        meds = conn.execute(
            sa.text(
                "SELECT \"order\" FROM pipeline_stages "
                "WHERE pipeline_id = :pid AND slug = 'meds_started' AND deleted_at IS NULL"
            ),
            {"pid": pipeline_id},
        ).first()

        if meds:
            insert_order = meds[0]
            conn.execute(
                sa.text(
                    "UPDATE pipeline_stages "
                    "SET \"order\" = \"order\" + 1 "
                    "WHERE pipeline_id = :pid AND \"order\" >= :order"
                ),
                {"pid": pipeline_id, "order": insert_order},
            )
        elif pending:
            insert_order = pending[0] + 1
            conn.execute(
                sa.text(
                    "UPDATE pipeline_stages "
                    "SET \"order\" = \"order\" + 1 "
                    "WHERE pipeline_id = :pid AND \"order\" > :order"
                ),
                {"pid": pipeline_id, "order": pending[0]},
            )
        else:
            max_order = conn.execute(
                sa.text(
                    "SELECT COALESCE(MAX(\"order\"), 0) FROM pipeline_stages WHERE pipeline_id = :pid"
                ),
                {"pid": pipeline_id},
            ).scalar()
            insert_order = (max_order or 0) + 1

        conn.execute(
            sa.text(
                "INSERT INTO pipeline_stages "
                "(pipeline_id, slug, stage_type, label, color, \"order\", is_active, created_at, updated_at) "
                "VALUES (:pid, 'matched', 'post_approval', 'Matched', :color, :order, true, now(), now())"
            ),
            {"pid": pipeline_id, "color": MATCHED_COLOR, "order": insert_order},
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM pipeline_stages WHERE slug = 'matched'"))
    op.drop_column("organizations", "timezone")
