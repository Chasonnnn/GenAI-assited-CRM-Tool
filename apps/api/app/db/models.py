"""SQLAlchemy ORM models for authentication, tenant management, and surrogates."""

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    TIMESTAMP,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    DEFAULT_SURROGATE_SOURCE,
    DEFAULT_JOB_STATUS,
    DEFAULT_EMAIL_STATUS,
    DEFAULT_IP_STATUS,
    FormStatus,
    FormSubmissionStatus,
    TaskType,
    MeetingMode,
    AppointmentStatus,
)
from app.db.types import EncryptedDate, EncryptedString, EncryptedText


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
    __table_args__ = (
        Index("ix_organizations_deleted_at", "deleted_at"),
        Index("ix_organizations_purge_at", "purge_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    purge_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        server_default=text("'America/Los_Angeles'"),
        nullable=False,
    )
    # Feature flags
    ai_enabled: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False
    )
    # Version control
    current_version: Mapped[int] = mapped_column(
        default=1, server_default=text("1"), nullable=False
    )

    # Email signature branding (org-level, admin-controlled)
    signature_template: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,  # 'classic', 'modern', 'minimal', 'professional', 'creative'
    )
    signature_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signature_primary_color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,  # Hex color e.g. '#0066cc'
    )
    signature_company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signature_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signature_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    signature_website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signature_social_links: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'[]'::jsonb"),
        comment="Array of {platform, url} objects for org social links",
    )
    signature_disclaimer: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Optional compliance footer for email signatures"
    )

    # Relationships
    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    invites: Mapped[list["OrgInvite"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    surrogates: Mapped[list["Surrogate"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class User(Base):
    """
    Application user.

    Identity is established via AuthIdentity (SSO).
    No passwords stored - authentication is delegated to identity providers.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Email signature social links (user-editable)
    signature_linkedin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signature_twitter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signature_instagram: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Profile fields (for email signature)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Signature override fields (NULL = use profile value)
    signature_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Override display_name in signature (NULL = use profile)",
    )
    signature_title: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Override title in signature (NULL = use profile)"
    )
    signature_phone: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Override phone in signature (NULL = use profile)"
    )
    signature_photo_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Override avatar in signature (NULL = use profile)"
    )

    # MFA fields
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # Encrypted TOTP secret
    )
    totp_enabled_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    duo_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duo_enrolled_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    mfa_recovery_codes: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,  # Hashed recovery codes
    )
    mfa_required_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,  # When MFA enforcement started for this user
    )

    # Platform admin flag (cross-org access for ops console)
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )

    # Relationships
    membership: Mapped["Membership | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    auth_identities: Mapped[list["AuthIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Membership(Base):
    """
    Links a user to an organization with a role.

    Constraint: UNIQUE(user_id) enforces ONE organization per user.
    """

    __tablename__ = "memberships"
    __table_args__ = (Index("idx_memberships_org_id", "organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,  # ONE ORG PER USER
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="membership")
    organization: Mapped["Organization"] = relationship(back_populates="memberships")


class RolePermission(Base):
    """
    Org-specific role permission defaults.

    Overrides the global ROLE_DEFAULTS from permissions.py.
    Missing rows default to False at runtime.
    """

    __tablename__ = "role_permissions"
    __table_args__ = (
        Index("idx_role_permissions_org_role", "organization_id", "role"),
        UniqueConstraint(
            "organization_id",
            "role",
            "permission",
            name="uq_role_permissions_org_role_perm",
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
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    permission: Mapped[str] = mapped_column(String(100), nullable=False)
    is_granted: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class UserPermissionOverride(Base):
    """
    User-level permission grants/revokes.

    Precedence: revoke > grant > role_default
    """

    __tablename__ = "user_permission_overrides"
    __table_args__ = (
        Index("idx_user_overrides_org_user", "organization_id", "user_id"),
        UniqueConstraint(
            "organization_id",
            "user_id",
            "permission",
            name="uq_user_overrides_org_user_perm",
        ),
        CheckConstraint("override_type IN ('grant', 'revoke')", name="ck_override_type_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(String(100), nullable=False)
    override_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'grant' or 'revoke'
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


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
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="auth_identities")


class UserSession(Base):
    """
    Tracks active user sessions for revocation support.

    JWTs are stateless, so we store a hash of each token to enable:
    - Session listing (show all devices)
    - Session revocation (logout specific device)
    - Token validation (check if session still valid)

    Note: is_current is derived at query time by comparing token hashes,
    not stored as a column (would get stale).
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_user_sessions_user_id", "user_id"),
        Index("idx_user_sessions_org_id", "organization_id"),
        Index("idx_user_sessions_token_hash", "session_token_hash"),
        Index(
            "idx_user_sessions_expires",
            "expires_at",
            postgresql_where=text("expires_at > now()"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    session_token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="SHA256 hash of JWT token for revocation lookup",
    )
    device_info: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Parsed device name from user agent"
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True, comment="IPv4 or IPv6 address"
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Raw user agent string"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    # Relationships
    user: Mapped["User"] = relationship()
    organization: Mapped["Organization"] = relationship()


class OrgInvite(Base):
    """
    Invite-only access control.

    Constraint: One pending invite per email GLOBALLY.
    Enterprise features: resend throttling, revocation tracking.
    """

    __tablename__ = "org_invites"
    __table_args__ = (
        Index(
            "uq_pending_invite_email",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
        Index("idx_org_invites_org_id", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Resend throttling
    resend_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    last_resent_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Revocation tracking
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="invites")
    invited_by: Mapped["User | None"] = relationship(foreign_keys=[invited_by_user_id])
    revoked_by: Mapped["User | None"] = relationship(foreign_keys=[revoked_by_user_id])


class OrganizationSubscription(Base):
    """
    Subscription/billing status for an organization.

    Tracks plan, status, and renewal settings. Currently used as a placeholder
    for future billing enforcement - no charges are processed.
    """

    __tablename__ = "organization_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "plan_key IN ('starter', 'professional', 'enterprise')",
            name="ck_organization_subscriptions_plan_key",
        ),
        CheckConstraint(
            "status IN ('active', 'trial', 'past_due', 'canceled')",
            name="ck_organization_subscriptions_status",
        ),
        Index("idx_org_subscriptions_status", "status"),
        Index(
            "idx_org_subscriptions_period_end_active",
            "current_period_end",
            postgresql_where=text("status IN ('active', 'trial', 'past_due')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    plan_key: Mapped[str] = mapped_column(String(50), server_default="starter", nullable=False)
    status: Mapped[str] = mapped_column(String(30), server_default="active", nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    trial_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()


class AdminActionLog(Base):
    """
    Audit log for platform admin actions.

    Tracks who did what, when, and to which org/user. IP and user agent are
    stored as HMACs (salted hashes) for PII safety while maintaining traceability.
    actor_user_id is nullable for system-triggered actions (e.g., auto-extend).
    """

    __tablename__ = "admin_action_logs"
    __table_args__ = (
        Index("idx_admin_action_logs_created_at", text("created_at DESC")),
        Index("idx_admin_action_logs_target_org", "target_organization_id"),
        Index("idx_admin_action_logs_actor", "actor_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # Nullable for system actions
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )  # IDs only, NO PII
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address_hmac: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hmac: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    # Relationships
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id])
    target_organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[target_organization_id]
    )
    target_user: Mapped["User | None"] = relationship(foreign_keys=[target_user_id])


class SupportSession(Base):
    """
    Platform support session for cross-org role override.

    Used by platform admins to view/manage an org as a specific role without
    creating a membership. Time-boxed and revocable.
    """

    __tablename__ = "support_sessions"
    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name="ck_support_sessions_expires_after_created",
        ),
        Index("idx_support_sessions_actor", "actor_user_id"),
        Index("idx_support_sessions_org", "organization_id"),
        Index("idx_support_sessions_expires_at", "expires_at"),
        Index(
            "idx_support_sessions_actor_active",
            "actor_user_id",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role_override: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), server_default="write", nullable=False)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    actor: Mapped["User"] = relationship(foreign_keys=[actor_user_id])
    organization: Mapped["Organization"] = relationship(foreign_keys=[organization_id])


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
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=datetime.now, nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    members: Mapped[list["QueueMember"]] = relationship(
        back_populates="queue",
        cascade="all, delete-orphan",
    )


class QueueMember(Base):
    """
    Queue membership - assigns users to specific queues.

    Only members of a queue can claim cases from that queue.
    If a queue has no members, it's open to all case_manager+ users.
    """

    __tablename__ = "queue_members"
    __table_args__ = (
        UniqueConstraint("queue_id", "user_id", name="uq_queue_member"),
        Index("idx_queue_members_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queues.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    queue: Mapped["Queue"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()


# =============================================================================
# Surrogate Management Models
# =============================================================================


class Surrogate(Base):
    """
    Primary entity for surrogate applicants.

    Includes soft-delete (is_archived) for data safety.
    Hard delete requires is_archived=true and admin+ role.

    Ownership model (Salesforce-style):
    - owner_type: "user" or "queue"
    - owner_id: UUID of user or queue
    - When in queue, any case_manager+ can claim
    - Claiming sets owner_type="user", owner_id=claimer
    """

    __tablename__ = "surrogates"
    __table_args__ = (
        # Surrogate number unique per org (even archived)
        UniqueConstraint("organization_id", "surrogate_number", name="uq_surrogate_number"),
        # Email unique per org for active surrogates only
        Index(
            "uq_surrogate_email_hash_active",
            "organization_id",
            "email_hash",
            unique=True,
            postgresql_where=text("is_archived = FALSE"),
        ),
        # Query optimization indexes
        Index("idx_surrogates_stage", "stage_id"),  # Single-column for FK lookups
        Index("idx_surrogates_org_stage", "organization_id", "stage_id"),
        Index("idx_surrogates_org_owner", "organization_id", "owner_type", "owner_id"),
        Index("idx_surrogates_org_status_label", "organization_id", "status_label"),
        Index("idx_surrogates_org_created", "organization_id", "created_at"),
        Index("idx_surrogates_org_updated", "organization_id", "updated_at"),
        Index(
            "idx_surrogates_org_active",
            "organization_id",
            postgresql_where=text("is_archived = FALSE"),
        ),
        Index(
            "idx_surrogates_meta_ad",
            "organization_id",
            "meta_ad_external_id",
            postgresql_where=text("meta_ad_external_id IS NOT NULL"),
        ),
        Index(
            "idx_surrogates_meta_form",
            "organization_id",
            "meta_form_id",
            postgresql_where=text("meta_form_id IS NOT NULL"),
        ),
        # GIN index for full-text search
        Index(
            "ix_surrogates_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        # PII hash index for phone lookups
        Index("idx_surrogates_org_phone_hash", "organization_id", "phone_hash"),
        # Contact reminder check index for efficient daily job queries
        Index(
            "idx_surrogates_reminder_check",
            "organization_id",
            "owner_type",
            "contact_status",
            "stage_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_number: Mapped[str] = mapped_column(String(10), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Workflow (v2: pipeline stages)
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_stages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status_label: Mapped[str] = mapped_column(String(100), nullable=False)

    source: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{DEFAULT_SURROGATE_SOURCE.value}'"),
        nullable=False,
    )
    is_priority: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)

    # Ownership (Salesforce-style single owner model)
    # owner_type="user" + owner_id=user_id, or owner_type="queue" + owner_id=queue_id
    owner_type: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    meta_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_leads.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Campaign tracking (denormalized from meta_leads for easy filtering)
    meta_ad_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meta_form_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Additional campaign hierarchy tracking (captured at conversion time)
    meta_campaign_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meta_adset_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Import metadata (tracking junk from CSV - ad_id, campaign_id, form_id, etc.)
    # NOT for business data - business data goes to custom fields
    import_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Contact (normalized: E.164 phone, 2-letter state)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Demographics
    date_of_birth: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)
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

    # ============================================
    # INSURANCE INFO
    # ============================================
    insurance_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_plan_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    insurance_policy_number: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    insurance_member_id: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    insurance_group_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    insurance_subscriber_name: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    insurance_subscriber_dob: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)

    # ============================================
    # IVF CLINIC
    # ============================================
    clinic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    clinic_address_line1: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    clinic_address_line2: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    clinic_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clinic_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    clinic_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    clinic_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    clinic_email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # ============================================
    # MONITORING CLINIC
    # ============================================
    monitoring_clinic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monitoring_clinic_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
    monitoring_clinic_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
    monitoring_clinic_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monitoring_clinic_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    monitoring_clinic_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    monitoring_clinic_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    monitoring_clinic_email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # ============================================
    # OB PROVIDER
    # ============================================
    ob_provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ob_clinic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ob_address_line1: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    ob_address_line2: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    ob_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ob_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ob_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ob_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    ob_email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # ============================================
    # DELIVERY HOSPITAL
    # ============================================
    delivery_hospital_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_hospital_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
    delivery_hospital_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
    delivery_hospital_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_hospital_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    delivery_hospital_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivery_hospital_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    delivery_hospital_email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # ============================================
    # PREGNANCY TRACKING
    # ============================================
    pregnancy_start_date: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)
    pregnancy_due_date: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)
    actual_delivery_date: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)

    # Soft delete
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Last contact tracking
    last_contacted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_contact_method: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # email, phone, note

    # Contact attempts tracking
    assigned_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )  # When assigned to current owner
    contact_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'unreached'"), nullable=False
    )
    contacted_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )  # When first successful contact

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="surrogates")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    archived_by: Mapped["User | None"] = relationship(foreign_keys=[archived_by_user_id])
    stage: Mapped["PipelineStage"] = relationship(foreign_keys=[stage_id])

    # Owner relationships for eager loading (fixes N+1 query)
    # These use custom join conditions since owner_id can point to either User or Queue
    # Using selectin loading to avoid LEFT OUTER JOIN conflicts with FOR UPDATE
    owner_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[owner_id],
        primaryjoin="and_(Surrogate.owner_id==User.id, Surrogate.owner_type=='user')",
        viewonly=True,
        lazy="selectin",
    )
    owner_queue: Mapped["Queue | None"] = relationship(
        "Queue",
        foreign_keys=[owner_id],
        primaryjoin="and_(Surrogate.owner_id==Queue.id, Surrogate.owner_type=='queue')",
        viewonly=True,
        lazy="selectin",
    )

    # Notes use EntityNote with entity_type='surrogate' - no direct relationship
    status_history: Mapped[list["SurrogateStatusHistory"]] = relationship(
        back_populates="surrogate", cascade="all, delete-orphan"
    )
    contact_attempts: Mapped[list["SurrogateContactAttempt"]] = relationship(
        back_populates="surrogate",
        cascade="all, delete-orphan",
        order_by="desc(SurrogateContactAttempt.attempted_at)",
    )


class StatusChangeRequest(Base):
    """
    Tracks pending regression requests that require admin approval.

    Used for both surrogates (stage changes) and intended parents (status changes).
    Regressions = moving to an earlier stage/status in the defined order.
    """

    __tablename__ = "status_change_requests"
    __table_args__ = (
        Index("idx_status_change_requests_org_status", "organization_id", "status"),
        # Partial unique indexes to prevent duplicate pending requests
        Index(
            "idx_pending_surrogate_requests",
            "organization_id",
            "entity_id",
            "target_stage_id",
            "effective_at",
            unique=True,
            postgresql_where=text("entity_type = 'surrogate' AND status = 'pending'"),
        ),
        Index(
            "idx_pending_ip_requests",
            "organization_id",
            "entity_id",
            "target_status",
            "effective_at",
            unique=True,
            postgresql_where=text("entity_type = 'intended_parent' AND status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'surrogate' or 'intended_parent'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True
    )  # For surrogates
    target_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # For intended parents
    effective_at: Mapped[datetime] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Request tracking
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="pending", nullable=False)

    # Approval tracking
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Rejection tracking
    rejected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Cancellation tracking
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )


class SurrogateStatusHistory(Base):
    """
    Tracks all status changes on surrogates for audit and timeline.

    Also records archive/restore operations.

    Dual timestamps for backdating support:
    - effective_at: When the change actually occurred (user-provided or now)
    - recorded_at: When it was recorded in the system (always server-generated)
    - changed_at: Derived from effective_at for backward compatibility
    """

    __tablename__ = "surrogate_status_history"
    __table_args__ = (
        Index("idx_surrogate_history_surrogate", "surrogate_id", "changed_at"),
        Index("idx_surrogate_history_org_changed", "organization_id", "changed_at"),
        Index(
            "idx_surrogate_history_org_stage_changed",
            "organization_id",
            "to_stage_id",
            "changed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # v2: Stage references with label snapshots
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
        nullable=True,
    )
    from_label_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    to_label_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)

    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Dual timestamps for backdating support
    effective_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )  # When it actually happened
    recorded_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), nullable=False
    )  # When recorded

    # Audit fields for approval flow
    requested_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )  # For regressions: when requested
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)  # When admin approved
    is_undo: Mapped[bool] = mapped_column(
        server_default=text("false"), nullable=False
    )  # Undo within grace period
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("status_change_requests.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship(back_populates="status_history")


class SurrogateActivityLog(Base):
    """
    Comprehensive activity log for all surrogate changes.

    Tracks: create, edit, status change, assign, archive, notes, etc.
    Stores new values for changed fields. Actor names resolved at read-time.
    """

    __tablename__ = "surrogate_activity_log"
    __table_args__ = (
        Index("idx_surrogate_activity_surrogate_time", "surrogate_id", "created_at"),
        Index("idx_surrogate_activity_org_time", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id])


# NOTE: SurrogateNote model removed (migrated to EntityNote with entity_type='surrogate')
# See migration 0013_migrate_casenotes.py


class SurrogateContactAttempt(Base):
    """
    Track individual contact attempts for surrogates.

    Supports:
    - Multi-method attempts per entry
    - Back-dated entries with audit trail
    - Assignment tracking for reminder logic
    """

    __tablename__ = "surrogate_contact_attempts"
    __table_args__ = (
        Index("idx_contact_attempts_surrogate", "surrogate_id", "attempted_at"),
        Index(
            "idx_contact_attempts_org_pending",
            "organization_id",
            "outcome",
            "attempted_at",
            postgresql_where=text("outcome != 'reached'"),
        ),
        Index(
            "idx_contact_attempts_surrogate_owner",
            "surrogate_id",
            "surrogate_owner_id_at_attempt",
            "attempted_at",
        ),
        CheckConstraint(
            "array_length(contact_methods, 1) > 0", name="ck_contact_methods_not_empty"
        ),
        CheckConstraint(
            "contact_methods <@ ARRAY['phone', 'email', 'sms']::VARCHAR[]",
            name="ck_contact_methods_valid",
        ),
        CheckConstraint(
            "attempted_at <= (now() + interval '5 minutes')",
            name="ck_attempted_at_not_future",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Multi-method support: store as array
    contact_methods: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )

    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit trail: distinguish when logged vs when it actually happened
    attempted_at: Mapped[datetime] = mapped_column(
        nullable=False
    )  # When the attempt actually occurred
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), nullable=False
    )  # When it was logged

    # Denormalized for performance: which assignment does this attempt belong to?
    surrogate_owner_id_at_attempt: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )  # surrogates.owner_id at time of attempt

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship(back_populates="contact_attempts")
    attempted_by: Mapped["User | None"] = relationship()

    @property
    def is_backdated(self) -> bool:
        """Check if this attempt was logged after it occurred."""
        return self.attempted_at < self.created_at


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
        Index(
            "idx_tasks_org_owner",
            "organization_id",
            "owner_type",
            "owner_id",
            "is_completed",
        ),
        Index("idx_tasks_org_status", "organization_id", "is_completed"),
        Index("idx_tasks_org_created", "organization_id", "created_at"),
        Index("idx_tasks_org_updated", "organization_id", "updated_at"),
        Index(
            "idx_tasks_due",
            "organization_id",
            "due_date",
            postgresql_where=text("is_completed = FALSE"),
        ),
        Index("idx_tasks_intended_parent", "intended_parent_id"),
        Index(
            "idx_task_wf_approval_unique",
            "workflow_execution_id",
            "workflow_action_index",
            unique=True,
            postgresql_where=text("task_type = 'workflow_approval'"),
        ),
        Index(
            "idx_tasks_pending_approvals",
            "organization_id",
            "status",
            "due_at",
            postgresql_where=text(
                "task_type = 'workflow_approval' AND status IN ('pending', 'in_progress')"
            ),
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
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=True
    )
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Ownership (Salesforce-style single owner model)
    # owner_type="user" + owner_id=user_id, or owner_type="queue" + owner_id=queue_id
    owner_type: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(
        String(50), server_default=text(f"'{TaskType.OTHER.value}'"), nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_completed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # ==========================================================================
    # Workflow Approval Fields (for task_type='workflow_approval')
    # ==========================================================================

    # Workflow execution reference
    workflow_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Action context
    workflow_action_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workflow_action_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workflow_action_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_action_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Internal only - never exposed via API"
    )

    # Audit context
    workflow_triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Resolution
    workflow_denial_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status for workflow approvals (richer than is_completed boolean)
    status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="For workflow approvals: pending, completed, denied, expired",
    )

    # Due datetime with time precision (for approval deadlines)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    surrogate: Mapped["Surrogate | None"] = relationship()
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])
    completed_by: Mapped["User | None"] = relationship(foreign_keys=[completed_by_user_id])
    workflow_triggered_by: Mapped["User | None"] = relationship(
        foreign_keys=[workflow_triggered_by_user_id]
    )

    @property
    def is_workflow_approval(self) -> bool:
        """Check if this is a workflow approval task."""
        return self.task_type == "workflow_approval"


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

    # Encrypted access token (Fernet)
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

    # Encrypted credentials (Fernet) - one token per account
    system_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # CAPI config (per account - replaces global settings.META_PIXEL_ID)
    pixel_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capi_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    capi_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

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


class Job(Base):
    """
    Background job for async processing.

    Used for: email sending, scheduled reminders, webhook retries.
    Worker polls for pending jobs and processes them.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        Index(
            "idx_jobs_pending",
            "status",
            "run_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("idx_jobs_org", "organization_id", "created_at"),
        Index(
            "uq_job_idempotency",
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

    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    run_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default=text(f"'{DEFAULT_JOB_STATUS.value}'"), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("3"), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
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
    created_by: Mapped["User | None"] = relationship()


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


class IntendedParent(Base):
    """
    Prospective parents seeking surrogacy services.

    Mirrors Surrogate patterns: org-scoped, soft-delete, status history.
    """

    __tablename__ = "intended_parents"
    __table_args__ = (
        Index("idx_ip_org_status", "organization_id", "status"),
        Index("idx_ip_org_created", "organization_id", "created_at"),
        Index("idx_ip_org_updated", "organization_id", "updated_at"),
        Index("idx_ip_org_owner", "organization_id", "owner_type", "owner_id"),
        UniqueConstraint(
            "organization_id",
            "intended_parent_number",
            name="uq_intended_parent_number",
        ),
        # Partial unique index: unique email per org for non-archived records
        Index(
            "uq_ip_email_hash_active",
            "organization_id",
            "email_hash",
            unique=True,
            postgresql_where=text("is_archived = false"),
        ),
        # GIN index for full-text search
        Index(
            "ix_intended_parents_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        # PII hash index for phone lookups
        Index("idx_ip_org_phone_hash", "organization_id", "phone_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    intended_parent_number: Mapped[str] = mapped_column(String(10), nullable=False)

    # Contact info
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Location (state only)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Budget (single field, Decimal for precision)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Internal notes (not the polymorphic notes, just a quick text field)
    notes_internal: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)

    # Status & workflow
    status: Mapped[str] = mapped_column(
        String(50), server_default=text(f"'{DEFAULT_IP_STATUS.value}'"), nullable=False
    )

    # Owner model (user or queue)
    owner_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Soft delete
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Activity tracking
    last_activity: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    status_history: Mapped[list["IntendedParentStatusHistory"]] = relationship(
        back_populates="intended_parent", cascade="all, delete-orphan"
    )


class IntendedParentStatusHistory(Base):
    """Tracks all status changes on intended parents for audit."""

    __tablename__ = "intended_parent_status_history"
    __table_args__ = (Index("idx_ip_history_ip", "intended_parent_id", "changed_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    intended_parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Dual timestamps for backdating support
    effective_at: Mapped[datetime | None] = mapped_column(nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Audit fields for approval flow
    requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_undo: Mapped[bool] = mapped_column(server_default=text("false"), nullable=False)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("status_change_requests.id", ondelete="SET NULL"),
        nullable=True,
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
    Author or admin+ can delete.
    """

    __tablename__ = "entity_notes"
    __table_args__ = (
        Index("idx_entity_notes_lookup", "entity_type", "entity_id", "created_at"),
        Index("idx_entity_notes_org", "organization_id", "created_at"),
        # GIN index for full-text search
        Index(
            "ix_entity_notes_search_vector",
            "search_vector",
            postgresql_using="gin",
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

    # Polymorphic reference
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'case', 'intended_parent'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Note content
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)  # HTML allowed, sanitized

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

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
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
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

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

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
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # In-app notification toggles (all default TRUE)
    surrogate_assigned: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    surrogate_status_changed: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )
    surrogate_claim_available: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )
    task_assigned: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    workflow_approvals: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    task_reminders: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )  # Due soon/overdue
    appointments: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )  # New/confirmed/cancelled
    contact_reminder: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )  # Contact attempt reminders

    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
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
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    integration_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="healthy", server_default=text("'healthy'")
    )
    config_status: Mapped[str] = mapped_column(
        String(30), default="configured", server_default=text("'configured'")
    )
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (
        Index("ix_integration_health_org_type", "organization_id", "integration_type"),
        Index(
            "uq_integration_health_org_type_null_key",
            "organization_id",
            "integration_type",
            unique=True,
            postgresql_where=text("integration_key IS NULL"),
        ),
        UniqueConstraint(
            "organization_id",
            "integration_type",
            "integration_key",
            name="uq_integration_health_org_type_key",
        ),
    )


class IntegrationErrorRollup(Base):
    """
    Hourly error counts per integration.

    Used to compute "errors in last 24h" as SUM(error_count) WHERE period_start > now() - 24h.
    Avoids storing raw events while maintaining accurate counts.
    """

    __tablename__ = "integration_error_rollup"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    integration_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    period_start: Mapped[datetime] = mapped_column(nullable=False)  # Hour bucket
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (
        Index(
            "ix_integration_error_rollup_lookup",
            "organization_id",
            "integration_type",
            "period_start",
        ),
        Index(
            "uq_integration_error_rollup_null_key",
            "organization_id",
            "integration_type",
            "period_start",
            unique=True,
            postgresql_where=text("integration_key IS NULL"),
        ),
        UniqueConstraint(
            "organization_id",
            "integration_type",
            "integration_key",
            "period_start",
            name="uq_integration_error_rollup",
        ),
    )


class SystemAlert(Base):
    """
    Deduplicated actionable alerts.

    Alerts are grouped by dedupe_key (fingerprint hash).
    Occurrence count tracks how many times the same issue occurred.
    """

    __tablename__ = "system_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), default="error", server_default=text("'error'")
    )
    status: Mapped[str] = mapped_column(String(20), default="open", server_default=text("'open'"))
    first_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # Null for unauthenticated requests
    )
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(10), default="minute", server_default=text("'minute'")
    )
    route: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_2xx: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    status_4xx: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    status_5xx: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    request_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    __table_args__ = (
        Index("ix_request_metrics_period", "period_start", "period_type"),
        Index(
            "uq_request_metrics_rollup_null_org",
            "period_start",
            "route",
            "method",
            unique=True,
            postgresql_where=text("organization_id IS NULL"),
        ),
        UniqueConstraint(
            "organization_id",
            "period_start",
            "route",
            "method",
            name="uq_request_metrics_rollup",
        ),
    )


# =============================================================================
# Analytics Snapshots (Cached aggregates)
# =============================================================================


class AnalyticsSnapshot(Base):
    """
    Cached analytics payloads for dashboard and reports.

    snapshot_key is a deterministic hash of the request params.
    """

    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "snapshot_key", name="uq_analytics_snapshot_key"),
        Index("idx_analytics_snapshot_org_type", "organization_id", "snapshot_type"),
        Index("idx_analytics_snapshot_expires", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_type: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_key: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    range_start: Mapped[datetime | None] = mapped_column(nullable=True)
    range_end: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    organization: Mapped["Organization"] = relationship()


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
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    provider: Mapped[str] = mapped_column(
        String(20), default="openai", server_default=text("'openai'")
    )
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(
        String(50), default="gpt-4o-mini", server_default=text("'gpt-4o-mini'")
    )
    context_notes_limit: Mapped[int | None] = mapped_column(
        Integer, default=5, server_default=text("5")
    )
    conversation_history_limit: Mapped[int | None] = mapped_column(
        Integer, default=10, server_default=text("10")
    )
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


class ResendSettings(Base):
    """
    Org-level email provider configuration (Resend or Gmail).

    Stores encrypted API keys and webhook secrets.
    Only one settings record per organization.
    """

    __tablename__ = "resend_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Provider selection: 'resend' | 'gmail' | None (not configured)
    email_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Resend configuration
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reply_to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_key_validated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Gmail configuration: org-level default sender (must be admin)
    default_sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Webhook configuration (unique ID for URL routing)
    webhook_id: Mapped[str] = mapped_column(
        String(36), server_default=text("gen_random_uuid()::text"), nullable=False
    )
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Version control (same as AI settings)
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    default_sender: Mapped["User | None"] = relationship()

    __table_args__ = (Index("idx_resend_settings_webhook_id", "webhook_id", unique=True),)


class AIConversation(Base):
    """
    AI conversation thread.

    Each user has their own conversation per entity (case).
    Developers can view all conversations for audit purposes.
    """

    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'case'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()
    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation", order_by="AIMessage.created_at"
    )

    __table_args__ = (
        Index("ix_ai_conversations_entity", "organization_id", "entity_type", "entity_id"),
        Index("ix_ai_conversations_user", "user_id", "entity_type", "entity_id"),
        UniqueConstraint(
            "organization_id",
            "user_id",
            "entity_type",
            "entity_id",
            name="uq_ai_conversations_user_entity",
        ),
    )


class AIMessage(Base):
    """
    Individual message in an AI conversation.

    Role can be 'user', 'assistant', or 'system'.
    proposed_actions is a JSONB array of action specs when AI proposes actions.
    """

    __tablename__ = "ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_actions: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    conversation: Mapped["AIConversation"] = relationship(back_populates="messages")
    action_approvals: Mapped[list["AIActionApproval"]] = relationship(back_populates="message")

    __table_args__ = (Index("ix_ai_messages_conversation", "conversation_id", "created_at"),)


class AIActionApproval(Base):
    """
    Track approval status for each proposed action.

    Separates approval state from message content for cleaner queries.
    One record per action in the proposed_actions array.
    """

    __tablename__ = "ai_action_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default=text("'pending'")
    )
    executed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    message: Mapped["AIMessage"] = relationship(back_populates="action_approvals")

    __table_args__ = (
        Index("ix_ai_action_approvals_message", "message_id"),
        Index("ix_ai_action_approvals_status", "status"),
    )


class AIBulkTaskRequest(Base):
    """
    Idempotency store for AI bulk task creation.

    Ensures repeated request_id submissions return the same response.
    """

    __tablename__ = "ai_bulk_task_requests"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "request_id",
            name="uq_ai_bulk_task_requests",
        ),
        Index("ix_ai_bulk_task_requests_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class AIEntitySummary(Base):
    """
    Cached entity context for AI.

    Updated when case notes, status, or tasks change.
    Avoids regenerating context on every chat request.
    """

    __tablename__ = "ai_entity_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    notes_plain_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (UniqueConstraint("organization_id", "entity_type", "entity_id"),)


class AIUsageLog(Base):
    """
    Token usage tracking for cost monitoring.

    Records each AI API call with token counts and estimated cost.
    """

    __tablename__ = "ai_usage_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (Index("ix_ai_usage_log_org_date", "organization_id", "created_at"),)


class UserIntegration(Base):
    """
    Per-user OAuth integrations.

    Stores encrypted tokens for Gmail, Zoom, Google Calendar, etc.
    Each user can connect their own accounts.
    """

    __tablename__ = "user_integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    integration_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # gmail, zoom, google_calendar
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    # Version control
    current_version: Mapped[int] = mapped_column(
        default=1, server_default=text("1"), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "integration_type"),)


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
        Index(
            "idx_audit_org_actor_created",
            "organization_id",
            "actor_user_id",
            "created_at",
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
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # System events have no actor
    )

    # Event classification
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # AuditEventType

    # Target entity (optional)
    target_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'user', 'case', 'ai_action', etc.
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
        nullable=True,
    )
    after_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    actor: Mapped["User | None"] = relationship()


# =============================================================================
# Compliance
# =============================================================================


class ExportJob(Base):
    """
    Asynchronous export job for compliance/audit data.

    Files are stored in external storage (S3 or local dev) and accessed via
    short-lived signed URLs generated on demand.
    """

    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("idx_export_jobs_org_created", "organization_id", "created_at"),
        Index("idx_export_jobs_org_status", "organization_id", "status"),
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

    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # pending, processing, completed, failed
    export_type: Mapped[str] = mapped_column(String(30), nullable=False)  # audit, cases, analytics
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # csv, json
    redact_mode: Mapped[str] = mapped_column(String(10), nullable=False)  # redacted, full

    date_range_start: Mapped[datetime] = mapped_column(nullable=False)
    date_range_end: Mapped[datetime] = mapped_column(nullable=False)

    record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledgment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()


class LegalHold(Base):
    """
    Legal hold to block data purges.

    If entity_type/entity_id are NULL, the hold is org-wide.
    """

    __tablename__ = "legal_holds"
    __table_args__ = (
        Index("idx_legal_holds_org_active", "organization_id", "released_at"),
        Index(
            "idx_legal_holds_entity_active",
            "organization_id",
            "entity_type",
            "entity_id",
            "released_at",
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
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    released_by: Mapped["User | None"] = relationship(foreign_keys=[released_by_user_id])


class DataRetentionPolicy(Base):
    """
    Data retention policy by entity type (audit logs are archive-only).

    retention_days=0 means "keep forever".
    """

    __tablename__ = "data_retention_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_type", name="uq_retention_policy_org_entity"),
        Index("idx_retention_policy_org_active", "organization_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()


class OrgCounter(Base):
    """
    Atomic counter for sequential ID generation (e.g., case numbers).

    Uses INSERT...ON CONFLICT for atomic increment without race conditions.
    """

    __tablename__ = "org_counters"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    counter_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    current_value: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )


# =============================================================================
# CSV Import
# =============================================================================


class SurrogateImport(Base):
    """
    Tracks CSV import jobs for surrogates.

    Flow: upload → preview → confirm (async job) → complete

    Dedupe:
    - Matches by email against all surrogates (including archived)
    - Also checks for duplicates within the CSV itself
    """

    __tablename__ = "surrogate_imports"
    __table_args__ = (Index("idx_surrogate_imports_org_created", "organization_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # File info
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

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
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Enhanced detection & mapping (v2)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    detected_encoding: Mapped[str | None] = mapped_column(String(20), nullable=True)
    detected_delimiter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    column_mapping_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    date_ambiguity_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    unknown_column_behavior: Mapped[str] = mapped_column(
        String(20), default="ignore", nullable=False
    )

    # Admin approval workflow
    # Status values: 'pending', 'awaiting_approval', 'approved', 'processing', 'completed', 'rejected', 'failed'
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deduplication_stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])
    template: Mapped["ImportTemplate | None"] = relationship(back_populates="imports")


# =============================================================================
# Import Templates & Custom Fields
# =============================================================================


class ImportTemplate(Base):
    """
    Reusable CSV import configuration.

    Stores column mappings, transformations, and import settings.
    One template per org can be is_default=true (enforced via partial index).
    """

    __tablename__ = "import_templates"
    __table_args__ = (
        Index("idx_import_templates_org", "organization_id"),
        Index(
            "uq_import_template_default",
            "organization_id",
            unique=True,
            postgresql_where=text("is_default = TRUE"),
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

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)

    # File format settings
    encoding: Mapped[str] = mapped_column(
        String(20), default="auto", nullable=False
    )  # 'auto', 'utf-8', 'utf-16'
    delimiter: Mapped[str] = mapped_column(
        String(5), default="auto", nullable=False
    )  # 'auto', ',', '\t'
    has_header: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Column mappings: [{csv_column: str, surrogate_field: str, transformation: str|null}]
    column_mappings: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Transformations config: {field: {transformer: str, options: dict}}
    transformations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # What to do with unmapped columns: 'ignore', 'metadata', 'warn'
    unknown_column_behavior: Mapped[str] = mapped_column(
        String(20), default="ignore", nullable=False
    )

    # Usage stats
    usage_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Audit
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()
    imports: Mapped[list["SurrogateImport"]] = relationship(back_populates="template")


class CustomField(Base):
    """
    Org-scoped custom field definition.

    Allows organizations to define additional fields for surrogates
    to capture data that doesn't fit in standard schema fields.
    """

    __tablename__ = "custom_fields"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_custom_field_key"),
        Index("idx_custom_fields_org", "organization_id"),
        Index("idx_custom_fields_org_active", "organization_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Field definition
    key: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "criminal_history"
    label: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g., "Criminal History"
    field_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'text', 'number', 'boolean', 'date', 'select'
    options: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )  # For select type: ["option1", "option2"]

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Audit
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()
    values: Mapped[list["CustomFieldValue"]] = relationship(
        back_populates="custom_field",
        cascade="all, delete-orphan",
    )


class CustomFieldValue(Base):
    """
    Custom field value for a surrogate.

    Stores the actual value for a custom field on a specific surrogate.
    """

    __tablename__ = "custom_field_values"
    __table_args__ = (
        UniqueConstraint("surrogate_id", "custom_field_id", name="uq_custom_field_value"),
        Index("idx_custom_field_values_surrogate", "surrogate_id"),
        Index("idx_custom_field_values_field", "custom_field_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogates.id", ondelete="CASCADE"),
        nullable=False,
    )
    custom_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_fields.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Store any type as JSONB
    value_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    custom_field: Mapped["CustomField"] = relationship(back_populates="values")


# =============================================================================
# Org-Configurable Pipelines (v2 - Full CRUD)
# =============================================================================


class Pipeline(Base):
    """
    Organization pipeline configuration.

    v2 (Full CRUD):
    - PipelineStage rows define custom stages
    - Surrogates reference stage_id (FK)
    - Stages have immutable slugs, editable labels/colors
    """

    __tablename__ = "pipelines"
    __table_args__ = (Index("idx_pipelines_org", "organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(100), default="Default", nullable=False)
    is_default: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Version control
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    stages: Mapped[list["PipelineStage"]] = relationship(
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="PipelineStage.order",
    )


class PipelineStage(Base):
    """
    Individual pipeline stage configuration.

    - slug: Immutable after creation, unique per pipeline
    - stage_type: Immutable, controls role access (intake/post_approval/terminal)
    - Soft-delete via is_active + deleted_at
    - Surrogates reference stage_id (FK)
    """

    __tablename__ = "pipeline_stages"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "slug", name="uq_stage_slug"),
        Index("idx_stage_pipeline_order", "pipeline_id", "order"),
        Index("idx_stage_pipeline_active", "pipeline_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Immutable after creation
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    stage_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # intake/post_approval/terminal

    # Editable
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)  # hex #RRGGBB
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Soft-delete
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)

    # Contact attempts UI gating
    is_intake_stage: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )

    # Future: transition rules
    allowed_next_slugs: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )

    # Relationships
    pipeline: Mapped["Pipeline"] = relationship(back_populates="stages")


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

    NOT used for: Surrogates, tasks, notes (use activity logs instead)

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
        Index(
            "idx_entity_versions_lookup",
            "organization_id",
            "entity_type",
            "entity_id",
            "created_at",
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

    # What's being versioned
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "pipeline", "email_template", etc.
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Version metadata
    version: Mapped[int] = mapped_column(nullable=False)  # Monotonic, starts at 1
    schema_version: Mapped[int] = mapped_column(
        default=1, nullable=False
    )  # For future payload migrations

    # Encrypted payload (Fernet)
    payload_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Integrity verification
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 of decrypted payload

    # Audit trail
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # "Updated stages", "Rollback from v3"

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
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

    # Recurrence settings
    recurrence_mode: Mapped[str] = mapped_column(
        String(20), server_default=text("'one_time'"), nullable=False
    )  # 'one_time' | 'recurring'
    recurrence_interval_hours: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 24 = daily, 168 = weekly
    recurrence_stop_on_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # Stop when entity reaches this status

    # Rate limiting (None = unlimited)
    rate_limit_per_hour: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Max executions per hour globally
    rate_limit_per_entity_per_day: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Max times can run on same entity per 24h

    # System workflow fields
    is_system_workflow: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    system_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Unique key for system workflows

    # First-run review tracking
    requires_review: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Audit
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_user_id])
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    user_preferences: Mapped[list["UserWorkflowPreference"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
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
        Index(
            "idx_exec_paused",
            "organization_id",
            "status",
            postgresql_where=text("status = 'paused'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automation_workflows.id", ondelete="CASCADE"),
        nullable=False,
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

    executed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # ==========================================================================
    # Workflow Approval Pause State
    # ==========================================================================

    # When paused for approval, track which action and task
    paused_at_action_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paused_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    workflow: Mapped["AutomationWorkflow"] = relationship(back_populates="executions")
    paused_task: Mapped["Task | None"] = relationship(foreign_keys=[paused_task_id])


class UserWorkflowPreference(Base):
    """
    Per-user workflow opt-out preferences.

    Allows individual users to opt out of specific workflows
    (e.g., disable notification workflows they don't want).
    """

    __tablename__ = "user_workflow_preferences"
    __table_args__ = (UniqueConstraint("user_id", "workflow_id", name="uq_user_workflow"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automation_workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_opted_out: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship()
    workflow: Mapped["AutomationWorkflow"] = relationship(back_populates="user_preferences")


class WorkflowResumeJob(Base):
    """
    Idempotency table for workflow resume jobs.

    Prevents duplicate resume processing when the same approval
    is resolved multiple times (e.g., race conditions, retries).
    """

    __tablename__ = "workflow_resume_jobs"
    __table_args__ = (
        Index(
            "idx_resume_jobs_pending",
            "status",
            "created_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship()
    task: Mapped["Task"] = relationship()


# =============================================================================
# Workflow Templates (Marketplace)
# =============================================================================


class WorkflowTemplate(Base):
    """
    Reusable workflow templates for the template marketplace.

    Templates can be global (system-provided) or organization-specific.
    Users can create workflows from templates via "Use Template".
    """

    __tablename__ = "workflow_templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_template_name"),
        Index("idx_template_org", "organization_id"),
        Index("idx_template_category", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="template")
    category: Mapped[str] = mapped_column(
        String(50), default="general"
    )  # "onboarding", "follow-up", "notifications", "compliance", "general"

    # Workflow configuration (template content)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    conditions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    condition_logic: Mapped[str] = mapped_column(String(10), default="AND")
    actions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # Scope
    is_global: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )  # True = system template, False = org-specific
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,  # Null for global templates
    )

    # Usage tracking
    usage_count: Mapped[int] = mapped_column(default=0)

    # Audit
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization | None"] = relationship()
    created_by: Mapped["User | None"] = relationship()


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
        Index("ix_zoom_meetings_surrogate_id", "surrogate_id"),
        Index("ix_zoom_meetings_org_created", "organization_id", "created_at"),
        Index(
            "uq_zoom_meetings_idempotency",
            "organization_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # Allow null if user deleted
    )
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="SET NULL"), nullable=True
    )
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Zoom meeting details
    zoom_meeting_id: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(nullable=True)
    duration: Mapped[int] = mapped_column(default=30, nullable=False)  # minutes
    timezone: Mapped[str] = mapped_column(
        String(100), default="America/Los_Angeles", nullable=False
    )
    join_url: Mapped[str] = mapped_column(String(500), nullable=False)
    start_url: Mapped[str] = mapped_column(Text, nullable=False)  # Can be very long
    password: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()
    intended_parent: Mapped["IntendedParent"] = relationship()


class ZoomWebhookEvent(Base):
    """
    Zoom webhook events for deduplication and audit trail.

    Stores processed webhook events to prevent duplicate processing
    and track meeting lifecycle (started/ended timestamps).
    """

    __tablename__ = "zoom_webhook_events"
    __table_args__ = (
        Index("ix_zoom_webhook_events_zoom_meeting_id", "zoom_meeting_id"),
        Index("ix_zoom_webhook_events_processed_at", "processed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_event_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )  # Dedupe key from Zoom
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # meeting.started, meeting.ended
    zoom_meeting_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )


# =============================================================================
# Matching
# =============================================================================


class Match(Base):
    """
    Proposed match between a surrogate and intended parent.

    Tracks the matching workflow from proposal through acceptance/rejection.
    Only one accepted match is allowed per surrogate.
    """

    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "surrogate_id",
            "intended_parent_id",
            name="uq_match_org_surrogate_ip",
        ),
        UniqueConstraint(
            "organization_id",
            "match_number",
            name="uq_match_number",
        ),
        # Only one accepted match allowed per surrogate per org
        Index(
            "uq_one_accepted_match_per_surrogate",
            "organization_id",
            "surrogate_id",
            unique=True,
            postgresql_where=text("status = 'accepted'"),
        ),
        Index("ix_matches_match_number", "match_number"),
        Index("ix_matches_surrogate_id", "surrogate_id"),
        Index("ix_matches_ip_id", "intended_parent_id"),
        Index("ix_matches_status", "status"),
        Index("idx_matches_org_status", "organization_id", "status"),
        Index("idx_matches_org_created", "organization_id", "created_at"),
        Index("idx_matches_org_updated", "organization_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    intended_parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_number: Mapped[str] = mapped_column(String(10), nullable=False)

    # Status workflow: proposed → reviewing → accepted/rejected/cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    compatibility_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),  # 0.00 to 100.00
        nullable=True,
    )

    # Who proposed and when
    proposed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    proposed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Review details
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Notes and rejection reason
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()
    intended_parent: Mapped["IntendedParent"] = relationship()
    proposed_by: Mapped["User"] = relationship(foreign_keys=[proposed_by_user_id])
    reviewed_by: Mapped["User"] = relationship(foreign_keys=[reviewed_by_user_id])

    # Match events relationship
    events: Mapped[list["MatchEvent"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="MatchEvent.starts_at",
    )


class MatchEvent(Base):
    """
    Calendar events for a match between surrogate and intended parents.

    Tracks important dates like medications, medical exams, legal milestones,
    and delivery dates with color coding for person type and event type.

    Timezone-safe: stores starts_at/ends_at in UTC with timezone string for display.
    For all-day events, use start_date/end_date (date only, no timezone conversion).
    """

    __tablename__ = "match_events"
    __table_args__ = (
        Index("ix_match_events_match_starts", "match_id", "starts_at"),
        Index("ix_match_events_org_starts", "organization_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )

    # Who and what
    person_type: Mapped[str] = mapped_column(
        String(20),  # "surrogate" or "ip"
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(20),  # medication, medical_exam, legal, delivery, custom
        nullable=False,
    )

    # Event details
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timezone-aware datetime (for timed events)
    starts_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="America/Los_Angeles")

    # All-day events (date only, no timezone conversion)
    all_day: Mapped[bool] = mapped_column(nullable=False, default=False)
    start_date: Mapped[date | None] = mapped_column(nullable=True)
    end_date: Mapped[date | None] = mapped_column(nullable=True)

    # Audit
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    match: Mapped["Match"] = relationship(back_populates="events")
    created_by: Mapped["User"] = relationship()


# =============================================================================
# Attachments
# =============================================================================


class Attachment(Base):
    """
    File attachments for cases (and future: intended parents).

    Security features:
    - SHA-256 checksum for integrity verification
    - Virus scan status with quarantine until clean
    - Soft-delete with audit trail
    - Access control via case ownership
    """

    __tablename__ = "attachments"
    __table_args__ = (
        Index("idx_attachments_surrogate", "surrogate_id"),
        Index("idx_attachments_org_scan", "organization_id", "scan_status"),
        Index(
            "idx_attachments_active",
            "surrogate_id",
            postgresql_where=text("deleted_at IS NULL AND quarantined = FALSE"),
        ),
        Index("idx_attachments_intended_parent", "intended_parent_id"),
        # GIN index for full-text search
        Index(
            "ix_attachments_search_vector",
            "search_vector",
            postgresql_using="gin",
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
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=True
    )
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=True,
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # Security / Virus scan
    scan_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )  # pending | clean | infected | error
    scanned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    quarantined: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)

    # Soft-delete
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()
    uploaded_by: Mapped["User | None"] = relationship(foreign_keys=[uploaded_by_user_id])
    deleted_by: Mapped["User | None"] = relationship(foreign_keys=[deleted_by_user_id])


# =============================================================================
# Forms & Applications
# =============================================================================


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
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )
    quarantined: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )

    submission: Mapped["FormSubmission"] = relationship()


class SurrogateProfileOverride(Base):
    """
    Override values for profile card (independent of submission/surrogate fields).

    Used by case_manager+ to customize profile view without modifying
    the original submission or surrogate fields.
    """

    __tablename__ = "surrogate_profile_overrides"
    __table_args__ = (
        UniqueConstraint("surrogate_id", "field_key", name="uq_surrogate_profile_override_field"),
        Index("idx_profile_overrides_surrogate", "surrogate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    updated_by: Mapped["User | None"] = relationship()


class SurrogateProfileState(Base):
    """
    Tracks the base submission used for a surrogate profile card.

    Allows Sync + Save to pin the profile base to a new submission.
    """

    __tablename__ = "surrogate_profile_states"
    __table_args__ = (
        UniqueConstraint("surrogate_id", name="uq_surrogate_profile_state_surrogate"),
        Index("idx_profile_state_surrogate", "surrogate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    updated_by: Mapped["User | None"] = relationship()


class SurrogateProfileHiddenField(Base):
    """
    Tracks hidden fields in surrogate profile card.

    Hidden fields show as masked values ('*' or '-') in profile exports.
    case_manager+ can toggle visibility.
    """

    __tablename__ = "surrogate_profile_hidden_fields"
    __table_args__ = (
        UniqueConstraint("surrogate_id", "field_key", name="uq_surrogate_profile_hidden_field"),
        Index("idx_profile_hidden_surrogate", "surrogate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(255), nullable=False)
    hidden_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    hidden_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    hidden_by: Mapped["User | None"] = relationship()


# =============================================================================
# Appointments & Scheduling Models
# =============================================================================


class AppointmentType(Base):
    """
    Appointment type template (e.g., "Initial Consultation", "Follow-up").

    Defines duration, meeting mode, buffer times, and reminder settings.
    Each user can have multiple appointment types.
    """

    __tablename__ = "appointment_types"
    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_appointment_type_slug"),
        Index("idx_appointment_types_user", "user_id", "is_active"),
        Index("idx_appointment_types_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Type details
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)  # URL-safe identifier
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scheduling
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    buffer_before_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    buffer_after_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Meeting mode
    meeting_mode: Mapped[str] = mapped_column(
        String(20), server_default=text(f"'{MeetingMode.ZOOM.value}'"), nullable=False
    )

    # Notifications
    reminder_hours_before: Mapped[int] = mapped_column(Integer, default=24, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()


class AvailabilityRule(Base):
    """
    Weekly availability rule (e.g., "Monday 9am-5pm").

    Uses ISO weekday: Monday=0, Sunday=6.
    Multiple rules per user (one per day or multiple time blocks per day).
    """

    __tablename__ = "availability_rules"
    __table_args__ = (
        Index("idx_availability_rules_user", "user_id"),
        Index("idx_availability_rules_org", "organization_id"),
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_valid_day_of_week"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Day of week (ISO: Monday=0, Sunday=6)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)

    # Time range (in user's timezone, stored as time)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # User's timezone for interpretation
    timezone: Mapped[str] = mapped_column(String(50), default="America/Los_Angeles", nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()


class AvailabilityOverride(Base):
    """
    Date-specific override for availability.

    Can mark a day as unavailable or provide custom hours.
    """

    __tablename__ = "availability_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "override_date", name="uq_availability_override_date"),
        Index("idx_availability_overrides_user", "user_id"),
        Index("idx_availability_overrides_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Date being overridden
    override_date: Mapped[date] = mapped_column(Date, nullable=False)

    # If unavailable, both times are NULL. If custom hours, both are set.
    is_unavailable: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), nullable=False
    )
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Reason (optional, e.g., "Holiday", "Vacation")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()


class BookingLink(Base):
    """
    Secure public booking link for a user.

    Public slug is used in URLs (/book/{public_slug}).
    Can be regenerated to invalidate old links.
    """

    __tablename__ = "booking_links"
    __table_args__ = (
        UniqueConstraint("public_slug", name="uq_booking_link_slug"),
        UniqueConstraint("user_id", name="uq_booking_link_user"),
        Index("idx_booking_links_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Public URL slug (cryptographically random)
    public_slug: Mapped[str] = mapped_column(String(32), nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()


class Appointment(Base):
    """
    Booked appointment.

    Lifecycle: pending → confirmed → completed/cancelled/no_show
    Includes tokens for client self-service (reschedule/cancel).
    """

    __tablename__ = "appointments"
    __table_args__ = (
        Index("idx_appointments_user_date", "user_id", "scheduled_start"),
        Index("idx_appointments_org_status", "organization_id", "status"),
        Index("idx_appointments_org_user", "organization_id", "user_id"),
        Index("idx_appointments_org_created", "organization_id", "created_at"),
        Index("idx_appointments_org_updated", "organization_id", "updated_at"),
        Index("idx_appointments_type", "appointment_type_id"),
        Index("idx_appointments_surrogate", "surrogate_id"),
        Index("idx_appointments_ip", "intended_parent_id"),
        Index(
            "idx_appointments_pending_expiry",
            "pending_expires_at",
            postgresql_where=text("status = 'pending'"),
        ),
        UniqueConstraint("idempotency_key", name="uq_appointment_idempotency"),
        UniqueConstraint("reschedule_token", name="uq_appointment_reschedule_token"),
        UniqueConstraint("cancel_token", name="uq_appointment_cancel_token"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointment_types.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Optional link to surrogate/IP for match-scoped filtering
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="SET NULL"), nullable=True
    )
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Client info
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    client_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    client_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_timezone: Mapped[str] = mapped_column(String(50), nullable=False)

    # Scheduling (stored in UTC)
    scheduled_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_before_minutes: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    buffer_after_minutes: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )

    # Meeting mode (snapshot from appointment type)
    meeting_mode: Mapped[str] = mapped_column(String(20), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{AppointmentStatus.PENDING.value}'"),
        nullable=False,
    )

    # Pending expiry (60 min TTL for unapproved requests)
    pending_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Approval tracking
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Cancellation tracking
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_by_client: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Integration IDs
    google_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_meet_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    zoom_meeting_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zoom_join_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Meeting lifecycle timestamps (from webhook events)
    meeting_started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    meeting_ended_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Self-service tokens (one-time use tokens for client actions)
    reschedule_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reschedule_token_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    cancel_token_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Idempotency (prevent duplicate bookings)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    appointment_type: Mapped["AppointmentType | None"] = relationship()
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])
    email_logs: Mapped[list["AppointmentEmailLog"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan"
    )


class AppointmentEmailLog(Base):
    """
    Log of emails sent for an appointment.

    Tracks: request received, confirmed, rescheduled, cancelled, reminder.
    """

    __tablename__ = "appointment_email_logs"
    __table_args__ = (
        Index("idx_appointment_email_logs_appt", "appointment_id"),
        Index("idx_appointment_email_logs_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Email details
    email_type: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )  # pending, sent, failed
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # External ID from email service
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    appointment: Mapped["Appointment"] = relationship(back_populates="email_logs")


# =============================================================================
# Campaigns Module
# =============================================================================


class Campaign(Base):
    """
    Bulk email campaign definition.

    Allows sending targeted emails to groups of cases or intended parents
    with filtering, scheduling, and tracking.
    """

    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_campaign_name"),
        Index("idx_campaigns_org_status", "organization_id", "status"),
        Index("idx_campaigns_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Campaign details
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Template
    email_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Recipient filtering
    recipient_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'case' | 'intended_parent'
    filter_criteria: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )  # {stage_id, state, created_after, tags, etc.}

    # Scheduling
    scheduled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'draft'"), nullable=False
    )  # 'draft' | 'scheduled' | 'sending' | 'completed' | 'cancelled' | 'failed'

    # Audit
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    email_template: Mapped["EmailTemplate"] = relationship()
    created_by: Mapped["User | None"] = relationship()
    runs: Mapped[list["CampaignRun"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignRun.started_at.desc()",
    )


class CampaignRun(Base):
    """
    Execution record for a campaign send.

    Tracks the progress and results of a campaign execution.
    """

    __tablename__ = "campaign_runs"
    __table_args__ = (
        Index("idx_campaign_runs_campaign", "campaign_id", "started_at"),
        Index("idx_campaign_runs_org", "organization_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Execution timing
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'running'"), nullable=False
    )  # 'running' | 'completed' | 'failed'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Email provider locked at run creation: 'resend' | 'gmail'
    email_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Counts
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opened_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    campaign: Mapped["Campaign"] = relationship(back_populates="runs")
    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class CampaignRecipient(Base):
    """
    Per-recipient status for a campaign run.

    Tracks the delivery status of each email sent.
    """

    __tablename__ = "campaign_recipients"
    __table_args__ = (
        Index("idx_campaign_recipients_run", "run_id"),
        Index("idx_campaign_recipients_entity", "entity_type", "entity_id"),
        Index("idx_campaign_recipients_tracking_token", "tracking_token", unique=True),
        UniqueConstraint("run_id", "entity_type", "entity_id", name="uq_campaign_recipient"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Recipient reference
    entity_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'case' | 'intended_parent'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recipient_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )  # 'pending' | 'sent' | 'delivered' | 'failed' | 'skipped'
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timing
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # External ID from email service
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Tracking - unique index 'idx_campaign_recipients_tracking_token' created by migration c3e9f2a1b8d4
    tracking_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    run: Mapped["CampaignRun"] = relationship(back_populates="recipients")
    tracking_events: Mapped[list["CampaignTrackingEvent"]] = relationship(
        back_populates="recipient", cascade="all, delete-orphan"
    )


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


class CampaignTrackingEvent(Base):
    """
    Individual email open/click events for campaign analytics.

    Records each time an email is opened or a link is clicked,
    capturing IP address and user agent for device analytics.
    """

    __tablename__ = "campaign_tracking_events"
    __table_args__ = (
        Index("idx_tracking_events_recipient", "recipient_id"),
        Index("idx_tracking_events_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_recipients.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Event type
    event_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'open' | 'click'

    # For clicks: the URL that was clicked
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Analytics data
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    recipient: Mapped["CampaignRecipient"] = relationship(back_populates="tracking_events")


# =============================================================================
# Interview Models
# =============================================================================


class SurrogateInterview(Base):
    """
    Interview record for a surrogate.

    Supports multiple interviews per surrogate with versioned transcripts.
    Transcripts > 100KB are offloaded to S3 (text kept inline for search).
    """

    __tablename__ = "surrogate_interviews"
    __table_args__ = (
        Index("ix_surrogate_interviews_surrogate_id", "surrogate_id"),
        Index("ix_surrogate_interviews_org_conducted", "organization_id", "conducted_at"),
        Index(
            "ix_surrogate_interviews_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogates.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Metadata
    interview_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'phone', 'video', 'in_person'
    conducted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    conducted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Current transcript (denormalized for quick reads)
    transcript_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # TipTap JSON (canonical format)
    transcript_text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Always stored for search/diff
    transcript_storage_key: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # S3 key if offloaded
    transcript_version: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )
    transcript_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SHA256 for no-change guard
    transcript_size_bytes: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'completed'"), nullable=False
    )  # 'draft', 'completed'

    # Retention
    retention_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_retention_policies.id"),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    conducted_by: Mapped["User"] = relationship()
    versions: Mapped[list["InterviewTranscriptVersion"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )
    notes: Mapped[list["InterviewNote"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )
    interview_attachments: Mapped[list["InterviewAttachment"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )
    retention_policy: Mapped["DataRetentionPolicy | None"] = relationship()


class InterviewTranscriptVersion(Base):
    """
    Version history for interview transcripts.

    Created automatically when transcript changes (with no-change guard via hash).
    Supports restore to any previous version.
    """

    __tablename__ = "interview_transcript_versions"
    __table_args__ = (
        UniqueConstraint("interview_id", "version", name="uq_interview_version"),
        Index("ix_interview_versions_interview", "interview_id", "version"),
        Index("ix_interview_versions_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogate_interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Content
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Metadata
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'manual', 'ai_transcription', 'restore'

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    interview: Mapped["SurrogateInterview"] = relationship(back_populates="versions")
    organization: Mapped["Organization"] = relationship()
    author: Mapped["User"] = relationship()


class InterviewNote(Base):
    """
    Shared notes on interviews, optionally anchored to transcript selections.

    Supports:
    - General notes (no anchor)
    - Anchored comments (with comment_id + anchor_text)
    - Reply threads (parent_id links to parent note)
    - Resolve functionality (resolved_at/resolved_by_user_id)

    Anchors are tied to a specific transcript version.
    """

    __tablename__ = "interview_notes"
    __table_args__ = (
        Index("ix_interview_notes_interview", "interview_id"),
        Index("ix_interview_notes_org", "organization_id"),
        Index("ix_interview_notes_parent", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogate_interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Content (sanitized HTML)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Anchor to specific version (prevents drift)
    transcript_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # TipTap comment mark ID (preferred - stable anchor)
    comment_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )  # UUID format

    anchor_text: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Metadata
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Thread support (for replies)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_notes.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Resolve support
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    interview: Mapped["SurrogateInterview"] = relationship(back_populates="notes")
    organization: Mapped["Organization"] = relationship()
    author: Mapped["User"] = relationship(foreign_keys=[author_user_id])
    resolved_by: Mapped["User | None"] = relationship(foreign_keys=[resolved_by_user_id])
    parent: Mapped["InterviewNote | None"] = relationship(
        "InterviewNote",
        remote_side="InterviewNote.id",
        back_populates="replies",
        foreign_keys=[parent_id],
    )
    replies: Mapped[list["InterviewNote"]] = relationship(
        "InterviewNote",
        back_populates="parent",
        foreign_keys="InterviewNote.parent_id",
        order_by="InterviewNote.created_at",
    )


class InterviewAttachment(Base):
    """
    Links attachments to interviews.

    Reuses the existing Attachment model. Supports AI transcription
    for audio/video files.
    """

    __tablename__ = "interview_attachments"
    __table_args__ = (
        UniqueConstraint("interview_id", "attachment_id", name="uq_interview_attachment"),
        Index("ix_interview_attachments_interview", "interview_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogate_interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # AI transcription (for audio/video only)
    transcription_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # 'pending', 'processing', 'completed', 'failed'
    transcription_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transcription_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcription_completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    interview: Mapped["SurrogateInterview"] = relationship(back_populates="interview_attachments")
    attachment: Mapped["Attachment"] = relationship()
    organization: Mapped["Organization"] = relationship()


# =============================================================================
# Journey Featured Images
# =============================================================================


class JourneyFeaturedImage(Base):
    """
    Featured image selection for journey milestones.

    Allows case managers to select from surrogate attachments
    as the featured image for each milestone in the journey timeline.
    """

    __tablename__ = "journey_featured_images"
    __table_args__ = (
        UniqueConstraint("surrogate_id", "milestone_slug", name="uq_journey_featured_image"),
        Index("ix_journey_featured_images_surrogate", "surrogate_id"),
        Index("ix_journey_featured_images_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogates.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    milestone_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Audit fields
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    attachment: Mapped["Attachment"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_user_id])
