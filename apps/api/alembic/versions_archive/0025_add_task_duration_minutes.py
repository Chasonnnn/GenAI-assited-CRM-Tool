"""Add duration_minutes to tasks

Revision ID: 0025_add_task_duration_minutes
Revises: 0024_enforce_case_ownership_not_null
Create Date: 2025-12-18

Adds an optional duration_minutes column to support meeting-style tasks
with a start time (due_date/due_time) and a derived end time.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0025_add_task_duration_minutes"
down_revision = "0024_enforce_case_ownership_not_null"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("duration_minutes", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("tasks", "duration_minutes")
