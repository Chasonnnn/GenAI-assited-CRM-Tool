"""add surrogate journey timing field and template mapping

Revision ID: 20260329_2230
Revises: 20260321_1800
Create Date: 2026-03-29 22:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260329_2230"
down_revision: str | Sequence[str] | None = "20260321_1800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TEMPLATE_NAME = "Surrogate Pre-Screening Questionnaire"
JOURNEY_FIELD_KEY = "journey_timing_preference"
JOURNEY_FIELD_LABEL = "When would you like to start your surrogacy journey?"
JOURNEY_FIELD = {
    "key": JOURNEY_FIELD_KEY,
    "label": JOURNEY_FIELD_LABEL,
    "type": "radio",
    "required": False,
    "options": [
        {"label": "0–3 months", "value": "months_0_3"},
        {"label": "3–6 months", "value": "months_3_6"},
        {"label": "Still deciding", "value": "still_deciding"},
    ],
}
JOURNEY_MAPPING = {
    "field_key": JOURNEY_FIELD_KEY,
    "surrogate_field": "journey_timing_preference",
}


def _template_table() -> sa.Table:
    return sa.table(
        "platform_form_templates",
        sa.column("name", sa.String),
        sa.column("schema_json", postgresql.JSONB),
        sa.column("settings_json", postgresql.JSONB),
        sa.column("published_schema_json", postgresql.JSONB),
        sa.column("published_settings_json", postgresql.JSONB),
    )


def _with_journey_field(schema: dict | None) -> dict | None:
    if not isinstance(schema, dict):
        return schema
    next_schema = deepcopy(schema)
    pages = next_schema.get("pages")
    if not isinstance(pages, list) or not pages:
        return next_schema
    first_page = pages[0]
    if not isinstance(first_page, dict):
        return next_schema
    fields = first_page.get("fields")
    if not isinstance(fields, list):
        return next_schema
    if any(isinstance(field, dict) and field.get("key") == JOURNEY_FIELD_KEY for field in fields):
        return next_schema

    insert_index = next(
        (
            index + 1
            for index, field in enumerate(fields)
            if isinstance(field, dict) and field.get("key") == "surrogate_experience"
        ),
        len(fields),
    )
    fields.insert(insert_index, deepcopy(JOURNEY_FIELD))
    return next_schema


def _without_journey_field(schema: dict | None) -> dict | None:
    if not isinstance(schema, dict):
        return schema
    next_schema = deepcopy(schema)
    pages = next_schema.get("pages")
    if not isinstance(pages, list):
        return next_schema
    for page in pages:
        if not isinstance(page, dict):
            continue
        fields = page.get("fields")
        if not isinstance(fields, list):
            continue
        page["fields"] = [
            field
            for field in fields
            if not (isinstance(field, dict) and field.get("key") == JOURNEY_FIELD_KEY)
        ]
    return next_schema


def _with_journey_mapping(settings: dict | None) -> dict | None:
    if not isinstance(settings, dict):
        return settings
    next_settings = deepcopy(settings)
    mappings = next_settings.get("mappings")
    if not isinstance(mappings, list):
        return next_settings
    if any(
        isinstance(mapping, dict)
        and mapping.get("surrogate_field") == JOURNEY_MAPPING["surrogate_field"]
        for mapping in mappings
    ):
        return next_settings

    insert_index = next(
        (
            index + 1
            for index, mapping in enumerate(mappings)
            if isinstance(mapping, dict)
            and mapping.get("surrogate_field") == "has_surrogate_experience"
        ),
        len(mappings),
    )
    mappings.insert(insert_index, deepcopy(JOURNEY_MAPPING))
    return next_settings


def _without_journey_mapping(settings: dict | None) -> dict | None:
    if not isinstance(settings, dict):
        return settings
    next_settings = deepcopy(settings)
    mappings = next_settings.get("mappings")
    if not isinstance(mappings, list):
        return next_settings
    next_settings["mappings"] = [
        mapping
        for mapping in mappings
        if not (
            isinstance(mapping, dict)
            and mapping.get("surrogate_field") == JOURNEY_MAPPING["surrogate_field"]
        )
    ]
    return next_settings


def _update_template_records(add_field: bool) -> None:
    conn = op.get_bind()
    template_table = _template_table()
    row = conn.execute(
        sa.select(
            template_table.c.schema_json,
            template_table.c.settings_json,
            template_table.c.published_schema_json,
            template_table.c.published_settings_json,
        ).where(template_table.c.name == TEMPLATE_NAME)
    ).mappings().first()
    if row is None:
        return

    transform_schema = _with_journey_field if add_field else _without_journey_field
    transform_settings = _with_journey_mapping if add_field else _without_journey_mapping

    conn.execute(
        sa.update(template_table)
        .where(template_table.c.name == TEMPLATE_NAME)
        .values(
            schema_json=transform_schema(row["schema_json"]),
            settings_json=transform_settings(row["settings_json"]),
            published_schema_json=transform_schema(row["published_schema_json"]),
            published_settings_json=transform_settings(row["published_settings_json"]),
        )
    )


def upgrade() -> None:
    op.add_column(
        "surrogates",
        sa.Column("journey_timing_preference", sa.String(length=50), nullable=True),
    )
    _update_template_records(add_field=True)


def downgrade() -> None:
    _update_template_records(add_field=False)
    op.drop_column("surrogates", "journey_timing_preference")
