"""Snapshot immutable attachment metadata on outbound email logs.

Revision ID: 20260723_0190
Revises: 20260723_0180
Create Date: 2026-07-23 03:40:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260723_0190"
down_revision = "20260723_0180"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_logs",
        sa.Column(
            "attachment_manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_email_logs_attachment_manifest_array",
        "email_logs",
        "jsonb_typeof(attachment_manifest) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_email_logs_attachment_manifest_array",
        "email_logs",
        type_="check",
    )
    op.drop_column("email_logs", "attachment_manifest")
