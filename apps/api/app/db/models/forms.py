"""SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    FormLeadKind,
    FormPurpose,
    FormStatus,
    FormSubmissionMatchStatus,
    FormSubmissionStatus,
)
from app.db.types import EncryptedDate

if TYPE_CHECKING:
    from app.db.models import Donor, Organization, Surrogate, User


class Form(Base):
    """Application form configuration."""

    __tablename__ = "forms"
    __table_args__ = (
        Index("idx_forms_org", "organization_id"),
        Index("idx_forms_org_status", "organization_id", "status"),
        Index("idx_forms_org_purpose_status", "organization_id", "purpose", "status"),
        Index("idx_forms_org_lead_kind_status", "organization_id", "lead_kind", "status"),
        CheckConstraint(
            "lead_kind IN ('surrogate', 'egg_donor', 'sperm_donor')",
            name="ck_forms_lead_kind",
        ),
        CheckConstraint(
            "routing_exact_match IN ('auto', 'review')", name="ck_forms_routing_exact_match"
        ),
        CheckConstraint(
            "routing_no_match IN ('auto', 'review', 'off')", name="ck_forms_routing_no_match"
        ),
        CheckConstraint(
            "routing_lead_source IS NULL OR routing_lead_source IN ('website', 'form_embed')",
            name="ck_forms_routing_lead_source",
        ),
        CheckConstraint(
            "NOT routing_auto_create_donor OR lead_kind <> 'surrogate'",
            name="ck_forms_routing_auto_create_donor",
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
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{FormStatus.DRAFT.value}'"),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(
        String(40),
        server_default=text(f"'{FormPurpose.SURROGATE_APPLICATION.value}'"),
        nullable=False,
    )
    lead_kind: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{FormLeadKind.SURROGATE.value}'"),
        nullable=False,
    )

    routing_exact_match: Mapped[str] = mapped_column(
        String(10),
        default=lambda ctx: (
            "auto"
            if ctx.get_current_parameters().get("lead_kind") in {"egg_donor", "sperm_donor"}
            else "review"
        ),
        nullable=False,
        server_default=text("'review'"),
    )
    routing_no_match: Mapped[str] = mapped_column(
        String(10),
        default=lambda ctx: (
            "auto"
            if ctx.get_current_parameters().get("lead_kind") in {"egg_donor", "sperm_donor"}
            else "review"
        ),
        nullable=False,
        server_default=text("'review'"),
    )
    routing_lead_source: Mapped[str | None] = mapped_column(
        String(20),
        default=lambda ctx: (
            "website"
            if ctx.get_current_parameters().get("lead_kind") in {"egg_donor", "sperm_donor"}
            else None
        ),
        nullable=True,
    )
    routing_auto_create_donor: Mapped[bool] = mapped_column(
        Boolean,
        default=lambda ctx: (
            ctx.get_current_parameters().get("lead_kind") in {"egg_donor", "sperm_donor"}
        ),
        nullable=False,
        server_default=text("false"),
    )
    routing_updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Draft + published schemas (no versioning; published is last published snapshot)
    schema_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    published_schema_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # File settings (per form, configurable by admin)
    max_file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        default=10 * 1024 * 1024,
        server_default=text("10485760"),
        nullable=False,
    )
    max_file_count: Mapped[int] = mapped_column(
        Integer, default=10, server_default=text("10"), nullable=False
    )
    allowed_mime_types: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    default_application_email_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )

    organization: Mapped[Organization] = relationship(foreign_keys=[organization_id])


class FormLogo(Base):
    """Stored logo asset for forms."""

    __tablename__ = "form_logos"
    __table_args__ = (Index("idx_form_logos_org", "organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    organization: Mapped[Organization] = relationship()
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])


class FormFieldMapping(Base):
    """Map form field keys to case fields."""

    __tablename__ = "form_field_mappings"
    __table_args__ = (
        UniqueConstraint("form_id", "field_key", name="uq_form_field_key"),
        UniqueConstraint("form_id", "surrogate_field", name="uq_form_surrogate_field"),
        Index("idx_form_mappings_form", "form_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    surrogate_field: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )


class FormSubmission(Base):
    """A submitted application form response."""

    __tablename__ = "form_submissions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_form_submissions_org_id"),
        CheckConstraint(
            "routing_review_step IS NULL OR routing_review_step IN ('match', 'create_lead')",
            name="ck_form_submissions_routing_review_step",
        ),
        CheckConstraint(
            "(match_status = 'routing_review') = (routing_review_step IS NOT NULL)",
            name="ck_form_submissions_routing_review_status",
        ),
        Index("idx_form_submissions_org", "organization_id"),
        Index("idx_form_submissions_form", "form_id"),
        Index("idx_form_submissions_surrogate", "surrogate_id"),
        Index("idx_form_submissions_donor", "donor_id"),
        Index("idx_form_submissions_status", "status"),
        Index("idx_form_submissions_match_status", "match_status"),
        Index(
            "uq_form_submission_surrogate_non_null",
            "form_id",
            "surrogate_id",
            unique=True,
            postgresql_where=text("surrogate_id IS NOT NULL"),
        ),
        Index(
            "uq_form_submission_donor_non_null",
            "form_id",
            "donor_id",
            unique=True,
            postgresql_where=text("donor_id IS NOT NULL"),
        ),
        CheckConstraint(
            "lead_kind IN ('surrogate', 'egg_donor', 'sperm_donor')",
            name="ck_form_submissions_lead_kind",
        ),
        CheckConstraint(
            "surrogate_id IS NULL OR donor_id IS NULL",
            name="ck_form_submissions_single_subject",
        ),
        Index(
            "uq_form_submission_intake_idempotency",
            "organization_id",
            "intake_link_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "idx_form_submission_duplicate_email",
            "organization_id",
            "form_id",
            "full_name_normalized",
            "date_of_birth_hash",
            "email_hash",
            postgresql_where=text("email_hash IS NOT NULL"),
        ),
        Index(
            "idx_form_submission_duplicate_phone",
            "organization_id",
            "form_id",
            "full_name_normalized",
            "date_of_birth_hash",
            "phone_hash",
            postgresql_where=text("phone_hash IS NOT NULL"),
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
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=True
    )
    donor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("donors.id", ondelete="SET NULL"), nullable=True
    )
    intake_link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_intake_links.id", ondelete="SET NULL"),
        nullable=True,
    )
    intake_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intake_leads.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("published_intake_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    form_schema_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consent_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tracking_policy_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)
    date_of_birth_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_mode: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'shared'"),
        nullable=False,
    )
    lead_kind: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{FormLeadKind.SURROGATE.value}'"),
        nullable=False,
    )
    match_status: Mapped[str] = mapped_column(
        String(30),
        server_default=text(f"'{FormSubmissionMatchStatus.LINKED.value}'"),
        nullable=False,
    )
    match_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    routing_review_step: Mapped[str | None] = mapped_column(String(20), nullable=True)
    matched_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{FormSubmissionStatus.PENDING_REVIEW.value}'"),
        nullable=False,
    )
    answers_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    schema_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    mapping_snapshot: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    form: Mapped[Form] = relationship()
    surrogate: Mapped[Surrogate | None] = relationship()
    donor: Mapped[Donor | None] = relationship()


class FormSubmissionDraft(Base):
    """Server-side draft responses for public form autosave."""

    __tablename__ = "form_submission_drafts"
    __table_args__ = (
        UniqueConstraint("form_id", "surrogate_id", name="uq_form_draft_surrogate"),
        Index("idx_form_drafts_org", "organization_id"),
        Index("idx_form_drafts_form", "form_id"),
        Index("idx_form_drafts_surrogate", "surrogate_id"),
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
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )

    answers_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )

    form: Mapped[Form] = relationship()
    surrogate: Mapped[Surrogate] = relationship()


class FormSubmissionFile(Base):
    """File uploaded as part of a form submission."""

    __tablename__ = "form_submission_files"
    __table_args__ = (
        Index("idx_form_files_org", "organization_id"),
        Index("idx_form_files_submission", "submission_id"),
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
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    field_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )
    quarantined: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    submission: Mapped[FormSubmission] = relationship()
