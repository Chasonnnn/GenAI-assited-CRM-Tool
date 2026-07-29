"""Add portal domain to organizations.

Revision ID: 20260116_0900
Revises: 20260115_1800
Create Date: 2026-01-16 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260116_0900"
down_revision: str | None = "20260115_1800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("portal_domain", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_organizations_portal_domain",
        "organizations",
        ["portal_domain"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_organizations_portal_domain", "organizations", type_="unique")
    op.drop_column("organizations", "portal_domain")
