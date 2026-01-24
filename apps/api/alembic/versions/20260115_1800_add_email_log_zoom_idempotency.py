"""Add idempotency keys to email logs and zoom meetings.

Revision ID: 20260115_1800
Revises: 20260115_1720
Create Date: 2026-01-15 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260115_1800"
down_revision: Union[str, None] = "20260115_1720"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("email_logs", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.create_index(
        "uq_email_logs_idempotency",
        "email_logs",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.add_column(
        "zoom_meetings", sa.Column("idempotency_key", sa.String(length=255), nullable=True)
    )
    op.create_index(
        "uq_zoom_meetings_idempotency",
        "zoom_meetings",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_zoom_meetings_idempotency", table_name="zoom_meetings")
    op.drop_column("zoom_meetings", "idempotency_key")

    op.drop_index("uq_email_logs_idempotency", table_name="email_logs")
    op.drop_column("email_logs", "idempotency_key")
