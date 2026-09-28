"""Record the stage effective time on Zapier outbound events.

Replaying a skipped surrogate event re-runs enqueue with the original effective
time, which surrogate rows did not store. Existing rows keep NULL and are not
replayable; donor replays read the time from donor_status_history.

Revision ID: 20260928_1340_zapier_event_effective_at
Revises: 20260928_1320_donor_workflow_source_canonical
"""

import sqlalchemy as sa

from alembic import op

revision = "20260928_1340_zapier_event_effective_at"
down_revision = "20260928_1320_donor_workflow_source_canonical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.add_column(
        "zapier_outbound_events",
        sa.Column("effective_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_column("zapier_outbound_events", "effective_at")
