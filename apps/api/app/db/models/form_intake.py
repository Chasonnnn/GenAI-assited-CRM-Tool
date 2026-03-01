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
from app.db.enums import IntakeLeadStatus
from app.db.types import EncryptedDate, EncryptedString

if TYPE_CHECKING:
    from app.db.models import Form, FormSubmission, Organization, Surrogate, User


class FormIntakeLink(Base):
    """Public shared intake link bound to a form."""

    __tablename__ = "form_intake_links"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_form_intake_link_slug"),
        Index("idx_form_intake_links_org", "organization_id"),
        Index("idx_form_intake_links_form", "form_id"),
        Index("idx_form_intake_links_slug", "slug"),
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
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)
    max_submissions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submissions_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

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
    promoted_surrogate: Mapped["Surrogate | None"] = relationship(
        foreign_keys=[promoted_surrogate_id]
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
