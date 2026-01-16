"""Update intended parent statuses to new workflow.

Revision ID: 20260115_1720
Revises: 20260115_1715
Create Date: 2026-01-15 17:20:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260115_1720"
down_revision: Union[str, None] = "20260115_1715"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Map old statuses to new workflow values
    op.execute("""
        UPDATE intended_parents
        SET status = 'ready_to_match'
        WHERE status = 'in_review';

        UPDATE intended_parents
        SET status = 'delivered'
        WHERE status = 'inactive';

        UPDATE intended_parent_status_history
        SET old_status = CASE
            WHEN old_status = 'in_review' THEN 'ready_to_match'
            WHEN old_status = 'inactive' THEN 'delivered'
            ELSE old_status
        END,
        new_status = CASE
            WHEN new_status = 'in_review' THEN 'ready_to_match'
            WHEN new_status = 'inactive' THEN 'delivered'
            ELSE new_status
        END;

        UPDATE status_change_requests
        SET target_status = CASE
            WHEN target_status = 'in_review' THEN 'ready_to_match'
            WHEN target_status = 'inactive' THEN 'delivered'
            ELSE target_status
        END
        WHERE entity_type = 'intended_parent';
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE intended_parents
        SET status = 'in_review'
        WHERE status = 'ready_to_match';

        UPDATE intended_parents
        SET status = 'inactive'
        WHERE status = 'delivered';

        UPDATE intended_parent_status_history
        SET old_status = CASE
            WHEN old_status = 'ready_to_match' THEN 'in_review'
            WHEN old_status = 'delivered' THEN 'inactive'
            ELSE old_status
        END,
        new_status = CASE
            WHEN new_status = 'ready_to_match' THEN 'in_review'
            WHEN new_status = 'delivered' THEN 'inactive'
            ELSE new_status
        END;

        UPDATE status_change_requests
        SET target_status = CASE
            WHEN target_status = 'ready_to_match' THEN 'in_review'
            WHEN target_status = 'delivered' THEN 'inactive'
            ELSE target_status
        END
        WHERE entity_type = 'intended_parent';
    """)
