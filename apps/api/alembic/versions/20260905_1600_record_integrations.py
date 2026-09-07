"""Add explicit appointment case context and record correspondence links.

Revision ID: 20260905_1600_record_integrations
Revises: 20260905_1500_match_work
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260905_1600_record_integrations"
down_revision = "20260905_1500_match_work"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    for field, table in (
        ("donor_id", "donors"),
        ("match_id", "matches"),
        ("attempt_id", "match_attempts"),
    ):
        op.add_column(
            "appointments", sa.Column(field, postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.create_foreign_key(
            f"fk_appointments_{field}",
            "appointments",
            table,
            [field],
            ["id"],
            ondelete="SET NULL" if field == "donor_id" else "RESTRICT",
        )
    op.create_foreign_key(
        "fk_appointments_match_org",
        "appointments",
        "matches",
        ["organization_id", "match_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_appointments_attempt_context",
        "appointments",
        "match_attempts",
        ["organization_id", "match_id", "attempt_id"],
        ["organization_id", "match_id", "id"],
    )
    op.create_check_constraint(
        "ck_appointments_attempt_match",
        "appointments",
        "attempt_id IS NULL OR match_id IS NOT NULL",
    )
    op.create_index("ix_appointments_donor_id", "appointments", ["donor_id"])
    op.create_index("ix_appointments_match_id", "appointments", ["match_id"])
    op.create_table(
        "record_ticket_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ticket_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "donor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("donors.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "intended_parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intended_parents.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "created_by_user_id",
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
            "num_nonnulls(donor_id, intended_parent_id) = 1", name="ck_record_ticket_one_record"
        ),
        sa.UniqueConstraint("ticket_id", "donor_id", name="uq_record_ticket_donor"),
        sa.UniqueConstraint("ticket_id", "intended_parent_id", name="uq_record_ticket_ip"),
    )
    op.create_index(
        "ix_record_ticket_org_donor", "record_ticket_links", ["organization_id", "donor_id"]
    )
    op.create_index(
        "ix_record_ticket_org_ip", "record_ticket_links", ["organization_id", "intended_parent_id"]
    )

    op.execute("""
        CREATE FUNCTION validate_record_integration_context() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE case_row matches%ROWTYPE;
        BEGIN
            IF NEW.donor_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM donors WHERE id=NEW.donor_id AND organization_id=NEW.organization_id) THEN
                RAISE EXCEPTION 'Invalid donor organization' USING ERRCODE='23514';
            END IF;
            IF NEW.intended_parent_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM intended_parents WHERE id=NEW.intended_parent_id AND organization_id=NEW.organization_id) THEN
                RAISE EXCEPTION 'Invalid intended parent organization' USING ERRCODE='23514';
            END IF;
            IF TG_TABLE_NAME = 'record_ticket_links' THEN
                IF NOT EXISTS(SELECT 1 FROM tickets WHERE id=NEW.ticket_id AND organization_id=NEW.organization_id) THEN
                    RAISE EXCEPTION 'Invalid ticket organization' USING ERRCODE='23514';
                END IF;
            ELSE
                IF NEW.match_id IS NOT NULL THEN
                    SELECT * INTO case_row FROM matches WHERE id=NEW.match_id AND organization_id=NEW.organization_id;
                    IF NOT FOUND OR (NEW.donor_id IS NOT NULL AND NEW.donor_id IS DISTINCT FROM case_row.donor_id)
                        OR (NEW.intended_parent_id IS NOT NULL AND NEW.intended_parent_id IS DISTINCT FROM case_row.intended_parent_id)
                        OR (NEW.surrogate_id IS NOT NULL AND NEW.surrogate_id IS DISTINCT FROM case_row.surrogate_id) THEN
                        RAISE EXCEPTION 'Invalid appointment match participants' USING ERRCODE='23514';
                    END IF;
                END IF;
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER appointments_record_context BEFORE INSERT OR UPDATE OF organization_id, donor_id, intended_parent_id, surrogate_id, match_id, attempt_id ON appointments FOR EACH ROW EXECUTE FUNCTION validate_record_integration_context()"
    )
    op.execute(
        "CREATE TRIGGER record_ticket_links_context BEFORE INSERT OR UPDATE ON record_ticket_links FOR EACH ROW EXECUTE FUNCTION validate_record_integration_context()"
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    # Prevent inserts or context changes between the history guard and removal.
    op.execute("LOCK TABLE appointments, record_ticket_links IN ACCESS EXCLUSIVE MODE")
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS(SELECT 1 FROM record_ticket_links) OR EXISTS(SELECT 1 FROM appointments WHERE donor_id IS NOT NULL OR match_id IS NOT NULL OR attempt_id IS NOT NULL)"
            )
        )
        .scalar()
    ):
        raise RuntimeError(
            "Record integrations contain history; retain this schema and roll forward"
        )
    op.execute("DROP TRIGGER appointments_record_context ON appointments")
    op.execute("DROP TRIGGER record_ticket_links_context ON record_ticket_links")
    op.execute("DROP FUNCTION validate_record_integration_context()")
    op.drop_constraint("fk_appointments_attempt_context", "appointments", type_="foreignkey")
    op.drop_constraint("fk_appointments_match_org", "appointments", type_="foreignkey")
    op.drop_constraint("ck_appointments_attempt_match", "appointments", type_="check")
    op.drop_table("record_ticket_links")
    op.drop_index("ix_appointments_match_id", table_name="appointments")
    op.drop_index("ix_appointments_donor_id", table_name="appointments")
    for field in ("attempt_id", "match_id", "donor_id"):
        op.drop_constraint(f"fk_appointments_{field}", "appointments", type_="foreignkey")
        op.drop_column("appointments", field)
