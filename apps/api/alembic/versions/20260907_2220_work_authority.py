"""Separate organization execution authority, publication credit and donor phases.

Revision ID: 20260907_2220_work_authority
Revises: 20260907_2210_record_scope
"""

from uuid import UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260907_2220_work_authority"
down_revision = "20260907_2210_record_scope"
branch_labels = None
depends_on = None

APPROVAL_NAMESPACE = UUID("1995553e-705e-49ea-95fd-78ba7ad7039c")


def upgrade() -> None:
    for table in ("automation_workflows", "campaigns", "email_templates"):
        op.add_column(table, sa.Column("proposed_by_user_id", sa.UUID(), nullable=True))
        op.add_column(table, sa.Column("proposed_by_name", sa.String(255), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_proposer",
            table,
            "users",
            ["proposed_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    for table in ("automation_workflows", "campaigns"):
        op.add_column(table, sa.Column("execution_authority", postgresql.JSONB(), nullable=True))
    for table in ("workflow_executions", "campaign_runs"):
        op.add_column(table, sa.Column("authority_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column(
        "campaigns", sa.Column("scope", sa.String(20), server_default="org", nullable=False)
    )
    op.add_column("campaigns", sa.Column("owner_user_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_campaigns_owner", "campaigns", "users", ["owner_user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_check_constraint("ck_campaigns_scope", "campaigns", "scope IN ('personal', 'org')")
    op.create_check_constraint(
        "ck_campaigns_org_owner", "campaigns", "scope != 'org' OR owner_user_id IS NULL"
    )
    op.drop_constraint("uq_campaign_name", "campaigns", type_="unique")
    op.create_index(
        "uq_campaign_org_name",
        "campaigns",
        ["organization_id", "name"],
        unique=True,
        postgresql_where=sa.text("scope = 'org'"),
    )
    op.create_index(
        "uq_campaign_personal_name",
        "campaigns",
        ["organization_id", "owner_user_id", "name"],
        unique=True,
        postgresql_where=sa.text("scope = 'personal'"),
    )
    op.add_column("donors", sa.Column("paused_from_stage_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_donors_paused_stage",
        "donors",
        "pipeline_stages",
        ["paused_from_stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    seed_donor_approval_gates(op.get_bind())


def seed_donor_approval_gates(conn) -> None:
    pipelines = (
        conn.execute(
            sa.text("SELECT id FROM pipelines WHERE entity_type IN ('egg_donor', 'sperm_donor')")
        )
        .scalars()
        .all()
    )
    for pipeline_id in pipelines:
        if conn.execute(
            sa.text("SELECT 1 FROM pipeline_stages WHERE pipeline_id=:id AND stage_key='approved'"),
            {"id": pipeline_id},
        ).scalar():
            continue
        gate_order = conn.execute(
            sa.text(
                """SELECT min("order") FROM pipeline_stages WHERE pipeline_id=:id AND stage_type='post_approval'"""
            ),
            {"id": pipeline_id},
        ).scalar()
        if gate_order is None:
            # Custom pipelines without a post-approval phase require explicit review.
            continue
        slug = "approved"
        existing_slugs = set(
            conn.execute(
                sa.text("SELECT slug FROM pipeline_stages WHERE pipeline_id=:id"),
                {"id": pipeline_id},
            ).scalars()
        )
        suffix = 1
        while slug in existing_slugs:
            suffix += 1
            slug = f"approved-{suffix}"
        conn.execute(
            sa.text(
                'UPDATE pipeline_stages SET "order"="order"+1 WHERE pipeline_id=:id AND "order">=:position'
            ),
            {"id": pipeline_id, "position": gate_order},
        )
        conn.execute(
            sa.text("""INSERT INTO pipeline_stages
            (id, pipeline_id, stage_key, slug, label, color, "order", stage_type, is_active, is_intake_stage, semantics)
            VALUES (:stage_id, :pipeline_id, 'approved', :slug, 'Approved', '#22C55E', :position, 'post_approval', true, false, '{}'::jsonb)
        """),
            {
                "slug": slug,
                "stage_id": uuid5(APPROVAL_NAMESPACE, str(pipeline_id)),
                "pipeline_id": pipeline_id,
                "position": gate_order,
            },
        )
    conn.execute(
        sa.text("""UPDATE donors d SET paused_from_stage_id = history.old_stage_id
        FROM pipeline_stages current_stage, LATERAL (
            SELECT h.donor_id, h.old_stage_id, h.new_stage_id,
                row_number() OVER (PARTITION BY h.donor_id ORDER BY h.recorded_at DESC, h.id DESC) AS rn
            FROM donor_status_history h
        ) history, pipeline_stages prior_stage
        WHERE current_stage.id = d.stage_id AND current_stage.stage_type = 'paused'
          AND history.donor_id = d.id AND history.rn = 1 AND history.new_stage_id = d.stage_id
          AND prior_stage.id = history.old_stage_id AND prior_stage.pipeline_id = current_stage.pipeline_id
          AND prior_stage.stage_type != 'paused'
    """)
    )


def downgrade() -> None:
    # Keep inserted stages: records or user configuration may now refer to them.
    conn = op.get_bind()
    conn.execute(
        sa.text("LOCK TABLE organizations, organization_permission_policies IN EXCLUSIVE MODE")
    )
    if conn.execute(
        sa.text("SELECT 1 FROM organization_permission_policies WHERE version=2 LIMIT 1")
    ).scalar():
        raise RuntimeError(
            "Active permission policies require a reviewed rollback before schema downgrade"
        )
    if conn.execute(sa.text("SELECT 1 FROM campaigns WHERE scope='personal' LIMIT 1")).scalar():
        raise RuntimeError("Review personal campaigns before reverting organization-only schema")
    op.drop_constraint("fk_donors_paused_stage", "donors", type_="foreignkey")
    op.drop_column("donors", "paused_from_stage_id")
    op.drop_index("uq_campaign_personal_name", table_name="campaigns")
    op.drop_index("uq_campaign_org_name", table_name="campaigns")
    op.create_unique_constraint("uq_campaign_name", "campaigns", ["organization_id", "name"])
    op.drop_constraint("ck_campaigns_org_owner", "campaigns", type_="check")
    op.drop_constraint("ck_campaigns_scope", "campaigns", type_="check")
    op.drop_constraint("fk_campaigns_owner", "campaigns", type_="foreignkey")
    op.drop_column("campaigns", "owner_user_id")
    op.drop_column("campaigns", "scope")
    for table in ("workflow_executions", "campaign_runs"):
        op.drop_column(table, "authority_snapshot")
    for table in ("automation_workflows", "campaigns"):
        op.drop_column(table, "execution_authority")
    for table in ("automation_workflows", "campaigns", "email_templates"):
        op.drop_constraint(f"fk_{table}_proposer", table, type_="foreignkey")
        op.drop_column(table, "proposed_by_name")
        op.drop_column(table, "proposed_by_user_id")
