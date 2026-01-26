"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
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

if TYPE_CHECKING:
    from app.db.models import Surrogate


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
