"""align intake pool grant timestamp timezones

Revision ID: 20260615_0945
Revises: 20260615_0900
Create Date: 2026-06-15 09:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260615_0945"
down_revision: str | Sequence[str] | None = "20260615_0900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE intake_pool_access_grants
        ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
        USING created_at AT TIME ZONE 'UTC'
        """
    )
    op.execute(
        """
        ALTER TABLE intake_pool_access_grants
        ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE
        USING updated_at AT TIME ZONE 'UTC'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE intake_pool_access_grants
        ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE
        USING updated_at AT TIME ZONE 'UTC'
        """
    )
    op.execute(
        """
        ALTER TABLE intake_pool_access_grants
        ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE
        USING created_at AT TIME ZONE 'UTC'
        """
    )
