"""Add scheduling v2 state, explicit calendar bindings, and request receipts.

Revision ID: 20260922_1000_scheduling_v2_schema
Revises: 20260921_0100_google_appointment_sync
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260922_1000_scheduling_v2_schema"
down_revision = "20260921_0100_google_appointment_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")

    # These redundant unique pairs are required targets for tenant- and owner-scoped FKs.
    op.create_unique_constraint(
        "uq_memberships_org_user", "memberships", ["organization_id", "user_id"]
    )
    op.create_unique_constraint(
        "uq_user_integrations_user_id", "user_integrations", ["user_id", "id"]
    )
    op.create_unique_constraint("uq_appointments_org_id", "appointments", ["organization_id", "id"])

    op.add_column(
        "appointments",
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    # PostgreSQL preserves the add-column default for existing rows; new ORM rows use crm.
    op.add_column(
        "appointments",
        sa.Column(
            "origin",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'legacy_unknown'"),
        ),
    )
    op.alter_column("appointments", "origin", server_default=sa.text("'crm'"))
    op.add_column(
        "appointments", sa.Column("google_last_synced", postgresql.JSONB(), nullable=True)
    )
    op.add_column("appointments", sa.Column("google_conflict", postgresql.JSONB(), nullable=True))
    op.add_column(
        "appointments", sa.Column("google_sync_error", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "appointments", sa.Column("availability_override_reason", sa.Text(), nullable=True)
    )
    op.create_check_constraint(
        "ck_appointments_revision_nonnegative", "appointments", "revision >= 0"
    )

    op.create_table(
        "calendar_bindings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_email", sa.String(length=255), nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("access_role", sa.String(length=50), nullable=False),
        sa.Column(
            "timezone", sa.String(length=50), nullable=False, server_default=sa.text("'UTC'")
        ),
        sa.Column("check_busy", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("show_events", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("write_bookings", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sync_token", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sync_error", sa.String(length=100), nullable=True),
        sa.Column("channel_id", sa.String(length=255), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("channel_token_encrypted", sa.Text(), nullable=True),
        sa.Column("channel_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_id"], ["user_integrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_calendar_bindings_membership_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "integration_id"],
            ["user_integrations.user_id", "user_integrations.id"],
            name="fk_calendar_bindings_integration_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_calendar_bindings_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "integration_id",
            "calendar_id",
            name="uq_calendar_bindings_org_integration_calendar",
        ),
    )
    op.create_index(
        "idx_calendar_bindings_org_user", "calendar_bindings", ["organization_id", "user_id"]
    )
    op.create_index(
        "uq_calendar_bindings_active_booking_owner",
        "calendar_bindings",
        ["organization_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND write_bookings"),
    )

    op.create_table(
        "external_calendar_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("scheduled_start", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("scheduled_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("html_link", sa.String(length=1000), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_busy", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("recurring_event_id", sa.String(length=255), nullable=True),
        sa.Column("original_start", sa.String(length=64), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "binding_id"],
            ["calendar_bindings.organization_id", "calendar_bindings.id"],
            name="fk_external_calendar_events_binding_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "binding_id", "event_id", name="uq_external_calendar_events_binding_event"
        ),
    )
    op.create_index(
        "idx_external_calendar_events_org_interval",
        "external_calendar_events",
        ["organization_id", "scheduled_start"],
    )
    op.create_index(
        "idx_external_calendar_events_binding_interval",
        "external_calendar_events",
        ["binding_id", "scheduled_start"],
    )

    op.create_table(
        "scheduling_request_receipts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_key", sa.String(length=255), nullable=False),
        sa.Column("actor_scope", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_revision", sa.Integer(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "appointment_id"],
            ["appointments.organization_id", "appointments.id"],
            name="fk_scheduling_request_receipts_appointment_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "actor_scope",
            "request_key",
            name="uq_scheduling_request_receipts_scope_key",
        ),
    )
    op.create_index(
        "idx_scheduling_request_receipts_appointment",
        "scheduling_request_receipts",
        ["organization_id", "appointment_id"],
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_index(
        "idx_scheduling_request_receipts_appointment", table_name="scheduling_request_receipts"
    )
    op.drop_table("scheduling_request_receipts")
    op.drop_index(
        "idx_external_calendar_events_binding_interval", table_name="external_calendar_events"
    )
    op.drop_index(
        "idx_external_calendar_events_org_interval", table_name="external_calendar_events"
    )
    op.drop_table("external_calendar_events")
    op.drop_index("uq_calendar_bindings_active_booking_owner", table_name="calendar_bindings")
    op.drop_index("idx_calendar_bindings_org_user", table_name="calendar_bindings")
    op.drop_table("calendar_bindings")
    op.drop_constraint("ck_appointments_revision_nonnegative", "appointments", type_="check")
    for name in (
        "availability_override_reason",
        "google_sync_error",
        "google_conflict",
        "google_last_synced",
        "origin",
        "revision",
    ):
        op.drop_column("appointments", name)
    op.drop_constraint("uq_appointments_org_id", "appointments", type_="unique")
    op.drop_constraint("uq_user_integrations_user_id", "user_integrations", type_="unique")
    op.drop_constraint("uq_memberships_org_user", "memberships", type_="unique")
