"""Update second_hcg_confirmed label casing.

Revision ID: 20260117_1015
Revises: 20260117_1000
Create Date: 2026-01-17 10:15:00
"""

from alembic import op


revision = "20260117_1015"
down_revision = "20260117_1000"
branch_labels = None
depends_on = None


OLD_LABEL = "Second Hcg Confirmed"
NEW_LABEL = "Second hCG confirmed"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE pipeline_stages
        SET label = '{NEW_LABEL}'
        WHERE slug = 'second_hcg_confirmed'
        """
    )
    op.execute(
        f"""
        UPDATE surrogates s
        SET status_label = '{NEW_LABEL}'
        FROM pipeline_stages p
        WHERE s.stage_id = p.id
          AND p.slug = 'second_hcg_confirmed'
        """
    )
    op.execute(
        f"""
        UPDATE surrogate_status_history h
        SET to_label_snapshot = '{NEW_LABEL}'
        FROM pipeline_stages p
        WHERE h.to_stage_id = p.id
          AND p.slug = 'second_hcg_confirmed'
        """
    )
    op.execute(
        f"""
        UPDATE surrogate_status_history h
        SET from_label_snapshot = '{NEW_LABEL}'
        FROM pipeline_stages p
        WHERE h.from_stage_id = p.id
          AND p.slug = 'second_hcg_confirmed'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE pipeline_stages
        SET label = '{OLD_LABEL}'
        WHERE slug = 'second_hcg_confirmed'
        """
    )
    op.execute(
        f"""
        UPDATE surrogates s
        SET status_label = '{OLD_LABEL}'
        FROM pipeline_stages p
        WHERE s.stage_id = p.id
          AND p.slug = 'second_hcg_confirmed'
        """
    )
    op.execute(
        f"""
        UPDATE surrogate_status_history h
        SET to_label_snapshot = '{OLD_LABEL}'
        FROM pipeline_stages p
        WHERE h.to_stage_id = p.id
          AND p.slug = 'second_hcg_confirmed'
        """
    )
    op.execute(
        f"""
        UPDATE surrogate_status_history h
        SET from_label_snapshot = '{OLD_LABEL}'
        FROM pipeline_stages p
        WHERE h.from_stage_id = p.id
          AND p.slug = 'second_hcg_confirmed'
        """
    )
