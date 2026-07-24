"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    DEFAULT_EMAIL_STATUS,
    EmailDeliveryAttemptOutcome,
    EmailDeliveryStatus,
    EmailSuppressionPolicy,
)

if TYPE_CHECKING:
    from app.db.models import Attachment, Job, Organization, Surrogate, User


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


class EmailTemplateDraft(Base):
    """Isolated working copy for a new or existing email template.

    Published sends continue reading from ``email_templates``. Draft rows are
    only promoted there by an explicit publish transaction.
    """

    __tablename__ = "email_template_drafts"
    __table_args__ = (
        UniqueConstraint("template_id", name="uq_email_template_drafts_template"),
        CheckConstraint(
            "scope IN ('org', 'personal')",
            name="ck_email_template_drafts_scope",
        ),
        CheckConstraint(
            "(scope = 'org' AND owner_user_id IS NULL) "
            "OR (scope = 'personal' AND owner_user_id IS NOT NULL)",
            name="ck_email_template_drafts_scope_owner",
        ),
        Index(
            "idx_email_template_drafts_org_updated",
            "organization_id",
            "updated_at",
        ),
        Index(
            "idx_email_template_drafts_owner",
            "organization_id",
            "owner_user_id",
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
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    from_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    base_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    last_tested_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
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

    template: Mapped["EmailTemplate | None"] = relationship()
    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_user_id])


class EmailLog(Base):
    """
    Log of all outbound emails for audit and debugging.

    Links to job, template, and optionally surrogate.
    """

    __tablename__ = "email_logs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_email_logs_org_id",
        ),
        CheckConstraint(
            "suppression_policy IN "
            f"('{EmailSuppressionPolicy.ENFORCE_ALL.value}', "
            f"'{EmailSuppressionPolicy.ALLOW_OPT_OUT.value}')",
            name="ck_email_logs_suppression_policy",
        ),
        CheckConstraint(
            "jsonb_typeof(attachment_manifest) = 'array'",
            name="ck_email_logs_attachment_manifest_array",
        ),
        Index("idx_email_logs_org", "organization_id", "created_at"),
        Index("idx_email_logs_org_external_id", "organization_id", "external_id"),
        Index("idx_email_logs_surrogate", "surrogate_id", "created_at"),
        Index("idx_email_logs_actor_user", "actor_user_id"),
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
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reply_to_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    headers: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    safe_tags: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    attachment_manifest: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    content_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(50), nullable=True)
    suppression_policy: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{EmailSuppressionPolicy.ENFORCE_ALL.value}'"),
        nullable=False,
    )
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
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
    bounce_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    complained_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    clicked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    resend_status_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    job: Mapped["Job | None"] = relationship()
    template: Mapped["EmailTemplate | None"] = relationship()
    surrogate: Mapped["Surrogate | None"] = relationship()
    attachment_links: Mapped[list["EmailLogAttachment"]] = relationship(
        back_populates="email_log",
        cascade="all, delete-orphan",
    )
    resend_webhook_events: Mapped[list["ResendWebhookEvent"]] = relationship(
        back_populates="email_log",
        cascade="all, delete-orphan",
    )
    delivery: Mapped["EmailDelivery | None"] = relationship(
        back_populates="email_log",
        cascade="all, delete-orphan",
        uselist=False,
    )


class EmailDelivery(Base):
    """Leased transactional outbox row for one immutable email message."""

    __tablename__ = "email_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('pending', 'leased', 'retry_scheduled', 'sent', 'failed', "
            "'cancelled', 'reconciliation_required')",
            name="ck_email_deliveries_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts >= 1 AND attempt_count <= max_attempts",
            name="ck_email_deliveries_attempt_bounds",
        ),
        CheckConstraint(
            "(status = 'leased' AND lease_token IS NOT NULL "
            "AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'leased' AND lease_token IS NULL "
            "AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="ck_email_deliveries_lease_coherence",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_email_deliveries_org_id",
        ),
        UniqueConstraint(
            "email_log_id",
            name="uq_email_deliveries_email_log",
        ),
        UniqueConstraint(
            "provider",
            "provider_account_id",
            "idempotency_key",
            name="uq_email_deliveries_provider_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "email_log_id"],
            ["email_logs.organization_id", "email_logs.id"],
            name="fk_email_deliveries_org_email_log",
            ondelete="CASCADE",
        ),
        Index(
            "idx_email_deliveries_due",
            "status",
            "run_at",
            postgresql_where=text("status IN ('pending', 'retry_scheduled')"),
        ),
        Index(
            "idx_email_deliveries_expired_lease",
            "lease_expires_at",
            postgresql_where=text("status = 'leased'"),
        ),
        Index("idx_email_deliveries_org_created", "organization_id", "created_at"),
        Index(
            "uq_email_deliveries_provider_message",
            "provider",
            "provider_account_id",
            "provider_message_id",
            unique=True,
            postgresql_where=text("provider_message_id IS NOT NULL"),
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
    email_log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_credential_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        server_default=text(f"'{EmailDeliveryStatus.PENDING.value}'"),
        nullable=False,
    )
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("5"), nullable=False)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    first_attempt_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(overlaps="delivery,email_log")
    email_log: Mapped["EmailLog"] = relationship(
        back_populates="delivery",
        overlaps="organization",
    )
    attempts: Mapped[list["EmailDeliveryAttempt"]] = relationship(
        back_populates="delivery",
        cascade="all, delete-orphan",
        order_by="EmailDeliveryAttempt.attempt_number",
    )


class EmailDeliveryAttempt(Base):
    """Sanitized diagnostic record for one provider delivery attempt."""

    __tablename__ = "email_delivery_attempts"
    __table_args__ = (
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_email_delivery_attempt_number",
        ),
        CheckConstraint(
            "outcome IN "
            "('in_progress', 'succeeded', 'retryable_error', "
            "'terminal_error', 'lease_expired')",
            name="ck_email_delivery_attempt_outcome",
        ),
        CheckConstraint(
            "retry_after_seconds IS NULL OR retry_after_seconds >= 0",
            name="ck_email_delivery_attempt_retry_after",
        ),
        UniqueConstraint(
            "delivery_id",
            "attempt_number",
            name="uq_email_delivery_attempt_number",
        ),
        ForeignKeyConstraint(
            ["organization_id", "delivery_id"],
            ["email_deliveries.organization_id", "email_deliveries.id"],
            name="fk_email_delivery_attempts_org_delivery",
            ondelete="CASCADE",
        ),
        Index(
            "idx_email_delivery_attempts_org_delivery",
            "organization_id",
            "delivery_id",
            "started_at",
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
    delivery_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(
        String(30),
        server_default=text(f"'{EmailDeliveryAttemptOutcome.IN_PROGRESS.value}'"),
        nullable=False,
    )
    provider_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    organization: Mapped["Organization"] = relationship(overlaps="attempts,delivery")
    delivery: Mapped["EmailDelivery"] = relationship(
        back_populates="attempts",
        overlaps="organization",
    )


class EmailProviderAdmission(Base):
    """Durable next-request slot for one provider credential account."""

    __tablename__ = "email_provider_admission"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_account_id",
            name="uq_email_provider_admission_account",
        ),
        Index(
            "idx_email_provider_admission_next_slot",
            "next_slot_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    next_slot_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class ResendWebhookEvent(Base):
    """Verified Resend webhook event retained for deduplication and audit."""

    __tablename__ = "resend_webhook_events"
    __table_args__ = (
        CheckConstraint(
            "(provider_scope IS NULL AND provider_account_id IS NULL) OR "
            "(provider_scope IN ('platform', 'organization') "
            "AND provider_account_id IS NOT NULL "
            "AND btrim(provider_account_id) <> '')",
            name="ck_resend_webhook_events_route",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_resend_webhook_events_org_id",
        ),
        UniqueConstraint(
            "organization_id",
            "provider_event_id",
            name="uq_resend_webhook_events_org_provider_event",
        ),
        Index(
            "idx_resend_webhook_events_org_email_time",
            "organization_id",
            "email_log_id",
            "event_created_at",
        ),
        Index(
            "idx_resend_webhook_events_org_route_received",
            "organization_id",
            "provider_scope",
            "provider_account_id",
            "received_at",
        ),
        Index("idx_resend_webhook_events_processed_at", "processed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_logs.id", ondelete="CASCADE"),
        nullable=True,
    )
    provider_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship()
    email_log: Mapped["EmailLog | None"] = relationship(back_populates="resend_webhook_events")


class EmailReconciliationCase(Base):
    """PII-safe operator case for an email outcome requiring reconciliation."""

    __tablename__ = "email_reconciliation_cases"
    __table_args__ = (
        CheckConstraint(
            "case_type IN ('orphan_webhook', 'unknown_delivery')",
            name="ck_email_reconciliation_cases_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'action_required', 'resolved', 'dismissed')",
            name="ck_email_reconciliation_cases_status",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_email_reconciliation_cases_version",
        ),
        CheckConstraint(
            "((case_type = 'orphan_webhook' "
            "AND resend_webhook_event_id IS NOT NULL "
            "AND email_delivery_id IS NULL) "
            "OR (case_type = 'unknown_delivery' "
            "AND email_delivery_id IS NOT NULL "
            "AND resend_webhook_event_id IS NULL))",
            name="ck_email_reconciliation_cases_source",
        ),
        CheckConstraint(
            "((status IN ('resolved', 'dismissed') "
            "AND resolved_at IS NOT NULL AND resolution_code IS NOT NULL) "
            "OR (status NOT IN ('resolved', 'dismissed') "
            "AND resolved_at IS NULL AND resolution_code IS NULL))",
            name="ck_email_reconciliation_cases_resolution",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_email_reconciliation_cases_org_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "resend_webhook_event_id"],
            ["resend_webhook_events.organization_id", "resend_webhook_events.id"],
            name="fk_email_reconciliation_cases_org_event",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "email_delivery_id"],
            ["email_deliveries.organization_id", "email_deliveries.id"],
            name="fk_email_reconciliation_cases_org_delivery",
            ondelete="CASCADE",
        ),
        Index(
            "uq_email_reconciliation_cases_event",
            "organization_id",
            "resend_webhook_event_id",
            unique=True,
            postgresql_where=text("resend_webhook_event_id IS NOT NULL"),
        ),
        Index(
            "uq_email_reconciliation_cases_delivery",
            "organization_id",
            "email_delivery_id",
            unique=True,
            postgresql_where=text("email_delivery_id IS NOT NULL"),
        ),
        Index(
            "idx_email_reconciliation_cases_org_status_detected",
            "organization_id",
            "status",
            "detected_at",
            "id",
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
    case_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        server_default=text("'pending'"),
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    resend_webhook_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    email_delivery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_code: Mapped[str | None] = mapped_column(String(80), nullable=True)

    organization: Mapped["Organization"] = relationship(
        overlaps="email_delivery,resend_webhook_event"
    )
    resend_webhook_event: Mapped["ResendWebhookEvent | None"] = relationship(
        overlaps="email_delivery,organization"
    )
    email_delivery: Mapped["EmailDelivery | None"] = relationship(
        overlaps="organization,resend_webhook_event"
    )
    resolved_by: Mapped["User | None"] = relationship()


class EmailLogAttachment(Base):
    """Join table linking sent emails to attachment records."""

    __tablename__ = "email_log_attachments"
    __table_args__ = (
        UniqueConstraint(
            "email_log_id", "attachment_id", name="uq_email_log_attachments_unique_link"
        ),
        Index("idx_email_log_attachments_org", "organization_id"),
        Index("idx_email_log_attachments_email_log", "email_log_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_logs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    organization: Mapped["Organization"] = relationship()
    email_log: Mapped["EmailLog"] = relationship(back_populates="attachment_links")
    attachment: Mapped["Attachment"] = relationship(back_populates="email_log_links")


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
