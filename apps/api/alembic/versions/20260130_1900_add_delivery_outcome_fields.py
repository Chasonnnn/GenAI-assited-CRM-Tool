"""Add delivery outcome fields to surrogates.

Revision ID: 20260130_1900
Revises: 20260130_0300
Create Date: 2026-01-30 19:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db import types


# revision identifiers, used by Alembic.
revision: str = "20260130_1900"
down_revision: Union[str, Sequence[str], None] = "20260130_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "surrogates",
        sa.Column("delivery_baby_gender", types.EncryptedString(), nullable=True),
    )
    op.add_column(
        "surrogates",
        sa.Column("delivery_baby_weight", types.EncryptedString(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("surrogates", "delivery_baby_weight")
    op.drop_column("surrogates", "delivery_baby_gender")
