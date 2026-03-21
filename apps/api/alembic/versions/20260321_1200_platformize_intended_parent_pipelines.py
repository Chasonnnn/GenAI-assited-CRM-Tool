"""platformize intended parent pipelines

Revision ID: 20260321_1200
Revises: 20260320_1100
Create Date: 2026-03-21 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core.stage_definitions import (
    INTENDED_PARENT_PIPELINE_ENTITY,
    SURROGATE_PIPELINE_ENTITY,
    get_default_stage_defs,
)
from app.schemas.pipeline_semantics import (
    default_pipeline_feature_config,
    default_stage_semantics,
)


# revision identifiers, used by Alembic.
revision: str = "20260321_1200"
down_revision: str | Sequence[str] | None = "20260320_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PSEUDO_IP_STATUSES = {"archived", "restored"}


def _actual_ip_stage_key(
    stage_keys: set[str],
    status: str | None,
    fallback_status: str | None = None,
    *,
    default: str = "new",
) -> str:
    normalized_status = str(status or "").strip()
    if normalized_status in stage_keys:
        return normalized_status
    normalized_fallback = str(fallback_status or "").strip()
    if normalized_fallback in stage_keys:
        return normalized_fallback
    return default


def _build_ip_stage_maps(conn: sa.Connection) -> tuple[dict[UUID, dict[str, UUID]], set[str]]:
    rows = conn.execute(
        sa.text(
            """
            SELECT
                p.organization_id AS organization_id,
                ps.id AS stage_id,
                ps.stage_key AS stage_key
            FROM pipelines p
            JOIN pipeline_stages ps ON ps.pipeline_id = p.id
            WHERE p.entity_type = :entity_type
              AND p.is_default = TRUE
              AND ps.is_active = TRUE
            """
        ),
        {"entity_type": INTENDED_PARENT_PIPELINE_ENTITY},
    ).mappings()

    by_org: dict[UUID, dict[str, UUID]] = {}
    all_stage_keys: set[str] = set()
    for row in rows:
        organization_id = row["organization_id"]
        stage_key = row["stage_key"]
        stage_id = row["stage_id"]
        by_org.setdefault(organization_id, {})[stage_key] = stage_id
        all_stage_keys.add(stage_key)
    return by_org, all_stage_keys


def _insert_default_ip_pipelines(conn: sa.Connection) -> None:
    pipeline_insert = sa.text(
        """
        INSERT INTO pipelines (
            id,
            organization_id,
            entity_type,
            name,
            is_default,
            current_version,
            feature_config
        )
        VALUES (
            :id,
            :organization_id,
            :entity_type,
            :name,
            TRUE,
            1,
            :feature_config
        )
        """
    ).bindparams(sa.bindparam("feature_config", type_=postgresql.JSONB()))
    stage_insert = sa.text(
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
            semantics,
            is_active,
            is_intake_stage
        )
        VALUES (
            :id,
            :pipeline_id,
            :stage_key,
            :slug,
            :stage_type,
            :label,
            :color,
            :order,
            :semantics,
            TRUE,
            :is_intake_stage
        )
        """
    ).bindparams(sa.bindparam("semantics", type_=postgresql.JSONB()))

    org_rows = conn.execute(
        sa.text(
            """
            SELECT o.id
            FROM organizations o
            WHERE NOT EXISTS (
                SELECT 1
                FROM pipelines p
                WHERE p.organization_id = o.id
                  AND p.entity_type = :entity_type
                  AND p.is_default = TRUE
            )
            """
        ),
        {"entity_type": INTENDED_PARENT_PIPELINE_ENTITY},
    ).scalars()

    feature_config = default_pipeline_feature_config(INTENDED_PARENT_PIPELINE_ENTITY)
    stage_defs = get_default_stage_defs(INTENDED_PARENT_PIPELINE_ENTITY)

    for organization_id in org_rows:
        pipeline_id = uuid4()
        conn.execute(
            pipeline_insert,
            {
                "id": pipeline_id,
                "organization_id": organization_id,
                "entity_type": INTENDED_PARENT_PIPELINE_ENTITY,
                "name": "Default",
                "feature_config": feature_config,
            },
        )
        for stage in stage_defs:
            conn.execute(
                stage_insert,
                {
                    "id": uuid4(),
                    "pipeline_id": pipeline_id,
                    "stage_key": stage["stage_key"],
                    "slug": stage["slug"],
                    "stage_type": stage["stage_type"],
                    "label": stage["label"],
                    "color": stage["color"],
                    "order": stage["order"],
                    "semantics": default_stage_semantics(
                        stage["stage_key"],
                        stage["stage_type"],
                        INTENDED_PARENT_PIPELINE_ENTITY,
                    ),
                    "is_intake_stage": stage["stage_type"] == "intake",
                },
            )


def _backfill_intended_parent_stage_ids(conn: sa.Connection) -> None:
    update_stmt = sa.text(
        """
        UPDATE intended_parents
        SET stage_id = :stage_id,
            status = :status
        WHERE id = :intended_parent_id
        """
    )

    archived_history_by_ip = {
        row["intended_parent_id"]: row["old_status"]
        for row in conn.execute(
            sa.text(
                """
                SELECT DISTINCT ON (h.intended_parent_id)
                    h.intended_parent_id,
                    h.old_status
                FROM intended_parent_status_history h
                JOIN intended_parents ip ON ip.id = h.intended_parent_id
                WHERE ip.is_archived = TRUE
                  AND h.new_status = 'archived'
                ORDER BY h.intended_parent_id, COALESCE(h.recorded_at, h.changed_at) DESC
                """
            )
        ).mappings()
    }

    stage_ids_by_org, all_stage_keys = _build_ip_stage_maps(conn)

    ip_rows = conn.execute(
        sa.text(
            """
            SELECT id, organization_id, status, is_archived
            FROM intended_parents
            """
        )
    ).mappings()

    for row in ip_rows:
        organization_id = row["organization_id"]
        status = row["status"]
        fallback_status = archived_history_by_ip.get(row["id"]) if row["is_archived"] else None
        target_stage_key = _actual_ip_stage_key(
            all_stage_keys,
            status,
            fallback_status,
        )
        target_stage_id = stage_ids_by_org.get(organization_id, {}).get(target_stage_key)
        if target_stage_id is None:
            target_stage_key = "new"
            target_stage_id = stage_ids_by_org[organization_id][target_stage_key]
        conn.execute(
            update_stmt,
            {
                "intended_parent_id": row["id"],
                "stage_id": target_stage_id,
                "status": target_stage_key,
            },
        )


def _backfill_intended_parent_history_stage_ids(conn: sa.Connection) -> None:
    update_stmt = sa.text(
        """
        UPDATE intended_parent_status_history
        SET old_stage_id = :old_stage_id,
            new_stage_id = :new_stage_id
        WHERE id = :history_id
        """
    )
    stage_ids_by_org, all_stage_keys = _build_ip_stage_maps(conn)

    history_rows = conn.execute(
        sa.text(
            """
            SELECT
                h.id,
                ip.organization_id,
                h.old_status,
                h.new_status
            FROM intended_parent_status_history h
            JOIN intended_parents ip ON ip.id = h.intended_parent_id
            """
        )
    ).mappings()

    for row in history_rows:
        organization_id = row["organization_id"]
        org_stage_ids = stage_ids_by_org.get(organization_id, {})

        old_status = row["old_status"]
        new_status = row["new_status"]

        old_stage_key = None
        new_stage_key = None

        if old_status in all_stage_keys:
            old_stage_key = old_status
        elif old_status in PSEUDO_IP_STATUSES and new_status in all_stage_keys:
            old_stage_key = new_status

        if new_status in all_stage_keys:
            new_stage_key = new_status
        elif new_status in PSEUDO_IP_STATUSES and old_status in all_stage_keys:
            new_stage_key = old_status

        conn.execute(
            update_stmt,
            {
                "history_id": row["id"],
                "old_stage_id": org_stage_ids.get(old_stage_key) if old_stage_key else None,
                "new_stage_id": org_stage_ids.get(new_stage_key) if new_stage_key else None,
            },
        )


def _backfill_intended_parent_request_stage_ids(conn: sa.Connection) -> None:
    update_stmt = sa.text(
        """
        UPDATE status_change_requests
        SET target_stage_id = :target_stage_id
        WHERE id = :request_id
        """
    )
    stage_ids_by_org, all_stage_keys = _build_ip_stage_maps(conn)

    request_rows = conn.execute(
        sa.text(
            """
            SELECT id, organization_id, target_status
            FROM status_change_requests
            WHERE entity_type = :entity_type
              AND target_stage_id IS NULL
            """
        ),
        {"entity_type": INTENDED_PARENT_PIPELINE_ENTITY},
    ).mappings()

    for row in request_rows:
        target_stage_key = _actual_ip_stage_key(all_stage_keys, row["target_status"])
        target_stage_id = stage_ids_by_org.get(row["organization_id"], {}).get(target_stage_key)
        if target_stage_id is None:
            continue
        conn.execute(
            update_stmt,
            {
                "request_id": row["id"],
                "target_stage_id": target_stage_id,
            },
        )


def upgrade() -> None:
    op.add_column(
        "pipelines",
        sa.Column(
            "entity_type",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text(f"'{SURROGATE_PIPELINE_ENTITY}'"),
        ),
    )
    op.create_index("idx_pipelines_org_entity", "pipelines", ["organization_id", "entity_type"])
    op.create_index(
        "uq_pipelines_default_per_entity",
        "pipelines",
        ["organization_id", "entity_type"],
        unique=True,
        postgresql_where=sa.text("is_default = TRUE"),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE pipelines SET entity_type = :entity_type WHERE entity_type IS NULL"),
        {"entity_type": SURROGATE_PIPELINE_ENTITY},
    )

    _insert_default_ip_pipelines(conn)

    op.add_column(
        "intended_parents",
        sa.Column(
            "stage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_stages.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("idx_ip_org_stage", "intended_parents", ["organization_id", "stage_id"])
    _backfill_intended_parent_stage_ids(conn)
    op.alter_column("intended_parents", "stage_id", nullable=False)

    op.add_column(
        "intended_parent_status_history",
        sa.Column(
            "old_stage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "intended_parent_status_history",
        sa.Column(
            "new_stage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    _backfill_intended_parent_history_stage_ids(conn)

    op.execute("DROP INDEX IF EXISTS idx_pending_ip_requests")
    _backfill_intended_parent_request_stage_ids(conn)
    op.create_index(
        "idx_pending_ip_requests",
        "status_change_requests",
        ["organization_id", "entity_id", "target_stage_id", "effective_at"],
        unique=True,
        postgresql_where=sa.text("entity_type = 'intended_parent' AND status = 'pending'"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE status_change_requests
            SET target_status = COALESCE(
                (
                    SELECT ps.stage_key
                    FROM pipeline_stages ps
                    WHERE ps.id = status_change_requests.target_stage_id
                ),
                target_status
            )
            WHERE entity_type = :entity_type
            """
        ),
        {"entity_type": INTENDED_PARENT_PIPELINE_ENTITY},
    )
    op.drop_index("idx_pending_ip_requests", table_name="status_change_requests")
    op.create_index(
        "idx_pending_ip_requests",
        "status_change_requests",
        ["organization_id", "entity_id", "target_status", "effective_at"],
        unique=True,
        postgresql_where=sa.text("entity_type = 'intended_parent' AND status = 'pending'"),
    )

    conn.execute(
        sa.text(
            """
            UPDATE intended_parents
            SET status = 'archived'
            WHERE is_archived = TRUE
            """
        )
    )

    op.drop_column("intended_parent_status_history", "new_stage_id")
    op.drop_column("intended_parent_status_history", "old_stage_id")

    op.drop_index("idx_ip_org_stage", table_name="intended_parents")
    op.drop_column("intended_parents", "stage_id")

    conn.execute(
        sa.text(
            """
            DELETE FROM pipeline_stages
            WHERE pipeline_id IN (
                SELECT id
                FROM pipelines
                WHERE entity_type = :entity_type
            )
            """
        ),
        {"entity_type": INTENDED_PARENT_PIPELINE_ENTITY},
    )
    conn.execute(
        sa.text("DELETE FROM pipelines WHERE entity_type = :entity_type"),
        {"entity_type": INTENDED_PARENT_PIPELINE_ENTITY},
    )

    op.drop_index("uq_pipelines_default_per_entity", table_name="pipelines")
    op.drop_index("idx_pipelines_org_entity", table_name="pipelines")
    op.drop_column("pipelines", "entity_type")
