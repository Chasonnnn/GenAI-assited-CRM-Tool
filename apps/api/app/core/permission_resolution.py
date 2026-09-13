"""Resolve loaded permission overrides without database access."""

from collections.abc import Iterable

from app.core.permissions import (
    ADMIN_ONLY_PERMISSIONS,
    PERMISSION_REGISTRY,
    PROTECTED_ROLES,
    V2_AI_PERMISSIONS,
    V2_DEFAULT_PERMISSIONS,
    get_role_default_permissions,
    is_developer_only,
    is_valid_permission,
)


def resolve_effective_permissions(
    role: str,
    *,
    role_overrides: Iterable[tuple[str, bool]] = (),
    user_overrides: Iterable[tuple[str, str]] = (),
    policy_version: int = 1,
    ai_enabled: bool = True,
) -> set[str]:
    """Apply role defaults, organization overrides, then user grants/revokes.

    Developer bypasses overrides. Other roles cannot receive developer-only
    permissions. Unknown keys and override types retain the existing behavior:
    an explicit grant preserves its key; an unrecognized user override is ignored.
    """
    unavailable = V2_AI_PERMISSIONS if policy_version >= 2 and not ai_enabled else set()
    if role == "developer":
        return set(PERMISSION_REGISTRY) - unavailable

    effective = get_role_default_permissions(role, policy_version=policy_version).copy()
    if policy_version >= 2 and role in PROTECTED_ROLES:
        return effective - unavailable

    for permission, is_granted in role_overrides:
        if policy_version >= 2 and (
            not is_valid_permission(permission) or permission in V2_DEFAULT_PERMISSIONS
        ):
            continue
        if is_granted:
            effective.add(permission)
        else:
            effective.discard(permission)

    for permission, override_type in user_overrides:
        if policy_version >= 2 and (
            not is_valid_permission(permission) or permission in V2_DEFAULT_PERMISSIONS
        ):
            continue
        if override_type == "grant":
            effective.add(permission)
        elif override_type == "revoke" and policy_version < 2:
            effective.discard(permission)

    return {
        permission
        for permission in effective
        if permission not in unavailable
        and not is_developer_only(permission, policy_version=policy_version)
        and (policy_version < 2 or permission not in ADMIN_ONLY_PERMISSIONS)
    }
