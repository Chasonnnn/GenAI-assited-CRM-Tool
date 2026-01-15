"""Add appointment scheduling tables.

Revision ID: 0042_appointments
Revises: 0041_rename_manager_to_admin
Create Date: 2024-12-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


revision = "0042_appointments"
down_revision = "0041_rename_manager_to_admin"
branch_labels = None
depends_on = None


def upgrade():
    """Create appointment scheduling tables."""

    # ==========================================================================
    # appointment_types - Appointment templates per user
    # ==========================================================================
    op.create_table(
        "appointment_types",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("buffer_before_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("buffer_after_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("meeting_mode", sa.String(20), nullable=False, server_default="'zoom'"),
        sa.Column("reminder_hours_before", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "slug", name="uq_appointment_type_slug"),
    )
    op.create_index("idx_appointment_types_user", "appointment_types", ["user_id", "is_active"])
    op.create_index("idx_appointment_types_org", "appointment_types", ["organization_id"])

    # ==========================================================================
    # availability_rules - Weekly availability per user
    # ==========================================================================
    op.create_table(
        "availability_rules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),  # Monday=0, Sunday=6
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "timezone",
            sa.String(50),
            nullable=False,
            server_default="'America/New_York'",
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_valid_day_of_week"),
    )
    op.create_index("idx_availability_rules_user", "availability_rules", ["user_id"])
    op.create_index("idx_availability_rules_org", "availability_rules", ["organization_id"])

    # ==========================================================================
    # availability_overrides - Date-specific overrides
    # ==========================================================================
    op.create_table(
        "availability_overrides",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("override_date", sa.Date(), nullable=False),
        sa.Column(
            "is_unavailable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "override_date", name="uq_availability_override_date"),
    )
    op.create_index("idx_availability_overrides_user", "availability_overrides", ["user_id"])
    op.create_index("idx_availability_overrides_org", "availability_overrides", ["organization_id"])

    # ==========================================================================
    # booking_links - Secure public URLs for booking
    # ==========================================================================
    op.create_table(
        "booking_links",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("public_slug", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("public_slug", name="uq_booking_link_slug"),
        sa.UniqueConstraint("user_id", name="uq_booking_link_user"),
    )
    op.create_index("idx_booking_links_org", "booking_links", ["organization_id"])

    # ==========================================================================
    # appointments - Booked appointments
    # ==========================================================================
    op.create_table(
        "appointments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_type_id", UUID(as_uuid=True), nullable=True),
        # Client info
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("client_email", postgresql.CITEXT(), nullable=False),
        sa.Column("client_phone", sa.String(20), nullable=False),
        sa.Column("client_notes", sa.Text(), nullable=True),
        sa.Column("client_timezone", sa.String(50), nullable=False),
        # Scheduling
        sa.Column("scheduled_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("meeting_mode", sa.String(20), nullable=False),
        # Status
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("pending_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Approval
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), nullable=True),
        # Cancellation
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "cancelled_by_client",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        # Integrations
        sa.Column("google_event_id", sa.String(255), nullable=True),
        sa.Column("zoom_meeting_id", sa.String(100), nullable=True),
        sa.Column("zoom_join_url", sa.String(500), nullable=True),
        # Tokens
        sa.Column("reschedule_token", sa.String(64), nullable=True),
        sa.Column("cancel_token", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        # Timestamps
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["appointment_type_id"], ["appointment_types.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("idempotency_key", name="uq_appointment_idempotency"),
        sa.UniqueConstraint("reschedule_token", name="uq_appointment_reschedule_token"),
        sa.UniqueConstraint("cancel_token", name="uq_appointment_cancel_token"),
    )
    op.create_index("idx_appointments_user_date", "appointments", ["user_id", "scheduled_start"])
    op.create_index("idx_appointments_org_status", "appointments", ["organization_id", "status"])
    op.create_index("idx_appointments_type", "appointments", ["appointment_type_id"])
    op.create_index(
        "idx_appointments_pending_expiry",
        "appointments",
        ["pending_expires_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # ==========================================================================
    # appointment_email_logs - Email tracking for appointments
    # ==========================================================================
    op.create_table(
        "appointment_email_logs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email_type", sa.String(30), nullable=False),
        sa.Column("recipient_email", postgresql.CITEXT(), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("external_message_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_appointment_email_logs_appt", "appointment_email_logs", ["appointment_id"])
    op.create_index("idx_appointment_email_logs_org", "appointment_email_logs", ["organization_id"])


def downgrade():
    """Drop appointment scheduling tables."""
    op.drop_table("appointment_email_logs")
    op.drop_table("appointments")
    op.drop_table("booking_links")
    op.drop_table("availability_overrides")
    op.drop_table("availability_rules")
    op.drop_table("appointment_types")
