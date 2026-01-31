"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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
from app.db.enums import (
    FormStatus,
    FormSubmissionStatus,
)

if TYPE_CHECKING:
    from app.db.models import Organization, Surrogate, User


class Form(Base):
    """Application form configuration."""

    __tablename__ = "forms"
    __table_args__ = (
        Index("idx_forms_org", "organization_id"),
        Index("idx_forms_org_status", "organization_id", "status"),
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

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
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
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )

    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])


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
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )


class FormSubmissionToken(Base):
    """One-time submission token tied to a case + form."""

    __tablename__ = "form_submission_tokens"
    __table_args__ = (
        Index("idx_form_tokens_org", "organization_id"),
        Index("idx_form_tokens_form", "form_id"),
        Index("idx_form_tokens_surrogate", "surrogate_id"),
        UniqueConstraint("token", name="uq_form_submission_token"),
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
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(), nullable=False)
    max_submissions: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )
    used_submissions: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )


class FormSubmission(Base):
    """A submitted application form response."""

    __tablename__ = "form_submissions"
    __table_args__ = (
        UniqueConstraint("form_id", "surrogate_id", name="uq_form_submission_surrogate"),
        Index("idx_form_submissions_org", "organization_id"),
        Index("idx_form_submissions_form", "form_id"),
        Index("idx_form_submissions_surrogate", "surrogate_id"),
        Index("idx_form_submissions_status", "status"),
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
    token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_submission_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{FormSubmissionStatus.PENDING_REVIEW.value}'"),
        nullable=False,
    )
    answers_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    schema_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    mapping_snapshot: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )

    form: Mapped["Form"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()


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
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )

    submission: Mapped["FormSubmission"] = relationship()
