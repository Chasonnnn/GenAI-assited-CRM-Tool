"""introduce stage_key and cut over qualified to pre_qualified

Revision ID: 20260227_1200
Revises: 20260225_1100
Create Date: 2026-02-27 12:00:00.000000
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260227_1200"
down_revision: str | Sequence[str] | None = "20260225_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_EVENT_MAPPING = [
    {"stage_key": "new_unread", "event_name": "Lead", "enabled": True},
    {"stage_key": "pre_qualified", "event_name": "PreQualifiedLead", "enabled": True},
    {"stage_key": "matched", "event_name": "ConvertedLead", "enabled": True},
]


def _canonical_stage_key(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "qualified":
        return "pre_qualified"
    return normalized


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _normalize_event_mapping(mapping: Any) -> list[dict[str, Any]]:
    if not isinstance(mapping, list):
        return DEFAULT_EVENT_MAPPING

    normalized: list[dict[str, Any]] = []
    for item in mapping:
        if not isinstance(item, dict):
            continue

        stage_key = _canonical_stage_key(item.get("stage_key") or item.get("stage_slug"))
        event_name = str(item.get("event_name") or "").strip()
        enabled = bool(item.get("enabled", True))

        if not stage_key or not event_name:
            continue

        if stage_key == "pre_qualified" and event_name == "QualifiedLead":
            event_name = "PreQualifiedLead"

        normalized.append(
            {
                "stage_key": stage_key,
                "event_name": event_name,
                "enabled": enabled,
            }
        )

    return normalized or DEFAULT_EVENT_MAPPING


def _load_default_stage_maps(conn) -> dict[Any, dict[str, dict[str, Any]]]:
    rows = conn.execute(
        sa.text(
            """
            SELECT
                p.organization_id AS organization_id,
                s.id AS stage_id,
                s.slug AS slug,
                s.stage_key AS stage_key
            FROM pipelines p
            JOIN pipeline_stages s ON s.pipeline_id = p.id
            WHERE p.is_default = true
              AND s.is_active = true
            """
        )
    ).mappings()

    maps: dict[Any, dict[str, dict[str, Any]]] = {}
    for row in rows:
        org_id = row["organization_id"]
        if org_id not in maps:
            maps[org_id] = {"by_key": {}, "by_slug": {}}

        stage_id = row["stage_id"]
        stage_key = _canonical_stage_key(row["stage_key"] or row["slug"])
        stage_slug = str(row["slug"] or "").strip().lower()

        maps[org_id]["by_key"].setdefault(stage_key, stage_id)
        maps[org_id]["by_slug"].setdefault(stage_slug, stage_id)

    return maps


def _resolve_stage_id(
    stage_map: dict[str, dict[str, Any]] | None,
    stage_ref: Any,
):
    if not stage_map:
        return None
    key = _canonical_stage_key(stage_ref)
    if key in stage_map["by_key"]:
        return stage_map["by_key"][key]
    slug = str(stage_ref or "").strip().lower()
    return stage_map["by_slug"].get(slug)


def _rewrite_workflow_trigger_configs(conn) -> None:
    stage_maps = _load_default_stage_maps(conn)

    for table_name in ("automation_workflows", "workflow_templates"):
        rows = conn.execute(
            sa.text(
                f"SELECT id, organization_id, trigger_config FROM {table_name}"  # noqa: S608
            )
        ).mappings()

        for row in rows:
            trigger_config = row["trigger_config"]
            if not isinstance(trigger_config, dict):
                continue

            updated = dict(trigger_config)
            stage_map = stage_maps.get(row["organization_id"])

            to_ref = (
                updated.get("to_stage_key")
                or updated.get("to_stage_slug")
                or updated.get("to_status")
            )
            if to_ref:
                to_stage_key = _canonical_stage_key(to_ref)
                updated["to_stage_key"] = to_stage_key
                stage_id = _resolve_stage_id(stage_map, to_stage_key)
                if stage_id:
                    updated["to_stage_id"] = str(stage_id)

            from_ref = (
                updated.get("from_stage_key")
                or updated.get("from_stage_slug")
                or updated.get("from_status")
            )
            if from_ref:
                from_stage_key = _canonical_stage_key(from_ref)
                updated["from_stage_key"] = from_stage_key
                stage_id = _resolve_stage_id(stage_map, from_stage_key)
                if stage_id:
                    updated["from_stage_id"] = str(stage_id)

            stage_slugs = updated.get("stage_slugs")
            if isinstance(stage_slugs, list):
                stage_keys = _dedupe_preserve_order(
                    [_canonical_stage_key(value) for value in stage_slugs]
                )
                if stage_keys:
                    updated["stage_keys"] = stage_keys

                    resolved_stage_ids: list[str] = []
                    for stage_key in stage_keys:
                        stage_id = _resolve_stage_id(stage_map, stage_key)
                        if stage_id:
                            resolved_stage_ids.append(str(stage_id))
                    if resolved_stage_ids:
                        updated["stage_ids"] = _dedupe_preserve_order(resolved_stage_ids)

                updated.pop("stage_slugs", None)

            updated.pop("to_status", None)
            updated.pop("from_status", None)
            updated.pop("to_stage_slug", None)
            updated.pop("from_stage_slug", None)

            if updated != trigger_config:
                conn.execute(
                    sa.text(
                        f"UPDATE {table_name} SET trigger_config = :trigger_config WHERE id = :id"  # noqa: S608
                    ),
                    {
                        "id": row["id"],
                        "trigger_config": updated,
                    },
                )


def _rewrite_campaign_filters(conn) -> None:
    stage_maps = _load_default_stage_maps(conn)
    inspector = sa.inspect(conn)
    campaign_columns = {column["name"] for column in inspector.get_columns("campaigns")}
    has_legacy_criteria = "criteria" in campaign_columns

    select_columns = "id, organization_id, recipient_type, filter_criteria"
    if has_legacy_criteria:
        select_columns += ", criteria"

    rows = conn.execute(sa.text(f"SELECT {select_columns} FROM campaigns")).mappings()  # noqa: S608

    for row in rows:
        if row["recipient_type"] != "case":
            continue

        stage_map = stage_maps.get(row["organization_id"])
        updates: dict[str, Any] = {}

        for field_name in ("filter_criteria", "criteria"):
            if field_name not in row:
                continue

            payload = row[field_name]
            if not isinstance(payload, dict):
                continue

            updated = dict(payload)
            stage_refs: list[str] = []

            if isinstance(updated.get("stage_keys"), list):
                stage_refs.extend([str(value) for value in updated["stage_keys"]])
            if isinstance(updated.get("stage_slugs"), list):
                stage_refs.extend([str(value) for value in updated["stage_slugs"]])

            if not stage_refs:
                continue

            stage_keys = _dedupe_preserve_order(
                [_canonical_stage_key(value) for value in stage_refs]
            )
            if not stage_keys:
                continue

            updated["stage_keys"] = stage_keys

            resolved_stage_ids: list[str] = []
            for stage_key in stage_keys:
                stage_id = _resolve_stage_id(stage_map, stage_key)
                if stage_id:
                    resolved_stage_ids.append(str(stage_id))
            if resolved_stage_ids:
                updated["stage_ids"] = _dedupe_preserve_order(resolved_stage_ids)

            updated.pop("stage_slugs", None)

            if updated != payload:
                updates[field_name] = updated

        if updates:
            assignments = ", ".join(f"{key} = :{key}" for key in updates)
            params = {"id": row["id"], **updates}
            conn.execute(
                sa.text(f"UPDATE campaigns SET {assignments} WHERE id = :id"),  # noqa: S608
                params,
            )


def _rewrite_zapier_mappings(conn) -> None:
    rows = conn.execute(
        sa.text("SELECT id, outbound_event_mapping FROM zapier_webhook_settings")
    ).mappings()

    for row in rows:
        mapping = row["outbound_event_mapping"]
        normalized = _normalize_event_mapping(mapping)
        if normalized != mapping:
            conn.execute(
                sa.text(
                    """
                    UPDATE zapier_webhook_settings
                    SET outbound_event_mapping = :outbound_event_mapping
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "outbound_event_mapping": normalized,
                },
            )


def _remap_stage_references(conn, *, old_stage_id, new_stage_id, new_label: str) -> None:
    conn.execute(
        sa.text(
            """
            UPDATE surrogates
            SET stage_id = :new_stage_id,
                status_label = :new_label
            WHERE stage_id = :old_stage_id
            """
        ),
        {
            "old_stage_id": old_stage_id,
            "new_stage_id": new_stage_id,
            "new_label": new_label,
        },
    )

    conn.execute(
        sa.text(
            "UPDATE surrogate_status_history SET from_stage_id = :new_stage_id WHERE from_stage_id = :old_stage_id"
        ),
        {"old_stage_id": old_stage_id, "new_stage_id": new_stage_id},
    )

    conn.execute(
        sa.text(
            "UPDATE surrogate_status_history SET to_stage_id = :new_stage_id WHERE to_stage_id = :old_stage_id"
        ),
        {"old_stage_id": old_stage_id, "new_stage_id": new_stage_id},
    )

    conn.execute(
        sa.text(
            "UPDATE status_change_requests SET target_stage_id = :new_stage_id WHERE target_stage_id = :old_stage_id"
        ),
        {"old_stage_id": old_stage_id, "new_stage_id": new_stage_id},
    )


def _merge_stage_key_collisions(conn) -> None:
    stage_rows = conn.execute(
        sa.text(
            """
            SELECT
                id,
                pipeline_id,
                slug,
                stage_key,
                label,
                is_active,
                "order",
                created_at
            FROM pipeline_stages
            """
        )
    ).mappings()

    grouped: dict[tuple[Any, str], list[dict[str, Any]]] = defaultdict(list)
    for row in stage_rows:
        stage_key = _canonical_stage_key(row["stage_key"] or row["slug"])
        grouped[(row["pipeline_id"], stage_key)].append(dict(row))

    for (_pipeline_id, stage_key), rows in grouped.items():
        if len(rows) <= 1:
            continue

        def _sort_rank(item: dict[str, Any]) -> tuple[Any, ...]:
            slug = str(item.get("slug") or "").strip().lower()
            if slug == "pre_qualified":
                slug_rank = 0
            elif slug == "qualified":
                slug_rank = 1
            else:
                slug_rank = 2

            return (
                slug_rank,
                0 if item.get("is_active") else 1,
                item.get("order") or 10_000,
                item.get("created_at") or datetime.max,
                str(item.get("id")),
            )

        ranked = sorted(rows, key=_sort_rank)
        canonical = ranked[0]
        canonical_stage_id = canonical["id"]
        canonical_label = (
            "Pre-Qualified"
            if stage_key == "pre_qualified"
            else str(canonical.get("label") or "")
        )

        for duplicate in ranked[1:]:
            old_stage_id = duplicate["id"]
            _remap_stage_references(
                conn,
                old_stage_id=old_stage_id,
                new_stage_id=canonical_stage_id,
                new_label=canonical_label,
            )
            conn.execute(
                sa.text("DELETE FROM pipeline_stages WHERE id = :id"),
                {"id": old_stage_id},
            )


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column(
        "pipeline_stages",
        sa.Column("stage_key", sa.String(length=50), nullable=True),
    )

    conn.execute(
        sa.text(
            """
            UPDATE pipeline_stages
            SET stage_key = lower(trim(slug))
            WHERE stage_key IS NULL
            """
        )
    )

    conn.execute(
        sa.text(
            "UPDATE pipeline_stages SET stage_key = 'pre_qualified' WHERE stage_key = 'qualified'"
        )
    )

    _merge_stage_key_collisions(conn)

    conn.execute(
        sa.text(
            "UPDATE pipeline_stages SET slug = 'pre_qualified' WHERE slug = 'qualified'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE pipeline_stages SET label = 'Pre-Qualified' WHERE stage_key = 'pre_qualified'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE pipeline_stages SET stage_key = 'pre_qualified' WHERE slug = 'pre_qualified'"
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE surrogates s
            SET status_label = 'Pre-Qualified'
            FROM pipeline_stages ps
            WHERE s.stage_id = ps.id
              AND ps.stage_key = 'pre_qualified'
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE surrogate_status_history h
            SET from_label_snapshot = 'Pre-Qualified'
            FROM pipeline_stages ps
            WHERE h.from_stage_id = ps.id
              AND ps.stage_key = 'pre_qualified'
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE surrogate_status_history h
            SET to_label_snapshot = 'Pre-Qualified'
            FROM pipeline_stages ps
            WHERE h.to_stage_id = ps.id
              AND ps.stage_key = 'pre_qualified'
            """
        )
    )

    conn.execute(
        sa.text(
            "UPDATE surrogate_status_history SET from_label_snapshot = 'Pre-Qualified' WHERE from_label_snapshot = 'Qualified'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE surrogate_status_history SET to_label_snapshot = 'Pre-Qualified' WHERE to_label_snapshot = 'Qualified'"
        )
    )

    _rewrite_workflow_trigger_configs(conn)
    _rewrite_campaign_filters(conn)
    _rewrite_zapier_mappings(conn)

    conn.execute(sa.text("DELETE FROM entity_versions WHERE entity_type = 'pipeline'"))
    conn.execute(sa.text("UPDATE pipelines SET current_version = 1"))

    op.alter_column("pipeline_stages", "stage_key", existing_type=sa.String(length=50), nullable=False)
    op.create_unique_constraint("uq_stage_key", "pipeline_stages", ["pipeline_id", "stage_key"])
    op.create_index(
        "idx_stage_pipeline_key",
        "pipeline_stages",
        ["pipeline_id", "stage_key"],
        unique=False,
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "UPDATE pipeline_stages SET slug = 'qualified', label = 'Qualified' WHERE slug = 'pre_qualified'"
        )
    )

    rows = conn.execute(
        sa.text("SELECT id, outbound_event_mapping FROM zapier_webhook_settings")
    ).mappings()
    for row in rows:
        mapping = row["outbound_event_mapping"]
        if not isinstance(mapping, list):
            continue
        reverted: list[dict[str, Any]] = []
        for item in mapping:
            if not isinstance(item, dict):
                continue
            stage_key = str(item.get("stage_key") or "").strip().lower()
            event_name = str(item.get("event_name") or "").strip()
            if stage_key == "pre_qualified":
                stage_slug = "qualified"
                if event_name == "PreQualifiedLead":
                    event_name = "QualifiedLead"
            else:
                stage_slug = stage_key
            if stage_slug and event_name:
                reverted.append(
                    {
                        "stage_slug": stage_slug,
                        "event_name": event_name,
                        "enabled": bool(item.get("enabled", True)),
                    }
                )
        if reverted:
            conn.execute(
                sa.text(
                    "UPDATE zapier_webhook_settings SET outbound_event_mapping = :mapping WHERE id = :id"
                ),
                {"id": row["id"], "mapping": reverted},
            )

    op.drop_index("idx_stage_pipeline_key", table_name="pipeline_stages")
    op.drop_constraint("uq_stage_key", "pipeline_stages", type_="unique")
    op.drop_column("pipeline_stages", "stage_key")
