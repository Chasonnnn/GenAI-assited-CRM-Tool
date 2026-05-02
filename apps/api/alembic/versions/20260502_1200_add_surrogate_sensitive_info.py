"""add surrogate sensitive personal info

Revision ID: 20260502_1200
Revises: 20260406_1700
Create Date: 2026-05-02 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260502_1200"
down_revision: Union[str, None] = "20260406_1700"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("surrogates", sa.Column("marital_status", sa.String(length=100), nullable=True))
    op.add_column("surrogates", sa.Column("ssn", sa.Text(), nullable=True))
    op.add_column("surrogates", sa.Column("ssn_last4", sa.String(length=4), nullable=True))
    op.add_column("surrogates", sa.Column("partner_name", sa.String(length=255), nullable=True))
    op.add_column("surrogates", sa.Column("partner_email", sa.Text(), nullable=True))
    op.add_column("surrogates", sa.Column("partner_email_hash", sa.String(length=64), nullable=True))
    op.add_column("surrogates", sa.Column("partner_phone", sa.Text(), nullable=True))
    op.add_column("surrogates", sa.Column("partner_phone_last4", sa.String(length=4), nullable=True))
    op.add_column("surrogates", sa.Column("partner_ssn", sa.Text(), nullable=True))
    op.add_column("surrogates", sa.Column("partner_ssn_last4", sa.String(length=4), nullable=True))
    op.add_column("surrogates", sa.Column("partner_address_line1", sa.Text(), nullable=True))
    op.add_column("surrogates", sa.Column("partner_address_line2", sa.Text(), nullable=True))
    op.add_column("surrogates", sa.Column("partner_city", sa.String(length=100), nullable=True))
    op.add_column("surrogates", sa.Column("partner_state", sa.String(length=2), nullable=True))
    op.add_column("surrogates", sa.Column("partner_postal", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("surrogates", "partner_postal")
    op.drop_column("surrogates", "partner_state")
    op.drop_column("surrogates", "partner_city")
    op.drop_column("surrogates", "partner_address_line2")
    op.drop_column("surrogates", "partner_address_line1")
    op.drop_column("surrogates", "partner_ssn_last4")
    op.drop_column("surrogates", "partner_ssn")
    op.drop_column("surrogates", "partner_phone_last4")
    op.drop_column("surrogates", "partner_phone")
    op.drop_column("surrogates", "partner_email_hash")
    op.drop_column("surrogates", "partner_email")
    op.drop_column("surrogates", "partner_name")
    op.drop_column("surrogates", "ssn_last4")
    op.drop_column("surrogates", "ssn")
    op.drop_column("surrogates", "marital_status")
