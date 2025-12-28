"""change_cases_stage_fk_to_restrict

Revision ID: e64c5c89667e
Revises: 91836fa19e8a
Create Date: 2025-12-26 10:34:23.514096

Changes:
- Drop existing FK on cases.stage_id (was ON DELETE SET NULL)
- Recreate FK with ON DELETE RESTRICT
- This aligns with stage_id being NOT NULL (can't set null on delete)
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e64c5c89667e"
down_revision: Union[str, Sequence[str], None] = "91836fa19e8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change cases.stage_id FK from SET NULL to RESTRICT."""
    # Drop the old FK constraint (actual name in DB is fk_cases_stage)
    op.drop_constraint("fk_cases_stage", "cases", type_="foreignkey")

    # Recreate with ON DELETE RESTRICT
    op.create_foreign_key(
        "fk_cases_stage",
        "cases",
        "pipeline_stages",
        ["stage_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Revert to ON DELETE SET NULL."""
    op.drop_constraint("fk_cases_stage", "cases", type_="foreignkey")

    op.create_foreign_key(
        "fk_cases_stage",
        "cases",
        "pipeline_stages",
        ["stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
