"""Pipeline v2: Remove legacy status columns and enforce stage references.

Revision ID: 0037_pipeline_cutover
Revises: 0036_pipeline_stages
Create Date: 2025-12-20
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0037_pipeline_cutover"
down_revision = "0036_pipeline_stages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Ensure all cases have stage_id and status_label
    conn.execute(sa.text("""
        UPDATE cases
        SET status_label = ps.label
        FROM pipeline_stages ps
        WHERE cases.stage_id = ps.id
          AND cases.status_label IS NULL
    """))
    conn.execute(sa.text("""
        UPDATE cases
        SET 
            stage_id = ps.id,
            status_label = ps.label
        FROM pipelines p, pipeline_stages ps
        WHERE (cases.stage_id IS NULL OR cases.status_label IS NULL)
          AND p.organization_id = cases.organization_id
          AND p.is_default = TRUE
          AND ps.pipeline_id = p.id
          AND ps.slug = 'new_unread'
    """))

    # Enforce non-null stage references
    op.alter_column("cases", "stage_id", nullable=False)
    op.alter_column("cases", "status_label", nullable=False)

    # Drop legacy status columns
    op.drop_index("idx_cases_org_status", table_name="cases")
    op.drop_column("cases", "status")

    op.drop_column("case_status_history", "from_status")
    op.drop_column("case_status_history", "to_status")

    op.drop_column("pipelines", "stages")

    # Drop legacy pipeline_id if it exists from earlier iterations
    op.execute("ALTER TABLE cases DROP COLUMN IF EXISTS pipeline_id")

    # Add new index for stage-based filtering
    op.create_index("idx_cases_org_stage", "cases", ["organization_id", "stage_id"])


def downgrade() -> None:
    # Recreate legacy columns (no data backfill)
    op.add_column("pipelines", sa.Column("stages", sa.JSON(), nullable=True))

    op.add_column("case_status_history", sa.Column("to_status", sa.String(length=50), nullable=True))
    op.add_column("case_status_history", sa.Column("from_status", sa.String(length=50), nullable=True))

    op.add_column("cases", sa.Column("status", sa.String(length=50), nullable=True))
    op.create_index("idx_cases_org_status", "cases", ["organization_id", "status"])

    op.drop_index("idx_cases_org_stage", table_name="cases")
    op.alter_column("cases", "status_label", nullable=True)
    op.alter_column("cases", "stage_id", nullable=True)
