"""add surrogate on-hold support

Revision ID: 20260306_1400
Revises: 20260303_1000
Create Date: 2026-03-06 14:00:00.000000

"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260306_1400"
down_revision: Union[str, Sequence[str], None] = "20260303_1000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ON_HOLD_STAGE_KEY = "on_hold"
ON_HOLD_LABEL = "On-Hold"
ON_HOLD_COLOR = "#B4536A"
ON_HOLD_STAGE_TYPE = "paused"


def _all_pipeline_stages(conn, pipeline_id):
    return conn.execute(
        sa.text(
            """
            SELECT
                id,
                pipeline_id,
                stage_key,
                slug,
                label,
                color,
                stage_type,
                "order",
                is_active,
                deleted_at
            FROM pipeline_stages
            WHERE pipeline_id = :pipeline_id
            ORDER BY "order", created_at, id
            """
        ),
        {"pipeline_id": pipeline_id},
    ).mappings().all()


def _active_ordered_stages(stages):
    return [stage for stage in stages if stage["deleted_at"] is None]


def _find_on_hold_stage(stages):
    for stage in stages:
        stage_key = (stage["stage_key"] or "").strip().lower()
        slug = (stage["slug"] or "").strip().lower()
        if stage_key == ON_HOLD_STAGE_KEY or slug == ON_HOLD_STAGE_KEY:
            return stage
    return None


def _reorder_with_on_hold(conn, pipeline_id) -> None:
    stages = _all_pipeline_stages(conn, pipeline_id)
    if not stages:
        return

    now = datetime.utcnow()
    on_hold_stage = _find_on_hold_stage(stages)
    active_stages = _active_ordered_stages(stages)

    ordered_active = [
        stage for stage in active_stages if not _is_on_hold_stage(stage)
    ]
    insert_at = next(
        (index for index, stage in enumerate(ordered_active) if stage["stage_type"] == "terminal"),
        len(ordered_active),
    )

    if on_hold_stage is None:
        on_hold_id = uuid.uuid4()
        conn.execute(
            sa.text(
                """
                INSERT INTO pipeline_stages (
                    id,
                    pipeline_id,
                    stage_key,
                    slug,
                    stage_type,
                    label,
                    color,
                    "order",
                    is_active,
                    deleted_at,
                    is_intake_stage,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :pipeline_id,
                    :stage_key,
                    :slug,
                    :stage_type,
                    :label,
                    :color,
                    0,
                    TRUE,
                    NULL,
                    FALSE,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": on_hold_id,
                "pipeline_id": pipeline_id,
                "stage_key": ON_HOLD_STAGE_KEY,
                "slug": ON_HOLD_STAGE_KEY,
                "stage_type": ON_HOLD_STAGE_TYPE,
                "label": ON_HOLD_LABEL,
                "color": ON_HOLD_COLOR,
                "created_at": now,
                "updated_at": now,
            },
        )
        on_hold_stage = {"id": on_hold_id}
    else:
        conn.execute(
            sa.text(
                """
                UPDATE pipeline_stages
                SET
                    stage_key = :stage_key,
                    slug = :slug,
                    stage_type = :stage_type,
                    label = :label,
                    color = :color,
                    is_active = TRUE,
                    deleted_at = NULL,
                    is_intake_stage = FALSE,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "id": on_hold_stage["id"],
                "stage_key": ON_HOLD_STAGE_KEY,
                "slug": ON_HOLD_STAGE_KEY,
                "stage_type": ON_HOLD_STAGE_TYPE,
                "label": ON_HOLD_LABEL,
                "color": ON_HOLD_COLOR,
                "updated_at": now,
            },
        )

    ordered_active.insert(insert_at, {"id": on_hold_stage["id"]})
    for order, stage in enumerate(ordered_active, start=1):
        conn.execute(
            sa.text(
                """
                UPDATE pipeline_stages
                SET "order" = :order, updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {"id": stage["id"], "order": order, "updated_at": now},
        )


def _is_on_hold_stage(stage) -> bool:
    stage_key = (stage.get("stage_key") or "").strip().lower()
    slug = (stage.get("slug") or "").strip().lower()
    return stage_key == ON_HOLD_STAGE_KEY or slug == ON_HOLD_STAGE_KEY


def _remove_on_hold_stage(conn, pipeline_id) -> None:
    stages = _all_pipeline_stages(conn, pipeline_id)
    on_hold_stage = _find_on_hold_stage(stages)
    if on_hold_stage is None:
        return

    active_stages = _active_ordered_stages(stages)
    remaining_stages = [stage for stage in active_stages if stage["id"] != on_hold_stage["id"]]
    fallback_stage = next(
        (stage for stage in remaining_stages if stage["stage_type"] == "terminal"),
        remaining_stages[-1] if remaining_stages else None,
    )

    if fallback_stage is not None:
        conn.execute(
            sa.text(
                """
                UPDATE surrogates
                SET
                    stage_id = :stage_id,
                    status_label = :status_label
                WHERE stage_id = :on_hold_stage_id
                """
            ),
            {
                "stage_id": fallback_stage["id"],
                "status_label": fallback_stage["label"],
                "on_hold_stage_id": on_hold_stage["id"],
            },
        )

    conn.execute(
        sa.text("DELETE FROM pipeline_stages WHERE id = :stage_id"),
        {"stage_id": on_hold_stage["id"]},
    )

    now = datetime.utcnow()
    for order, stage in enumerate(remaining_stages, start=1):
        conn.execute(
            sa.text(
                """
                UPDATE pipeline_stages
                SET "order" = :order, updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {"id": stage["id"], "order": order, "updated_at": now},
        )


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "surrogates",
        sa.Column("paused_from_stage_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "surrogates",
        sa.Column("on_hold_follow_up_task_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_surrogates_paused_from_stage_id",
        "surrogates",
        "pipeline_stages",
        ["paused_from_stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_surrogates_on_hold_follow_up_task_id",
        "surrogates",
        "tasks",
        ["on_hold_follow_up_task_id"],
        ["id"],
        ondelete="SET NULL",
    )

    conn = op.get_bind()
    pipeline_ids = conn.execute(sa.text("SELECT id FROM pipelines")).scalars().all()
    for pipeline_id in pipeline_ids:
        _reorder_with_on_hold(conn, pipeline_id)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    pipeline_ids = conn.execute(sa.text("SELECT id FROM pipelines")).scalars().all()
    for pipeline_id in pipeline_ids:
        _remove_on_hold_stage(conn, pipeline_id)

    op.drop_constraint(
        "fk_surrogates_on_hold_follow_up_task_id",
        "surrogates",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_surrogates_paused_from_stage_id",
        "surrogates",
        type_="foreignkey",
    )
    op.drop_column("surrogates", "on_hold_follow_up_task_id")
    op.drop_column("surrogates", "paused_from_stage_id")
