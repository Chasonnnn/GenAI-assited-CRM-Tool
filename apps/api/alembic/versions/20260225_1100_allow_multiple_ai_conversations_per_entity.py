"""allow multiple ai conversations per entity

Revision ID: 20260225_1100
Revises: 20260224_1835
Create Date: 2026-02-25 11:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260225_1100"
down_revision: str | Sequence[str] | None = "20260224_1835"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def upgrade() -> None:
    if _has_unique_constraint("ai_conversations", "uq_ai_conversations_user_entity"):
        op.drop_constraint(
            "uq_ai_conversations_user_entity",
            "ai_conversations",
            type_="unique",
        )


def downgrade() -> None:
    if not _has_unique_constraint("ai_conversations", "uq_ai_conversations_user_entity"):
        op.create_unique_constraint(
            "uq_ai_conversations_user_entity",
            "ai_conversations",
            ["organization_id", "user_id", "entity_type", "entity_id"],
        )
