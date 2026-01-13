"""Meta analytics enhancement: ad accounts, hierarchy, spend, forms.

Revision ID: 20260113_1000
Revises: 20260112_1631
Create Date: 2026-01-13

Comprehensive migration covering:
- Phase 1: MetaAdAccount table for per-org config
- Phase 2: Hierarchy tables (MetaCampaign, MetaAdSet, MetaAd) + Case field rename
- Phase 3: MetaDailySpend table for stored spend data
- Phase 4: Form tracking tables (MetaForm, MetaFormVersion) + MetaLead updates
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260113_1000"
down_revision: Union[str, Sequence[str], None] = "20260112_1631"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # PHASE 1: MetaAdAccount table
    # =========================================================================
    op.create_table(
        "meta_ad_accounts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        # Meta identifiers
        sa.Column("ad_account_external_id", sa.String(100), nullable=False),
        sa.Column("ad_account_name", sa.String(255), nullable=True),
        # Encrypted credentials
        sa.Column("system_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        # CAPI config (per account)
        sa.Column("pixel_id", sa.String(100), nullable=True),
        sa.Column(
            "capi_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("capi_token_encrypted", sa.Text(), nullable=True),
        # Sync watermarks
        sa.Column("hierarchy_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("spend_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("spend_sync_cursor", sa.String(255), nullable=True),
        # Status
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        # Observability
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "ad_account_external_id",
            name="uq_meta_ad_account",
        ),
    )
    op.create_index(
        "idx_meta_ad_account_org",
        "meta_ad_accounts",
        ["organization_id"],
    )

    # =========================================================================
    # PHASE 2: Hierarchy tables
    # =========================================================================

    # MetaCampaign
    op.create_table(
        "meta_campaigns",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("ad_account_id", sa.UUID(), nullable=False),
        sa.Column("campaign_external_id", sa.String(100), nullable=False),
        sa.Column("campaign_name", sa.String(500), nullable=False),
        sa.Column("objective", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ad_account_id"],
            ["meta_ad_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "ad_account_id",
            "campaign_external_id",
            name="uq_meta_campaign",
        ),
    )
    op.create_index(
        "idx_meta_campaign_account",
        "meta_campaigns",
        ["organization_id", "ad_account_id"],
    )

    # MetaAdSet
    op.create_table(
        "meta_adsets",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("ad_account_id", sa.UUID(), nullable=False),
        sa.Column("adset_external_id", sa.String(100), nullable=False),
        sa.Column("adset_name", sa.String(500), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("campaign_external_id", sa.String(100), nullable=False),
        sa.Column("targeting_geo", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ad_account_id"],
            ["meta_ad_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["meta_campaigns.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "ad_account_id",
            "adset_external_id",
            name="uq_meta_adset",
        ),
    )
    op.create_index(
        "idx_meta_adset_campaign",
        "meta_adsets",
        ["organization_id", "campaign_id"],
    )

    # MetaAd
    op.create_table(
        "meta_ads",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("ad_account_id", sa.UUID(), nullable=False),
        sa.Column("ad_external_id", sa.String(100), nullable=False),
        sa.Column("ad_name", sa.String(500), nullable=False),
        sa.Column("adset_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("adset_external_id", sa.String(100), nullable=False),
        sa.Column("campaign_external_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ad_account_id"],
            ["meta_ad_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["adset_id"],
            ["meta_adsets.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["meta_campaigns.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "ad_account_id",
            "ad_external_id",
            name="uq_meta_ad",
        ),
    )
    op.create_index(
        "idx_meta_ad_adset",
        "meta_ads",
        ["organization_id", "adset_id"],
    )
    op.create_index(
        "idx_meta_ad_external",
        "meta_ads",
        ["organization_id", "ad_external_id"],
    )

    # PHASE 2: Rename Case.meta_ad_id to meta_ad_external_id and add new fields
    # First drop the old index
    op.drop_index("idx_cases_meta_ad", table_name="cases")

    # Rename the column
    op.alter_column("cases", "meta_ad_id", new_column_name="meta_ad_external_id")

    # Add new campaign/adset tracking fields
    op.add_column(
        "cases",
        sa.Column("meta_campaign_external_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column("meta_adset_external_id", sa.String(100), nullable=True),
    )

    # Recreate index with new column name
    op.create_index(
        "idx_cases_meta_ad",
        "cases",
        ["organization_id", "meta_ad_external_id"],
        postgresql_where=sa.text("meta_ad_external_id IS NOT NULL"),
    )

    # =========================================================================
    # PHASE 3: MetaDailySpend table
    # =========================================================================
    op.create_table(
        "meta_daily_spend",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("ad_account_id", sa.UUID(), nullable=False),
        sa.Column("spend_date", sa.Date(), nullable=False),
        sa.Column("campaign_external_id", sa.String(100), nullable=False),
        sa.Column("campaign_name", sa.String(500), nullable=False),
        # Breakdown dimension - use "_total" for aggregate rows
        sa.Column("breakdown_type", sa.String(50), nullable=False),
        sa.Column("breakdown_value", sa.String(255), nullable=False),
        # Metrics
        sa.Column("spend", sa.Numeric(12, 4), nullable=False),
        sa.Column("impressions", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reach", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("leads", sa.BigInteger(), nullable=False, server_default="0"),
        # Timestamps
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ad_account_id"],
            ["meta_ad_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "ad_account_id",
            "campaign_external_id",
            "spend_date",
            "breakdown_type",
            "breakdown_value",
            name="uq_meta_daily_spend",
        ),
    )
    op.create_index(
        "idx_meta_spend_date_range",
        "meta_daily_spend",
        ["organization_id", "spend_date"],
    )
    op.create_index(
        "idx_meta_spend_campaign",
        "meta_daily_spend",
        ["organization_id", "campaign_external_id"],
    )

    # =========================================================================
    # PHASE 4: Form tracking tables + MetaLead updates
    # =========================================================================

    # Add field_data_raw to MetaLead
    op.add_column(
        "meta_leads",
        sa.Column("field_data_raw", postgresql.JSONB(), nullable=True),
    )

    # Add forms_synced_at to MetaPageMapping
    op.add_column(
        "meta_page_mappings",
        sa.Column("forms_synced_at", sa.DateTime(timezone=True), nullable=True),
    )

    # MetaForm
    op.create_table(
        "meta_forms",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("page_id", sa.String(100), nullable=False),
        sa.Column("form_external_id", sa.String(100), nullable=False),
        sa.Column("form_name", sa.String(500), nullable=False),
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "page_id",
            "form_external_id",
            name="uq_meta_form",
        ),
    )
    op.create_index(
        "idx_meta_form_page",
        "meta_forms",
        ["organization_id", "page_id"],
    )

    # MetaFormVersion
    op.create_table(
        "meta_form_versions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("form_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("field_schema", postgresql.JSONB(), nullable=False),
        sa.Column("schema_hash", sa.String(64), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["form_id"],
            ["meta_forms.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "form_id",
            "version_number",
            name="uq_meta_form_version",
        ),
        sa.UniqueConstraint(
            "form_id",
            "schema_hash",
            name="uq_meta_form_schema",
        ),
    )
    op.create_index(
        "idx_meta_form_version",
        "meta_form_versions",
        ["form_id", "version_number"],
    )

    # Add FK from meta_forms.current_version_id to meta_form_versions.id
    # (done after table creation to avoid circular dependency)
    op.create_foreign_key(
        "fk_meta_form_current_version",
        "meta_forms",
        "meta_form_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop FK first
    op.drop_constraint("fk_meta_form_current_version", "meta_forms", type_="foreignkey")

    # PHASE 4: Drop form tables
    op.drop_index("idx_meta_form_version", table_name="meta_form_versions")
    op.drop_table("meta_form_versions")

    op.drop_index("idx_meta_form_page", table_name="meta_forms")
    op.drop_table("meta_forms")

    # Remove columns from meta_page_mappings and meta_leads
    op.drop_column("meta_page_mappings", "forms_synced_at")
    op.drop_column("meta_leads", "field_data_raw")

    # PHASE 3: Drop spend table
    op.drop_index("idx_meta_spend_campaign", table_name="meta_daily_spend")
    op.drop_index("idx_meta_spend_date_range", table_name="meta_daily_spend")
    op.drop_table("meta_daily_spend")

    # PHASE 2: Revert Case column changes
    op.drop_index("idx_cases_meta_ad", table_name="cases")
    op.drop_column("cases", "meta_adset_external_id")
    op.drop_column("cases", "meta_campaign_external_id")
    op.alter_column("cases", "meta_ad_external_id", new_column_name="meta_ad_id")
    op.create_index(
        "idx_cases_meta_ad",
        "cases",
        ["organization_id", "meta_ad_id"],
        postgresql_where=sa.text("meta_ad_id IS NOT NULL"),
    )

    # PHASE 2: Drop hierarchy tables
    op.drop_index("idx_meta_ad_external", table_name="meta_ads")
    op.drop_index("idx_meta_ad_adset", table_name="meta_ads")
    op.drop_table("meta_ads")

    op.drop_index("idx_meta_adset_campaign", table_name="meta_adsets")
    op.drop_table("meta_adsets")

    op.drop_index("idx_meta_campaign_account", table_name="meta_campaigns")
    op.drop_table("meta_campaigns")

    # PHASE 1: Drop ad accounts table
    op.drop_index("idx_meta_ad_account_org", table_name="meta_ad_accounts")
    op.drop_table("meta_ad_accounts")
