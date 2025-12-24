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
    
    Only trusts X-Forwarded-For when TRUST_PROXY_HEADERS=True (behind reverse proxy).
    In development/direct connections, uses request.client.host.
    """
    if not request:
        return None
    
    # Only trust X-Forwarded-For when explicitly configured (behind nginx/Cloudflare)
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # X-Forwarded-For: client, proxy1, proxy2 - take first
            return forwarded.split(",")[0].strip()
    
    # Direct connection or TRUST_PROXY_HEADERS=False
    if request.client:
        return request.client.host
    
    return None


def canonical_json(obj: dict | None) -> str:
    """
    Serialize object to canonical JSON for consistent hashing.
    
    Uses sorted keys, compact separators, and str() for non-JSON types.
    This MUST be used consistently everywhere hashes are computed.
    """
    import json as json_module
    return json_module.dumps(obj or {}, sort_keys=True, separators=(",", ":"), default=str)



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
    request_id: UUID | None = None,
    before_version_id: UUID | None = None,
    after_version_id: UUID | None = None,
) -> AuditLog:
    """
    Log an audit event with hash chain.
    
    Args:
        db: Database session
        org_id: Organization context
        event_type: Type of event (from AuditEventType)
        actor_user_id: User who performed the action (None for system)
        target_type: Type of entity affected (e.g., 'user', 'case', 'ai_action')
        target_id: ID of the affected entity
        details: Additional context (must be redacted - no secrets/raw PII)
        request: FastAPI request for IP/user-agent extraction
        request_id: Optional request ID for correlating related events
        before_version_id: EntityVersion ID before change (for config changes)
        after_version_id: EntityVersion ID after change (for config changes)
    
    Returns:
        The created audit log entry with computed hash chain
    """
    from app.services import version_service
    import json as json_module
    
    # Get previous hash for chain
    prev_hash = version_service.get_last_audit_hash(db, org_id)
    
    entry = AuditLog(
        organization_id=org_id,
        actor_user_id=actor_user_id,
        event_type=event_type.value,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        request_id=request_id,
        prev_hash=prev_hash,
        before_version_id=before_version_id,
        after_version_id=after_version_id,
    )
    db.add(entry)
    db.flush()  # Get ID and created_at
    
    # Compute entry hash using canonical JSON and ALL immutable fields
    details_json = canonical_json(details)
    entry_hash = version_service.compute_audit_hash(
        prev_hash=prev_hash,
        entry_id=str(entry.id),
        org_id=str(org_id),
        event_type=event_type.value,
        created_at=str(entry.created_at),
        details_json=details_json,
        actor_user_id=str(actor_user_id) if actor_user_id else "",
        target_type=target_type or "",
        target_id=str(target_id) if target_id else "",
        ip_address=entry.ip_address or "",
        user_agent=entry.user_agent or "",
        request_id=str(request_id) if request_id else "",
        before_version_id=str(before_version_id) if before_version_id else "",
        after_version_id=str(after_version_id) if after_version_id else "",
    )
    entry.entry_hash = entry_hash
    
    return entry


def log_config_changed(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    before_version_id: UUID | None,
    after_version_id: UUID,
    action: str = "updated",  # "created", "updated", "rolled_back"
    request: Request | None = None,
) -> AuditLog:
    """
    Log versioned config change with before/after version links.
    
    Used for: pipelines, email templates, AI settings, integrations
    """
    event_map = {
        "pipeline": AuditEventType.CONFIG_PIPELINE_UPDATED,
        "email_template": AuditEventType.CONFIG_TEMPLATE_UPDATED,
        "ai_settings": AuditEventType.SETTINGS_AI_UPDATED,
        "org_settings": AuditEventType.SETTINGS_ORG_UPDATED,
        "integration": AuditEventType.INTEGRATION_CONNECTED,
    }
    event_type = event_map.get(entity_type, AuditEventType.SETTINGS_ORG_UPDATED)
    
    return log_event(
        db=db,
        org_id=org_id,
        event_type=event_type,
        actor_user_id=user_id,
        target_type=entity_type,
        target_id=entity_id,
        details={"action": action},
        request=request,
        before_version_id=before_version_id,
        after_version_id=after_version_id,
    )


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


def log_ai_action_failed(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    approval_id: UUID,
    action_type: str,
    error: str | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Log AI action failure during execution."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.AI_ACTION_FAILED,
        actor_user_id=user_id,
        target_type="ai_action",
        target_id=approval_id,
        details={"action_type": action_type, "error": error},
        request=request,
    )


def log_ai_action_denied(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    approval_id: UUID,
    action_type: str,
    reason: str | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Log AI action denial (permission/authorization)."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.AI_ACTION_DENIED,
        actor_user_id=user_id,
        target_type="ai_action",
        target_id=approval_id,
        details={"action_type": action_type, "reason": reason},
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


def log_compliance_export_requested(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    export_job_id: UUID,
    export_type: str,
    record_count: int,
    redact_mode: str,
    file_format: str,
    request: Request | None = None,
) -> AuditLog:
    """Log compliance export request."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.COMPLIANCE_EXPORT_REQUESTED,
        actor_user_id=user_id,
        target_type="export_job",
        target_id=export_job_id,
        details={
            "export_type": export_type,
            "record_count": record_count,
            "redact_mode": redact_mode,
            "format": file_format,
        },
        request=request,
    )


def log_compliance_export_downloaded(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    export_job_id: UUID,
    request: Request | None = None,
) -> AuditLog:
    """Log compliance export download."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.COMPLIANCE_EXPORT_DOWNLOADED,
        actor_user_id=user_id,
        target_type="export_job",
        target_id=export_job_id,
        request=request,
    )


def log_compliance_legal_hold_created(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    hold_id: UUID,
    entity_type: str | None,
    entity_id: UUID | None,
    reason: str,
    request: Request | None = None,
) -> AuditLog:
    """Log legal hold creation."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.COMPLIANCE_LEGAL_HOLD_CREATED,
        actor_user_id=user_id,
        target_type="legal_hold",
        target_id=hold_id,
        details={"entity_type": entity_type, "entity_id": str(entity_id) if entity_id else None, "reason": reason},
        request=request,
    )


def log_compliance_legal_hold_released(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    hold_id: UUID,
    entity_type: str | None,
    entity_id: UUID | None,
    request: Request | None = None,
) -> AuditLog:
    """Log legal hold release."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.COMPLIANCE_LEGAL_HOLD_RELEASED,
        actor_user_id=user_id,
        target_type="legal_hold",
        target_id=hold_id,
        details={"entity_type": entity_type, "entity_id": str(entity_id) if entity_id else None},
        request=request,
    )


def log_compliance_retention_updated(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    policy_id: UUID,
    entity_type: str,
    retention_days: int,
    is_active: bool,
    request: Request | None = None,
) -> AuditLog:
    """Log retention policy changes."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.COMPLIANCE_RETENTION_UPDATED,
        actor_user_id=user_id,
        target_type="retention_policy",
        target_id=policy_id,
        details={
            "entity_type": entity_type,
            "retention_days": retention_days,
            "is_active": is_active,
        },
        request=request,
    )


def log_compliance_purge_previewed(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    results: list[dict[str, int]],
    request: Request | None = None,
) -> AuditLog:
    """Log purge preview."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.COMPLIANCE_PURGE_PREVIEWED,
        actor_user_id=user_id,
        details={"results": results},
        request=request,
    )


def log_compliance_purge_executed(
    db: Session,
    org_id: UUID,
    user_id: UUID | None,
    results: list[object],
    request: Request | None = None,
) -> AuditLog:
    """Log purge execution."""
    formatted = [
        {"entity_type": result.entity_type, "count": result.count}
        for result in results
    ]
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.COMPLIANCE_PURGE_EXECUTED,
        actor_user_id=user_id,
        details={"results": formatted},
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


# =============================================================================
# AI Workflow Events
# =============================================================================

def log_ai_workflow_created(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    workflow_id: UUID,
    workflow_name: str,
    request: Request | None = None,
) -> AuditLog:
    """Log AI-generated workflow creation."""
    return log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.AI_ACTION_APPROVED,  # Reuse existing event type
        actor_user_id=user_id,
        target_type="workflow",
        target_id=workflow_id,
        details={"action": "ai_workflow_created", "workflow_name": workflow_name},
        request=request,
    )

