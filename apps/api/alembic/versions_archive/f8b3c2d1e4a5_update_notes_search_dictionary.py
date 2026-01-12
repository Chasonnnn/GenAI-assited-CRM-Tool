"""Update notes search to use english dictionary.

Revision ID: f8b3c2d1e4a5
Revises: a06f4ea4bd21
Create Date: 2024-12-27
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "f8b3c2d1e4a5"
down_revision = "a06f4ea4bd21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update the trigger function to use 'english' dictionary for notes
    # This provides stemming for better search coverage
    op.execute("""
        CREATE OR REPLACE FUNCTION entity_notes_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                regexp_replace(coalesce(NEW.content, ''), '<[^>]+>', ' ', 'g')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    # Backfill existing notes with new dictionary
    op.execute("""
        UPDATE entity_notes SET search_vector = to_tsvector('english',
            regexp_replace(coalesce(content, ''), '<[^>]+>', ' ', 'g')
        );
    """)


def downgrade() -> None:
    # Revert to 'simple' dictionary
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

    # Backfill existing notes with simple dictionary
    op.execute("""
        UPDATE entity_notes SET search_vector = to_tsvector('simple',
            regexp_replace(coalesce(content, ''), '<[^>]+>', ' ', 'g')
        );
    """)
