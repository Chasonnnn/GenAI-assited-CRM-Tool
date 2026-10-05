"""Reviewed activation and configuration of the organization permission policy.

Callers commit configuration writes and their audit records together. Organization
row locking serializes policy activation with role and individual-permission writes.
Activation with paused workflow cancellations commits them with form routing before
returning, after all configuration writes and their audit have been staged.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permission_resolution import MATCH_ACTION_PERMISSIONS, resolve_effective_permissions
from app.core.permissions import (
    ADMIN_ONLY_PERMISSIONS,
    PERMISSION_REGISTRY,
    PROTECTED_ROLES,
    V2_DEFAULT_PERMISSIONS,
    V2_ROLE_DEFAULTS,
    is_developer_only,
)
from app.db.enums import AuditEventType
from app.db.models.auth import (
    Membership,
    Organization,
    RolePermission,
    User,
    UserPermissionOverride,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.schemas.permission_policy import (
    LegacyRevoke,
    PermissionMemberDifference,
    PermissionPolicyChanges,
    PermissionPolicyConfiguration,
    PermissionPolicyPreview,
)
from app.services import audit_service


class PermissionPolicyConflict(ValueError):
    """The reviewed policy is incomplete or changed before activation."""


def require_administrator(db: Session, org_id: UUID, actor_user_id: UUID) -> None:
    actor = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == org_id,
            Membership.user_id == actor_user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
            Membership.role.in_(PROTECTED_ROLES),
        )
        .populate_existing()
        .one_or_none()
    )
    if actor is None:
        raise ValueError("Only an active organization Admin or Developer can configure permissions")


def get_version(db: Session, org_id: UUID) -> int:
    value = (
        db.query(OrganizationPermissionPolicy.version)
        .filter(OrganizationPermissionPolicy.organization_id == org_id)
        .scalar()
    )
    return value if value is not None else 1


def is_enabled(db: Session, org_id: UUID) -> bool:
    return get_version(db, org_id) >= 2


def lock_configuration(db: Session, org_id: UUID) -> None:
    # NO KEY UPDATE serializes configuration without blocking audit inserts' FK checks.
    organization = (
        db.query(Organization.id)
        .filter(Organization.id == org_id)
        .with_for_update(key_share=True)
        .one_or_none()
    )
    if organization is None:
        raise ValueError("Organization not found")


def touch_configuration(db: Session, org_id: UUID) -> None:
    policy = db.get(OrganizationPermissionPolicy, org_id)
    if policy is not None:
        policy.configuration_revision += 1
        policy.updated_at = datetime.now(UTC)


def administration_capabilities(role: str, permissions: set[str], version: int) -> dict[str, bool]:
    administrator = role in PROTECTED_ROLES
    return {
        "can_manage_roles": administrator if version >= 2 else role == "developer",
        "can_manage_members": administrator if version >= 2 else "manage_team" in permissions,
        "can_add_permissions": administrator if version >= 2 else "manage_team" in permissions,
        "can_activate_policy": administrator,
    }


def get_included_features(
    db: Session, org_id: UUID, *, policy_version: int | None = None
) -> dict[str, bool]:
    version = get_version(db, org_id) if policy_version is None else policy_version
    enabled = version >= 2
    ai_enabled = db.query(Organization.ai_enabled).filter(Organization.id == org_id).scalar()
    return {"personal_workspace": enabled, "ai_assistant": enabled and bool(ai_enabled)}


def get_configuration(db: Session, org_id: UUID) -> PermissionPolicyConfiguration:
    policy = db.get(OrganizationPermissionPolicy, org_id)
    version = policy.version if policy else 1
    from app.core.permissions import ROLE_DEFAULTS

    defaults = V2_ROLE_DEFAULTS if version >= 2 else ROLE_DEFAULTS
    rows = db.query(RolePermission).filter(RolePermission.organization_id == org_id).all()
    ai_enabled = get_included_features(db, org_id, policy_version=version)["ai_assistant"]
    role_permissions = {}
    for role in defaults:
        resolved = resolve_effective_permissions(
            role,
            role_overrides=((row.permission, row.is_granted) for row in rows if row.role == role),
            policy_version=version,
            ai_enabled=ai_enabled,
        )
        role_permissions[role] = {key: key in resolved for key in sorted(PERMISSION_REGISTRY)}
    return PermissionPolicyConfiguration(
        version=version,
        configuration_revision=policy.configuration_revision if policy else 1,
        status="active" if version >= 2 else "legacy",
        role_permissions=role_permissions,
        protected_roles=sorted(PROTECTED_ROLES) if version >= 2 else ["developer"],
    )


def _validate_changes(changes: PermissionPolicyChanges) -> None:
    for role, permissions in changes.role_permissions.items():
        if role not in V2_ROLE_DEFAULTS:
            raise ValueError(f"Unknown role: {role}")
        if role in PROTECTED_ROLES:
            raise ValueError(f"The {role} role baseline is protected")
        for permission, granted in permissions.items():
            if permission not in PERMISSION_REGISTRY:
                raise ValueError(f"Invalid permission: {permission}")
            if permission in V2_DEFAULT_PERMISSIONS:
                raise ValueError("Included features cannot be configured in role baselines")
            if granted and is_developer_only(permission, policy_version=2):
                raise ValueError(f"Permission '{permission}' is developer-only")
            if granted and permission in ADMIN_ONLY_PERMISSIONS:
                raise ValueError(f"Permission '{permission}' is reserved for Admin and Developer")
    ids = [resolution.override_id for resolution in changes.revoke_resolutions]
    if len(set(ids)) != len(ids):
        raise ValueError("Each legacy revoke must have exactly one resolution")
    execution_ids = [(item.item_type, item.id) for item in changes.execution_resolutions]
    if len(set(execution_ids)) != len(execution_ids):
        raise ValueError("Each legacy execution item must have exactly one resolution")


def _match_actions(permissions: set[str], *, legacy: bool) -> set[str]:
    if "view_matches" not in permissions:
        return set()
    actions = {"propose"} if not legacy or "propose_matches" in permissions else set()
    if "decide_matches" in permissions:
        actions.update({"accept", "decline"})
    if "close_matches" in permissions:
        actions.update({"request_cancel", "withdraw_cancel"})
    return actions


def _mapped_match_grants(user_overrides: list[tuple[str, str]]) -> list[tuple[str, str]]:
    if ("propose_matches", "grant") in user_overrides:
        return [*user_overrides, *((key, "grant") for key in sorted(MATCH_ACTION_PERMISSIONS))]
    return user_overrides


def preview(db: Session, org_id: UUID, changes: PermissionPolicyChanges) -> PermissionPolicyPreview:
    _validate_changes(changes)
    policy = db.get(OrganizationPermissionPolicy, org_id)
    version = policy.version if policy else 1
    revision = policy.configuration_revision if policy else 1
    from app.services import approval_handoff_service

    pool_transfers = (
        approval_handoff_service.build_surrogate_pool_transfer_plan(db, org_id)
        if version < 2
        else []
    )
    member_rows = (
        db.query(Membership, User.is_active)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.organization_id == org_id)
        .order_by(Membership.id)
        .all()
    )
    members = [member for member, _ in member_rows]
    active_users = {member.user_id for member, is_active in member_rows if is_active}
    role_rows = (
        db.query(RolePermission)
        .filter(RolePermission.organization_id == org_id)
        .order_by(RolePermission.id)
        .all()
    )
    user_rows = (
        db.query(UserPermissionOverride)
        .filter(UserPermissionOverride.organization_id == org_id)
        .order_by(UserPermissionOverride.id)
        .all()
    )
    proposed_roles: dict[str, dict[str, bool]] = {}
    for row in role_rows:
        if row.permission in V2_DEFAULT_PERMISSIONS:
            continue
        proposed_roles.setdefault(row.role, {})[row.permission] = row.is_granted
    if version < 2:
        for role in V2_ROLE_DEFAULTS:
            if role in PROTECTED_ROLES:
                continue
            legacy = resolve_effective_permissions(
                role, role_overrides=proposed_roles.get(role, {}).items()
            )
            proposed_roles.setdefault(role, {}).update(
                {key: "propose_matches" in legacy for key in MATCH_ACTION_PERMISSIONS}
            )
    for role, permissions in changes.role_permissions.items():
        proposed_roles.setdefault(role, {}).update(permissions)

    ai_enabled = bool(db.query(Organization.ai_enabled).filter(Organization.id == org_id).scalar())
    proposed_action_sets = {
        role: resolve_effective_permissions(
            role, role_overrides=values.items(), policy_version=2, ai_enabled=ai_enabled
        )
        for role, values in {**{role: {} for role in V2_ROLE_DEFAULTS}, **proposed_roles}.items()
    }
    members_by_user = {member.user_id: member for member in members}
    resolutions = {item.override_id: item.action for item in changes.revoke_resolutions}
    revokes = [row for row in user_rows if row.override_type == "revoke"]
    if resolutions.keys() - {row.id for row in revokes}:
        raise ValueError("Revoke resolution does not belong to this organization's legacy revokes")
    revoke_details = []
    for row in revokes:
        member = members_by_user.get(row.user_id)
        role = member.role if member else None
        action = resolutions.get(row.id)
        if action == "deny_for_role":
            if row.permission in V2_DEFAULT_PERMISSIONS:
                raise ValueError("Included feature revokes must be explicitly removed")
            if role is None or role in PROTECTED_ROLES:
                raise ValueError("Cannot move this revoke to a protected or missing role")
            if row.permission not in PERMISSION_REGISTRY:
                raise ValueError("An unknown permission revoke must be explicitly removed")
            if row.permission not in proposed_action_sets.get(role, set()):
                raise ValueError(
                    "Role already denies this permission; explicitly remove the legacy revoke"
                )
            proposed_roles.setdefault(role, {})[row.permission] = False
            if version < 2 and row.permission == "propose_matches":
                proposed_roles[role].update({key: False for key in MATCH_ACTION_PERMISSIONS})
        revoke_details.append(
            LegacyRevoke(
                can_deny_for_role=(
                    role is not None
                    and role not in PROTECTED_ROLES
                    and row.permission not in V2_DEFAULT_PERMISSIONS
                    and row.permission in PERMISSION_REGISTRY
                    and row.permission in proposed_action_sets.get(role, set())
                ),
                override_id=row.id,
                user_id=row.user_id,
                role=role,
                permission=row.permission,
                resolution=action,
            )
        )

    differences = []
    for member in members:
        if not member.is_active or member.user_id not in active_users:
            continue
        user_overrides = [
            (row.permission, row.override_type)
            for row in user_rows
            if row.user_id == member.user_id
        ]
        current = resolve_effective_permissions(
            member.role,
            role_overrides=(
                (row.permission, row.is_granted) for row in role_rows if row.role == member.role
            ),
            user_overrides=user_overrides,
            policy_version=version,
            ai_enabled=ai_enabled,
        )
        proposed = resolve_effective_permissions(
            member.role,
            role_overrides=proposed_roles.get(member.role, {}).items(),
            user_overrides=_mapped_match_grants(user_overrides) if version < 2 else user_overrides,
            policy_version=2,
            ai_enabled=ai_enabled,
        )
        # This explicitly labeled historical comparison shows the new proposing
        # action without pretending its legacy permission (also used for editing) was granted.
        previous_actions = _match_actions(current, legacy=version < 2)
        proposed_actions = _match_actions(proposed, legacy=False)
        differences.append(
            PermissionMemberDifference(
                membership_id=member.id,
                user_id=member.user_id,
                role=member.role,
                current=sorted(current),
                proposed=sorted(proposed),
                gained=sorted(proposed - current),
                lost=sorted(current - proposed),
                previous_match_actions=sorted(previous_actions),
                proposed_match_actions=sorted(proposed_actions),
                gained_match_actions=sorted(proposed_actions - previous_actions),
                lost_match_actions=sorted(previous_actions - proposed_actions),
            )
        )

    scope_review = get_scope_review(db, org_id)
    execution_review = get_execution_review(db, org_id)
    execution_ids = {f"{item['item_type']}:{item['id']}" for item in execution_review}
    resolved_executions = {f"{item.item_type}:{item.id}" for item in changes.execution_resolutions}
    if resolved_executions - execution_ids:
        raise ValueError(
            "Execution resolution does not belong to this organization's unreviewed work"
        )
    unresolved_executions = sorted(execution_ids - resolved_executions)
    snapshot = {
        "org_id": str(org_id),
        "version": version,
        "revision": revision,
        "ai_enabled": ai_enabled,
        "defaults": {role: sorted(values) for role, values in V2_ROLE_DEFAULTS.items()},
        "members": [
            (str(m.id), str(m.user_id), m.role, m.is_active, m.user_id in active_users)
            for m in members
        ],
        "roles": [(str(r.id), r.role, r.permission, r.is_granted) for r in role_rows],
        "overrides": [
            (str(r.id), str(r.user_id), r.permission, r.override_type) for r in user_rows
        ],
        "changes": changes.model_dump(mode="json"),
        "scope_review": scope_review,
        "execution_review": execution_review,
        "surrogate_pool_transfers": pool_transfers,
    }
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()
    unresolved = [row.id for row in revokes if row.id not in resolutions]
    return PermissionPolicyPreview(
        digest=digest,
        current_version=version,
        configuration_revision=revision,
        ready=not unresolved
        and not unresolved_executions
        and bool(scope_review.get("ready", True)),
        match_action_baseline="pre_step_7" if version < 2 else "current",
        members=differences,
        revokes=revoke_details,
        unresolved_revoke_ids=unresolved,
        role_permissions=proposed_roles,
        scope_review=scope_review,
        execution_review=execution_review,
        unresolved_execution_ids=unresolved_executions,
        surrogate_pool_transfers=pool_transfers,
    )


def get_scope_review(db: Session, org_id: UUID) -> dict:
    """Record-scope migration review is supplied by the shared access module."""
    from app.services import record_scope_service

    return record_scope_service.get_policy_scope_snapshot(db, org_id)


def get_execution_review(db: Session, org_id: UUID) -> list[dict]:
    from app.services import campaign_access, workflow_execution_authority

    return [
        *workflow_execution_authority.get_policy_execution_snapshot(db, org_id),
        *campaign_access.get_policy_execution_snapshot(db, org_id),
    ]


def _apply_role_changes(db: Session, org_id: UUID, changes: dict[str, dict[str, bool]]) -> None:
    mutable_roles = [role for role in changes if role not in PROTECTED_ROLES]
    if not mutable_roles:
        return
    existing = {
        (row.role, row.permission): row
        for row in db.query(RolePermission)
        .filter(
            RolePermission.organization_id == org_id,
            RolePermission.role.in_(mutable_roles),
        )
        .all()
    }
    for role in mutable_roles:
        permissions = changes[role]
        for permission, granted in permissions.items():
            row = existing.get((role, permission))
            if row:
                row.is_granted = granted
                row.updated_at = datetime.now(UTC)
            else:
                db.add(
                    RolePermission(
                        organization_id=org_id, role=role, permission=permission, is_granted=granted
                    )
                )


def activate(
    db: Session,
    org_id: UUID,
    actor_user_id: UUID,
    changes: PermissionPolicyChanges,
    digest: str,
) -> PermissionPolicyConfiguration:
    lock_configuration(db, org_id)
    require_administrator(db, org_id, actor_user_id)
    if is_enabled(db, org_id):
        raise PermissionPolicyConflict("Permission policy is already active")
    reviewed = preview(db, org_id, changes)
    if not hmac.compare_digest(reviewed.digest, digest):
        raise PermissionPolicyConflict(
            "Permissions changed; review a fresh preview before activation"
        )
    if not reviewed.ready:
        raise PermissionPolicyConflict(
            "Resolve all legacy revokes, record-scope review items, and unreviewed execution first"
        )
    completions = []
    if changes.execution_resolutions:
        from app.services import campaign_access, workflow_execution_authority

        for item_type, service in (
            ("workflow", workflow_execution_authority),
            ("campaign", campaign_access),
        ):
            resolutions = [
                item.model_dump(mode="json")
                for item in changes.execution_resolutions
                if item.item_type == item_type
            ]
            if resolutions:
                ended = service.apply_policy_execution_resolutions(
                    db, org_id, actor_user_id, resolutions
                )
                if item_type == "workflow":
                    completions.extend(ended)
    _apply_role_changes(db, org_id, reviewed.role_permissions)
    for resolution in changes.revoke_resolutions:
        row = (
            db.query(UserPermissionOverride)
            .filter(
                UserPermissionOverride.organization_id == org_id,
                UserPermissionOverride.id == resolution.override_id,
                UserPermissionOverride.override_type == "revoke",
            )
            .one()
        )
        db.delete(row)
    db.flush()
    legacy_grants = (
        db.query(UserPermissionOverride)
        .filter(
            UserPermissionOverride.organization_id == org_id,
            UserPermissionOverride.permission == "propose_matches",
            UserPermissionOverride.override_type == "grant",
        )
        .all()
    )
    if legacy_grants:
        user_ids = {grant.user_id for grant in legacy_grants}
        existing = set(
            db.query(UserPermissionOverride.user_id, UserPermissionOverride.permission)
            .filter(
                UserPermissionOverride.organization_id == org_id,
                UserPermissionOverride.user_id.in_(user_ids),
                UserPermissionOverride.permission.in_(MATCH_ACTION_PERMISSIONS),
            )
            .all()
        )
        for user_id in user_ids:
            for key in MATCH_ACTION_PERMISSIONS:
                if (user_id, key) not in existing:
                    db.add(
                        UserPermissionOverride(
                            organization_id=org_id,
                            user_id=user_id,
                            permission=key,
                            override_type="grant",
                        )
                    )
    policy = db.get(OrganizationPermissionPolicy, org_id)
    if policy is None:
        policy = OrganizationPermissionPolicy(organization_id=org_id, configuration_revision=1)
        db.add(policy)
    policy.version = 2
    policy.configuration_revision = reviewed.configuration_revision + 1
    policy.activated_at = datetime.now(UTC)
    policy.activated_by_user_id = actor_user_id
    policy.updated_at = datetime.now(UTC)
    db.flush()
    from app.services import approval_handoff_service

    try:
        transferred = approval_handoff_service.apply_surrogate_pool_transfers(
            db,
            org_id,
            actor_user_id,
            [row.model_dump(mode="json") for row in reviewed.surrogate_pool_transfers],
        )
    except ValueError as exc:
        raise PermissionPolicyConflict(
            "Records changed; review a fresh preview before activation"
        ) from exc
    audit_service.log_event(
        db=db,
        org_id=org_id,
        actor_user_id=actor_user_id,
        event_type=AuditEventType.SETTINGS_ORG_UPDATED,
        target_type="permission_policy",
        target_id=org_id,
        details={
            "policy_version": 2,
            "surrogate_pool_transfers": transferred,
            "review_digest": digest,
            "resolved_revokes": [
                resolution.model_dump(mode="json") for resolution in changes.revoke_resolutions
            ],
            "execution_resolutions": [
                item.model_dump(mode="json") for item in changes.execution_resolutions
            ],
        },
    )
    db.flush()
    if completions:
        from app.services.workflow_engine_core import complete_paused_executions

        # Configuration, its audit, cancellations, and form routing share this commit.
        complete_paused_executions(db, completions)
    return get_configuration(db, org_id)


def update_configuration(
    db: Session,
    org_id: UUID,
    actor_user_id: UUID,
    changes: PermissionPolicyChanges,
) -> PermissionPolicyConfiguration:
    lock_configuration(db, org_id)
    require_administrator(db, org_id, actor_user_id)
    if not is_enabled(db, org_id):
        raise PermissionPolicyConflict(
            "Review and activate version 2 before editing this configuration"
        )
    _validate_changes(changes)
    if changes.revoke_resolutions or changes.execution_resolutions:
        raise ValueError("Legacy resolutions are only accepted during activation")
    _apply_role_changes(db, org_id, changes.role_permissions)
    touch_configuration(db, org_id)
    audit_service.log_event(
        db=db,
        org_id=org_id,
        actor_user_id=actor_user_id,
        event_type=AuditEventType.SETTINGS_ORG_UPDATED,
        target_type="permission_policy",
        target_id=org_id,
        details={"role_permissions": changes.role_permissions},
    )
    db.flush()
    return get_configuration(db, org_id)
