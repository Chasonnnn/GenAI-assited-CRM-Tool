"""Rebuild the enrollment-confirmation uniqueness predicate.

Revision ID: 20260824_1150
Revises: 20260804_0040
Create Date: 2026-08-25 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260824_1150"
down_revision: str | Sequence[str] | None = "20260804_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "uq_message_delivery_enrollment_epoch",
        table_name="message_deliveries",
    )
    op.create_index(
        "uq_message_delivery_enrollment_epoch",
        "message_deliveries",
        ["organization_id", "contact_id", "purpose", "consent_evidence_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_enrollment_confirmation = true AND consent_evidence_id IS NOT NULL "
            "AND status NOT IN ('failed', 'cancelled')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_message_delivery_enrollment_epoch",
        table_name="message_deliveries",
    )
    op.create_index(
        "uq_message_delivery_enrollment_epoch",
        "message_deliveries",
        ["organization_id", "contact_id", "purpose", "consent_evidence_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_enrollment_confirmation = true AND consent_evidence_id IS NOT NULL"
        ),
    )
