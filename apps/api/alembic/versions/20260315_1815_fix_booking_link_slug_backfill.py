"""repair booking link slugs backfilled with escaped regex bug

Revision ID: 20260315_1815
Revises: 20260315_1800
Create Date: 2026-03-15 18:15:00.000000
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
import re

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260315_1815"
down_revision: str | Sequence[str] | None = "20260315_1800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _build_slug_base(value: str) -> str:
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9\s-]", "", normalized)
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized[:32] or "staff"


def _format_candidate(base: str, sequence: int) -> str:
    if sequence <= 1:
        return base[:32]

    suffix = f"-{sequence}"
    return f"{base[: max(1, 32 - len(suffix))]}{suffix}"


def _reassign_booking_slugs() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT
                bl.id,
                bl.organization_id,
                COALESCE(u.display_name, '') AS display_name
            FROM booking_links bl
            JOIN users u ON u.id = bl.user_id
            ORDER BY bl.organization_id, bl.created_at, bl.id
            """
        )
    ).mappings()

    used_by_scope: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        scope = str(row["organization_id"])
        base = _build_slug_base(row["display_name"])
        sequence = 1

        while True:
            candidate = _format_candidate(base, sequence)
            if candidate not in used_by_scope[scope]:
                used_by_scope[scope].add(candidate)
                bind.execute(
                    sa.text(
                        """
                        UPDATE booking_links
                        SET public_slug = :public_slug
                        WHERE id = :booking_link_id
                        """
                    ),
                    {
                        "public_slug": candidate,
                        "booking_link_id": row["id"],
                    },
                )
                break
            sequence += 1


def upgrade() -> None:
    op.drop_constraint("uq_booking_link_org_slug", "booking_links", type_="unique")
    _reassign_booking_slugs()
    op.create_unique_constraint(
        "uq_booking_link_org_slug",
        "booking_links",
        ["organization_id", "public_slug"],
    )


def downgrade() -> None:
    """Data repair migration is intentionally not reversed."""
