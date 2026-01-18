"""Reorder default pipeline stages so interview follows application submission.

Revision ID: 20260117_0935
Revises: 20260117_0900
Create Date: 2026-01-17
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260117_0935"
down_revision: Union[str, Sequence[str], None] = "20260117_0900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _apply_order(prefer_application_first: bool) -> None:
    if prefer_application_first:
        app_expr = "LEAST(app_order, interview_order)"
        interview_expr = "GREATEST(app_order, interview_order)"
    else:
        app_expr = "GREATEST(app_order, interview_order)"
        interview_expr = "LEAST(app_order, interview_order)"

    op.execute(
        f"""
        WITH defaults AS (
            SELECT
                pipeline_id,
                MAX(CASE WHEN slug = 'application_submitted' THEN "order" END) AS app_order,
                MAX(CASE WHEN slug = 'interview_scheduled' THEN "order" END) AS interview_order
            FROM pipeline_stages
            WHERE pipeline_id IN (SELECT id FROM pipelines WHERE is_default = true)
              AND is_active = true
            GROUP BY pipeline_id
        ),
        updates AS (
            SELECT
                pipeline_id,
                {app_expr} AS new_app_order,
                {interview_expr} AS new_interview_order
            FROM defaults
            WHERE app_order IS NOT NULL AND interview_order IS NOT NULL
        )
        UPDATE pipeline_stages ps
        SET "order" = CASE
                WHEN ps.slug = 'application_submitted' THEN updates.new_app_order
                WHEN ps.slug = 'interview_scheduled' THEN updates.new_interview_order
                ELSE ps."order"
            END,
            updated_at = NOW()
        FROM updates
        WHERE ps.pipeline_id = updates.pipeline_id
          AND ps.slug IN ('application_submitted', 'interview_scheduled')
        """
    )


def upgrade() -> None:
    _apply_order(prefer_application_first=True)


def downgrade() -> None:
    _apply_order(prefer_application_first=False)
