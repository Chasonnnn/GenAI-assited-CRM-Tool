"""harden pre-questionaire public fields

Revision ID: 20260624_1730
Revises: 20260624_1130
Create Date: 2026-06-24 17:30:00.000000
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260624_1730"
down_revision: str | Sequence[str] | None = "20260624_1130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _stable_json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _jsonb_statement(sql: str, *jsonb_params: str) -> sa.TextClause:
    statement = sa.text(sql)
    for param in jsonb_params:
        statement = statement.bindparams(sa.bindparam(param, type_=postgresql.JSONB))
    return statement


def _patch_schema(schema: dict[str, Any] | None) -> tuple[dict[str, Any] | None, bool]:
    if not isinstance(schema, dict):
        return schema, False

    patched = copy.deepcopy(schema)
    changed = False
    for page in patched.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for field in page.get("fields") or []:
            if not isinstance(field, dict):
                continue
            key = field.get("key")
            if key == "state":
                desired_validation = {
                    "min_length": 2,
                    "max_length": 2,
                    "pattern": "^[A-Za-z]{2}$",
                }
                if field.get("help_text") != "Use the 2-letter state code, e.g. CA.":
                    field["help_text"] = "Use the 2-letter state code, e.g. CA."
                    changed = True
                if field.get("validation") != desired_validation:
                    field["validation"] = desired_validation
                    changed = True
            elif key == "height_ft":
                if field.get("label") != "Height":
                    field["label"] = "Height"
                    changed = True
                if field.get("type") != "height":
                    field["type"] = "height"
                    changed = True
            elif key == "weight_lb":
                desired_validation = {"min_value": 1, "max_value": 1000}
                if field.get("label") != "Weight (lb)":
                    field["label"] = "Weight (lb)"
                    changed = True
                if field.get("type") != "number":
                    field["type"] = "number"
                    changed = True
                if field.get("validation") != desired_validation:
                    field["validation"] = desired_validation
                    changed = True
            elif key == "num_deliveries":
                desired_validation = {"min_value": 1, "max_value": 20}
                if field.get("validation") != desired_validation:
                    field["validation"] = desired_validation
                    changed = True
            elif key == "num_csections":
                desired_validation = {"min_value": 0, "max_value": 20}
                if field.get("validation") != desired_validation:
                    field["validation"] = desired_validation
                    changed = True
    return patched, changed


def _schema_has_public_field_targets(schema: dict[str, Any] | None) -> bool:
    if not isinstance(schema, dict):
        return False
    keys: set[str] = set()
    for page in schema.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for field in page.get("fields") or []:
            if isinstance(field, dict) and isinstance(field.get("key"), str):
                keys.add(field["key"])
    return {"state", "height_ft", "weight_lb"}.issubset(keys)


def _looks_like_ewi_pre_questionnaire(
    name: str | None,
    schema: dict[str, Any] | None,
    published_schema: dict[str, Any] | None,
) -> bool:
    haystack = " ".join(
        str(value or "").lower()
        for value in (
            name,
            (schema or {}).get("public_title") if isinstance(schema, dict) else None,
            (published_schema or {}).get("public_title")
            if isinstance(published_schema, dict)
            else None,
        )
    )
    if "pre-question" not in haystack and "pre question" not in haystack:
        return False
    if "ewi" not in haystack and "questionaire" not in haystack and "questionnaire" not in haystack:
        return False
    return _schema_has_public_field_targets(schema) or _schema_has_public_field_targets(
        published_schema
    )


def _field_policy(schema: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    policy: dict[str, dict[str, Any]] = {}
    if not isinstance(schema, dict):
        return policy
    for page in schema.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for field in page.get("fields") or []:
            if not isinstance(field, dict):
                continue
            key = field.get("key")
            if not isinstance(key, str) or not key:
                continue
            policy[key] = {
                "type": field.get("type"),
                "required": bool(field.get("required", False)),
                "sensitivity": field.get("sensitivity"),
            }
    return policy


def upgrade() -> None:
    bind = op.get_bind()

    template_rows = bind.execute(
        sa.text(
            """
            SELECT name, schema_json, published_schema_json
            FROM platform_form_templates
            WHERE name = 'pre-questionaire'
            """
        )
    ).mappings()
    for row in template_rows:
        schema_json, schema_changed = _patch_schema(row["schema_json"])
        published_schema_json, published_changed = _patch_schema(row["published_schema_json"])
        if schema_changed or published_changed:
            bind.execute(
                _jsonb_statement(
                    """
                    UPDATE platform_form_templates
                    SET
                        schema_json = :schema_json,
                        published_schema_json = :published_schema_json
                    WHERE name = :name
                    """,
                    "schema_json",
                    "published_schema_json",
                ),
                {
                    "name": row["name"],
                    "schema_json": schema_json,
                    "published_schema_json": published_schema_json,
                },
            )

    target_form_ids: list[Any] = []
    form_rows = bind.execute(
        sa.text(
            """
            SELECT id, name, schema_json, published_schema_json
            FROM forms
            WHERE purpose = 'lead_capture'
            """
        )
    ).mappings()
    for row in form_rows:
        if not _looks_like_ewi_pre_questionnaire(
            row["name"], row["schema_json"], row["published_schema_json"]
        ):
            continue
        schema_json, schema_changed = _patch_schema(row["schema_json"])
        published_schema_json, published_changed = _patch_schema(row["published_schema_json"])
        if schema_changed or published_changed:
            target_form_ids.append(row["id"])
            bind.execute(
                _jsonb_statement(
                    """
                    UPDATE forms
                    SET
                        schema_json = :schema_json,
                        published_schema_json = :published_schema_json,
                        updated_at = now()
                    WHERE id = :form_id
                    """,
                    "schema_json",
                    "published_schema_json",
                ),
                {
                    "form_id": row["id"],
                    "schema_json": schema_json,
                    "published_schema_json": published_schema_json,
                },
            )

    for form_id in target_form_ids:
        version_rows = bind.execute(
            sa.text(
                """
                SELECT id, form_schema_snapshot_json
                FROM published_intake_versions
                WHERE form_id = :form_id
                """
            ),
            {"form_id": form_id},
        ).mappings()
        for version_row in version_rows:
            schema_json, schema_changed = _patch_schema(version_row["form_schema_snapshot_json"])
            if not schema_changed:
                continue
            bind.execute(
                _jsonb_statement(
                    """
                    UPDATE published_intake_versions
                    SET
                        form_schema_snapshot_json = :schema_json,
                        form_version_hash = :form_version_hash,
                        field_policy_snapshot_json = :field_policy
                    WHERE id = :version_id
                    """,
                    "schema_json",
                    "field_policy",
                ),
                {
                    "version_id": version_row["id"],
                    "schema_json": schema_json,
                    "form_version_hash": _stable_json_hash(schema_json),
                    "field_policy": _field_policy(schema_json),
                },
            )


def downgrade() -> None:
    # No-op: reversing this would weaken public validation and may overwrite operator edits.
    pass
