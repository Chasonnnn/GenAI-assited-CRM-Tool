"""Resolve loaded permission overrides without database access."""

from collections.abc import Iterable

from app.core.permissions import (
    PERMISSION_REGISTRY,
    get_role_default_permissions,
    is_developer_only,
)


def resolve_effective_permissions(
    role: str,
    *,
    role_overrides: Iterable[tuple[str, bool]] = (),
    user_overrides: Iterable[tuple[str, str]] = (),
) -> set[str]:
    """Apply role defaults, organization overrides, then user grants/revokes.

    Developer bypasses overrides. Other roles cannot receive developer-only
    permissions. Unknown keys and override types retain the existing behavior:
    an explicit grant preserves its key; an unrecognized user override is ignored.
    """
    if role == "developer":
        return set(PERMISSION_REGISTRY)

    effective = get_role_default_permissions(role).copy()

    for permission, is_granted in role_overrides:
        if is_granted:
            effective.add(permission)
        else:
            effective.discard(permission)

    for permission, override_type in user_overrides:
        if override_type == "grant":
            effective.add(permission)
        elif override_type == "revoke":
            effective.discard(permission)

    return {permission for permission in effective if not is_developer_only(permission)}
