"""Enforce non-null case ownership

Revision ID: 0024_enforce_case_ownership_not_null
Revises: 0023_add_queues_ownership
Create Date: 2025-12-18

Ensures every case has an owner (Salesforce-style):
- owner_type: 'user' | 'queue'
- owner_id: UUID of the owner

Backfills any legacy rows where owner_type/owner_id are null by assigning them to the
org's default "Unassigned" queue, then makes columns NOT NULL.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0024_enforce_case_ownership_not_null"
down_revision = "0023_add_queues_ownership"
branch_labels = None
depends_on = None


def upgrade():
    # Create the default queue for orgs that have unowned cases (idempotent).
    op.execute(
        """
        INSERT INTO queues (id, organization_id, name, description, is_active, created_at, updated_at)
        SELECT gen_random_uuid(), c.organization_id, 'Unassigned', 'System default queue', TRUE, now(), now()
        FROM cases c
        WHERE (c.owner_type IS NULL OR c.owner_id IS NULL)
        GROUP BY c.organization_id
        ON CONFLICT (organization_id, name) DO NOTHING
        """
    )

    # Backfill any remaining owner nulls to the default queue.
    op.execute(
        """
        UPDATE cases c
        SET owner_type = 'queue',
            owner_id = q.id
        FROM queues q
        WHERE q.organization_id = c.organization_id
          AND q.name = 'Unassigned'
          AND (c.owner_type IS NULL OR c.owner_id IS NULL)
        """
    )

    op.alter_column("cases", "owner_type", existing_type=sa.String(length=10), nullable=False)
    op.alter_column("cases", "owner_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)


def downgrade():
    op.alter_column("cases", "owner_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column("cases", "owner_type", existing_type=sa.String(length=10), nullable=True)
