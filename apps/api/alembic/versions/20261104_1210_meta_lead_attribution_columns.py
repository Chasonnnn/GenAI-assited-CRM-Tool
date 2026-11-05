"""Promote Meta lead platform and ad id out of the field data JSONB.

Revision ID: 20261104_1210_meta_lead_attribution_columns
Revises: 20261104_1200_job_subject_columns
"""

import sqlalchemy as sa

from alembic import op

revision = "20261104_1210_meta_lead_attribution_columns"
down_revision = "20261104_1200_job_subject_columns"
branch_labels = None
depends_on = None

# Frozen copy of the analytics lookup order: raw field data first, then normalized.
PLATFORM_KEYS = ("meta_platform", "platform", "publisher_platform")
AD_ID_KEYS = ("meta_ad_id", "ad_id")


def _first_value(row: str, keys: tuple[str, ...]) -> str:
    lookups = [
        f"{row}.{column} ->> '{key}'" for column in ("field_data_raw", "field_data") for key in keys
    ]
    return f"coalesce({', '.join(lookups)})"


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    # Nullable without a default: a catalog-only change, no table rewrite.
    op.add_column("meta_leads", sa.Column("meta_platform", sa.Text(), nullable=True))
    op.add_column("meta_leads", sa.Column("meta_ad_id", sa.Text(), nullable=True))
    # Field data has several writers; the trigger keeps every one of them in step.
    op.execute(
        f"""
        CREATE FUNCTION meta_leads_attribution_from_fields() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.meta_platform := {_first_value("NEW", PLATFORM_KEYS)};
            NEW.meta_ad_id := {_first_value("NEW", AD_ID_KEYS)};
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER meta_leads_attribution_from_fields "
        "BEFORE INSERT OR UPDATE OF field_data, field_data_raw ON meta_leads "
        "FOR EACH ROW EXECUTE FUNCTION meta_leads_attribution_from_fields()"
    )
    op.execute(
        f"""
        UPDATE meta_leads SET
            meta_platform = {_first_value("meta_leads", PLATFORM_KEYS)},
            meta_ad_id = {_first_value("meta_leads", AD_ID_KEYS)}
        WHERE field_data IS NOT NULL OR field_data_raw IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("DROP TRIGGER meta_leads_attribution_from_fields ON meta_leads")
    op.execute("DROP FUNCTION meta_leads_attribution_from_fields()")
    op.drop_column("meta_leads", "meta_ad_id")
    op.drop_column("meta_leads", "meta_platform")
