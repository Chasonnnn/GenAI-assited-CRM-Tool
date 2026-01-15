"""Service layer modules."""

from app.services.auth_service import (
    create_user_from_invite,
    find_user_by_identity,
    get_expired_invite,
    get_valid_invite,
    resolve_user_and_create_session,
)
from app.services.google_oauth import (
    GoogleUserInfo,
    exchange_code_for_tokens,
    validate_email_domain,
    verify_id_token,
)
from app.services.org_service import (
    create_org,
    get_org_by_id,
    get_org_by_slug,
)
from app.services.user_service import (
    disable_user,
    enable_user,
    get_user_by_email,
    get_user_by_id,
    revoke_all_sessions,
    update_user_profile,
)

# Import service modules (not individual functions) for cleaner access
from app.services import surrogate_service
from app.services import note_service
from app.services import task_service
from app.services import meta_lead_service

__all__ = [
    # Auth service
    "find_user_by_identity",
    "get_valid_invite",
    "get_expired_invite",
    "create_user_from_invite",
    "resolve_user_and_create_session",
    # Google OAuth
    "GoogleUserInfo",
    "exchange_code_for_tokens",
    "verify_id_token",
    "validate_email_domain",
    # User service
    "get_user_by_id",
    "get_user_by_email",
    "revoke_all_sessions",
    "disable_user",
    "enable_user",
    "update_user_profile",
    # Org service
    "get_org_by_id",
    "get_org_by_slug",
    "create_org",
    # Service modules
    "surrogate_service",
    "note_service",
    "task_service",
    "meta_lead_service",
]
