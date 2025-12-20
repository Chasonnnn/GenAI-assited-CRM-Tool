"""Permissions router - API endpoints for RBAC management.

Endpoints for:
- Listing org members with roles
- Managing member roles and permission overrides
- Viewing and editing role default permissions
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.permissions import (
    PERMISSION_REGISTRY,
    ROLE_DEFAULTS,
    get_all_permissions,
    get_permissions_by_category,
    get_role_default_permissions,
    is_developer_only,
)
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import permission_service


router = APIRouter(prefix="/settings/permissions", tags=["Permissions"])


# =============================================================================
# Schemas
# =============================================================================

class PermissionInfo(BaseModel):
    """Permission metadata for UI."""
    key: str
    label: str
    description: str
    category: str
    developer_only: bool


class MemberRead(BaseModel):
    """Org member with role and last login."""
    id: UUID  # membership_id
    user_id: UUID
    email: str
    display_name: str | None
    role: str
    last_login_at: str | None
    created_at: str


class MemberDetail(BaseModel):
    """Member detail with effective permissions and overrides."""
    id: UUID
    user_id: UUID
    email: str
    display_name: str | None
    role: str
    last_login_at: str | None
    created_at: str
    effective_permissions: list[str]
    overrides: list["OverrideRead"]


class OverrideRead(BaseModel):
    """User permission override."""
    permission: str
    override_type: str  # 'grant' or 'revoke'
    label: str
    category: str


class MemberUpdate(BaseModel):
    """Update member role or overrides."""
    role: str | None = None
    add_overrides: list["OverrideCreate"] | None = None
    remove_overrides: list[str] | None = None  # permission keys to remove


class OverrideCreate(BaseModel):
    """Create override."""
    permission: str
    override_type: str = Field(pattern="^(grant|revoke)$")


class RoleSummary(BaseModel):
    """Role with permission count."""
    role: str
    label: str
    permission_count: int
    is_developer: bool


class RoleDetail(BaseModel):
    """Role with all permissions grouped by category."""
    role: str
    label: str
    permissions_by_category: dict[str, list["RolePermissionRead"]]


class RolePermissionRead(BaseModel):
    """Permission in role context."""
    key: str
    label: str
    description: str
    is_granted: bool
    developer_only: bool


class RolePermissionUpdate(BaseModel):
    """Update role default permissions."""
    permissions: dict[str, bool]  # {permission_key: is_granted}


class EffectivePermissions(BaseModel):
    """Effective permissions for a user."""
    user_id: UUID
    role: str
    permissions: list[str]
    overrides: list[OverrideRead]


# =============================================================================
# Available Permissions
# =============================================================================

@router.get("/available", response_model=list[PermissionInfo])
def list_available_permissions(
    session: UserSession = Depends(require_permission("manage_team")),
):
    """
    List all available permissions with metadata.
    
    Requires: Manager+ role
    """
    return [
        PermissionInfo(
            key=p.key,
            label=p.label,
            description=p.description,
            category=p.category,
            developer_only=p.developer_only,
        )
        for p in get_all_permissions()
    ]


# =============================================================================
# Members
# =============================================================================

@router.get("/members", response_model=list[MemberRead])
def list_members(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_team")),
):
    """
    List all org members with roles.
    
    Requires: Manager+ role
    """
    from app.db.models import Membership, User
    
    members = db.query(Membership, User).join(
        User, Membership.user_id == User.id
    ).filter(
        Membership.organization_id == session.org_id
    ).order_by(User.display_name, User.email).all()
    
    return [
        MemberRead(
            id=m.id,
            user_id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=m.role,
            last_login_at=u.last_login_at.isoformat() if hasattr(u, 'last_login_at') and u.last_login_at else None,
            created_at=m.created_at.isoformat(),
        )
        for m, u in members
    ]


@router.get("/members/{member_id}", response_model=MemberDetail)
def get_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_team")),
):
    """
    Get member detail with effective permissions and overrides.
    
    Requires: Manager+ role
    """
    from app.db.models import Membership, User
    
    result = db.query(Membership, User).join(
        User, Membership.user_id == User.id
    ).filter(
        Membership.id == member_id,
        Membership.organization_id == session.org_id,
    ).first()
    
    if not result:
        raise HTTPException(404, "Member not found")
    
    membership, user = result
    
    # Get effective permissions
    effective = permission_service.get_effective_permissions(
        db, session.org_id, user.id, membership.role
    )
    
    # Get overrides
    overrides = permission_service.get_user_overrides(db, session.org_id, user.id)
    override_list = [
        OverrideRead(
            permission=o.permission,
            override_type=o.override_type,
            label=PERMISSION_REGISTRY[o.permission].label if o.permission in PERMISSION_REGISTRY else o.permission,
            category=PERMISSION_REGISTRY[o.permission].category if o.permission in PERMISSION_REGISTRY else "Unknown",
        )
        for o in overrides
    ]
    
    return MemberDetail(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        last_login_at=user.last_login_at.isoformat() if hasattr(user, 'last_login_at') and user.last_login_at else None,
        created_at=membership.created_at.isoformat(),
        effective_permissions=sorted(effective),
        overrides=override_list,
    )


@router.patch("/members/{member_id}", response_model=MemberDetail, dependencies=[Depends(require_csrf_header)])
def update_member(
    member_id: UUID,
    data: MemberUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_team")),
):
    """
    Update member role or permission overrides.
    
    Rules:
    - Cannot modify your own permissions
    - Cannot grant permissions you don't have
    - Developer-only permissions require Developer role
    
    Requires: Manager+ role
    """
    from app.db.models import Membership, User
    
    result = db.query(Membership, User).join(
        User, Membership.user_id == User.id
    ).filter(
        Membership.id == member_id,
        Membership.organization_id == session.org_id,
    ).first()
    
    if not result:
        raise HTTPException(404, "Member not found")
    
    membership, user = result
    
    # Protect developer accounts from non-developer edits
    if membership.role == Role.DEVELOPER.value and session.role != Role.DEVELOPER:
        raise HTTPException(403, "Only Developers can modify Developer accounts")

    # Self-modification check
    if user.id == session.user_id:
        raise HTTPException(403, "Cannot modify your own permissions")
    
    # Get actor's effective permissions for escalation check
    actor_permissions = permission_service.get_effective_permissions(
        db, session.org_id, session.user_id, session.role.value
    )
    
    # Update role
    if data.role:
        if not Role.has_value(data.role):
            raise HTTPException(400, f"Invalid role: {data.role}")
        
        # Cannot promote to Developer unless you are Developer
        if data.role == "developer" and session.role != Role.DEVELOPER:
            raise HTTPException(403, "Only Developers can promote to Developer role")
        
        membership.role = data.role
    
    # Add overrides
    if data.add_overrides:
        for override in data.add_overrides:
            # Escalation check
            if override.override_type == "grant":
                if not permission_service.can_grant_permission(
                    actor_permissions, override.permission, session.role.value
                ):
                    raise HTTPException(
                        403, 
                        f"Cannot grant permission '{override.permission}' - you don't have it"
                    )
            
            try:
                permission_service.set_user_override(
                    db, session.org_id, user.id, session.user_id,
                    override.permission, override.override_type
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    
    # Remove overrides
    if data.remove_overrides:
        for permission in data.remove_overrides:
            try:
                permission_service.set_user_override(
                    db, session.org_id, user.id, session.user_id,
                    permission, None  # None = delete
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    
    db.commit()
    
    # Return updated detail
    return get_member(member_id, db, session)


@router.delete("/members/{member_id}", dependencies=[Depends(require_csrf_header)])
def remove_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_team")),
):
    """
    Remove member from organization.
    
    Deletes membership and all permission overrides.
    Cannot remove yourself.
    
    Requires: Manager+ role
    """
    from app.db.models import Membership, User
    
    result = db.query(Membership, User).join(
        User, Membership.user_id == User.id
    ).filter(
        Membership.id == member_id,
        Membership.organization_id == session.org_id,
    ).first()
    
    if not result:
        raise HTTPException(404, "Member not found")
    
    membership, user = result
    
    # Protect developer accounts from non-developer removal
    if membership.role == Role.DEVELOPER.value and session.role != Role.DEVELOPER:
        raise HTTPException(403, "Only Developers can remove Developer accounts")

    if user.id == session.user_id:
        raise HTTPException(403, "Cannot remove yourself from the organization")
    
    # Delete overrides
    permission_service.delete_user_overrides(db, session.org_id, user.id)
    
    # Delete membership
    db.delete(membership)
    db.commit()
    
    return {"removed": True, "user_id": str(user.id)}


@router.get("/effective/{user_id}", response_model=EffectivePermissions)
def get_effective_permissions(
    user_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_team")),
):
    """
    Get effective permissions for a specific user.
    
    Shows combined result of role defaults + overrides.
    
    Requires: Manager+ role
    """
    from app.db.models import Membership, User
    
    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.organization_id == session.org_id,
    ).first()
    
    if not membership:
        raise HTTPException(404, "User not found in organization")
    
    effective = permission_service.get_effective_permissions(
        db, session.org_id, user_id, membership.role
    )
    
    overrides = permission_service.get_user_overrides(db, session.org_id, user_id)
    override_list = [
        OverrideRead(
            permission=o.permission,
            override_type=o.override_type,
            label=PERMISSION_REGISTRY[o.permission].label if o.permission in PERMISSION_REGISTRY else o.permission,
            category=PERMISSION_REGISTRY[o.permission].category if o.permission in PERMISSION_REGISTRY else "Unknown",
        )
        for o in overrides
    ]
    
    return EffectivePermissions(
        user_id=user_id,
        role=membership.role,
        permissions=sorted(effective),
        overrides=override_list,
    )


# =============================================================================
# Roles
# =============================================================================

ROLE_LABELS = {
    "intake_specialist": "Intake Specialist",
    "case_manager": "Case Manager",
    "manager": "Manager",
    "developer": "Developer",
}

@router.get("/roles", response_model=list[RoleSummary])
def list_roles(
    session: UserSession = Depends(require_permission("view_roles")),
):
    """
    List all roles with permission counts.
    
    Requires: Manager+ role
    """
    return [
        RoleSummary(
            role=role,
            label=ROLE_LABELS.get(role, role.title()),
            permission_count=len(perms),
            is_developer=role == "developer",
        )
        for role, perms in ROLE_DEFAULTS.items()
    ]


@router.get("/roles/{role}", response_model=RoleDetail)
def get_role_detail(
    role: str,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("view_roles")),
):
    """
    Get role detail with all permissions grouped by category.
    
    Shows which permissions are granted by default for this role.
    
    Requires: Manager+ role
    """
    if role not in ROLE_DEFAULTS:
        raise HTTPException(404, f"Unknown role: {role}")
    
    # Get org-specific overrides
    from app.db.models import RolePermission
    
    org_overrides = {
        rp.permission: rp.is_granted
        for rp in db.query(RolePermission).filter(
            RolePermission.organization_id == session.org_id,
            RolePermission.role == role,
        ).all()
    }
    
    # Get global defaults
    global_defaults = get_role_default_permissions(role)
    
    # Build permissions by category
    perms_by_cat: dict[str, list[RolePermissionRead]] = {}
    
    for perm in get_all_permissions():
        # Effective value: org override > global default
        if perm.key in org_overrides:
            is_granted = org_overrides[perm.key]
        else:
            is_granted = perm.key in global_defaults
        
        if perm.category not in perms_by_cat:
            perms_by_cat[perm.category] = []
        
        perms_by_cat[perm.category].append(RolePermissionRead(
            key=perm.key,
            label=perm.label,
            description=perm.description,
            is_granted=is_granted,
            developer_only=perm.developer_only,
        ))
    
    return RoleDetail(
        role=role,
        label=ROLE_LABELS.get(role, role.title()),
        permissions_by_category=perms_by_cat,
    )


@router.patch("/roles/{role}", response_model=RoleDetail, dependencies=[Depends(require_csrf_header)])
def update_role_permissions(
    role: str,
    data: RolePermissionUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_roles")),  # Developer only enforced by permission
):
    """
    Update role default permissions.
    
    Creates org-specific overrides of the global defaults.
    Developer role cannot be modified.
    
    Requires: Developer role
    """
    if role not in ROLE_DEFAULTS:
        raise HTTPException(404, f"Unknown role: {role}")
    
    if role == "developer":
        raise HTTPException(400, "Developer role permissions cannot be modified")
    
    for permission, is_granted in data.permissions.items():
        try:
            permission_service.set_role_default(
                db, session.org_id, role, permission, is_granted, session.user_id
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    db.commit()
    
    return get_role_detail(role, db, session)


# Forward references
MemberDetail.model_rebuild()
