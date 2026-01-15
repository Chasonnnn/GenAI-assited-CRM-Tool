"""Add full-text search infrastructure.

Revision ID: 5764ba19b573
Revises: fdd16771f703
Create Date: 2024-12-27
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5764ba19b573"
down_revision = "fdd16771f703"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add tsvector columns for full-text search
    op.add_column(
        "cases",
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR, nullable=True),
    )
    op.add_column(
        "entity_notes",
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR, nullable=True),
    )
    op.add_column(
        "attachments",
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR, nullable=True),
    )
    op.add_column(
        "intended_parents",
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR, nullable=True),
    )

    # Create GIN indexes for full-text search
    op.create_index(
        "ix_cases_search_vector",
        "cases",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_entity_notes_search_vector",
        "entity_notes",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_attachments_search_vector",
        "attachments",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_intended_parents_search_vector",
        "intended_parents",
        ["search_vector"],
        postgresql_using="gin",
    )

    # Create trigger functions for auto-updating tsvector columns
    # Using 'simple' dictionary for names/emails (no stemming)

    # Cases trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION cases_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '') || ' ' ||
                coalesce(NEW.case_number, '') || ' ' ||
                coalesce(NEW.email, '') || ' ' ||
                coalesce(NEW.phone, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER cases_search_vector_trigger
        BEFORE INSERT OR UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION cases_search_vector_update();
    """)

    # Entity notes trigger function (strip HTML tags)
    op.execute("""
        CREATE OR REPLACE FUNCTION entity_notes_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                regexp_replace(coalesce(NEW.content, ''), '<[^>]+>', ' ', 'g')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER entity_notes_search_vector_trigger
        BEFORE INSERT OR UPDATE ON entity_notes
        FOR EACH ROW EXECUTE FUNCTION entity_notes_search_vector_update();
    """)

    # Attachments trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION attachments_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.filename, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER attachments_search_vector_trigger
        BEFORE INSERT OR UPDATE ON attachments
        FOR EACH ROW EXECUTE FUNCTION attachments_search_vector_update();
    """)

    # Intended parents trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION intended_parents_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '') || ' ' ||
                coalesce(NEW.email, '') || ' ' ||
                coalesce(NEW.phone, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER intended_parents_search_vector_trigger
        BEFORE INSERT OR UPDATE ON intended_parents
        FOR EACH ROW EXECUTE FUNCTION intended_parents_search_vector_update();
    """)

    # Backfill existing rows
    op.execute("""
        UPDATE cases SET search_vector = to_tsvector('simple',
            coalesce(full_name, '') || ' ' ||
            coalesce(case_number, '') || ' ' ||
            coalesce(email, '') || ' ' ||
            coalesce(phone, '')
        );
    """)

    op.execute("""
        UPDATE entity_notes SET search_vector = to_tsvector('simple',
            regexp_replace(coalesce(content, ''), '<[^>]+>', ' ', 'g')
        );
    """)

    op.execute("""
        UPDATE attachments SET search_vector = to_tsvector('simple',
            coalesce(filename, '')
        );
    """)

    op.execute("""
        UPDATE intended_parents SET search_vector = to_tsvector('simple',
            coalesce(full_name, '') || ' ' ||
            coalesce(email, '') || ' ' ||
            coalesce(phone, '')
        );
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS cases_search_vector_trigger ON cases;")
    op.execute("DROP TRIGGER IF EXISTS entity_notes_search_vector_trigger ON entity_notes;")
    op.execute("DROP TRIGGER IF EXISTS attachments_search_vector_trigger ON attachments;")
    op.execute("DROP TRIGGER IF EXISTS intended_parents_search_vector_trigger ON intended_parents;")

    # Drop trigger functions
    op.execute("DROP FUNCTION IF EXISTS cases_search_vector_update();")
    op.execute("DROP FUNCTION IF EXISTS entity_notes_search_vector_update();")
    op.execute("DROP FUNCTION IF EXISTS attachments_search_vector_update();")
    op.execute("DROP FUNCTION IF EXISTS intended_parents_search_vector_update();")

    # Drop indexes
    op.drop_index("ix_cases_search_vector", "cases")
    op.drop_index("ix_entity_notes_search_vector", "entity_notes")
    op.drop_index("ix_attachments_search_vector", "attachments")
    op.drop_index("ix_intended_parents_search_vector", "intended_parents")

    # Drop columns
    op.drop_column("cases", "search_vector")
    op.drop_column("entity_notes", "search_vector")
    op.drop_column("attachments", "search_vector")
    op.drop_column("intended_parents", "search_vector")
