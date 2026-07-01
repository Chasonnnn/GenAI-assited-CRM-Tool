"""Add indexes for intelligent suggestion summary queries.

Revision ID: 20260701_1025
Revises: 20260624_1730
Create Date: 2026-07-01 10:25:00
"""

from alembic import op


revision = "20260701_1025"
down_revision = "20260624_1730"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_surrogate_activity_org_surrogate_time",
        "surrogate_activity_log",
        ["organization_id", "surrogate_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_surrogate_activity_org_type_surrogate_time",
        "surrogate_activity_log",
        ["organization_id", "activity_type", "surrogate_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_appointments_org_status_surrogate",
        "appointments",
        ["organization_id", "status", "surrogate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_appointments_org_status_surrogate",
        table_name="appointments",
    )
    op.drop_index(
        "idx_surrogate_activity_org_type_surrogate_time",
        table_name="surrogate_activity_log",
    )
    op.drop_index(
        "idx_surrogate_activity_org_surrogate_time",
        table_name="surrogate_activity_log",
    )
