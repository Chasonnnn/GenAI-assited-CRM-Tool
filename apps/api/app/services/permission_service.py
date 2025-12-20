"""Permission service for RBAC with precedence, caching, and seeding.

Resolution order: revoke > grant > role_default
Developer role: always has all permissions (immutable, no DB lookup)
Missing permission: defaults to False (deny)
"""

import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.permissions import (
    PERMISSION_REGISTRY,
    ROLE_DEFAULTS,
    get_role_default_permissions,
    is_developer_only,
    is_valid_permission,
)
from app.db.enums import AuditEventType
from app.services import audit_service

if TYPE_CHECKING:
    from app.db.models import RolePermission, UserPermissionOverride


# =============================================================================
# Permission Resolution
# =============================================================================

def get_effective_permissions(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> set[str]:
    """
    Get effective permissions for a user.
    
    Resolution: role_defaults + grants - revokes
    Developer role always gets all permissions.
    Developer-only permissions are filtered out for non-developers.
    """
    # Developer always has everything
    if role == "developer":
        return set(PERMISSION_REGISTRY.keys())
    
    # Start with role defaults
    effective = get_role_default_permissions(role).copy()
    
    # Apply org-level role overrides (if any exist)
    from app.db.models import RolePermission
    role_perms = db.query(RolePermission).filter(
        RolePermission.organization_id == org_id,
        RolePermission.role == role,
    ).all()
    
    for rp in role_perms:
        if rp.is_granted:
            effective.add(rp.permission)
        else:
            effective.discard(rp.permission)
    
    # Apply user-level overrides
    from app.db.models import UserPermissionOverride
    user_overrides = db.query(UserPermissionOverride).filter(
        UserPermissionOverride.organization_id == org_id,
        UserPermissionOverride.user_id == user_id,
    ).all()
    
    for override in user_overrides:
        if override.override_type == "grant":
            effective.add(override.permission)
        elif override.override_type == "revoke":
            effective.discard(override.permission)
    
    # Enforcement: Developer-only permissions cannot be granted to non-developers
    # This is the final filter to ensure security even if override was created
    effective = {
        p for p in effective 
        if not is_developer_only(p)
    }
    
    return effective


def check_permission(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    permission: str,
) -> bool:
    """Check if user has a specific permission."""
    # Developer always has everything
    if role == "developer":
        return True
    
    effective = get_effective_permissions(db, org_id, user_id, role)
    return permission in effective


# =============================================================================
# Permission Modification
# =============================================================================

def can_grant_permission(actor_permissions: set[str], target_permission: str, actor_role: str) -> bool:
    """
    Check if actor can grant a permission.
    
    Rules:
    1. Developer-only permissions can only be granted by Developer role
    2. Actor must have the permission themselves to grant it
    """
    if is_developer_only(target_permission):
        return actor_role == "developer"
    
    return target_permission in actor_permissions


def set_user_override(
    db: Session,
    org_id: uuid.UUID,
    target_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    permission: str,
    override_type: str | None,  # 'grant', 'revoke', or None to remove
) -> bool:
    """
    Set or remove a user permission override.
    
    Args:
        override_type: 'grant' to add, 'revoke' to remove, None to delete override
    
    Returns True if successful.
    """
    if not is_valid_permission(permission):
        raise ValueError(f"Invalid permission: {permission}")
    
    # Block granting developer_only permissions to non-developers
    # These permissions should ONLY ever be held by Developer role
    if override_type == "grant" and is_developer_only(permission):
        from app.db.models import Membership
        target_membership = db.query(Membership).filter(
            Membership.organization_id == org_id,
            Membership.user_id == target_user_id,
        ).first()
        if target_membership and target_membership.role != "developer":
            raise ValueError(
                f"Permission '{permission}' is developer-only and cannot be granted to non-developers"
            )
    
    # Self-modification prevention
    if target_user_id == actor_user_id:
        raise ValueError("Cannot modify your own permissions")
    
    from app.db.models import UserPermissionOverride
    
    existing = db.query(UserPermissionOverride).filter(
        UserPermissionOverride.organization_id == org_id,
        UserPermissionOverride.user_id == target_user_id,
        UserPermissionOverride.permission == permission,
    ).first()
    
    before_value = existing.override_type if existing else None
    
    if override_type is None:
        # Remove override
        if existing:
            db.delete(existing)
    else:
        if existing:
            existing.override_type = override_type
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(UserPermissionOverride(
                organization_id=org_id,
                user_id=target_user_id,
                permission=permission,
                override_type=override_type,
            ))
    
    # Audit log
    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.SETTINGS_ORG_UPDATED,
        actor_user_id=actor_user_id,
        target_type="user_permission_override",
        target_id=target_user_id,
        details={
            "permission": permission,
            "before": before_value,
            "after": override_type,
        },
    )
    
    return True


def set_role_default(
    db: Session,
    org_id: uuid.UUID,
    role: str,
    permission: str,
    is_granted: bool,
    actor_user_id: uuid.UUID,
) -> bool:
    """
    Set role default permission for an org.
    
    Creates org-specific override of the global defaults.
    """
    if not is_valid_permission(permission):
        raise ValueError(f"Invalid permission: {permission}")
    
    from app.db.models import RolePermission
    
    existing = db.query(RolePermission).filter(
        RolePermission.organization_id == org_id,
        RolePermission.role == role,
        RolePermission.permission == permission,
    ).first()
    
    before_value = existing.is_granted if existing else None
    
    if existing:
        existing.is_granted = is_granted
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(RolePermission(
            organization_id=org_id,
            role=role,
            permission=permission,
            is_granted=is_granted,
        ))
    
    # Audit log
    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.SETTINGS_ORG_UPDATED,
        actor_user_id=actor_user_id,
        target_type="role_permission",
        target_id=None,
        details={
            "role": role,
            "permission": permission,
            "before": before_value,
            "after": is_granted,
        },
    )
    
    return True


# =============================================================================
# Seeding & Backfill
# =============================================================================

def seed_role_defaults(db: Session, org_id: uuid.UUID) -> int:
    """
    Seed role_permissions table with defaults for a new org.
    
    Only creates rows for permissions explicitly in ROLE_DEFAULTS (granted).
    Missing permissions default to False at runtime.
    
    Returns count of rows created.
    """
    from app.db.models import RolePermission
    
    count = 0
    for role, permissions in ROLE_DEFAULTS.items():
        if role == "developer":
            continue  # Developer is immutable, no DB rows needed
        
        for permission in permissions:
            existing = db.query(RolePermission).filter(
                RolePermission.organization_id == org_id,
                RolePermission.role == role,
                RolePermission.permission == permission,
            ).first()
            
            if not existing:
                db.add(RolePermission(
                    organization_id=org_id,
                    role=role,
                    permission=permission,
                    is_granted=True,
                ))
                count += 1
    
    return count


def backfill_new_permissions(db: Session) -> int:
    """
    Backfill new permissions to all orgs.
    
    For each org, ensures role_permissions rows exist for all 
    permissions in ROLE_DEFAULTS. Run on deploy or as nightly job.
    
    Returns total rows created.
    """
    from app.db.models import Organization
    
    orgs = db.query(Organization).all()
    total = 0
    
    for org in orgs:
        total += seed_role_defaults(db, org.id)
    
    db.commit()
    return total


# =============================================================================
# Member Management
# =============================================================================

def get_user_overrides(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list["UserPermissionOverride"]:
    """Get all permission overrides for a user."""
    from app.db.models import UserPermissionOverride
    
    return db.query(UserPermissionOverride).filter(
        UserPermissionOverride.organization_id == org_id,
        UserPermissionOverride.user_id == user_id,
    ).all()


def delete_user_overrides(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    """Delete all permission overrides for a user (on removal from org)."""
    from app.db.models import UserPermissionOverride
    
    count = db.query(UserPermissionOverride).filter(
        UserPermissionOverride.organization_id == org_id,
        UserPermissionOverride.user_id == user_id,
    ).delete()
    
    return count
