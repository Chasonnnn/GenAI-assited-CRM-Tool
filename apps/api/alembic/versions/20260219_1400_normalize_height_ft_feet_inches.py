"""Normalize stored surrogate heights from feet.inches shorthand.

Revision ID: 20260219_1400
Revises: 20260213_0900
Create Date: 2026-02-19 14:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260219_1400"
down_revision: Union[str, Sequence[str], None] = "20260213_0900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Historical entries often used feet.inches shorthand (e.g. 5.6 for 5 ft 6 in).
    # Re-normalize all plausible height values in-place so BMI calculations align.
    op.execute(
        """
        WITH normalized AS (
            SELECT
                id,
                ROUND(
                    (
                        TRUNC(height_ft)
                        + (ROUND((height_ft - TRUNC(height_ft)) * 10)::numeric / 12.0)
                    )::numeric,
                    1
                ) AS normalized_height_ft
            FROM surrogates
            WHERE height_ft IS NOT NULL
              AND height_ft BETWEEN 3 AND 8
        )
        UPDATE surrogates AS s
        SET height_ft = n.normalized_height_ft
        FROM normalized AS n
        WHERE s.id = n.id
          AND s.height_ft IS DISTINCT FROM n.normalized_height_ft
        """
    )


def downgrade() -> None:
    # Irreversible data migration: previous shorthand intent cannot be reconstructed.
    pass
