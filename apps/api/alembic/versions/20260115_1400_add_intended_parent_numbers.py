"""Add intended parent numbers and S/I numbering format.

Revision ID: 20260115_1400
Revises: 20260115_0900
Create Date: 2026-01-15 14:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260115_1400"
down_revision = "20260115_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intended_parents",
        sa.Column("intended_parent_number", sa.String(length=10), nullable=True),
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION intended_parents_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '') || ' ' || coalesce(NEW.intended_parent_number, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        WITH ranked AS (
            SELECT id,
                   organization_id,
                   row_number() OVER (PARTITION BY organization_id ORDER BY created_at, id) AS rn
            FROM intended_parents
        )
        UPDATE intended_parents ip
        SET intended_parent_number = 'I' || lpad((10000 + ranked.rn)::text, 5, '0')
        FROM ranked
        WHERE ip.id = ranked.id;
    """)

    op.execute("""
        WITH ranked AS (
            SELECT id,
                   organization_id,
                   row_number() OVER (PARTITION BY organization_id ORDER BY created_at, id) AS rn
            FROM surrogates
        )
        UPDATE surrogates s
        SET surrogate_number = 'S' || lpad((10000 + ranked.rn)::text, 5, '0')
        FROM ranked
        WHERE s.id = ranked.id;
    """)

    op.execute(
        "ALTER TABLE intended_parents ALTER COLUMN intended_parent_number SET NOT NULL"
    )
    op.create_unique_constraint(
        "uq_intended_parent_number",
        "intended_parents",
        ["organization_id", "intended_parent_number"],
    )

    op.execute("""
        WITH maxes AS (
            SELECT organization_id,
                   max((substring(surrogate_number from 2))::int) AS max_val
            FROM surrogates
            GROUP BY organization_id
        )
        INSERT INTO org_counters (organization_id, counter_type, current_value)
        SELECT organization_id, 'surrogate_number', max_val
        FROM maxes
        ON CONFLICT (organization_id, counter_type)
        DO UPDATE SET current_value = EXCLUDED.current_value,
                      updated_at = now();
    """)

    op.execute("""
        WITH maxes AS (
            SELECT organization_id,
                   max((substring(intended_parent_number from 2))::int) AS max_val
            FROM intended_parents
            GROUP BY organization_id
        )
        INSERT INTO org_counters (organization_id, counter_type, current_value)
        SELECT organization_id, 'intended_parent_number', max_val
        FROM maxes
        ON CONFLICT (organization_id, counter_type)
        DO UPDATE SET current_value = EXCLUDED.current_value,
                      updated_at = now();
    """)

    op.execute("""
        UPDATE org_counters
        SET current_value = GREATEST(current_value, 10000),
            updated_at = now()
        WHERE counter_type IN ('surrogate_number', 'intended_parent_number');
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION intended_parents_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.drop_constraint(
        "uq_intended_parent_number",
        "intended_parents",
        type_="unique",
    )
    op.drop_column("intended_parents", "intended_parent_number")

    op.execute(
        "DELETE FROM org_counters WHERE counter_type = 'intended_parent_number'"
    )

    op.execute("""
        UPDATE surrogates
        SET surrogate_number = lpad(substring(surrogate_number from 2), 5, '0')
        WHERE surrogate_number ~ '^S\\d+$';
    """)
