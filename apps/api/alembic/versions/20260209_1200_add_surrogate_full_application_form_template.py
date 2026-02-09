"""Seed Surrogate Full Application Form platform form template (2-page version).

Revision ID: 20260209_1200
Revises: 20260207_1200
Create Date: 2026-02-09 12:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union, Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260209_1200"
down_revision: Union[str, Sequence[str], None] = "20260207_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TEMPLATE_NAME = "Surrogate Full Application Form"
TEMPLATE_DESCRIPTION = "Full surrogate application form (condensed to two pages) based on the Jotform Surrogate Application Form."

# We build this template by cloning the canonical seeded Jotform form template.
BASE_TEMPLATE_NAME = "Surrogate Application Form Template"


def _template_table() -> sa.Table:
    return sa.table(
        "platform_form_templates",
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("schema_json", postgresql.JSONB),
        sa.column("settings_json", postgresql.JSONB),
        sa.column("published_name", sa.String),
        sa.column("published_description", sa.Text),
        sa.column("published_schema_json", postgresql.JSONB),
        sa.column("published_settings_json", postgresql.JSONB),
        sa.column("status", sa.String),
        sa.column("current_version", sa.Integer),
        sa.column("published_version", sa.Integer),
        sa.column("is_published_globally", sa.Boolean),
        sa.column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.column("updated_at", sa.TIMESTAMP(timezone=True)),
    )


def _to_two_pages(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema
    pages = schema.get("pages")
    if not isinstance(pages, list) or not pages:
        return schema

    # Preserve question order while merging into two pages.
    page_one_fields: list[dict] = []
    page_two_fields: list[dict] = []

    # Split after the first 5 sections (Personal through Family Support).
    for i, page in enumerate(pages):
        fields = page.get("fields") if isinstance(page, dict) else None
        if not isinstance(fields, list):
            continue
        if i < 5:
            page_one_fields.extend(fields)
        else:
            page_two_fields.extend(fields)

    # Fall back to a single-page schema if the split produced an empty second page.
    merged_pages = (
        [
            {"title": "Application", "fields": page_one_fields},
            {"title": "Medical & Preferences", "fields": page_two_fields},
        ]
        if page_two_fields
        else [{"title": "Application", "fields": page_one_fields}]
    )

    # Keep privacy_notice/logo_url as-is, but align public_title with the new template name.
    return {
        **schema,
        "pages": merged_pages,
        "public_title": TEMPLATE_NAME,
    }


def _fetch_base_snapshot(conn, template_table: sa.Table) -> tuple[dict, dict]:
    row = conn.execute(
        sa.select(
            template_table.c.published_schema_json,
            template_table.c.published_settings_json,
            template_table.c.schema_json,
            template_table.c.settings_json,
        ).where(template_table.c.name == BASE_TEMPLATE_NAME)
    ).first()

    if not row:
        raise RuntimeError(
            f"Base platform form template not found: {BASE_TEMPLATE_NAME!r}. "
            "Ensure prior seed migrations have been applied."
        )

    published_schema = row[0]
    published_settings = row[1]
    draft_schema = row[2]
    draft_settings = row[3]

    schema = published_schema or draft_schema
    settings = published_settings or draft_settings or {}

    if not isinstance(schema, dict):
        raise RuntimeError(
            f"Base platform form template schema_json is invalid for {BASE_TEMPLATE_NAME!r}."
        )
    if not isinstance(settings, dict):
        settings = {}

    return schema, settings


def upgrade() -> None:
    template_table = _template_table()
    conn = op.get_bind()

    base_schema, base_settings = _fetch_base_snapshot(conn, template_table)
    schema = _to_two_pages(base_schema)
    settings = base_settings

    conn.execute(
        sa.update(template_table)
        .where(template_table.c.name == TEMPLATE_NAME)
        .values(
            description=TEMPLATE_DESCRIPTION,
            schema_json=schema,
            settings_json=settings,
            published_name=TEMPLATE_NAME,
            published_description=TEMPLATE_DESCRIPTION,
            published_schema_json=schema,
            published_settings_json=settings,
            status="published",
            current_version=template_table.c.current_version + 1,
            published_version=template_table.c.published_version + 1,
            is_published_globally=True,
            published_at=sa.text("now()"),
            updated_at=sa.text("now()"),
        )
    )

    exists = conn.execute(
        sa.select(sa.literal(1))
        .select_from(template_table)
        .where(template_table.c.name == TEMPLATE_NAME)
    ).first()
    if not exists:
        conn.execute(
            sa.insert(template_table).values(
                name=TEMPLATE_NAME,
                description=TEMPLATE_DESCRIPTION,
                schema_json=schema,
                settings_json=settings,
                published_name=TEMPLATE_NAME,
                published_description=TEMPLATE_DESCRIPTION,
                published_schema_json=schema,
                published_settings_json=settings,
                status="published",
                current_version=1,
                published_version=1,
                is_published_globally=True,
                published_at=sa.text("now()"),
            )
        )


def downgrade() -> None:
    template_table = _template_table()
    conn = op.get_bind()
    conn.execute(
        sa.delete(template_table).where(
            sa.and_(
                template_table.c.name == TEMPLATE_NAME,
                template_table.c.description == TEMPLATE_DESCRIPTION,
                template_table.c.current_version == 1,
                template_table.c.published_version == 1,
            )
        )
    )
