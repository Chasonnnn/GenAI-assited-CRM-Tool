"""Models for shared form intake links and provisional leads."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import IntakeLeadStatus, TrackingMode
from app.db.types import EncryptedDate, EncryptedString

if TYPE_CHECKING:
    from app.db.models import Form, FormSubmission, Organization, Surrogate, User


class FormIntakeLink(Base):
    """Public shared intake link bound to a form."""

    __tablename__ = "form_intake_links"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_form_intake_link_org_slug"),
        Index("idx_form_intake_links_org", "organization_id"),
        Index("idx_form_intake_links_form", "form_id"),
        Index("idx_form_intake_links_slug", "slug"),
        Index("idx_form_intake_links_org_slug", "organization_id", "slug"),
        Index("idx_form_intake_links_active", "organization_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False)

    campaign_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_defaults: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    embed_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    allowed_embed_origins: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
    tracking_mode: Mapped[str] = mapped_column(
        String(30),
        server_default=text(f"'{TrackingMode.INTERNAL_ONLY.value}'"),
        nullable=False,
    )
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_policy_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thank_you_config: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    embed_theme_json: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("published_intake_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)
    max_submissions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submissions_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship()
    form: Mapped["Form"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])


class PublishedIntakeVersion(Base):
    """Immutable public intake configuration used to interpret submissions."""

    __tablename__ = "published_intake_versions"
    __table_args__ = (
        Index("idx_published_intake_versions_org", "organization_id"),
        Index("idx_published_intake_versions_link", "intake_link_id"),
        Index("idx_published_intake_versions_form", "form_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    intake_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_intake_links.id", ondelete="CASCADE"),
        nullable=False,
    )
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    form_version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    form_schema_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    field_policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    mapping_snapshot_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    consent_text_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    thank_you_config_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tracking_mode_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    tracking_policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embed_theme_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )

    organization: Mapped["Organization"] = relationship()
    form: Mapped["Form"] = relationship()
    intake_link: Mapped["FormIntakeLink"] = relationship(foreign_keys=[intake_link_id])


class IntakeLead(Base):
    """Provisional lead created from unmatched shared submissions."""

    __tablename__ = "intake_leads"
    __table_args__ = (
        Index("idx_intake_leads_org", "organization_id"),
        Index("idx_intake_leads_form", "form_id"),
        Index("idx_intake_leads_status", "organization_id", "status"),
        Index("idx_intake_leads_email_hash", "organization_id", "email_hash"),
        Index("idx_intake_leads_phone_hash", "organization_id", "phone_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="SET NULL"),
        nullable=True,
    )
    intake_link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_intake_links.id", ondelete="SET NULL"),
        nullable=True,
    )
    form_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(30), server_default=text("'shared_intake'"), nullable=False
    )
    lead_type: Mapped[str] = mapped_column(
        String(40), server_default=text("'surrogate'"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)

    status: Mapped[str] = mapped_column(
        String(30),
        server_default=text(f"'{IntakeLeadStatus.PENDING_REVIEW.value}'"),
        nullable=False,
    )
    promoted_surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogates.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )
    promoted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)

    organization: Mapped["Organization"] = relationship()
    form: Mapped["Form | None"] = relationship()
    intake_link: Mapped["FormIntakeLink | None"] = relationship()
    form_submission: Mapped["FormSubmission | None"] = relationship(
        foreign_keys=[form_submission_id]
    )
    promoted_surrogate: Mapped["Surrogate | None"] = relationship(
        foreign_keys=[promoted_surrogate_id]
    )


class LeadAttribution(Base):
    """Campaign attribution captured for a public intake submission."""

    __tablename__ = "lead_attribution"
    __table_args__ = (
        Index("idx_lead_attribution_org", "organization_id"),
        Index("idx_lead_attribution_submission", "form_submission_id"),
        Index("idx_lead_attribution_link", "intake_link_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    form_submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_submissions.id", ondelete="CASCADE"), nullable=False
    )
    intake_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_intake_links.id", ondelete="CASCADE"), nullable=False
    )
    source_surface: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    medium: Mapped[str | None] = mapped_column(String(255), nullable=True)
    campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ad_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adset_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    campaign_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fbclid: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fbc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fbp: Mapped[str | None] = mapped_column(String(500), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    parent_origin: Mapped[str | None] = mapped_column(String(500), nullable=True)
    landing_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    first_touch_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_touch_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )


class ConsentRecord(Base):
    """Immutable consent snapshot for a public intake submission."""

    __tablename__ = "consent_records"
    __table_args__ = (
        Index("idx_consent_records_org", "organization_id"),
        Index("idx_consent_records_submission", "form_submission_id"),
        Index("idx_consent_records_link", "intake_link_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    intake_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_intake_links.id", ondelete="CASCADE"), nullable=False
    )
    form_submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_submissions.id", ondelete="CASCADE"), nullable=False
    )
    consent_type: Mapped[str] = mapped_column(String(40), nullable=False)
    consent_text_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_origin: Mapped[str | None] = mapped_column(String(500), nullable=True)
    privacy_policy_url_snapshot: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class EmbedSession(Base):
    """Short-lived browser session required for embed submissions."""

    __tablename__ = "embed_sessions"
    __table_args__ = (
        UniqueConstraint("public_session_token_hash", name="uq_embed_session_token_hash"),
        Index("idx_embed_sessions_org", "organization_id"),
        Index("idx_embed_sessions_link", "intake_link_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    intake_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_intake_links.id", ondelete="CASCADE"), nullable=False
    )
    public_session_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_origin: Mapped[str] = mapped_column(String(500), nullable=False)
    attribution_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )


class TrackingEventLog(Base):
    """Outbound tracking gateway event log."""

    __tablename__ = "tracking_event_logs"
    __table_args__ = (
        Index("idx_tracking_event_logs_org", "organization_id"),
        Index("idx_tracking_event_logs_submission", "form_submission_id"),
        Index("idx_tracking_event_logs_destination", "organization_id", "destination", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    intake_link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_intake_links.id", ondelete="SET NULL"), nullable=True
    )
    form_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_submissions.id", ondelete="SET NULL"), nullable=True
    )
    event_name: Mapped[str] = mapped_column(String(80), nullable=False)
    destination: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )


class FormSubmissionMatchCandidate(Base):
    """Possible surrogate matches for an ambiguous shared submission."""

    __tablename__ = "form_submission_match_candidates"
    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            "surrogate_id",
            name="uq_form_submission_match_candidate_pair",
        ),
        Index("idx_form_submission_match_candidates_org", "organization_id"),
        Index("idx_form_submission_match_candidates_submission", "submission_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogates.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )

    submission: Mapped["FormSubmission"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()


class FormIntakeDraft(Base):
    """Autosaved draft state for shared intake sessions."""

    __tablename__ = "form_intake_drafts"
    __table_args__ = (
        UniqueConstraint(
            "intake_link_id",
            "draft_session_id",
            name="uq_form_intake_draft_session",
        ),
        Index("idx_form_intake_drafts_org", "organization_id"),
        Index("idx_form_intake_drafts_link", "intake_link_id"),
        Index("idx_form_intake_drafts_form", "form_id"),
        Index(
            "idx_form_intake_drafts_org_form_updated",
            "organization_id",
            "form_id",
            "updated_at",
        ),
        Index(
            "idx_form_intake_drafts_identity_email",
            "organization_id",
            "form_id",
            "full_name_normalized",
            "date_of_birth",
            "email_hash",
            "updated_at",
        ),
        Index(
            "idx_form_intake_drafts_identity_phone",
            "organization_id",
            "form_id",
            "full_name_normalized",
            "date_of_birth",
            "phone_hash",
            "updated_at",
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
    intake_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_intake_links.id", ondelete="CASCADE"),
        nullable=False,
    )
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    draft_session_id: Mapped[str] = mapped_column(String(120), nullable=False)
    answers_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    full_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship()
    intake_link: Mapped["FormIntakeLink"] = relationship()
    form: Mapped["Form"] = relationship()
