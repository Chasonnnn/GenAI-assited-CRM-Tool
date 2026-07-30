"""Remove portal_domain from organizations.

Portal URLs are now computed from slug: https://{slug}.{PLATFORM_BASE_DOMAIN}

Revision ID: 20260125_2400
Revises: 20260125_2330
Create Date: 2026-01-25 24:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260125_2400"
down_revision: str | Sequence[str] | None = "20260125_2330"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove portal_domain column - URLs are now computed from slug."""
    op.drop_constraint("uq_organizations_portal_domain", "organizations", type_="unique")
    op.drop_column("organizations", "portal_domain")


def downgrade() -> None:
    """Restore portal_domain column."""
    op.add_column(
        "organizations",
        sa.Column("portal_domain", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_organizations_portal_domain",
        "organizations",
        ["portal_domain"],
    )
