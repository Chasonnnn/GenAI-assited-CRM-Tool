"""Extend appointment idempotency_key length.

Revision ID: 20260202_2315
Revises: 20260202_1600
Create Date: 2026-02-02 23:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260202_2315"
down_revision: Union[str, Sequence[str], None] = "20260202_1600"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "appointments",
        "idempotency_key",
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "appointments",
        "idempotency_key",
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
