"""Promote the Meta ad name out of surrogates.import_metadata.

Revision ID: 20261104_1220_surrogate_meta_ad_name
Revises: 20261104_1210_meta_lead_attribution_columns
"""

import sqlalchemy as sa

from alembic import op

revision = "20261104_1220_surrogate_meta_ad_name"
down_revision = "20261104_1210_meta_lead_attribution_columns"
branch_labels = None
depends_on = None

# A backfill is not a record edit: keep updated_at and the stored search vector as they are.
BACKFILL_SKIPPED_TRIGGERS = ("update_cases_updated_at", "surrogates_search_vector_trigger")


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    # Nullable without a default: a catalog-only change, no table rewrite.
    op.add_column("surrogates", sa.Column("meta_ad_name", sa.Text(), nullable=True))
    op.execute(
        """
        CREATE FUNCTION surrogates_meta_ad_name_from_metadata() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.meta_ad_name := NEW.import_metadata ->> 'meta_ad_name';
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER surrogates_meta_ad_name_from_metadata "
        "BEFORE INSERT OR UPDATE OF import_metadata ON surrogates "
        "FOR EACH ROW EXECUTE FUNCTION surrogates_meta_ad_name_from_metadata()"
    )
    # add_column holds the table lock, so no other write can run while these are off.
    for trigger in BACKFILL_SKIPPED_TRIGGERS:
        op.execute(f"ALTER TABLE surrogates DISABLE TRIGGER {trigger}")
    op.execute(
        "UPDATE surrogates SET meta_ad_name = import_metadata ->> 'meta_ad_name' "
        "WHERE import_metadata ? 'meta_ad_name'"
    )
    for trigger in BACKFILL_SKIPPED_TRIGGERS:
        op.execute(f"ALTER TABLE surrogates ENABLE TRIGGER {trigger}")


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("DROP TRIGGER surrogates_meta_ad_name_from_metadata ON surrogates")
    op.execute("DROP FUNCTION surrogates_meta_ad_name_from_metadata()")
    op.drop_column("surrogates", "meta_ad_name")
