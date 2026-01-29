"""Add normalized identity fields and trigram indexes for search.

Adds:
- normalized columns for surrogate and intended parent identity fields
- pg_trgm + unaccent extensions
- triggers to keep normalized columns updated
- trigram GIN indexes (active-only) for fast substring search

Revision ID: 20260129_1200
Revises: 20260128_1400
Create Date: 2026-01-29 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260129_1200"
down_revision: Union[str, None] = "20260128_1400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    op.add_column(
        "surrogates",
        sa.Column("full_name_normalized", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "surrogates",
        sa.Column("surrogate_number_normalized", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "intended_parents",
        sa.Column("full_name_normalized", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "intended_parents",
        sa.Column("intended_parent_number_normalized", sa.String(length=20), nullable=True),
    )

    # Backfill normalized columns
    op.execute(
        """
        UPDATE surrogates
        SET full_name_normalized = lower(
                regexp_replace(unaccent(coalesce(full_name, '')), '\\s+', ' ', 'g')
            ),
            surrogate_number_normalized = lower(
                regexp_replace(coalesce(surrogate_number, ''), '\\s+', '', 'g')
            )
        WHERE full_name_normalized IS NULL OR surrogate_number_normalized IS NULL;
        """
    )
    op.execute(
        """
        UPDATE intended_parents
        SET full_name_normalized = lower(
                regexp_replace(unaccent(coalesce(full_name, '')), '\\s+', ' ', 'g')
            ),
            intended_parent_number_normalized = lower(
                regexp_replace(coalesce(intended_parent_number, ''), '\\s+', '', 'g')
            )
        WHERE full_name_normalized IS NULL OR intended_parent_number_normalized IS NULL;
        """
    )

    # Triggers to keep normalized columns updated
    op.execute(
        """
        CREATE OR REPLACE FUNCTION surrogates_normalize_identity_fields() RETURNS trigger AS $$
        BEGIN
            NEW.full_name_normalized :=
                lower(regexp_replace(unaccent(coalesce(NEW.full_name, '')), '\\s+', ' ', 'g'));
            NEW.surrogate_number_normalized :=
                lower(regexp_replace(coalesce(NEW.surrogate_number, ''), '\\s+', '', 'g'));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS surrogates_normalize_identity_fields_trigger ON surrogates;
        CREATE TRIGGER surrogates_normalize_identity_fields_trigger
        BEFORE INSERT OR UPDATE OF full_name, surrogate_number ON surrogates
        FOR EACH ROW EXECUTE FUNCTION surrogates_normalize_identity_fields();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION intended_parents_normalize_identity_fields() RETURNS trigger AS $$
        BEGIN
            NEW.full_name_normalized :=
                lower(regexp_replace(unaccent(coalesce(NEW.full_name, '')), '\\s+', ' ', 'g'));
            NEW.intended_parent_number_normalized :=
                lower(regexp_replace(coalesce(NEW.intended_parent_number, ''), '\\s+', '', 'g'));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS intended_parents_normalize_identity_fields_trigger ON intended_parents;
        CREATE TRIGGER intended_parents_normalize_identity_fields_trigger
        BEFORE INSERT OR UPDATE OF full_name, intended_parent_number ON intended_parents
        FOR EACH ROW EXECUTE FUNCTION intended_parents_normalize_identity_fields();
        """
    )

    op.create_index(
        "idx_surrogates_active_full_name_trgm",
        "surrogates",
        ["full_name_normalized"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"full_name_normalized": "gin_trgm_ops"},
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index(
        "idx_surrogates_active_number_trgm",
        "surrogates",
        ["surrogate_number_normalized"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"surrogate_number_normalized": "gin_trgm_ops"},
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index(
        "idx_ip_active_full_name_trgm",
        "intended_parents",
        ["full_name_normalized"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"full_name_normalized": "gin_trgm_ops"},
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index(
        "idx_ip_active_number_trgm",
        "intended_parents",
        ["intended_parent_number_normalized"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"intended_parent_number_normalized": "gin_trgm_ops"},
        postgresql_where=sa.text("is_archived = FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_ip_active_number_trgm", table_name="intended_parents")
    op.drop_index("idx_ip_active_full_name_trgm", table_name="intended_parents")
    op.drop_index("idx_surrogates_active_number_trgm", table_name="surrogates")
    op.drop_index("idx_surrogates_active_full_name_trgm", table_name="surrogates")

    op.execute(
        """
        DROP TRIGGER IF EXISTS surrogates_normalize_identity_fields_trigger ON surrogates;
        DROP FUNCTION IF EXISTS surrogates_normalize_identity_fields();
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS intended_parents_normalize_identity_fields_trigger ON intended_parents;
        DROP FUNCTION IF EXISTS intended_parents_normalize_identity_fields();
        """
    )

    op.drop_column("intended_parents", "intended_parent_number_normalized")
    op.drop_column("intended_parents", "full_name_normalized")
    op.drop_column("surrogates", "surrogate_number_normalized")
    op.drop_column("surrogates", "full_name_normalized")
