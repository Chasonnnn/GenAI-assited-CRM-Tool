"""Audit logging service - security and compliance event tracking.

This service logs security-sensitive events for enterprise compliance.

Security guidelines:
- NEVER log secrets (API keys, tokens, passwords)
- Hash PII in details (use hash_email for emails)
- Use IDs instead of raw data where possible
- IP: Trust X-Forwarded-For only in production behind LB
"""

import hashlib
from uuid import UUID
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import AuditEventType
from app.db.models import AuditLog


def hash_email(email: str) -> str:
    """Hash email for audit log (prefix + SHA256 suffix for debugging)."""
    if not email:
        return ""
    prefix = email.split("@")[0][:3] if "@" in email else email[:3]
    suffix = hashlib.sha256(email.lower().encode()).hexdigest()[:12]
    return f"{prefix}...@[hash:{suffix}]"


def get_client_ip(request: Request | None) -> str | None:
    """
    Extract client IP from request.
    
    In production (behind load balancer), trusts X-Forwarded-For.
    In development, uses request.client.host directly.
    """
    if not request:
        return None
    
    # In production, trust X-Forwarded-For (set by load balancer)
    # Check settings or environment to determine if behind proxy
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2 - take first
        return forwarded.split(",")[0].strip()
    
    # Direct connection (development)
    if request.client:
        return request.client.host
    
    return None


def get_user_agent(request: Request | None) -> str | None:
    """Extract user agent from request."""
    if not request:
        return None
    ua = request.headers.get("user-agent", "")
    # Truncate to 500 chars (DB limit)
    return ua[:500] if ua else None


def log_event(
    db: Session,
    org_id: UUID,
    event_type: AuditEventType,
    actor_user_id: UUID | None = None,
    target_type: str | None = None,
    target_id: UUID | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """
    Log an audit event.
    
    Args:
        db: Database session
        org_id: Organization context
        event_type: Type of event (from AuditEventType)
        actor_user_id: User who performed the action (None for system)
        target_type: Type of entity affected (e.g., 'user', 'case', 'ai_action')
        target_id: ID of the affected entity
        details: Additional context (must be redacted - no secrets/raw PII)
        request: FastAPI request for IP/user-agent extraction
    
    Returns:
        The created audit log entry
    """
    entry = AuditLog(
        organization_id=org_id,
        actor_user_id=actor_user_id,
        event_type=event_type.value,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    db.add(entry)
    db.flush()  # Get ID, let caller control commit
    return entry


# =============================================================================
# Authentication Events
# =============================================================================

def log_login_success(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    request: Request | None = None,
    provider: str = "google",
) -> AuditLog:
    """Log successful login."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
        actor_user_id=user_id,
        target_type="user",
        target_id=user_id,
        details={"provider": provider},
        request=request,
    )


def log_login_failed(
    db: Session,
    org_id: UUID,
    email: str,
    reason: str,
    request: Request | None = None,
) -> AuditLog:
    """Log failed login attempt."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.AUTH_LOGIN_FAILED,
        actor_user_id=None,
        details={"email_hash": hash_email(email), "reason": reason},
        request=request,
    )


def log_logout(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    request: Request | None = None,
) -> AuditLog:
    """Log user logout."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.AUTH_LOGOUT,
        actor_user_id=user_id,
        target_type="user",
        target_id=user_id,
        request=request,
    )


# =============================================================================
# Settings Events
# =============================================================================

def log_settings_changed(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    setting_area: str,
    changes: dict[str, Any],
    request: Request | None = None,
) -> AuditLog:
    """Log organization or AI settings change."""
    event_type = (
        AuditEventType.SETTINGS_AI_UPDATED 
        if setting_area == "ai" 
        else AuditEventType.SETTINGS_ORG_UPDATED
    )
    return log_event(
        db=db,
        org_id=org_id,
        event_type=event_type,
        actor_user_id=user_id,
        target_type="organization",
        target_id=org_id,
        details={"area": setting_area, "changes": changes},
        request=request,
    )


def log_api_key_rotated(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    provider: str,
    request: Request | None = None,
) -> AuditLog:
    """Log AI API key rotation (key itself is NEVER logged)."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.SETTINGS_API_KEY_ROTATED,
        actor_user_id=user_id,
        target_type="ai_settings",
        details={"provider": provider, "key": "[REDACTED]"},
        request=request,
    )


def log_consent_accepted(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    request: Request | None = None,
) -> AuditLog:
    """Log AI consent acceptance."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.SETTINGS_AI_CONSENT_ACCEPTED,
        actor_user_id=user_id,
        target_type="ai_settings",
        request=request,
    )


# =============================================================================
# AI Action Events
# =============================================================================

def log_ai_action_approved(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    approval_id: UUID,
    action_type: str,
    request: Request | None = None,
) -> AuditLog:
    """Log AI action approval."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.AI_ACTION_APPROVED,
        actor_user_id=user_id,
        target_type="ai_action",
        target_id=approval_id,
        details={"action_type": action_type},
        request=request,
    )


def log_ai_action_rejected(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    approval_id: UUID,
    action_type: str,
    request: Request | None = None,
) -> AuditLog:
    """Log AI action rejection."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.AI_ACTION_REJECTED,
        actor_user_id=user_id,
        target_type="ai_action",
        target_id=approval_id,
        details={"action_type": action_type},
        request=request,
    )


# =============================================================================
# Integration Events
# =============================================================================

def log_integration_connected(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    integration_type: str,
    request: Request | None = None,
) -> AuditLog:
    """Log integration connection."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.INTEGRATION_CONNECTED,
        actor_user_id=user_id,
        target_type="integration",
        details={"integration_type": integration_type},
        request=request,
    )


def log_integration_disconnected(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    integration_type: str,
    request: Request | None = None,
) -> AuditLog:
    """Log integration disconnection."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.INTEGRATION_DISCONNECTED,
        actor_user_id=user_id,
        target_type="integration",
        details={"integration_type": integration_type},
        request=request,
    )


# =============================================================================
# Data Export/Import Events
# =============================================================================

def log_data_export(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    export_type: str,  # 'cases', 'analytics'
    record_count: int,
    request: Request | None = None,
) -> AuditLog:
    """Log data export."""
    event_type = (
        AuditEventType.DATA_EXPORT_CASES 
        if export_type == "cases" 
        else AuditEventType.DATA_EXPORT_ANALYTICS
    )
    return log_event(
        db=db,
        org_id=org_id,
        event_type=event_type,
        actor_user_id=user_id,
        details={"export_type": export_type, "record_count": record_count},
        request=request,
    )


def log_import_started(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    import_id: UUID,
    filename: str,
    row_count: int,
    request: Request | None = None,
) -> AuditLog:
    """Log import job started."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.DATA_IMPORT_STARTED,
        actor_user_id=user_id,
        target_type="import",
        target_id=import_id,
        details={"filename": filename, "row_count": row_count},
        request=request,
    )


def log_import_completed(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    import_id: UUID,
    imported: int,
    skipped: int,
    errors: int,
) -> AuditLog:
    """Log import job completion."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.DATA_IMPORT_COMPLETED,
        actor_user_id=user_id,
        target_type="import",
        target_id=import_id,
        details={"imported": imported, "skipped": skipped, "errors": errors},
    )


# =============================================================================
# User Management Events
# =============================================================================

def log_user_invited(
    db: Session,
    org_id: UUID,
    actor_user_id: UUID,
    invited_email: str,
    role: str,
    request: Request | None = None,
) -> AuditLog:
    """Log user invitation."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.USER_INVITED,
        actor_user_id=actor_user_id,
        details={"email_hash": hash_email(invited_email), "role": role},
        request=request,
    )


def log_user_role_changed(
    db: Session,
    org_id: UUID,
    actor_user_id: UUID,
    target_user_id: UUID,
    old_role: str,
    new_role: str,
    request: Request | None = None,
) -> AuditLog:
    """Log user role change."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.USER_ROLE_CHANGED,
        actor_user_id=actor_user_id,
        target_type="user",
        target_id=target_user_id,
        details={"old_role": old_role, "new_role": new_role},
        request=request,
    )
