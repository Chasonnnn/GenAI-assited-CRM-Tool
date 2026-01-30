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
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    DEFAULT_EMAIL_STATUS,
)

if TYPE_CHECKING:
    from app.db.models import Job, Organization, Surrogate, User


class EmailTemplate(Base):
    """
    Email templates with variable placeholders.

    Supports both org-wide (scope='org') and personal (scope='personal') templates.
    Body supports {{variable}} syntax for personalization.
    """

    __tablename__ = "email_templates"
    __table_args__ = (
        # Partial unique indexes are created in migration
        # Org templates: unique (org_id, name) WHERE scope = 'org'
        # Personal templates: unique (org_id, owner_user_id, name) WHERE scope = 'personal'
        Index(
            "uq_email_template_org_name",
            "organization_id",
            "name",
            unique=True,
            postgresql_where=text("scope = 'org'"),
        ),
        Index(
            "uq_email_template_personal_name",
            "organization_id",
            "owner_user_id",
            "name",
            unique=True,
            postgresql_where=text("scope = 'personal'"),
        ),
        Index("idx_email_templates_org", "organization_id", "is_active"),
        Index("idx_email_templates_scope", "organization_id", "scope", "owner_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    # Optional per-template From header override (e.g. "Surrogacy Force <invites@surrogacyforce.com>")
    from_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)

    # Scope: 'org' (shared) or 'personal' (user-owned)
    scope: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'org'"),
        nullable=False,
        comment="Template scope: 'org' or 'personal'",
    )
    # Owner for personal templates (NULL for org templates)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="Owner for personal templates (NULL for org templates)",
    )
    # Source template when copied or shared
    source_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
        comment="Source template when copied/shared",
    )

    # System template fields (idempotent seeding/upgrades)
    is_system_template: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    system_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Unique key for system templates, e.g. 'welcome_new_lead'
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'welcome', 'reminder', 'status', 'match', 'appointment'

    # Version control
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_user_id])
    source_template: Mapped["EmailTemplate | None"] = relationship(remote_side=[id])


class EmailLog(Base):
    """
    Log of all outbound emails for audit and debugging.

    Links to job, template, and optionally surrogate.
    """

    __tablename__ = "email_logs"
    __table_args__ = (
        Index("idx_email_logs_org", "organization_id", "created_at"),
        Index("idx_email_logs_surrogate", "surrogate_id", "created_at"),
        Index(
            "uq_email_logs_idempotency",
            "organization_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
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
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="SET NULL"), nullable=True
    )

    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{DEFAULT_EMAIL_STATUS.value}'"),
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resend webhook tracking fields
    resend_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # 'sent' | 'delivered' | 'bounced' | 'complained'
    delivered_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    bounced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    bounce_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'hard' | 'soft'
    complained_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    clicked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    job: Mapped["Job | None"] = relationship()
    template: Mapped["EmailTemplate | None"] = relationship()
    surrogate: Mapped["Surrogate | None"] = relationship()


# =============================================================================
# Intended Parents Models
# =============================================================================


class EmailSuppression(Base):
    """
    Suppression list for opt-out, bounced, and archived emails.

    Prevents sending emails to addresses that have opted out or are invalid.
    """

    __tablename__ = "email_suppressions"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_email_suppression"),
        Index("idx_email_suppressions_org", "organization_id"),
        Index("idx_email_suppressions_email", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Suppressed email
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)

    # Reason
    reason: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'opt_out' | 'bounced' | 'archived' | 'complaint'

    # Optional source reference
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
