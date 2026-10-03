"""Add module-owned form routing settings and review tasks.

Revision ID: 20261003_1300_form_module_routing
Revises: 20261003_1200_repair_seeded_system_workflows
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261003_1300_form_module_routing"
down_revision = "20261003_1200_repair_seeded_system_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.add_column(
        "forms",
        sa.Column("routing_exact_match", sa.String(10), nullable=False, server_default="review"),
    )
    op.add_column(
        "forms",
        sa.Column("routing_no_match", sa.String(10), nullable=False, server_default="review"),
    )
    op.add_column("forms", sa.Column("routing_lead_source", sa.String(20), nullable=True))
    op.add_column(
        "forms",
        sa.Column(
            "routing_auto_create_donor", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "forms",
        sa.Column("routing_updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_forms_routing_updated_by_user",
        "forms",
        "users",
        ["routing_updated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE forms SET routing_exact_match = 'auto', routing_no_match = 'auto', routing_lead_source = 'website', routing_auto_create_donor = true WHERE lead_kind IN ('egg_donor', 'sperm_donor')"
    )
    for name, condition in (
        ("exact_match", "routing_exact_match IN ('auto', 'review')"),
        ("no_match", "routing_no_match IN ('auto', 'review', 'off')"),
        (
            "lead_source",
            "routing_lead_source IS NULL OR routing_lead_source IN ('website', 'form_embed')",
        ),
        ("auto_create_donor", "NOT routing_auto_create_donor OR lead_kind <> 'surrogate'"),
    ):
        op.create_check_constraint(f"ck_forms_routing_{name}", "forms", condition)
    op.add_column(
        "form_submissions", sa.Column("routing_review_step", sa.String(20), nullable=True)
    )
    op.create_check_constraint(
        "ck_form_submissions_routing_review_step",
        "form_submissions",
        "routing_review_step IS NULL OR routing_review_step IN ('match', 'create_lead')",
    )
    op.create_check_constraint(
        "ck_form_submissions_routing_review_status",
        "form_submissions",
        "(match_status = 'routing_review') = (routing_review_step IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_form_submissions_org_id", "form_submissions", ["organization_id", "id"]
    )
    op.add_column(
        "tasks", sa.Column("form_submission_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_tasks_form_submission_org",
        "tasks",
        "form_submissions",
        ["organization_id", "form_submission_id"],
        ["organization_id", "id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_tasks_form_submission", "tasks", ["form_submission_id"])
    op.create_index(
        "uq_tasks_open_submission_review",
        "tasks",
        ["form_submission_id"],
        unique=True,
        postgresql_where=sa.text("task_type = 'review' AND status IN ('pending', 'in_progress')"),
    )


def downgrade() -> None:
    op.drop_index("uq_tasks_open_submission_review", table_name="tasks")
    op.drop_index("idx_tasks_form_submission", table_name="tasks")
    op.drop_constraint("fk_tasks_form_submission_org", "tasks", type_="foreignkey")
    op.drop_column("tasks", "form_submission_id")
    op.drop_constraint("uq_form_submissions_org_id", "form_submissions", type_="unique")
    op.drop_constraint(
        "ck_form_submissions_routing_review_status", "form_submissions", type_="check"
    )
    op.drop_constraint("ck_form_submissions_routing_review_step", "form_submissions", type_="check")
    op.execute(
        "UPDATE form_submissions SET match_status = 'ambiguous_review' WHERE match_status = 'routing_review'"
    )
    op.drop_column("form_submissions", "routing_review_step")
    for name in ("exact_match", "no_match", "lead_source", "auto_create_donor"):
        op.drop_constraint(f"ck_forms_routing_{name}", "forms", type_="check")
    op.drop_constraint("fk_forms_routing_updated_by_user", "forms", type_="foreignkey")
    for name in (
        "exact_match",
        "no_match",
        "lead_source",
        "auto_create_donor",
        "updated_by_user_id",
    ):
        op.drop_column("forms", f"routing_{name}")
