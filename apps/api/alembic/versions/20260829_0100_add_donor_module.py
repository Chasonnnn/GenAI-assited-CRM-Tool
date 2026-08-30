"""Add the complete donor module.

Revision ID: 20260829_0100
Revises: 20260824_1200
Create Date: 2026-08-29 01:00:00.000000
"""

from collections.abc import Sequence

from app.db.migration_steps import (
    donor_attachments,
    donor_campaigns,
    donor_foundation,
    donor_hosted_forms,
    donor_meta_forms,
    donor_meta_snapshots,
    donor_pipelines,
    donor_stage_governance,
    donor_tasks,
    donor_workflows,
)

revision: str = "20260829_0100"
down_revision: str | Sequence[str] | None = "20260824_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    donor_foundation.upgrade()
    donor_pipelines.upgrade()
    donor_tasks.upgrade()
    donor_workflows.upgrade()
    donor_attachments.upgrade()
    donor_meta_forms.upgrade()
    donor_hosted_forms.upgrade()
    donor_meta_snapshots.upgrade()
    donor_campaigns.upgrade()
    donor_stage_governance.upgrade()


def downgrade() -> None:
    donor_stage_governance.downgrade()
    donor_campaigns.downgrade()
    donor_meta_snapshots.downgrade()
    donor_hosted_forms.downgrade()
    donor_meta_forms.downgrade()
    donor_attachments.downgrade()
    donor_workflows.downgrade()
    donor_tasks.downgrade()
    donor_pipelines.downgrade()
    donor_foundation.downgrade()
