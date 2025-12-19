"""SQLAlchemy ORM models for authentication, tenant management, and cases."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, ForeignKey, Index, Integer, LargeBinary, Numeric, String, 
    Text, Time, UniqueConstraint, text
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    DEFAULT_CASE_SOURCE, DEFAULT_CASE_STATUS, DEFAULT_JOB_STATUS, DEFAULT_EMAIL_STATUS,
    DEFAULT_IP_STATUS, CaseSource, CaseStatus, TaskType, JobType, JobStatus, EmailStatus,
    IntendedParentStatus, EntityType, OwnerType
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
    # Feature flags
    ai_enabled: Mapped[bool] = mapped_column(
        default=False,
        server_default=text("false"),
        nullable=False
    )
    # Version control
    current_version: Mapped[int] = mapped_column(
        default=1,
        server_default=text("1"),
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
    __table_args__ = (
        Index("idx_memberships_org_id", "organization_id"),
    )
    
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
        Index("idx_auth_identities_user_id", "user_id"),
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
        Index("idx_org_invites_org_id", "organization_id"),
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
# Queue/Ownership Models
# =============================================================================

class Queue(Base):
    """
    Work queues for case routing and assignment.
    
    Salesforce-style: cases can be owned by a queue or a user.
    When claimed, ownership transfers from queue to user.
    """
    __tablename__ = "queues"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_queue_name"),
        Index("idx_queues_org_active", "organization_id", "is_active"),
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
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
        onupdate=datetime.now,
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship()


# =============================================================================
# Case Management Models
# =============================================================================

class Case(Base):
    """
    Primary entity for surrogate applicants/cases.
    
    Includes soft-delete (is_archived) for data safety.
    Hard delete requires is_archived=true and manager+ role.
    
    Ownership model (Salesforce-style):
    - owner_type: "user" or "queue"
    - owner_id: UUID of user or queue
    - When in queue, any case_manager+ can claim
    - Claiming sets owner_type="user", owner_id=claimer
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
        Index("idx_cases_org_owner", "organization_id", "owner_type", "owner_id"),
        Index("idx_cases_org_created", "organization_id", "created_at"),
        Index(
            "idx_cases_org_active",
            "organization_id",
            postgresql_where=text("is_archived = FALSE")
        ),
        Index(
            "idx_cases_meta_ad",
            "organization_id", "meta_ad_id",
            postgresql_where=text("meta_ad_id IS NOT NULL")
        ),
        Index(
            "idx_cases_meta_form",
            "organization_id", "meta_form_id",
            postgresql_where=text("meta_form_id IS NOT NULL")
        ),
        # Ownership indexes
        Index("idx_cases_org_owner", "organization_id", "owner_type", "owner_id"),
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
    is_priority: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("FALSE"),
        nullable=False
    )
    
    # Ownership (Salesforce-style single owner model)
    # owner_type="user" + owner_id=user_id, or owner_type="queue" + owner_id=queue_id
    owner_type: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
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
    # Campaign tracking (denormalized from meta_leads for easy filtering)
    meta_ad_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meta_form_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
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
    
    # Last contact tracking
    last_contacted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_contact_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # email, phone, note
    
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
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    archived_by: Mapped["User | None"] = relationship(foreign_keys=[archived_by_user_id])
    
    # Owner relationships for eager loading (fixes N+1 query)
    # These use custom join conditions since owner_id can point to either User or Queue
    # Using selectin loading to avoid LEFT OUTER JOIN conflicts with FOR UPDATE
    owner_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[owner_id],
        primaryjoin="and_(Case.owner_id==User.id, Case.owner_type=='user')",
        viewonly=True,
        lazy="selectin"
    )
    owner_queue: Mapped["Queue | None"] = relationship(
        "Queue",
        foreign_keys=[owner_id],
        primaryjoin="and_(Case.owner_id==Queue.id, Case.owner_type=='queue')",
        viewonly=True,
        lazy="selectin"
    )
    
    # Notes use EntityNote with entity_type='case' - no direct relationship
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


class CaseActivityLog(Base):
    """
    Comprehensive activity log for all case changes.
    
    Tracks: create, edit, status change, assign, archive, notes, etc.
    Stores new values for changed fields. Actor names resolved at read-time.
    """
    __tablename__ = "case_activity_log"
    __table_args__ = (
        Index("idx_case_activity_case_time", "case_id", "created_at"),
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
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    case: Mapped["Case"] = relationship()
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id])


# NOTE: CaseNote model removed (migrated to EntityNote with entity_type='case')
# See migration 0013_migrate_casenotes.py


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
        Index("idx_tasks_org_owner", "organization_id", "owner_type", "owner_id", "is_completed"),
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
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    # Ownership (Salesforce-style single owner model)
    # owner_type="user" + owner_id=user_id, or owner_type="queue" + owner_id=queue_id
    owner_type: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(
        String(50),
        server_default=text(f"'{TaskType.OTHER.value}'"),
        nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
        Index("idx_meta_leads_status", "organization_id", "status"),
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
        ForeignKey("cases.id", ondelete="SET NULL", use_alter=True),
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
    
    # Processing status (for observability)
    # Values: received, fetching, fetch_failed, stored, converted, convert_failed
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'received'"),
        nullable=False
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
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Meta page info
    page_id: Mapped[str] = mapped_column(String(100), nullable=False)
    page_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Encrypted access token (Fernet)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("TRUE"),
        nullable=False
    )
    
    # Observability
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship()


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
        Index(
            "uq_job_idempotency",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
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
    
    # Idempotency key for deduplication (unique constraint in migration)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)


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
    
    # Version control
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)
    
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
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
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


# =============================================================================
# Intended Parents Models
# =============================================================================

class IntendedParent(Base):
    """
    Prospective parents seeking surrogacy services.
    
    Mirrors Case patterns: org-scoped, soft-delete, status history.
    """
    __tablename__ = "intended_parents"
    __table_args__ = (
        Index("idx_ip_org_status", "organization_id", "status"),
        Index("idx_ip_org_created", "organization_id", "created_at"),
        Index("idx_ip_org_owner", "organization_id", "owner_type", "owner_id"),
        # Partial unique index: unique email per org for non-archived records
        Index(
            "uq_ip_email_active",
            "organization_id", "email",
            unique=True,
            postgresql_where=text("is_archived = false")
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
    
    # Contact info
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Location (state only)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Budget (single field, Decimal for precision)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    
    # Internal notes (not the polymorphic notes, just a quick text field)
    notes_internal: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Status & workflow
    status: Mapped[str] = mapped_column(
        String(50),
        server_default=text(f"'{DEFAULT_IP_STATUS.value}'"),
        nullable=False
    )
    
    # Owner model (user or queue)
    owner_type: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )
    
    # Soft delete
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("FALSE"),
        nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Activity tracking
    last_activity: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship()
    status_history: Mapped[list["IntendedParentStatusHistory"]] = relationship(
        back_populates="intended_parent",
        cascade="all, delete-orphan"
    )


class IntendedParentStatusHistory(Base):
    """Tracks all status changes on intended parents for audit."""
    __tablename__ = "intended_parent_status_history"
    __table_args__ = (
        Index("idx_ip_history_ip", "intended_parent_id", "changed_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    intended_parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=False
    )
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    intended_parent: Mapped["IntendedParent"] = relationship(back_populates="status_history")


# =============================================================================
# Polymorphic Notes (replaces case_notes for new entities)
# =============================================================================

class EntityNote(Base):
    """
    Polymorphic notes for any entity (case, intended_parent, etc.).
    
    Uses entity_type + entity_id pattern instead of separate FK columns.
    Author or manager+ can delete.
    """
    __tablename__ = "entity_notes"
    __table_args__ = (
        Index("idx_entity_notes_lookup", "entity_type", "entity_id", "created_at"),
        Index("idx_entity_notes_org", "organization_id", "created_at"),
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
    
    # Polymorphic reference
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'case', 'intended_parent'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    # Note content
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)  # HTML allowed, sanitized
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    author: Mapped["User"] = relationship()


# =============================================================================
# Notifications
# =============================================================================


class Notification(Base):
    """
    In-app notifications for users.
    
    Supports case and task events with dedupe to prevent spam.
    """
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notif_user_unread", "user_id", "read_at", "created_at"),
        Index("idx_notif_org_user", "organization_id", "user_id", "created_at"),
        Index("idx_notif_dedupe", "dedupe_key", "created_at"),
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Notification type (enum)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Entity reference (for click-through)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "case", "task"
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Dedupe key: {type}:{entity_id}:{user_id} - prevents duplicate notifications
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Read status
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship()
    organization: Mapped["Organization"] = relationship()


class UserNotificationSettings(Base):
    """
    Per-user notification preferences.
    
    Missing row = all defaults ON.
    """
    __tablename__ = "user_notification_settings"
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # In-app notification toggles (all default TRUE)
    case_assigned: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    case_status_changed: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    case_handoff: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    task_assigned: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship()
    organization: Mapped["Organization"] = relationship()


# =============================================================================
# Week 10: Integration Health + System Alerts Models
# =============================================================================

class IntegrationHealth(Base):
    """
    Per-integration health status tracking.
    
    Tracks the health of integrations like Meta Leads, CAPI, etc.
    integration_key is nullable for now but allows per-page tracking later.
    """
    __tablename__ = "integration_health"
    
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
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    integration_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="healthy", server_default=text("'healthy'"))
    config_status: Mapped[str] = mapped_column(String(30), default="configured", server_default=text("'configured'"))
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    
    __table_args__ = (
        Index("ix_integration_health_org_type", "organization_id", "integration_type"),
        UniqueConstraint("organization_id", "integration_type", "integration_key", name="uq_integration_health_org_type_key"),
    )


class IntegrationErrorRollup(Base):
    """
    Hourly error counts per integration.
    
    Used to compute "errors in last 24h" as SUM(error_count) WHERE period_start > now() - 24h.
    Avoids storing raw events while maintaining accurate counts.
    """
    __tablename__ = "integration_error_rollup"
    
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
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    integration_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    period_start: Mapped[datetime] = mapped_column(nullable=False)  # Hour bucket
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    
    __table_args__ = (
        Index("ix_integration_error_rollup_lookup", "organization_id", "integration_type", "period_start"),
        UniqueConstraint("organization_id", "integration_type", "integration_key", "period_start", name="uq_integration_error_rollup"),
    )


class SystemAlert(Base):
    """
    Deduplicated actionable alerts.
    
    Alerts are grouped by dedupe_key (fingerprint hash).
    Occurrence count tracks how many times the same issue occurred.
    """
    __tablename__ = "system_alerts"
    
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
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="error", server_default=text("'error'"))
    status: Mapped[str] = mapped_column(String(20), default="open", server_default=text("'open'"))
    first_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(nullable=True)
    
    __table_args__ = (
        Index("ix_system_alerts_org_status", "organization_id", "status", "severity"),
        UniqueConstraint("organization_id", "dedupe_key", name="uq_system_alerts_dedupe"),
    )
    
    # Relationships
    resolved_by: Mapped["User | None"] = relationship()


class RequestMetricsRollup(Base):
    """
    Aggregated API request metrics.
    
    Uses DB upserts (ON CONFLICT DO UPDATE) for multi-replica safety.
    Keyed by (org_id, period_start, route, method) so multiple workers can safely increment.
    """
    __tablename__ = "request_metrics_rollup"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True  # Null for unauthenticated requests
    )
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), default="minute", server_default=text("'minute'"))
    route: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_2xx: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    status_4xx: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    status_5xx: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    request_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    
    __table_args__ = (
        Index("ix_request_metrics_period", "period_start", "period_type"),
        UniqueConstraint("organization_id", "period_start", "route", "method", name="uq_request_metrics_rollup"),
    )


# =============================================================================
# AI Assistant Models (Week 11)
# =============================================================================

class AISettings(Base):
    """
    Org-level AI configuration.
    
    Stores BYOK API keys (encrypted) and model preferences.
    Only one settings record per organization.
    """
    __tablename__ = "ai_settings"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    provider: Mapped[str] = mapped_column(String(20), default="openai", server_default=text("'openai'"))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(50), default="gpt-4o-mini", server_default=text("'gpt-4o-mini'"))
    context_notes_limit: Mapped[int | None] = mapped_column(Integer, default=5, server_default=text("5"))
    conversation_history_limit: Mapped[int | None] = mapped_column(Integer, default=10, server_default=text("10"))
    # Privacy settings
    consent_accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    consent_accepted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    anonymize_pii: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    
    # Version control
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    
    # Relationships
    organization: Mapped["Organization"] = relationship()


class AIConversation(Base):
    """
    AI conversation thread.
    
    Each user has their own conversation per entity (case).
    Developers can view all conversations for audit purposes.
    """
    __tablename__ = "ai_conversations"
    
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'case'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    
    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()
    messages: Mapped[list["AIMessage"]] = relationship(back_populates="conversation", order_by="AIMessage.created_at")
    
    __table_args__ = (
        Index("ix_ai_conversations_entity", "organization_id", "entity_type", "entity_id"),
        Index("ix_ai_conversations_user", "user_id", "entity_type", "entity_id"),
    )


class AIMessage(Base):
    """
    Individual message in an AI conversation.
    
    Role can be 'user', 'assistant', or 'system'.
    proposed_actions is a JSONB array of action specs when AI proposes actions.
    """
    __tablename__ = "ai_messages"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    
    # Relationships
    conversation: Mapped["AIConversation"] = relationship(back_populates="messages")
    action_approvals: Mapped[list["AIActionApproval"]] = relationship(back_populates="message")
    
    __table_args__ = (
        Index("ix_ai_messages_conversation", "conversation_id", "created_at"),
    )


class AIActionApproval(Base):
    """
    Track approval status for each proposed action.
    
    Separates approval state from message content for cleaner queries.
    One record per action in the proposed_actions array.
    """
    __tablename__ = "ai_action_approvals"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_messages.id", ondelete="CASCADE"),
        nullable=False
    )
    action_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default=text("'pending'"))
    executed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    
    # Relationships
    message: Mapped["AIMessage"] = relationship(back_populates="action_approvals")
    
    __table_args__ = (
        Index("ix_ai_action_approvals_message", "message_id"),
        Index("ix_ai_action_approvals_status", "status"),
    )


class AIEntitySummary(Base):
    """
    Cached entity context for AI.
    
    Updated when case notes, status, or tasks change.
    Avoids regenerating context on every chat request.
    """
    __tablename__ = "ai_entity_summaries"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    notes_plain_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_type", "entity_id"),
    )


class AIUsageLog(Base):
    """
    Token usage tracking for cost monitoring.
    
    Records each AI API call with token counts and estimated cost.
    """
    __tablename__ = "ai_usage_log"
    
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="SET NULL"),
        nullable=True
    )
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    
    __table_args__ = (
        Index("ix_ai_usage_log_org_date", "organization_id", "created_at"),
    )


class UserIntegration(Base):
    """
    Per-user OAuth integrations.
    
    Stores encrypted tokens for Gmail, Zoom, Google Calendar, etc.
    Each user can connect their own accounts.
    """
    __tablename__ = "user_integrations"
    
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
    integration_type: Mapped[str] = mapped_column(String(30), nullable=False)  # gmail, zoom, google_calendar
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    # Version control
    current_version: Mapped[int] = mapped_column(
        default=1,
        server_default=text("1"),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship()
    
    __table_args__ = (
        UniqueConstraint("user_id", "integration_type"),
    )


# =============================================================================
# Audit Trail
# =============================================================================

class AuditLog(Base):
    """
    Security and compliance audit log.
    
    Tracks authentication, settings changes, data exports, AI actions,
    and integration events for enterprise compliance.
    
    Security:
    - Never stores secrets/tokens
    - PII in details is hashed (email) or ID-only
    - IP captured from X-Forwarded-For or client IP
    - Hash chain makes tampering detectable
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_org_created", "organization_id", "created_at"),
        Index("idx_audit_org_event_created", "organization_id", "event_type", "created_at"),
        Index("idx_audit_org_actor_created", "organization_id", "actor_user_id", "created_at"),
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
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True  # System events have no actor
    )
    
    # Event classification
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # AuditEventType
    
    # Target entity (optional)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 'user', 'case', 'ai_action', etc.
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Event details (redacted - no secrets, hashed PII)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    # Request metadata
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Request correlation (for grouping related audit events)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Tamper-evident hash chain
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA256 hex
    entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA256 hex
    
    # Version control links (for config change auditing)
    before_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_versions.id", ondelete="SET NULL"),
        nullable=True
    )
    after_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_versions.id", ondelete="SET NULL"),
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship()
    actor: Mapped["User | None"] = relationship()



# =============================================================================
# CSV Import
# =============================================================================

class CaseImport(Base):
    """
    Tracks CSV import jobs for cases.
    
    Flow: upload → preview → confirm (async job) → complete
    
    Dedupe:
    - Matches by email against all cases (including archived)
    - Also checks for duplicates within the CSV itself
    """
    __tablename__ = "case_imports"
    __table_args__ = (
        Index("idx_case_imports_org_created", "organization_id", "created_at"),
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
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # File info
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Status: pending, processing, completed, failed
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    
    # Counts
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    imported_count: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Error details (list of {row: int, errors: list[str]})
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()


# =============================================================================
# Org-Configurable Pipelines (Display-Only v1)
# =============================================================================

class Pipeline(Base):
    """
    Organization pipeline configuration for case status display.
    
    v1 (Display-Only):
    - Maps existing CaseStatus values to custom labels/colors/order
    - Does NOT add new statuses (backend still uses CaseStatus enum)
    - Frontend reads this for UI customization
    
    stages JSON format:
    [
        {"status": "new_unread", "label": "New Lead", "color": "#3B82F6", "order": 1, "visible": true},
        {"status": "contacted", "label": "Reached Out", "color": "#10B981", "order": 2, "visible": true},
        ...
    ]
    """
    __tablename__ = "pipelines"
    __table_args__ = (
        Index("idx_pipelines_org", "organization_id"),
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
    
    name: Mapped[str] = mapped_column(String(100), default="Default", nullable=False)
    is_default: Mapped[bool] = mapped_column(default=True, nullable=False)
    
    # Stage configuration (JSON array of stage objects)
    stages: Mapped[list] = mapped_column(JSONB, nullable=False)
    
    # Version control
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship()


# =============================================================================
# Entity Versioning (Encrypted Config Snapshots)
# =============================================================================

class EntityVersion(Base):
    """
    Append-only configuration version snapshots.
    
    Used for:
    - Pipelines, email templates, AI settings, org settings
    - Integration configs (tokens redacted)
    - Membership/role changes
    
    NOT used for: Cases, tasks, notes (use activity logs instead)
    
    Security:
    - payload_encrypted: Fernet-encrypted JSON
    - checksum: SHA256 of decrypted payload for integrity
    - Never store secrets (tokens stored as [REDACTED:key_id])
    
    Rollback:
    - Creates new version from old payload (never rewrites history)
    - comment field tracks "Rollback from v{N}"
    """
    __tablename__ = "entity_versions"
    __table_args__ = (
        # Unique version per entity
        UniqueConstraint("organization_id", "entity_type", "entity_id", "version"),
        # History queries
        Index("idx_entity_versions_lookup", "organization_id", "entity_type", "entity_id", "created_at"),
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
    
    # What's being versioned
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "pipeline", "email_template", etc.
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    # Version metadata
    version: Mapped[int] = mapped_column(nullable=False)  # Monotonic, starts at 1
    schema_version: Mapped[int] = mapped_column(default=1, nullable=False)  # For future payload migrations
    
    # Encrypted payload (Fernet)
    payload_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Integrity verification
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 of decrypted payload
    
    # Audit trail
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)  # "Updated stages", "Rollback from v3"
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()


# =============================================================================
# Automation Workflows
# =============================================================================

class AutomationWorkflow(Base):
    """
    Automation workflow definition.
    
    Workflows are triggered by events (case created, status changed, etc.)
    and execute actions (send email, create task, etc.) when conditions match.
    """
    __tablename__ = "automation_workflows"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_workflow_name"),
        Index("idx_wf_org_enabled", "organization_id", "is_enabled"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="workflow")
    schema_version: Mapped[int] = mapped_column(default=1)
    
    # Trigger
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    
    # Conditions
    conditions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    condition_logic: Mapped[str] = mapped_column(String(10), default="AND")
    
    # Actions
    actions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    
    # State
    is_enabled: Mapped[bool] = mapped_column(default=True)
    run_count: Mapped[int] = mapped_column(default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Audit
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True
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
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_user_id])
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan"
    )
    user_preferences: Mapped[list["UserWorkflowPreference"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan"
    )


class WorkflowExecution(Base):
    """
    Audit log of workflow executions.
    
    Every time a workflow runs (or is skipped due to conditions),
    an execution record is created for debugging and analytics.
    """
    __tablename__ = "workflow_executions"
    __table_args__ = (
        Index("idx_exec_workflow", "workflow_id", "executed_at"),
        Index("idx_exec_event", "event_id"),
        Index("idx_exec_entity", "entity_type", "entity_id"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automation_workflows.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Loop protection
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    depth: Mapped[int] = mapped_column(default=0)
    event_source: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Context
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trigger_event: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Dedupe (for scheduled/sweep triggers)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Execution
    matched_conditions: Mapped[bool] = mapped_column(default=True)
    actions_executed: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    
    # Result
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    
    executed_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    workflow: Mapped["AutomationWorkflow"] = relationship(back_populates="executions")


class UserWorkflowPreference(Base):
    """
    Per-user workflow opt-out preferences.
    
    Allows individual users to opt out of specific workflows
    (e.g., disable notification workflows they don't want).
    """
    __tablename__ = "user_workflow_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "workflow_id", name="uq_user_workflow"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automation_workflows.id", ondelete="CASCADE"),
        nullable=False
    )
    is_opted_out: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship()
    workflow: Mapped["AutomationWorkflow"] = relationship(back_populates="user_preferences")


# =============================================================================
# Zoom Meetings
# =============================================================================

class ZoomMeeting(Base):
    """
    Zoom meetings created via the app.
    
    Tracks meetings scheduled for cases or intended parents,
    storing Zoom's meeting details for history and management.
    """
    __tablename__ = "zoom_meetings"
    __table_args__ = (
        Index("ix_zoom_meetings_user_id", "user_id"),
        Index("ix_zoom_meetings_case_id", "case_id"),
        Index("ix_zoom_meetings_org_created", "organization_id", "created_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True  # Allow null if user deleted
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True
    )
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Zoom meeting details
    zoom_meeting_id: Mapped[str] = mapped_column(String(50), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(nullable=True)
    duration: Mapped[int] = mapped_column(default=30, nullable=False)  # minutes
    timezone: Mapped[str] = mapped_column(String(100), default="UTC", nullable=False)
    join_url: Mapped[str] = mapped_column(String(500), nullable=False)
    start_url: Mapped[str] = mapped_column(Text, nullable=False)  # Can be very long
    password: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()
    case: Mapped["Case"] = relationship()
    intended_parent: Mapped["IntendedParent"] = relationship()


# =============================================================================
# Matching
# =============================================================================

class Match(Base):
    """
    Proposed match between a surrogate (Case) and intended parent.
    
    Tracks the matching workflow from proposal through acceptance/rejection.
    Only one accepted match is allowed per case.
    """
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "case_id", "intended_parent_id",
            name="uq_match_org_case_ip"
        ),
        Index("ix_matches_case_id", "case_id"),
        Index("ix_matches_ip_id", "intended_parent_id"),
        Index("ix_matches_status", "status"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False
    )
    intended_parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Status workflow: proposed → reviewing → accepted/rejected/cancelled
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="proposed"
    )
    compatibility_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),  # 0.00 to 100.00
        nullable=True
    )
    
    # Who proposed and when
    proposed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    proposed_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Review details
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Notes and rejection reason
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship()
    case: Mapped["Case"] = relationship()
    intended_parent: Mapped["IntendedParent"] = relationship()
    proposed_by: Mapped["User"] = relationship(foreign_keys=[proposed_by_user_id])
    reviewed_by: Mapped["User"] = relationship(foreign_keys=[reviewed_by_user_id])

