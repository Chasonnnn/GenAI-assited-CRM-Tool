"""Add email domain and phone last4 helpers for ops filtering.

Adds nullable helper columns:
- email_domain
- phone_last4

Indexes are active-only to match default list behavior.

Revision ID: 20260129_1300
Revises: 20260129_1200
Create Date: 2026-01-29 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260129_1300"
down_revision: Union[str, None] = "20260129_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "surrogates",
        sa.Column("email_domain", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "surrogates",
        sa.Column("phone_last4", sa.String(length=4), nullable=True),
    )
    op.add_column(
        "intended_parents",
        sa.Column("email_domain", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "intended_parents",
        sa.Column("phone_last4", sa.String(length=4), nullable=True),
    )

    op.create_index(
        "idx_surrogates_active_email_domain",
        "surrogates",
        ["organization_id", "email_domain"],
        unique=False,
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index(
        "idx_surrogates_active_phone_last4",
        "surrogates",
        ["organization_id", "phone_last4"],
        unique=False,
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index(
        "idx_ip_active_email_domain",
        "intended_parents",
        ["organization_id", "email_domain"],
        unique=False,
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index(
        "idx_ip_active_phone_last4",
        "intended_parents",
        ["organization_id", "phone_last4"],
        unique=False,
        postgresql_where=sa.text("is_archived = FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_ip_active_phone_last4", table_name="intended_parents")
    op.drop_index("idx_ip_active_email_domain", table_name="intended_parents")
    op.drop_index("idx_surrogates_active_phone_last4", table_name="surrogates")
    op.drop_index("idx_surrogates_active_email_domain", table_name="surrogates")

    op.drop_column("intended_parents", "phone_last4")
    op.drop_column("intended_parents", "email_domain")
    op.drop_column("surrogates", "phone_last4")
    op.drop_column("surrogates", "email_domain")
