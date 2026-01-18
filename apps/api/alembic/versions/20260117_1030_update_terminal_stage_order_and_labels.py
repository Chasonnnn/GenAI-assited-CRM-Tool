"""Update terminal stage order and pipeline labels.

Revision ID: 20260117_1030
Revises: 20260117_1015
Create Date: 2026-01-17 10:30:00
"""

from alembic import op


revision = "20260117_1030"
down_revision = "20260117_1015"
branch_labels = None
depends_on = None


LABEL_UPDATES = [
    ("transfer_cycle", "Transfer Cycle", "Transfer Cycle initiated"),
    ("ob_care_established", "Ob Care Established", "OB Care established"),
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

    op.execute(
        """
        WITH max_orders AS (
            SELECT pipeline_id, MAX("order") AS max_order
            FROM pipeline_stages
            WHERE slug NOT IN ('lost', 'disqualified')
            GROUP BY pipeline_id
        )
        UPDATE pipeline_stages s
        SET "order" = m.max_order + CASE WHEN s.slug = 'lost' THEN 1 ELSE 2 END
        FROM max_orders m
        WHERE s.pipeline_id = m.pipeline_id
          AND s.slug IN ('lost', 'disqualified')
        """
    )


def downgrade() -> None:
    _revert_labels(LABEL_UPDATES)

    op.execute(
        """
        WITH delivered_orders AS (
            SELECT pipeline_id, "order" AS delivered_order
            FROM pipeline_stages
            WHERE slug = 'delivered'
        )
        UPDATE pipeline_stages s
        SET "order" = d.delivered_order - CASE WHEN s.slug = 'lost' THEN 2 ELSE 1 END
        FROM delivered_orders d
        WHERE s.pipeline_id = d.pipeline_id
          AND s.slug IN ('lost', 'disqualified')
        """
    )
