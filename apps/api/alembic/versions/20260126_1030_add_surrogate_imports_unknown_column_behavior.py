"""Ensure surrogate_imports.unknown_column_behavior exists.

Some developer databases were stamped to the import templates migration after that
migration was edited, leaving `surrogate_imports.unknown_column_behavior` missing.
This migration makes the column exist (idempotently) and enforces the expected
default + NOT NULL constraint.

Revision ID: 20260126_1030
Revises: 20260126_1000
Create Date: 2026-01-26 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260126_1030"
down_revision: Union[str, Sequence[str], None] = "20260126_1000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL for IF NOT EXISTS support (Postgres).
    op.execute(
        """
        ALTER TABLE surrogate_imports
        ADD COLUMN IF NOT EXISTS unknown_column_behavior VARCHAR(20)
        """
    )
    op.execute(
        """
        ALTER TABLE surrogate_imports
        ALTER COLUMN unknown_column_behavior SET DEFAULT 'ignore'
        """
    )
    op.execute(
        """
        UPDATE surrogate_imports
        SET unknown_column_behavior = 'ignore'
        WHERE unknown_column_behavior IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE surrogate_imports
        ALTER COLUMN unknown_column_behavior SET NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE surrogate_imports
        DROP COLUMN IF EXISTS unknown_column_behavior
        """
    )
