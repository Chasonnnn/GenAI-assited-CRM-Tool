"""Authentication-related Pydantic schemas."""

from uuid import UUID

from pydantic import BaseModel

from app.db.enums import Role


class TokenPayload(BaseModel):
    """Decoded JWT payload structure."""

    sub: UUID  # user_id
    org_id: UUID
    role: str
    token_version: int
    mfa_verified: bool = False  # True after MFA challenge completed
    mfa_required: bool = True  # MFA required for this user


class UserSession(BaseModel):
    """
    Full session context for authenticated requests.

    This is returned by get_current_session dependency
    and contains all information needed for authorization.
    """

    user_id: UUID
    org_id: UUID
    role: Role  # Validated enum
    email: str
    display_name: str
    mfa_verified: bool = False
    mfa_required: bool = True
    token_hash: str | None = None  # For deriving is_current in session list


class MeResponse(BaseModel):
    """Response schema for GET /auth/me endpoint."""

    user_id: UUID
    email: str
    display_name: str
    avatar_url: str | None
    phone: str | None = None
    title: str | None = None
    org_id: UUID
    org_name: str
    org_slug: str
    org_timezone: str
    org_portal_domain: str | None = None
    role: Role
    ai_enabled: bool = False
    mfa_enabled: bool = False
    mfa_required: bool = True
    mfa_verified: bool = False


class SessionResponse(BaseModel):
    """Response schema for session listing."""

    id: str
    device_info: str | None
    ip_address: str | None
    created_at: str
    last_active_at: str
    expires_at: str
    is_current: bool
