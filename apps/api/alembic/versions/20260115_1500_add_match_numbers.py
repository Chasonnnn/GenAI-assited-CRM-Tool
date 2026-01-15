"""Add match numbers.

Revision ID: 20260115_1500
Revises: 20260115_1400
Create Date: 2026-01-15 15:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260115_1500"
down_revision = "20260115_1400"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("match_number", sa.String(length=10), nullable=True))

    op.execute(
        """
        WITH numbered AS (
            SELECT id,
                   organization_id,
                   row_number() OVER (PARTITION BY organization_id ORDER BY created_at, id) AS seq
            FROM matches
        )
        UPDATE matches m
        SET match_number = 'M' || lpad((numbered.seq + 10000)::text, 5, '0')
        FROM numbered
        WHERE m.id = numbered.id
        """
    )

    op.execute(
        """
        INSERT INTO org_counters (organization_id, counter_type, current_value)
        SELECT organization_id,
               'match_number',
               max(substring(match_number from 2)::int)
        FROM matches
        WHERE match_number IS NOT NULL
        GROUP BY organization_id
        ON CONFLICT (organization_id, counter_type)
        DO UPDATE SET current_value = EXCLUDED.current_value,
                      updated_at = now()
        """
    )

    op.alter_column("matches", "match_number", existing_type=sa.String(length=10), nullable=False)
    op.create_unique_constraint("uq_match_number", "matches", ["organization_id", "match_number"])
    op.create_index("ix_matches_match_number", "matches", ["match_number"])


def downgrade() -> None:
    op.drop_index("ix_matches_match_number", table_name="matches")
    op.drop_constraint("uq_match_number", "matches", type_="unique")
    op.drop_column("matches", "match_number")
    op.execute("DELETE FROM org_counters WHERE counter_type = 'match_number'")
