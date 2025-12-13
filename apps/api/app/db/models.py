"""SQLAlchemy ORM models for authentication and tenant management."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    """
    A tenant/company in the multi-tenant system.
    
    All domain entities (leads, cases, etc.) belong to an organization
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
    This simplifies tenant scoping and UI logic significantly.
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
    
    Supports multiple providers per user (Google now, Microsoft later).
    The provider_subject is the 'sub' claim from OIDC tokens.
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
    
    Constraint: One pending invite per email GLOBALLY (not per-org).
    This aligns with the "one org per user" model.
    
    Future: If contractors need multiple orgs, relax to UNIQUE(org_id, email)
    and add an org-picker flow.
    """
    __tablename__ = "org_invites"
    __table_args__ = (
        # Partial unique: only one PENDING invite per email globally
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
        nullable=True  # NULL for CLI bootstrap
    )
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)  # NULL = never
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)  # NULL = pending
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), 
        nullable=False
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="invites")