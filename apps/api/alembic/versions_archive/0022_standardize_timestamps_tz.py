"""Standardize legacy timestamps to TIMESTAMPTZ and normalize constraint names.

Revision ID: 0022_standardize_timestamps_tz
Revises: 0021_org_integration_versioning
Create Date: 2025-12-18

Why:
- Earlier migrations created some timestamps as TIMESTAMP WITHOUT TIME ZONE.
- Models now standardize on timezone-aware datetimes (TIMESTAMPTZ).
- auth_identities unique constraint was unnamed in the baseline (Postgres auto name).

This migration:
- Converts legacy timestamp columns to TIMESTAMPTZ, treating stored values as UTC.
- Renames the auth_identities (provider, provider_subject) unique constraint to uq_auth_identity.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0022_standardize_timestamps_tz"
down_revision: Union[str, Sequence[str], None] = "0021_org_integration_versioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _to_timestamptz(table: str, column: str) -> None:
    op.execute(
        f"ALTER TABLE {table} "
        f"ALTER COLUMN {column} TYPE TIMESTAMPTZ "
        f"USING {column} AT TIME ZONE 'UTC'"
    )


def _to_timestamp(table: str, column: str) -> None:
    op.execute(
        f"ALTER TABLE {table} "
        f"ALTER COLUMN {column} TYPE TIMESTAMP WITHOUT TIME ZONE "
        f"USING {column} AT TIME ZONE 'UTC'"
    )


def upgrade() -> None:
    # Rename baseline auto-generated unique constraint to match model metadata
    op.execute(
        "ALTER TABLE auth_identities "
        "RENAME CONSTRAINT auth_identities_provider_provider_subject_key TO uq_auth_identity"
    )

    # Legacy timestamp columns created without timezone
    _to_timestamptz("email_templates", "created_at")
    _to_timestamptz("email_templates", "updated_at")

    _to_timestamptz("jobs", "run_at")
    _to_timestamptz("jobs", "created_at")
    _to_timestamptz("jobs", "completed_at")

    _to_timestamptz("email_logs", "sent_at")
    _to_timestamptz("email_logs", "created_at")

    _to_timestamptz("entity_notes", "created_at")

    _to_timestamptz("intended_parents", "archived_at")
    _to_timestamptz("intended_parents", "last_activity")
    _to_timestamptz("intended_parents", "created_at")
    _to_timestamptz("intended_parents", "updated_at")

    _to_timestamptz("intended_parent_status_history", "changed_at")

    _to_timestamptz("case_activity_log", "created_at")

    _to_timestamptz("notifications", "read_at")
    _to_timestamptz("notifications", "created_at")
    _to_timestamptz("user_notification_settings", "updated_at")

    _to_timestamptz("audit_logs", "created_at")

    _to_timestamptz("case_imports", "created_at")
    _to_timestamptz("case_imports", "completed_at")

    _to_timestamptz("pipelines", "created_at")
    _to_timestamptz("pipelines", "updated_at")

    _to_timestamptz("entity_versions", "created_at")

    _to_timestamptz("meta_page_mappings", "token_expires_at")
    _to_timestamptz("meta_page_mappings", "last_success_at")
    _to_timestamptz("meta_page_mappings", "last_error_at")
    _to_timestamptz("meta_page_mappings", "created_at")
    _to_timestamptz("meta_page_mappings", "updated_at")


def downgrade() -> None:
    _to_timestamp("meta_page_mappings", "updated_at")
    _to_timestamp("meta_page_mappings", "created_at")
    _to_timestamp("meta_page_mappings", "last_error_at")
    _to_timestamp("meta_page_mappings", "last_success_at")
    _to_timestamp("meta_page_mappings", "token_expires_at")

    _to_timestamp("entity_versions", "created_at")

    _to_timestamp("pipelines", "updated_at")
    _to_timestamp("pipelines", "created_at")

    _to_timestamp("case_imports", "completed_at")
    _to_timestamp("case_imports", "created_at")

    _to_timestamp("audit_logs", "created_at")

    _to_timestamp("user_notification_settings", "updated_at")
    _to_timestamp("notifications", "created_at")
    _to_timestamp("notifications", "read_at")

    _to_timestamp("case_activity_log", "created_at")

    _to_timestamp("intended_parent_status_history", "changed_at")

    _to_timestamp("intended_parents", "updated_at")
    _to_timestamp("intended_parents", "created_at")
    _to_timestamp("intended_parents", "last_activity")
    _to_timestamp("intended_parents", "archived_at")

    _to_timestamp("entity_notes", "created_at")

    _to_timestamp("email_logs", "created_at")
    _to_timestamp("email_logs", "sent_at")

    _to_timestamp("jobs", "completed_at")
    _to_timestamp("jobs", "created_at")
    _to_timestamp("jobs", "run_at")

    _to_timestamp("email_templates", "updated_at")
    _to_timestamp("email_templates", "created_at")

    op.execute(
        "ALTER TABLE auth_identities "
        "RENAME CONSTRAINT uq_auth_identity TO auth_identities_provider_provider_subject_key"
    )
