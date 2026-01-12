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

    # Strategy 0: Create default pipelines for orgs that have cases but no pipeline
    # First, find orgs with cases but no pipelines and create pipelines for them
    conn.execute(
        sa.text("""
        INSERT INTO pipelines (id, organization_id, name, is_default, current_version, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            c.organization_id,
            'Default Pipeline',
            TRUE,
            1,
            NOW(),
            NOW()
        FROM cases c
        LEFT JOIN pipelines p ON p.organization_id = c.organization_id
        WHERE p.id IS NULL
        GROUP BY c.organization_id
    """)
    )

    # Create default stages for newly created pipelines that don't have stages
    conn.execute(
        sa.text("""
        INSERT INTO pipeline_stages (id, pipeline_id, slug, label, color, stage_type, "order", is_active, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            p.id,
            'new_unread',
            'New Unread',
            '#3B82F6',
            'intake',
            1,
            TRUE,
            NOW(),
            NOW()
        FROM pipelines p
        LEFT JOIN pipeline_stages ps ON ps.pipeline_id = p.id
        WHERE ps.id IS NULL
    """)
    )

    # Strategy 1: Update cases that have stage_id but missing status_label
    conn.execute(
        sa.text("""
        UPDATE cases
        SET status_label = ps.label
        FROM pipeline_stages ps
        WHERE cases.stage_id = ps.id
          AND cases.status_label IS NULL
    """)
    )

    # Strategy 2: Map null stage_id to org's default pipeline's new_unread stage
    conn.execute(
        sa.text("""
        UPDATE cases
        SET 
            stage_id = ps.id,
            status_label = ps.label
        FROM pipelines p, pipeline_stages ps
        WHERE cases.stage_id IS NULL
          AND p.organization_id = cases.organization_id
          AND p.is_default = TRUE
          AND ps.pipeline_id = p.id
          AND ps.slug = 'new_unread'
          AND ps.is_active = TRUE
    """)
    )

    # Strategy 3: Fallback to any default pipeline's first active stage
    conn.execute(
        sa.text("""
        UPDATE cases
        SET 
            stage_id = ps.id,
            status_label = ps.label
        FROM pipelines p, pipeline_stages ps
        WHERE cases.stage_id IS NULL
          AND p.organization_id = cases.organization_id
          AND p.is_default = TRUE
          AND ps.pipeline_id = p.id
          AND ps.is_active = TRUE
          AND ps.order = (
              SELECT MIN(ps2.order) 
              FROM pipeline_stages ps2 
              WHERE ps2.pipeline_id = p.id AND ps2.is_active = TRUE
          )
    """)
    )

    # Strategy 4: Fallback to any pipeline's first active stage in org
    conn.execute(
        sa.text("""
        UPDATE cases
        SET 
            stage_id = sub.stage_id,
            status_label = sub.label
        FROM (
            SELECT DISTINCT ON (p.organization_id)
                p.organization_id,
                ps.id as stage_id,
                ps.label
            FROM pipelines p
            JOIN pipeline_stages ps ON ps.pipeline_id = p.id AND ps.is_active = TRUE
            ORDER BY p.organization_id, p.is_default DESC, p.created_at, ps.order
        ) sub
        WHERE cases.stage_id IS NULL
          AND cases.organization_id = sub.organization_id
    """)
    )

    # Check if any cases still have null stage_id
    result = conn.execute(sa.text("SELECT COUNT(*) FROM cases WHERE stage_id IS NULL"))
    null_count = result.scalar()
    if null_count and null_count > 0:
        raise Exception(
            f"Cannot proceed: {null_count} case(s) still have NULL stage_id. "
            "Ensure all organizations have at least one pipeline with an active stage."
        )

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

    op.add_column(
        "case_status_history",
        sa.Column("to_status", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "case_status_history",
        sa.Column("from_status", sa.String(length=50), nullable=True),
    )

    op.add_column("cases", sa.Column("status", sa.String(length=50), nullable=True))
    op.create_index("idx_cases_org_status", "cases", ["organization_id", "status"])

    op.drop_index("idx_cases_org_stage", table_name="cases")
    op.alter_column("cases", "status_label", nullable=True)
    op.alter_column("cases", "stage_id", nullable=True)
