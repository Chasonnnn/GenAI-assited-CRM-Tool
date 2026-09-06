"""Add independent donor cases, explicit closure, and treatment attempts.

Expand schema before deploying compatible readers. Enable donor/repeat writes only
once every API/worker and exact-case work consumer runs the compatible version.
No existing outcomes or attempts are inferred. Lock budgets abort on contention.

Revision ID: 20260905_1400_match_cases
Revises: 20260830_0100
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260905_1400_match_cases"
down_revision = "20260830_0100"
branch_labels = None
depends_on = None

OPEN = "status IN ('proposed','reviewing','accepted','cancel_pending')"


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    op.add_column("matches", sa.Column("donor_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "matches",
        sa.Column("match_kind", sa.String(20), server_default="surrogate", nullable=False),
    )
    op.add_column("matches", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "matches", sa.Column("closed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("matches", sa.Column("closure_reason", sa.Text(), nullable=True))
    op.add_column("matches", sa.Column("outcome", sa.Text(), nullable=True))
    op.alter_column("matches", "surrogate_id", existing_type=postgresql.UUID(), nullable=True)
    op.create_foreign_key(
        "fk_matches_donor", "matches", "donors", ["donor_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_matches_closed_by",
        "matches",
        "users",
        ["closed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_match_two_parties",
        "matches",
        "(surrogate_id IS NOT NULL AND donor_id IS NULL) OR (surrogate_id IS NULL AND donor_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_match_kind",
        "matches",
        "(match_kind = 'surrogate' AND surrogate_id IS NOT NULL) OR (match_kind = 'donor' AND donor_id IS NOT NULL)",
    )
    op.create_unique_constraint("uq_matches_org_id", "matches", ["organization_id", "id"])
    op.create_index("ix_matches_donor_id", "matches", ["donor_id"])
    # A conflict must stop rollout for reconciliation; never discard old cases.
    op.drop_constraint("uq_match_org_surrogate_ip", "matches", type_="unique")
    op.create_index(
        "uq_match_open_surrogate_ip",
        "matches",
        ["organization_id", "surrogate_id", "intended_parent_id"],
        unique=True,
        postgresql_where=sa.text(OPEN),
    )
    op.create_index(
        "uq_match_open_donor_ip",
        "matches",
        ["organization_id", "donor_id", "intended_parent_id"],
        unique=True,
        postgresql_where=sa.text(OPEN),
    )
    op.drop_index("uq_one_accepted_match_per_surrogate", table_name="matches")
    op.create_index(
        "uq_one_accepted_match_per_surrogate",
        "matches",
        ["organization_id", "surrogate_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('accepted', 'cancel_pending')"),
    )
    op.create_table(
        "match_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("attempt_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.Date(), nullable=True),
        sa.Column("ended_at", sa.Date(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("match_id", "sequence", name="uq_match_attempt_sequence"),
        sa.UniqueConstraint(
            "organization_id", "match_id", "id", name="uq_match_attempts_org_match_id"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "match_id"],
            ["matches.organization_id", "matches.id"],
            name="fk_match_attempts_org_match",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("sequence > 0", name="ck_match_attempt_sequence"),
        sa.CheckConstraint(
            "attempt_type IN ('embryo_transfer','retrieval','collection','other')",
            name="ck_match_attempt_type",
        ),
        sa.CheckConstraint(
            "status IN ('planned','in_progress','completed','cancelled')",
            name="ck_match_attempt_status",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_match_attempt_dates",
        ),
    )
    op.create_index(
        "ix_match_attempts_org_match", "match_attempts", ["organization_id", "match_id"]
    )


def downgrade() -> None:
    # Old code cannot represent donor/repeat cases or attempts. Do not destroy them.
    bind = op.get_bind()
    incompatible = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM match_attempts) OR EXISTS (SELECT 1 FROM matches WHERE donor_id IS NOT NULL OR status = 'completed') OR EXISTS (SELECT 1 FROM matches GROUP BY organization_id,surrogate_id,intended_parent_id HAVING count(*) > 1)"
        )
    ).scalar()
    if incompatible:
        raise RuntimeError("Match case data requires a compatible forward revision")
    op.drop_table("match_attempts")
    op.drop_index("uq_match_open_surrogate_ip", table_name="matches")
    op.drop_index("uq_match_open_donor_ip", table_name="matches")
    op.drop_index("uq_one_accepted_match_per_surrogate", table_name="matches")
    op.create_index(
        "uq_one_accepted_match_per_surrogate",
        "matches",
        ["organization_id", "surrogate_id"],
        unique=True,
        postgresql_where=sa.text("status = 'accepted'"),
    )
    op.create_unique_constraint(
        "uq_match_org_surrogate_ip",
        "matches",
        ["organization_id", "surrogate_id", "intended_parent_id"],
    )
    op.drop_constraint("ck_match_two_parties", "matches", type_="check")
    op.drop_constraint("ck_match_kind", "matches", type_="check")
    op.drop_constraint("uq_matches_org_id", "matches", type_="unique")
    op.drop_index("ix_matches_donor_id", table_name="matches")
    op.drop_constraint("fk_matches_donor", "matches", type_="foreignkey")
    op.drop_constraint("fk_matches_closed_by", "matches", type_="foreignkey")
    op.alter_column("matches", "surrogate_id", existing_type=postgresql.UUID(), nullable=False)
    for column in (
        "outcome",
        "closure_reason",
        "closed_by_user_id",
        "closed_at",
        "match_kind",
        "donor_id",
    ):
        op.drop_column("matches", column)
