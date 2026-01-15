"""Pipeline v2: Stage CRUD with case migration.

Revision ID: 0036_pipeline_stages
Revises: 0035_compliance
Create Date: 2025-12-20

This migration:
1. Creates pipeline_stages table
2. Migrates JSON stages to pipeline_stages rows
3. Adds Case.stage_id, status_label
4. Adds CaseStatusHistory.from/to_stage_id + label snapshots
5. Maps old Case.status to stage_id
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0036_pipeline_stages"
down_revision = "0035_compliance"
branch_labels = None
depends_on = None

# Default stage type mappings
STAGE_TYPE_MAP = {
    "new_unread": "intake",
    "contacted": "intake",
    "qualified": "intake",
    "applied": "intake",
    "followup_scheduled": "intake",
    "application_submitted": "intake",
    "under_review": "intake",
    "approved": "intake",
    "pending_handoff": "intake",
    "pending_match": "post_approval",
    "meds_started": "post_approval",
    "exam_passed": "post_approval",
    "embryo_transferred": "post_approval",
    "disqualified": "terminal",
    "delivered": "terminal",
}


def upgrade() -> None:
    # 1. Create pipeline_stages table
    op.create_table(
        "pipeline_stages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("stage_type", sa.String(20), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("allowed_next_slugs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pipeline_id", "slug", name="uq_stage_slug"),
    )
    op.create_index("idx_stage_pipeline_order", "pipeline_stages", ["pipeline_id", "order"])
    op.create_index("idx_stage_pipeline_active", "pipeline_stages", ["pipeline_id", "is_active"])

    # 2. Add new columns to cases
    op.add_column("cases", sa.Column("stage_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("cases", sa.Column("status_label", sa.String(100), nullable=True))
    op.create_foreign_key(
        "fk_cases_stage",
        "cases",
        "pipeline_stages",
        ["stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_cases_stage", "cases", ["stage_id"])

    # 3. Add new columns to case_status_history
    op.add_column(
        "case_status_history",
        sa.Column("from_stage_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "case_status_history",
        sa.Column("to_stage_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "case_status_history",
        sa.Column("from_label_snapshot", sa.String(100), nullable=True),
    )
    op.add_column(
        "case_status_history",
        sa.Column("to_label_snapshot", sa.String(100), nullable=True),
    )
    op.create_foreign_key(
        "fk_history_from_stage",
        "case_status_history",
        "pipeline_stages",
        ["from_stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_history_to_stage",
        "case_status_history",
        "pipeline_stages",
        ["to_stage_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Make old columns nullable for migration
    op.alter_column("cases", "status", nullable=True)
    op.alter_column("case_status_history", "from_status", nullable=True)
    op.alter_column("case_status_history", "to_status", nullable=True)

    # 5. Migrate JSON stages to pipeline_stages rows
    conn = op.get_bind()

    # Get all pipelines with their JSON stages
    pipelines = conn.execute(
        sa.text("SELECT id, organization_id, stages FROM pipelines WHERE stages IS NOT NULL")
    ).fetchall()

    for pipeline in pipelines:
        pipeline_id = pipeline[0]
        stages_json = pipeline[2]

        if not stages_json:
            continue

        for stage in stages_json:
            slug = stage.get("status", stage.get("slug"))
            label = stage.get("label", slug)
            color = stage.get("color", "#6B7280")
            order = stage.get("order", 1)
            stage_type = STAGE_TYPE_MAP.get(slug, "intake")

            conn.execute(
                sa.text("""
                INSERT INTO pipeline_stages (pipeline_id, slug, stage_type, label, color, "order")
                VALUES (:pipeline_id, :slug, :stage_type, :label, :color, :order)
                ON CONFLICT (pipeline_id, slug) DO NOTHING
            """),
                {
                    "pipeline_id": pipeline_id,
                    "slug": slug,
                    "stage_type": stage_type,
                    "label": label,
                    "color": color,
                    "order": order,
                },
            )

    # 6. Map cases to their pipeline + stage
    conn.execute(
        sa.text("""
        UPDATE cases
        SET 
            stage_id = ps.id,
            status_label = ps.label
        FROM pipelines p, pipeline_stages ps
        WHERE p.organization_id = cases.organization_id 
          AND p.is_default = TRUE
          AND ps.pipeline_id = p.id 
          AND ps.slug = cases.status
    """)
    )

    # 7. Handle cases with invalid status (fallback to new_unread)
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
    """)
    )

    # 8. Map case_status_history from_stage references
    conn.execute(
        sa.text("""
        UPDATE case_status_history
        SET 
            from_stage_id = ps.id,
            from_label_snapshot = COALESCE(ps.label, case_status_history.from_status)
        FROM cases c, pipelines p, pipeline_stages ps
        WHERE c.id = case_status_history.case_id
          AND p.organization_id = c.organization_id
          AND p.is_default = TRUE
          AND ps.pipeline_id = p.id 
          AND ps.slug = case_status_history.from_status
    """)
    )

    # 9. Map case_status_history to_stage references
    conn.execute(
        sa.text("""
        UPDATE case_status_history
        SET 
            to_stage_id = ps.id,
            to_label_snapshot = COALESCE(ps.label, case_status_history.to_status)
        FROM cases c, pipelines p, pipeline_stages ps
        WHERE c.id = case_status_history.case_id
          AND p.organization_id = c.organization_id
          AND p.is_default = TRUE
          AND ps.pipeline_id = p.id 
          AND ps.slug = case_status_history.to_status
    """)
    )

    # 9. Make stages JSON nullable (will be removed in future migration)
    op.alter_column("pipelines", "stages", nullable=True)


def downgrade() -> None:
    # Remove new columns
    op.drop_constraint("fk_history_to_stage", "case_status_history", type_="foreignkey")
    op.drop_constraint("fk_history_from_stage", "case_status_history", type_="foreignkey")
    op.drop_column("case_status_history", "to_label_snapshot")
    op.drop_column("case_status_history", "from_label_snapshot")
    op.drop_column("case_status_history", "to_stage_id")
    op.drop_column("case_status_history", "from_stage_id")
    op.alter_column("case_status_history", "to_status", nullable=False)
    op.alter_column("case_status_history", "from_status", nullable=False)

    op.drop_index("idx_cases_stage", "cases")
    op.drop_constraint("fk_cases_stage", "cases", type_="foreignkey")
    op.drop_column("cases", "status_label")
    op.drop_column("cases", "stage_id")
    op.alter_column("cases", "status", nullable=False)

    op.alter_column("pipelines", "stages", nullable=False)

    op.drop_index("idx_stage_pipeline_active", "pipeline_stages")
    op.drop_index("idx_stage_pipeline_order", "pipeline_stages")
    op.drop_table("pipeline_stages")
