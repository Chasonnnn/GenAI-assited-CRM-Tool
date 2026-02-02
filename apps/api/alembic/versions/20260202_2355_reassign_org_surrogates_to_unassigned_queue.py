"""Reassign org surrogates to Unassigned queue.

Revision ID: 20260202_2355
Revises: 20260202_2350
Create Date: 2026-02-02 23:55:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260202_2355"
down_revision: Union[str, Sequence[str], None] = "20260202_2350"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORG_ID = "e27e066a-2841-4da5-89ae-98d0735d55b1"
DEFAULT_QUEUE_NAME = "Unassigned"
DEFAULT_QUEUE_DESCRIPTION = "System default queue"


def upgrade() -> None:
    conn = op.get_bind()

    org_exists = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM organizations
            WHERE id = :org_id
            """
        ),
        {"org_id": ORG_ID},
    ).first()

    if not org_exists:
        return

    queue_row = conn.execute(
        sa.text(
            """
            SELECT id, is_active
            FROM queues
            WHERE organization_id = :org_id AND name = :name
            """
        ),
        {"org_id": ORG_ID, "name": DEFAULT_QUEUE_NAME},
    ).first()

    if queue_row:
        queue_id = queue_row.id
        if queue_row.is_active is False:
            conn.execute(
                sa.text(
                    """
                    UPDATE queues
                    SET is_active = TRUE, updated_at = now()
                    WHERE id = :queue_id
                    """
                ),
                {"queue_id": queue_id},
            )
    else:
        queue_id = conn.execute(
            sa.text(
                """
                INSERT INTO queues (organization_id, name, description, is_active)
                VALUES (:org_id, :name, :description, TRUE)
                RETURNING id
                """
            ),
            {
                "org_id": ORG_ID,
                "name": DEFAULT_QUEUE_NAME,
                "description": DEFAULT_QUEUE_DESCRIPTION,
            },
        ).scalar_one()

    conn.execute(
        sa.text(
            """
            UPDATE surrogates
            SET owner_type = 'queue',
                owner_id = :queue_id,
                assigned_at = NULL,
                updated_at = now()
            WHERE organization_id = :org_id
            """
        ),
        {"queue_id": queue_id, "org_id": ORG_ID},
    )


def downgrade() -> None:
    pass
