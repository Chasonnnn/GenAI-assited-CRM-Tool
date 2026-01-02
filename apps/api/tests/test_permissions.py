"""
Permission service resolution tests.

Tests cover:
- Developer bypass (always true)
- Precedence: revoke > grant > role_default
- Missing permission = deny
- Developer-only permissions
- Self-modification guard
- Org scoping
"""

import uuid
import pytest
from app.db.enums import Role
from app.db.models import User, Membership, RolePermission, UserPermissionOverride
from app.services import permission_service


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def org_a(db):
    """Create organization A for scoping tests."""
    from app.db.models import Organization

    org = Organization(
        id=uuid.uuid4(),
        name="Org A",
        slug=f"org-a-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(org)
    db.flush()
    return org


@pytest.fixture
def org_b(db):
    """Create organization B for scoping tests."""
    from app.db.models import Organization

    org = Organization(
        id=uuid.uuid4(),
        name="Org B",
        slug=f"org-b-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(org)
    db.flush()
    return org


@pytest.fixture
def developer_user(db, org_a):
    """Create a developer user."""
    user = User(
        id=uuid.uuid4(),
        email=f"developer-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Developer User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org_a.id,
        role=Role.DEVELOPER.value,
    )
    db.add(membership)
    db.flush()
    return user


@pytest.fixture
def manager_user(db, org_a):
    """Create a manager user."""
    user = User(
        id=uuid.uuid4(),
        email=f"manager-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Manager User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org_a.id,
        role=Role.ADMIN.value,
    )
    db.add(membership)
    db.flush()
    return user


@pytest.fixture
def intake_user(db, org_a):
    """Create an intake specialist user."""
    user = User(
        id=uuid.uuid4(),
        email=f"intake-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Intake User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org_a.id,
        role=Role.INTAKE_SPECIALIST.value,
    )
    db.add(membership)
    db.flush()
    return user


@pytest.fixture
def user_in_org_b(db, org_b):
    """Create a user in org B for scoping tests."""
    user = User(
        id=uuid.uuid4(),
        email=f"user-b-{uuid.uuid4().hex[:8]}@test.com",
        display_name="User in Org B",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org_b.id,
        role=Role.ADMIN.value,
    )
    db.add(membership)
    db.flush()
    return user


# =============================================================================
# Test: Developer Bypass
# =============================================================================


def test_developer_bypass_always_true(db, org_a, developer_user):
    """Developer always has permission, even if role defaults or overrides deny."""
    # Even for a permission that doesn't exist or has no role default
    result = permission_service.check_permission(
        db, org_a.id, developer_user.id, Role.DEVELOPER.value, "any_random_permission"
    )
    assert result is True, "Developer should always have permission"


def test_developer_bypass_ignores_explicit_revoke(db, org_a, developer_user):
    """Developer bypasses even if there's a user revoke (which shouldn't happen but test anyway)."""
    # Create a revoke override (shouldn't affect developer)
    override = UserPermissionOverride(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        user_id=developer_user.id,
        permission="view_post_approval_cases",
        override_type="revoke",
    )
    db.add(override)
    db.flush()

    result = permission_service.check_permission(
        db,
        org_a.id,
        developer_user.id,
        Role.DEVELOPER.value,
        "view_post_approval_cases",
    )
    assert result is True, "Developer should bypass even explicit revokes"


# =============================================================================
# Test: Precedence (revoke > grant > role_default)
# =============================================================================


def test_precedence_user_revoke_overrides_role_grant(
    db, org_a, manager_user, developer_user
):
    """User revoke should override role grant."""
    # Set role default to grant
    role_perm = RolePermission(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        role=Role.ADMIN.value,
        permission="view_post_approval_cases",
        is_granted=True,
    )
    db.add(role_perm)
    db.flush()

    # Verify role grants permission
    result = permission_service.check_permission(
        db, org_a.id, manager_user.id, Role.ADMIN.value, "view_post_approval_cases"
    )
    assert result is True, "Role grant should work"

    # Add user revoke override
    override = UserPermissionOverride(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        user_id=manager_user.id,
        permission="view_post_approval_cases",
        override_type="revoke",
    )
    db.add(override)
    db.flush()

    # Verify revoke overrides role grant
    result = permission_service.check_permission(
        db, org_a.id, manager_user.id, Role.ADMIN.value, "view_post_approval_cases"
    )
    assert result is False, "User revoke should override role grant"


def test_precedence_user_grant_overrides_role_deny(
    db, org_a, intake_user, developer_user
):
    """User grant should override role deny (or missing)."""
    # Intake specialist has no archive_cases by default
    # Verify it's denied first
    result = permission_service.check_permission(
        db,
        org_a.id,
        intake_user.id,
        Role.INTAKE_SPECIALIST.value,
        "archive_cases",
    )
    assert result is False, "Intake should not have archive_cases access by default"

    # Add user grant override
    override = UserPermissionOverride(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        user_id=intake_user.id,
        permission="archive_cases",
        override_type="grant",
    )
    db.add(override)
    db.flush()

    # Verify grant overrides denial
    result = permission_service.check_permission(
        db,
        org_a.id,
        intake_user.id,
        Role.INTAKE_SPECIALIST.value,
        "archive_cases",
    )
    assert result is True, "User grant should override role denial"


# =============================================================================
# Test: Missing Permission = Deny
# =============================================================================


def test_missing_permission_returns_false(db, org_a, manager_user):
    """Missing/undefined permission should return False."""
    result = permission_service.check_permission(
        db,
        org_a.id,
        manager_user.id,
        Role.ADMIN.value,
        "completely_undefined_permission",
    )
    assert result is False, "Missing permission should return False"


# =============================================================================
# Test: Developer-Only Permissions
# =============================================================================


def test_developer_only_permission_cannot_be_granted_to_non_developer(
    db, org_a, intake_user, developer_user
):
    """Developer-only permissions cannot be granted to non-developers via overrides.

    Even if an override is created in the database, get_effective_permissions
    filters out developer_only permissions for non-developer roles.
    """
    # Use a real developer-only permission
    # 'manage_roles' is marked developer_only=True in the registry
    override = UserPermissionOverride(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        user_id=intake_user.id,
        permission="manage_roles",  # developer-only permission
        override_type="grant",
    )
    db.add(override)
    db.flush()

    # Developer-only permissions are filtered out for non-developers
    result = permission_service.check_permission(
        db, org_a.id, intake_user.id, Role.INTAKE_SPECIALIST.value, "manage_roles"
    )
    assert result is False, (
        "Developer-only permission should be denied for non-developers even with override"
    )


# =============================================================================
# Test: Self-Modification Guard
# =============================================================================


def test_self_modification_guard(db, org_a, manager_user):
    """set_user_override should reject when actor == target."""
    with pytest.raises(ValueError, match="[Cc]annot modify.*own"):
        permission_service.set_user_override(
            db=db,
            org_id=org_a.id,
            target_user_id=manager_user.id,
            actor_user_id=manager_user.id,  # same as target
            permission="view_post_approval_cases",
            override_type="grant",
        )


# =============================================================================
# Test: Org Scoping
# =============================================================================


def test_org_scoping_overrides_isolated(
    db, org_a, org_b, manager_user, user_in_org_b, developer_user
):
    """Overrides in org A should not affect users in org B."""
    # Use a permission that Manager does NOT have by default
    # Manager already has view_post_approval_cases in ROLE_DEFAULTS
    # So we test with a permission not in their defaults

    # Create a grant override for a custom permission in org A
    override = UserPermissionOverride(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        user_id=manager_user.id,
        permission="some_custom_permission_xyz",  # Not in ROLE_DEFAULTS
        override_type="grant",
    )
    db.add(override)
    db.flush()

    # Manager in org A should have the custom permission
    result_a = permission_service.check_permission(
        db, org_a.id, manager_user.id, Role.ADMIN.value, "some_custom_permission_xyz"
    )
    assert result_a is True, "Manager in org A should have permission from override"

    # User in org B should NOT have the custom permission
    # (they don't have the override, and it's not in ROLE_DEFAULTS)
    result_b = permission_service.check_permission(
        db, org_b.id, user_in_org_b.id, Role.ADMIN.value, "some_custom_permission_xyz"
    )
    assert result_b is False, (
        "User in org B should not have permission (no override/default)"
    )


def test_org_scoping_role_defaults_isolated(
    db, org_a, org_b, manager_user, user_in_org_b
):
    """Role defaults in org A should not affect org B."""
    # Create a role default in org A
    role_perm_a = RolePermission(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        role=Role.ADMIN.value,
        permission="some_custom_permission",
        is_granted=True,
    )
    db.add(role_perm_a)
    db.flush()

    # Manager in org A should have permission
    result_a = permission_service.check_permission(
        db, org_a.id, manager_user.id, Role.ADMIN.value, "some_custom_permission"
    )
    assert result_a is True, "Org A manager should have permission from role default"

    # Manager in org B should NOT have this permission (no role default there)
    result_b = permission_service.check_permission(
        db, org_b.id, user_in_org_b.id, Role.ADMIN.value, "some_custom_permission"
    )
    assert result_b is False, (
        "Org B manager should NOT have permission (no role default)"
    )
