"""Promote Meta lead platform, ad id, and click id out of the lead JSONB.

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
# Frozen copy of the outbound click id search: keys compare lowercased, with "-" and
# " " as "_"; each object checks its own keys before nested values.
CLICK_ID_KEYS = ("fbc", "meta_fbc", "click_id", "meta_click_id")
CLICK_ID_KEY_TEXT = "fbc|click[-_ ]id"
# ASCII whitespace that Python str.strip() removes; E-strings have no \v escape.
WHITESPACE = r"E' \t\n\r\f\x0b'"


def _first_value(row: str, keys: tuple[str, ...]) -> str:
    lookups = [
        f"{row}.{column} ->> '{key}'" for column in ("field_data_raw", "field_data") for key in keys
    ]
    return f"coalesce({', '.join(lookups)})"


def _click_id(row: str) -> str:
    return f"meta_lead_click_id({row}.field_data_raw, {row}.field_data, {row}.raw_payload)"


def _searched(doc: str) -> str:
    return (
        f"CASE WHEN {doc}::text ~* '{CLICK_ID_KEY_TEXT}' THEN meta_lead_click_id_search({doc}) END"
    )


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    # Nullable without a default: a catalog-only change, no table rewrite.
    op.add_column("meta_leads", sa.Column("meta_platform", sa.Text(), nullable=True))
    op.add_column("meta_leads", sa.Column("meta_ad_id", sa.Text(), nullable=True))
    op.add_column("meta_leads", sa.Column("meta_click_id", sa.Text(), nullable=True))
    keys = ", ".join(f"'{key}'" for key in CLICK_ID_KEYS)
    # A string is trimmed; a list gives its first non-empty string; other values give none.
    op.execute(
        f"""
        CREATE FUNCTION meta_lead_click_id_scalar(value jsonb) RETURNS text
        LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE
            item jsonb;
            found text;
        BEGIN
            IF jsonb_typeof(value) = 'string' THEN
                RETURN nullif(btrim(value #>> '{{}}', {WHITESPACE}), '');
            ELSIF jsonb_typeof(value) = 'array' THEN
                FOR item IN SELECT element FROM jsonb_array_elements(value) AS element LOOP
                    found := meta_lead_click_id_scalar(item);
                    IF found IS NOT NULL THEN
                        RETURN found;
                    END IF;
                END LOOP;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION meta_lead_click_id_search(doc jsonb) RETURNS text
        LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE
            entry record;
            found text;
        BEGIN
            IF jsonb_typeof(doc) = 'object' THEN
                FOR entry IN SELECT key, value FROM jsonb_each(doc) LOOP
                    IF replace(replace(lower(entry.key), '-', '_'), ' ', '_') IN ({keys}) THEN
                        found := meta_lead_click_id_scalar(entry.value);
                        IF found IS NOT NULL THEN
                            RETURN found;
                        END IF;
                    END IF;
                END LOOP;
                FOR entry IN SELECT value FROM jsonb_each(doc) LOOP
                    found := meta_lead_click_id_search(entry.value);
                    IF found IS NOT NULL THEN
                        RETURN found;
                    END IF;
                END LOOP;
            ELSIF jsonb_typeof(doc) = 'array' THEN
                FOR entry IN SELECT element AS value FROM jsonb_array_elements(doc) AS element LOOP
                    found := meta_lead_click_id_search(entry.value);
                    IF found IS NOT NULL THEN
                        RETURN found;
                    END IF;
                END LOOP;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    # The first value found decides; a value without the fb. prefix is not a click id.
    # Every matching key contains fbc or click?id, so a text scan skips most documents.
    op.execute(
        f"""
        CREATE FUNCTION meta_lead_click_id(field_data_raw jsonb, field_data jsonb, raw_payload jsonb)
        RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE
            found text;
        BEGIN
            found := coalesce(
                {_searched("field_data_raw")},
                {_searched("field_data")},
                {_searched("raw_payload")}
            );
            IF left(found, 3) = 'fb.' THEN
                RETURN found;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    # Field data has several writers; the trigger keeps every one of them in step.
    op.execute(
        f"""
        CREATE FUNCTION meta_leads_attribution_from_fields() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.meta_platform := {_first_value("NEW", PLATFORM_KEYS)};
            NEW.meta_ad_id := {_first_value("NEW", AD_ID_KEYS)};
            NEW.meta_click_id := {_click_id("NEW")};
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER meta_leads_attribution_from_fields "
        "BEFORE INSERT OR UPDATE OF field_data, field_data_raw, raw_payload ON meta_leads "
        "FOR EACH ROW EXECUTE FUNCTION meta_leads_attribution_from_fields()"
    )
    op.execute(
        f"""
        UPDATE meta_leads SET
            meta_platform = {_first_value("meta_leads", PLATFORM_KEYS)},
            meta_ad_id = {_first_value("meta_leads", AD_ID_KEYS)},
            meta_click_id = {_click_id("meta_leads")}
        WHERE field_data IS NOT NULL OR field_data_raw IS NOT NULL OR raw_payload IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("DROP TRIGGER meta_leads_attribution_from_fields ON meta_leads")
    op.execute("DROP FUNCTION meta_leads_attribution_from_fields()")
    op.execute("DROP FUNCTION meta_lead_click_id(jsonb, jsonb, jsonb)")
    op.execute("DROP FUNCTION meta_lead_click_id_search(jsonb)")
    op.execute("DROP FUNCTION meta_lead_click_id_scalar(jsonb)")
    op.drop_column("meta_leads", "meta_click_id")
    op.drop_column("meta_leads", "meta_ad_id")
    op.drop_column("meta_leads", "meta_platform")
