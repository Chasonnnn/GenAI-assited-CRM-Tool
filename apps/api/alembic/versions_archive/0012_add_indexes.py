"""Add performance indexes

Revision ID: 0012_add_indexes
Revises: ab9ee2996572
Create Date: 2025-12-16

This migration is a placeholder. All necessary indexes are already defined
in the SQLAlchemy model __table_args__ and were created when the tables
were first made.

Indexes exist for:
- Cases: org+status, org+assigned_to_user_id, org+created_at, org active
- Tasks: org+assigned_to_user_id+is_completed, org+due_date (not completed)
- AI Messages: conversation_id+created_at
- AI Conversations: user_id+org_id, entity lookup

No additional indexes needed at this time.
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0012_add_indexes"
down_revision: Union[str, Sequence[str], None] = "ab9ee2996572"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: indexes already exist from model definitions."""
    pass


def downgrade() -> None:
    """No-op."""
    pass
