"""Update stage label casing for transfer cycle and OB care.

Revision ID: 20260117_1045
Revises: 20260117_1030
Create Date: 2026-01-17 10:45:00
"""

from alembic import op


revision = "20260117_1045"
down_revision = "20260117_1030"
branch_labels = None
depends_on = None


LABEL_UPDATES = [
    ("transfer_cycle", "Transfer Cycle initiated", "Transfer Cycle Initiated"),
    ("ob_care_established", "OB Care established", "OB Care Established"),
]


def _update_labels(label_map: list[tuple[str, str, str]]) -> None:
    for slug, _old_label, new_label in label_map:
        op.execute(
            f"""
            UPDATE pipeline_stages
            SET label = '{new_label}'
            WHERE slug = '{slug}'
            """
        )
        op.execute(
            f"""
            UPDATE surrogates s
            SET status_label = '{new_label}'
            FROM pipeline_stages p
            WHERE s.stage_id = p.id
              AND p.slug = '{slug}'
            """
        )
        op.execute(
            f"""
            UPDATE surrogate_status_history h
            SET to_label_snapshot = '{new_label}'
            FROM pipeline_stages p
            WHERE h.to_stage_id = p.id
              AND p.slug = '{slug}'
            """
        )
        op.execute(
            f"""
            UPDATE surrogate_status_history h
            SET from_label_snapshot = '{new_label}'
            FROM pipeline_stages p
            WHERE h.from_stage_id = p.id
              AND p.slug = '{slug}'
            """
        )


def _revert_labels(label_map: list[tuple[str, str, str]]) -> None:
    for slug, old_label, _new_label in label_map:
        op.execute(
            f"""
            UPDATE pipeline_stages
            SET label = '{old_label}'
            WHERE slug = '{slug}'
            """
        )
        op.execute(
            f"""
            UPDATE surrogates s
            SET status_label = '{old_label}'
            FROM pipeline_stages p
            WHERE s.stage_id = p.id
              AND p.slug = '{slug}'
            """
        )
        op.execute(
            f"""
            UPDATE surrogate_status_history h
            SET to_label_snapshot = '{old_label}'
            FROM pipeline_stages p
            WHERE h.to_stage_id = p.id
              AND p.slug = '{slug}'
            """
        )
        op.execute(
            f"""
            UPDATE surrogate_status_history h
            SET from_label_snapshot = '{old_label}'
            FROM pipeline_stages p
            WHERE h.from_stage_id = p.id
              AND p.slug = '{slug}'
            """
        )


def upgrade() -> None:
    _update_labels(LABEL_UPDATES)


def downgrade() -> None:
    _revert_labels(LABEL_UPDATES)
