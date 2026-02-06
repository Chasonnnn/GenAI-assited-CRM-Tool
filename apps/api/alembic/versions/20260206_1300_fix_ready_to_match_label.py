"""Fix Ready to Match label casing.

Revision ID: 20260206_1300
Revises: 20260206_1031
Create Date: 2026-02-06 13:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260206_1300"
down_revision: Union[str, Sequence[str], None] = "20260206_1031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_LABEL = "Ready To Match"
NEW_LABEL = "Ready to Match"


def upgrade() -> None:
    conn = op.get_bind()

    # Update stage label where it matches the old casing (avoid overriding custom labels).
    conn.execute(
        sa.text(
            """
            UPDATE pipeline_stages
            SET label = :new_label,
                updated_at = now()
            WHERE slug = 'ready_to_match'
              AND label = :old_label
            """
        ),
        {"old_label": OLD_LABEL, "new_label": NEW_LABEL},
    )

    # Keep surrogate status_label consistent with stage label for active cases.
    conn.execute(
        sa.text(
            """
            UPDATE surrogates s
            SET status_label = :new_label,
                updated_at = now()
            FROM pipeline_stages ps
            WHERE ps.id = s.stage_id
              AND ps.slug = 'ready_to_match'
              AND s.status_label = :old_label
            """
        ),
        {"old_label": OLD_LABEL, "new_label": NEW_LABEL},
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            UPDATE pipeline_stages
            SET label = :old_label,
                updated_at = now()
            WHERE slug = 'ready_to_match'
              AND label = :new_label
            """
        ),
        {"old_label": OLD_LABEL, "new_label": NEW_LABEL},
    )

    conn.execute(
        sa.text(
            """
            UPDATE surrogates s
            SET status_label = :old_label,
                updated_at = now()
            FROM pipeline_stages ps
            WHERE ps.id = s.stage_id
              AND ps.slug = 'ready_to_match'
              AND s.status_label = :new_label
            """
        ),
        {"old_label": OLD_LABEL, "new_label": NEW_LABEL},
    )
