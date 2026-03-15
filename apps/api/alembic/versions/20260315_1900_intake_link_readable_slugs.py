"""convert intake links to readable org-scoped slugs

Revision ID: 20260315_1900
Revises: 20260315_1815
Create Date: 2026-03-15 19:00:00.000000
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
import re

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260315_1900"
down_revision: str | Sequence[str] | None = "20260315_1815"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INTAKE_SLUG_MAX_LENGTH = 100


def _normalize_slug(value: str) -> str:
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9\s-]", "", normalized)
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized[:INTAKE_SLUG_MAX_LENGTH]


def _build_slug_base(
    *,
    event_name: str | None,
    campaign_name: str | None,
    form_name: str | None,
) -> str:
    for raw_value in (event_name, campaign_name, form_name):
        if not raw_value:
            continue
        slug = _normalize_slug(raw_value)
        if slug:
            return slug
    return "intake"


def _format_slug_candidate(base: str, sequence: int) -> str:
    if sequence <= 1:
        return base[:INTAKE_SLUG_MAX_LENGTH]

    suffix = f"-{sequence}"
    trimmed_base = base[: max(1, INTAKE_SLUG_MAX_LENGTH - len(suffix))]
    return f"{trimmed_base}{suffix}"


def _reassign_intake_slugs(*, per_org: bool) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT
                fil.id,
                fil.organization_id,
                fil.campaign_name,
                fil.event_name,
                COALESCE(f.name, '') AS form_name
            FROM form_intake_links fil
            JOIN forms f ON f.id = fil.form_id
            ORDER BY fil.organization_id, fil.created_at, fil.id
            """
        )
    ).mappings()

    used_by_scope: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        scope = str(row["organization_id"]) if per_org else "global"
        base = _build_slug_base(
            event_name=row["event_name"],
            campaign_name=row["campaign_name"],
            form_name=row["form_name"],
        )
        sequence = 1

        while True:
            candidate = _format_slug_candidate(base, sequence)
            if candidate not in used_by_scope[scope]:
                used_by_scope[scope].add(candidate)
                bind.execute(
                    sa.text(
                        """
                        UPDATE form_intake_links
                        SET slug = :slug
                        WHERE id = :intake_link_id
                        """
                    ),
                    {
                        "slug": candidate,
                        "intake_link_id": row["id"],
                    },
                )
                break
            sequence += 1


def upgrade() -> None:
    op.drop_constraint("uq_form_intake_link_slug", "form_intake_links", type_="unique")
    _reassign_intake_slugs(per_org=True)
    op.create_unique_constraint(
        "uq_form_intake_link_org_slug",
        "form_intake_links",
        ["organization_id", "slug"],
    )
    op.create_index(
        "idx_form_intake_links_org_slug",
        "form_intake_links",
        ["organization_id", "slug"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_form_intake_links_org_slug", table_name="form_intake_links")
    op.drop_constraint("uq_form_intake_link_org_slug", "form_intake_links", type_="unique")
    _reassign_intake_slugs(per_org=False)
    op.create_unique_constraint("uq_form_intake_link_slug", "form_intake_links", ["slug"])
