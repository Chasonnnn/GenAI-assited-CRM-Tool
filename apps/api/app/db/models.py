"""SQLAlchemy ORM models for authentication, tenant management, and cases."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, ForeignKey, Index, Integer, Numeric, String, 
    Text, Time, UniqueConstraint, text
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    DEFAULT_CASE_SOURCE, DEFAULT_CASE_STATUS, DEFAULT_JOB_STATUS, DEFAULT_EMAIL_STATUS,
    CaseSource, CaseStatus, TaskType, JobType, JobStatus, EmailStatus
)


# =============================================================================
# Auth & Tenant Models
# =============================================================================

class Organization(Base):
    """
    A tenant/company in the multi-tenant system.
    
    All domain entities belong to an organization
    and must be scoped by organization_id in all queries.
    """
    __tablename__ = "organizations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), 
        nullable=False
    )
    
    # Relationships
    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization", 
        cascade="all, delete-orphan"
    )
    invites: Mapped[list["OrgInvite"]] = relationship(
        back_populates="organization", 
        cascade="all, delete-orphan"
    )
    cases: Mapped[list["Case"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan"
    )


class User(Base):
    """
    Application user.
    
    Identity is established via AuthIdentity (SSO).
    No passwords stored - authentication is delegated to identity providers.
    """
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_version: Mapped[int] = mapped_column(
        Integer, 
        server_default=text("1"), 
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        server_default=text("true"), 
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), 
        nullable=False
    )
    
    # Relationships
    membership: Mapped["Membership | None"] = relationship(
        back_populates="user", 
        cascade="all, delete-orphan",
        uselist=False
    )
    auth_identities: Mapped[list["AuthIdentity"]] = relationship(
        back_populates="user", 
        cascade="all, delete-orphan"
    )


class Membership(Base):
    """
    Links a user to an organization with a role.
    
    Constraint: UNIQUE(user_id) enforces ONE organization per user.
    """
    __tablename__ = "memberships"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        unique=True,  # ONE ORG PER USER
        nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), 
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="membership")
    organization: Mapped["Organization"] = relationship(back_populates="memberships")


class AuthIdentity(Base):
    """
    Links a user to an external identity provider.
    """
    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_auth_identity"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), 
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="auth_identities")


class OrgInvite(Base):
    """
    Invite-only access control.
    
    Constraint: One pending invite per email GLOBALLY.
    """
    __tablename__ = "org_invites"
    __table_args__ = (
        Index(
            "uq_pending_invite_email", 
            "email", 
            unique=True, 
            postgresql_where=text("accepted_at IS NULL")
        ),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), 
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="invites")


# =============================================================================
# Case Management Models
# =============================================================================

class Case(Base):
    """
    Primary entity for surrogate applicants/cases.
    
    Includes soft-delete (is_archived) for data safety.
    Hard delete requires is_archived=true and manager+ role.
    """
    __tablename__ = "cases"
    __table_args__ = (
        # Case number unique per org (even archived)
        UniqueConstraint("organization_id", "case_number", name="uq_case_number"),
        # Email unique per org for active cases only
        Index(
            "uq_case_email_active",
            "organization_id", "email",
            unique=True,
            postgresql_where=text("is_archived = FALSE")
        ),
        # Query optimization indexes
        Index("idx_cases_org_status", "organization_id", "status"),
        Index("idx_cases_org_assigned", "organization_id", "assigned_to_user_id"),
        Index("idx_cases_org_created", "organization_id", "created_at"),
        Index(
            "idx_cases_org_active",
            "organization_id",
            postgresql_where=text("is_archived = FALSE")
        ),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    case_number: Mapped[str] = mapped_column(String(10), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Workflow
    status: Mapped[str] = mapped_column(
        String(50),
        server_default=text(f"'{DEFAULT_CASE_STATUS.value}'"),
        nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{DEFAULT_CASE_SOURCE.value}'"),
        nullable=False
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    meta_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_leads.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Contact (normalized: E.164 phone, 2-letter state)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    
    # Demographics
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    race: Mapped[str | None] = mapped_column(String(100), nullable=True)
    height_ft: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    weight_lb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Eligibility
    is_age_eligible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_citizen_or_pr: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_child: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_non_smoker: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_surrogate_experience: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    num_deliveries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_csections: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Soft delete
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("FALSE"),
        nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="cases")
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_user_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    archived_by: Mapped["User | None"] = relationship(foreign_keys=[archived_by_user_id])
    notes: Mapped[list["CaseNote"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan"
    )
    status_history: Mapped[list["CaseStatusHistory"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan"
    )


class CaseStatusHistory(Base):
    """
    Tracks all status changes on cases for audit and timeline.
    
    Also records archive/restore operations.
    """
    __tablename__ = "case_status_history"
    __table_args__ = (
        Index("idx_case_history_case", "case_id", "changed_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    from_status: Mapped[str] = mapped_column(String(50), nullable=False)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    case: Mapped["Case"] = relationship(back_populates="status_history")


class CaseNote(Base):
    """
    Notes attached to cases.
    
    Author or manager+ can delete.
    """
    __tablename__ = "case_notes"
    __table_args__ = (
        Index("idx_case_notes_case", "case_id", "created_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)  # 2-4000 chars in schema
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    case: Mapped["Case"] = relationship(back_populates="notes")
    author: Mapped["User"] = relationship()


class Task(Base):
    """
    To-do items optionally linked to cases.
    
    Permissions:
    - Creator: edit/delete
    - Assignee: edit/complete
    - Manager+: all
    """
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_org_assigned", "organization_id", "assigned_to_user_id", "is_completed"),
        Index(
            "idx_tasks_due",
            "organization_id", "due_date",
            postgresql_where=text("is_completed = FALSE")
        ),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=True
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(
        String(50),
        server_default=text(f"'{TaskType.OTHER.value}'"),
        nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("FALSE"),
        nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False
    )
    
    # Relationships
    case: Mapped["Case | None"] = relationship()
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_user_id])
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])
    completed_by: Mapped["User | None"] = relationship(foreign_keys=[completed_by_user_id])


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
        Index(
            "idx_meta_unconverted",
            "organization_id",
            postgresql_where=text("is_converted = FALSE")
        ),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Meta identifiers
    meta_lead_id: Mapped[str] = mapped_column(String(100), nullable=False)
    meta_form_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meta_page_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Data storage
    field_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    # Conversion status
    is_converted: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("FALSE"),
        nullable=False
    )
    converted_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True
    )
    conversion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    meta_created_time: Mapped[datetime | None] = mapped_column(nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    converted_at: Mapped[datetime | None] = mapped_column(nullable=True)


# =============================================================================
# Jobs & Email Models
# =============================================================================

class Job(Base):
    """
    Background job for async processing.
    
    Used for: email sending, scheduled reminders, webhook retries.
    Worker polls for pending jobs and processes them.
    """
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_pending", "status", "run_at", postgresql_where=text("status = 'pending'")),
        Index("idx_jobs_org", "organization_id", "created_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    run_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{DEFAULT_JOB_STATUS.value}'"),
        nullable=False
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        server_default=text("3"),
        nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class EmailTemplate(Base):
    """
    Org-scoped email templates with variable placeholders.
    
    Body supports {{variable}} syntax for personalization.
    """
    __tablename__ = "email_templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_email_template_name"),
        Index("idx_email_templates_org", "organization_id", "is_active"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("TRUE"),
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False
    )
    
    # Relationships
    created_by: Mapped["User | None"] = relationship()


class EmailLog(Base):
    """
    Log of all outbound emails for audit and debugging.
    
    Links to job, template, and optionally case.
    """
    __tablename__ = "email_logs"
    __table_args__ = (
        Index("idx_email_logs_org", "organization_id", "created_at"),
        Index("idx_email_logs_case", "case_id", "created_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True
    )
    
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{DEFAULT_EMAIL_STATUS.value}'"),
        nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    job: Mapped["Job | None"] = relationship()
    template: Mapped["EmailTemplate | None"] = relationship()
    case: Mapped["Case | None"] = relationship()