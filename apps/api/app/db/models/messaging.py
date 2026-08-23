"""Organization-scoped Twilio messaging persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import EncryptedString, EncryptedText

if TYPE_CHECKING:
    from app.db.models import Organization


class TwilioSettings(Base):
    """Write-only Twilio credentials and messaging compliance configuration."""

    __tablename__ = "twilio_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    account_sid_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_sid_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    legal_messaging_brand: Mapped[str | None] = mapped_column(String(160), nullable=True)
    operational_disclosure: Mapped[str | None] = mapped_column(Text, nullable=True)
    promotional_disclosure: Mapped[str | None] = mapped_column(Text, nullable=True)
    sms_terms_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    privacy_policy_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    support_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_frequency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counsel_approved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    compliance_toolkit_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    twilio_edition: Mapped[str | None] = mapped_column(String(40), nullable=True)
    baa_verified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    compliance_approved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    phi_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    organization: Mapped[Organization] = relationship()
    routes: Mapped[list[TwilioRoute]] = relationship(
        back_populates="settings", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("current_version >= 1", name="ck_twilio_settings_version"),
    )


class TwilioRoute(Base):
    """Purpose-bound 10DLC sender. Operational and promotional routes never fall back."""

    __tablename__ = "twilio_routes"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "purpose", name="uq_twilio_routes_org_purpose"
        ),
        CheckConstraint(
            "purpose IN ('operational', 'promotional')",
            name="ck_twilio_routes_purpose",
        ),
        CheckConstraint(
            "a2p_status IN ('unconfigured', 'pending', 'approved', 'rejected')",
            name="ck_twilio_routes_a2p_status",
        ),
        CheckConstraint(
            "advanced_opt_out_status IN ('unconfigured', 'enabled', 'verified')",
            name="ck_twilio_routes_advanced_opt_out_status",
        ),
        CheckConstraint(
            "consent_management_status IN ('unknown', 'available', 'unavailable')",
            name="ck_twilio_routes_consent_management_status",
        ),
        Index("idx_twilio_routes_org", "organization_id"),
        Index("idx_twilio_routes_webhook_id", "webhook_id", unique=True),
        Index("idx_twilio_routes_sender_hash", "organization_id", "sender_phone_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    settings_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("twilio_settings.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    messaging_service_sid_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_phone_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sender_phone_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    a2p_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'unconfigured'")
    )
    advanced_opt_out_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'unconfigured'")
    )
    consent_management_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'unknown'")
    )
    capability_evidence: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    webhook_id: Mapped[str] = mapped_column(
        String(36), nullable=False, server_default=text("gen_random_uuid()::text")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    settings: Mapped[TwilioSettings] = relationship(back_populates="routes")
    organization: Mapped[Organization] = relationship()


class MessagingContact(Base):
    """One organization-scoped, encrypted recipient phone identity."""

    __tablename__ = "messaging_contacts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "phone_hash", name="uq_messaging_contacts_org_phone"
        ),
        Index("idx_messaging_contacts_org", "organization_id"),
        Index("idx_messaging_contacts_intake_lead", "organization_id", "intake_lead_id"),
        Index("idx_messaging_contacts_meta_lead", "organization_id", "meta_lead_id"),
        Index("idx_messaging_contacts_surrogate", "organization_id", "surrogate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    phone_e164: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    intake_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake_leads.id", ondelete="SET NULL"), nullable=True
    )
    meta_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_leads.id", ondelete="SET NULL"), nullable=True
    )
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    organization: Mapped[Organization] = relationship()
    consent_states: Mapped[list[MessagingConsentState]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )
    suppression: Mapped[MessagingGlobalSuppression | None] = relationship(
        back_populates="contact", cascade="all, delete-orphan", uselist=False
    )


class MessagingConsentEvidence(Base):
    """Append-only proof for one messaging consent transition."""

    __tablename__ = "messaging_consent_evidence"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_messaging_consent_evidence_org_idempotency",
        ),
        CheckConstraint(
            "purpose IN ('operational', 'promotional', 'all')",
            name="ck_messaging_consent_evidence_purpose",
        ),
        CheckConstraint(
            "action IN ('opt_in', 'opt_out', 'ambiguous_hold', 'restore')",
            name="ck_messaging_consent_evidence_action",
        ),
        Index(
            "idx_messaging_consent_evidence_timeline",
            "organization_id",
            "contact_id",
            "occurred_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messaging_contacts.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    disclosure_text_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclosure_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instruction_text: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    evidence_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    contact: Mapped[MessagingContact] = relationship()
    organization: Mapped[Organization] = relationship()


@event.listens_for(MessagingConsentEvidence, "before_update")
@event.listens_for(MessagingConsentEvidence, "before_delete")
def _prevent_messaging_consent_evidence_mutation(*_args: object) -> None:
    raise ValueError("Messaging consent evidence is immutable")


class MessagingConsentState(Base):
    """Current per-purpose projection derived from immutable evidence."""

    __tablename__ = "messaging_consent_states"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "contact_id", "purpose", name="uq_messaging_consent_state"
        ),
        CheckConstraint(
            "purpose IN ('operational', 'promotional')",
            name="ck_messaging_consent_state_purpose",
        ),
        CheckConstraint(
            "status IN ('unknown', 'opted_in', 'opted_out', 'reopt_pending')",
            name="ck_messaging_consent_state_status",
        ),
        CheckConstraint(
            "provider_sync_status IN "
            "('not_required', 'pending', 'synced', 'failed', 'unavailable')",
            name="ck_messaging_consent_state_provider_sync_status",
        ),
        Index("idx_messaging_consent_states_org_status", "organization_id", "purpose", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messaging_contacts.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'unknown'")
    )
    latest_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messaging_consent_evidence.id", ondelete="SET NULL"),
        nullable=True,
    )
    effective_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    provider_sync_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'not_required'")
    )
    provider_sync_error_code: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    provider_sync_requested_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    provider_synced_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    contact: Mapped[MessagingContact] = relationship(back_populates="consent_states")
    latest_evidence: Mapped[MessagingConsentEvidence | None] = relationship(
        foreign_keys=[latest_evidence_id]
    )


class MessagingGlobalSuppression(Base):
    """Organization-wide send block for global revocation or ambiguous scope."""

    __tablename__ = "messaging_global_suppressions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "contact_id", name="uq_messaging_global_suppression"
        ),
        CheckConstraint(
            "reason IN ('none', 'global_opt_out', 'ambiguous_hold')",
            name="ck_messaging_global_suppression_reason",
        ),
        Index("idx_messaging_global_suppressions_active", "organization_id", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messaging_contacts.id", ondelete="CASCADE"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    reason: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'none'")
    )
    latest_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messaging_consent_evidence.id", ondelete="SET NULL"),
        nullable=True,
    )
    effective_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    contact: Mapped[MessagingContact] = relationship(back_populates="suppression")
    latest_evidence: Mapped[MessagingConsentEvidence | None] = relationship(
        foreign_keys=[latest_evidence_id]
    )
