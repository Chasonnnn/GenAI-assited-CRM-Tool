"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization
    from app.db.models.auth import User


class MetaOAuthConnection(Base):
    """
    OAuth connection for Meta/Facebook Business.

    Stores long-lived user tokens for accessing Meta APIs.
    Multiple connections per org allowed (different users can connect different assets).
    """

    __tablename__ = "meta_oauth_connections"
    __table_args__ = (
        # Multiple connections per org allowed, but unique per Meta user
        UniqueConstraint("organization_id", "meta_user_id", name="uq_meta_oauth_org_user"),
        Index("idx_meta_oauth_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Meta user who authenticated (no email - just id and name)
    meta_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    meta_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Long-lived token (60 days or non-expiring for Marketing API)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Granted scopes - for validation and UI display
    granted_scopes: Mapped[list] = mapped_column(JSONB, nullable=False)

    # Who connected (internal user)
    connected_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Connection health tracking
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Error category for classification (auth, rate_limit, transient, permission, unknown)
    last_error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Future: support system user tokens
    connection_type: Mapped[str] = mapped_column(
        String(20), server_default=text("'user'"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    connected_by_user: Mapped["User"] = relationship(foreign_keys=[connected_by_user_id])


class MetaLead(Base):
    """
    Raw leads from Meta Lead Ads webhook.

    Stored separately from cases for clean separation:
    - meta_leads = raw ingestion (Meta-specific, immutable)
    - cases = normalized working object
    """

    __tablename__ = "meta_leads"
    __table_args__ = (
        UniqueConstraint("organization_id", "meta_lead_id", name="uq_meta_lead"),
        Index("idx_meta_leads_status", "organization_id", "status"),
        Index(
            "idx_meta_unconverted",
            "organization_id",
            postgresql_where=text("is_converted = FALSE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Meta identifiers
    meta_lead_id: Mapped[str] = mapped_column(String(100), nullable=False)
    meta_form_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meta_page_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Data storage
    field_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Raw field_data preserving multi-select arrays (for form analysis)
    field_data_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Fields not covered by current mapping (for review)
    unmapped_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Conversion status
    is_converted: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    converted_surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogates.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    conversion_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    meta_created_time: Mapped[datetime | None] = mapped_column(nullable=True)
    received_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    converted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Processing status (for observability)
    # Values: received, fetching, fetch_failed, stored, converted, convert_failed
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'received'"), nullable=False
    )
    fetch_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MetaPageMapping(Base):
    """
    Maps Meta page IDs to organizations for webhook routing.

    Stores encrypted access tokens for secure API calls.
    """

    __tablename__ = "meta_page_mappings"
    __table_args__ = (
        UniqueConstraint("page_id", name="uq_meta_page_id"),
        Index("idx_meta_page_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Meta page info
    page_id: Mapped[str] = mapped_column(String(100), nullable=False)
    page_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # OAuth connection (used for ownership + reauth tracking)
    oauth_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_oauth_connections.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Page access token from OAuth (/me/accounts) for leadgen/webhook calls
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)

    # Observability
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Form sync watermark (forms sync uses page tokens, not ad account tokens)
    forms_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    oauth_connection: Mapped["MetaOAuthConnection | None"] = relationship()


class MetaAdAccount(Base):
    """
    Per-org Meta Ad Account configuration with encrypted tokens.

    Replaces global META_AD_ACCOUNT_ID / META_SYSTEM_TOKEN with per-org config.
    """

    __tablename__ = "meta_ad_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "ad_account_external_id", name="uq_meta_ad_account"),
        Index("idx_meta_ad_account_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Meta identifiers
    ad_account_external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ad_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # OAuth connection for access token
    oauth_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_oauth_connections.id", ondelete="SET NULL"),
        nullable=True,
    )

    # CAPI config (per account - replaces global settings.META_PIXEL_ID)
    pixel_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capi_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )

    # Sync watermarks (hierarchy and spend only - forms use page tokens)
    hierarchy_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    spend_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    spend_sync_cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status (soft-delete to preserve historical data)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)

    # Observability
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    oauth_connection: Mapped["MetaOAuthConnection | None"] = relationship()
    campaigns: Mapped[list["MetaCampaign"]] = relationship(
        back_populates="ad_account", cascade="all, delete-orphan"
    )
    adsets: Mapped[list["MetaAdSet"]] = relationship(
        back_populates="ad_account", cascade="all, delete-orphan"
    )
    ads: Mapped[list["MetaAd"]] = relationship(
        back_populates="ad_account", cascade="all, delete-orphan"
    )


class MetaCampaign(Base):
    """
    Meta Ad Campaign synced from Marketing API.

    Part of the ad hierarchy: Account → Campaign → AdSet → Ad
    """

    __tablename__ = "meta_campaigns"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "ad_account_id",
            "campaign_external_id",
            name="uq_meta_campaign",
        ),
        Index("idx_meta_campaign_account", "organization_id", "ad_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    ad_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_ad_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    campaign_external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(500), nullable=False)
    objective: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Meta's updated_time for delta sync
    updated_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    ad_account: Mapped["MetaAdAccount"] = relationship(back_populates="campaigns")
    adsets: Mapped[list["MetaAdSet"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    ads: Mapped[list["MetaAd"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class MetaAdSet(Base):
    """
    Meta Ad Set synced from Marketing API.

    Contains targeting info useful for regional analysis.
    """

    __tablename__ = "meta_adsets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "ad_account_id",
            "adset_external_id",
            name="uq_meta_adset",
        ),
        Index("idx_meta_adset_campaign", "organization_id", "campaign_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    ad_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_ad_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    adset_external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    adset_name: Mapped[str] = mapped_column(String(500), nullable=False)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_external_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Targeting info (useful for regional analysis)
    targeting_geo: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    ad_account: Mapped["MetaAdAccount"] = relationship(back_populates="adsets")
    campaign: Mapped["MetaCampaign"] = relationship(back_populates="adsets")
    ads: Mapped[list["MetaAd"]] = relationship(back_populates="adset", cascade="all, delete-orphan")


class MetaAd(Base):
    """
    Meta Ad synced from Marketing API.

    Linked to cases via ad_external_id for campaign attribution.
    """

    __tablename__ = "meta_ads"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "ad_account_id",
            "ad_external_id",
            name="uq_meta_ad",
        ),
        Index("idx_meta_ad_adset", "organization_id", "adset_id"),
        Index("idx_meta_ad_external", "organization_id", "ad_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    ad_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_ad_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    ad_external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ad_name: Mapped[str] = mapped_column(String(500), nullable=False)
    adset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_adsets.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Denormalized external IDs for reporting joins
    adset_external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_external_id: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    ad_account: Mapped["MetaAdAccount"] = relationship(back_populates="ads")
    adset: Mapped["MetaAdSet"] = relationship(back_populates="ads")
    campaign: Mapped["MetaCampaign"] = relationship(back_populates="ads")


class MetaDailySpend(Base):
    """
    Daily spend data per campaign, with optional breakdown dimensions.

    Synced from Meta Marketing API insights endpoint.
    """

    __tablename__ = "meta_daily_spend"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "ad_account_id",
            "campaign_external_id",
            "spend_date",
            "breakdown_type",
            "breakdown_value",
            name="uq_meta_daily_spend",
        ),
        Index("idx_meta_spend_date_range", "organization_id", "spend_date"),
        Index("idx_meta_spend_campaign", "organization_id", "campaign_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    ad_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_ad_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Time dimension
    spend_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Campaign (denormalized for historical accuracy)
    campaign_external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Breakdown dimension (one per row, no cross-dim)
    # breakdown_type: "_total" (aggregate), "publisher_platform", etc.
    breakdown_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # For _total rows: breakdown_value="_all" (stable unique key)
    breakdown_value: Mapped[str] = mapped_column(String(255), nullable=False)

    # Metrics
    spend: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    impressions: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    reach: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    clicks: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    leads: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)

    synced_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    ad_account: Mapped["MetaAdAccount"] = relationship()


class MetaForm(Base):
    """
    Form metadata synced from Meta Lead Ads.

    Tracks form versions for schema change detection.
    """

    __tablename__ = "meta_forms"
    __table_args__ = (
        UniqueConstraint("organization_id", "page_id", "form_external_id", name="uq_meta_form"),
        Index("idx_meta_form_page", "organization_id", "page_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_id: Mapped[str] = mapped_column(String(100), nullable=False)

    form_external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    form_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Current schema version
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_form_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Mapping configuration (per form)
    mapping_rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    mapping_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_form_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    mapping_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'unmapped'"), nullable=False
    )  # unmapped, mapped, outdated
    unknown_column_behavior: Mapped[str] = mapped_column(
        String(20), server_default=text("'metadata'"), nullable=False
    )
    mapping_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mapping_updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    versions: Mapped[list["MetaFormVersion"]] = relationship(
        back_populates="form",
        foreign_keys="MetaFormVersion.form_id",
        cascade="all, delete-orphan",
    )


class MetaFormVersion(Base):
    """
    Versioned form field schema for historical analysis.

    New version created when schema changes (detected via hash).
    """

    __tablename__ = "meta_form_versions"
    __table_args__ = (
        UniqueConstraint("form_id", "version_number", name="uq_meta_form_version"),
        UniqueConstraint("form_id", "schema_hash", name="uq_meta_form_schema"),
        Index("idx_meta_form_version", "form_id", "version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_forms.id", ondelete="CASCADE"),
        nullable=False,
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    field_schema: Mapped[list] = mapped_column(JSONB, nullable=False)
    schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    detected_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    form: Mapped["MetaForm"] = relationship(back_populates="versions", foreign_keys=[form_id])


# =============================================================================
# Jobs & Email Models
# =============================================================================
