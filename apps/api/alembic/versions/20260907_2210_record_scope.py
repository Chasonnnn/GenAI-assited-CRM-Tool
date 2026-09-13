"""Add record scope rules and retained Intake collaborators.

Revision ID: 20260907_2210_record_scope
Revises: 20260907_2200_perm_policy
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260907_2210_record_scope"
down_revision = "20260907_2200_perm_policy"
branch_labels = None
depends_on = None


def _id():
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _org():
    return sa.Column(
        "organization_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )


def _member_columns():
    return [
        sa.Column(
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]


def _rule_columns():
    return [
        sa.Column("module", sa.String(30), nullable=False),
        sa.Column("assignment", sa.String(12), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column(
            "stage_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
    ]


def upgrade():
    op.create_table(
        "role_record_scopes",
        _id(),
        _org(),
        sa.Column("role", sa.String(50), nullable=False),
        *_rule_columns(),
        sa.CheckConstraint(
            "module IN ('surrogates', 'donors', 'intended_parents')", name="ck_role_scope_module"
        ),
        sa.CheckConstraint(
            "assignment IN ('all', 'assigned', 'none')", name="ck_role_scope_assignment"
        ),
        sa.CheckConstraint(
            "phase IN ('all', 'pre_approval', 'post_approval')", name="ck_role_scope_phase"
        ),
    )
    op.create_index(
        "uq_role_record_scope",
        "role_record_scopes",
        ["organization_id", "role", "module"],
        unique=True,
    )
    op.create_table(
        "user_record_scope_additions",
        _id(),
        _org(),
        *_member_columns(),
        *_rule_columns(),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "module IN ('surrogates', 'donors', 'intended_parents')", name="ck_user_scope_module"
        ),
        sa.CheckConstraint("assignment IN ('all', 'assigned')", name="ck_user_scope_assignment"),
        sa.CheckConstraint(
            "phase IN ('all', 'pre_approval', 'post_approval')", name="ck_user_scope_phase"
        ),
    )
    op.create_index(
        "idx_user_record_scope",
        "user_record_scope_additions",
        ["organization_id", "user_id", "module"],
    )
    op.create_table(
        "record_collaborators",
        _id(),
        _org(),
        *_member_columns(),
        sa.Column(
            "surrogate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("surrogates.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "donor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("donors.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "granted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(surrogate_id IS NOT NULL AND donor_id IS NULL) OR (surrogate_id IS NULL AND donor_id IS NOT NULL)",
            name="ck_record_collaborator_subject",
        ),
    )
    for kind in ("surrogate", "donor"):
        op.create_index(
            f"uq_{kind}_collaborator",
            "record_collaborators",
            ["organization_id", f"{kind}_id", "user_id"],
            unique=True,
            postgresql_where=sa.text(f"{kind}_id IS NOT NULL"),
        )
    op.create_index(
        "idx_record_collaborator_user", "record_collaborators", ["organization_id", "user_id"]
    )
    op.create_table(
        "record_scope_migration_reviews",
        _id(),
        _org(),
        sa.Column(
            "surrogate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("surrogates.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "donor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("donors.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "reviewed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "retained_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("resolved_phase", sa.String(20)),
        sa.Column(
            "reviewed_stage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
        ),
        sa.CheckConstraint(
            "resolved_phase IS NULL OR resolved_phase IN ('pre_approval', 'post_approval')",
            name="ck_record_scope_review_phase",
        ),
        sa.Column("evidence_reference", sa.String(500)),
        sa.Column("record_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(surrogate_id IS NOT NULL AND donor_id IS NULL) OR (surrogate_id IS NULL AND donor_id IS NOT NULL)",
            name="ck_record_scope_review_subject",
        ),
        sa.CheckConstraint(
            "decision IN ('retain_verified_owner', 'no_verified_owner')",
            name="ck_record_scope_review_decision",
        ),
    )
    for kind in ("surrogate", "donor"):
        op.create_index(
            f"uq_{kind}_scope_review",
            "record_scope_migration_reviews",
            ["organization_id", f"{kind}_id"],
            unique=True,
            postgresql_where=sa.text(f"{kind}_id IS NOT NULL"),
        )


def downgrade():
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
    op.drop_table("record_scope_migration_reviews")
    op.drop_table("record_collaborators")
    op.drop_table("user_record_scope_additions")
    op.drop_table("role_record_scopes")
