"""Universal personal features, module presentation, and reviewed policy changes."""

import uuid

import pytest

from app.core.permission_resolution import resolve_effective_permissions
from app.core.permissions import (
    PERMISSION_PRESENTATION,
    PERMISSION_REGISTRY,
    PERMISSION_TOPIC_SECTIONS,
    V2_AI_PERMISSIONS,
    V2_DEFAULT_PERMISSIONS,
    V2_PERSONAL_WORKSPACE_PERMISSIONS,
    V2_ROLE_DEFAULTS,
    get_permission_presentation,
)
from app.db.models import Membership, Organization, RolePermission, User, UserPermissionOverride
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.schemas.permission_policy import PermissionPolicyChanges, RevokeResolution
from app.services import permission_policy_service as policy
from app.services import permission_service


@pytest.fixture
def member_factory(db, test_org):
    def create(role="intake_specialist", org_id=None):
        user = User(
            email=f"defaults-{uuid.uuid4().hex}@example.com",
            display_name="Policy Test",
            is_active=True,
        )
        db.add(user)
        db.flush()
        membership = Membership(organization_id=org_id or test_org.id, user_id=user.id, role=role)
        db.add(membership)
        db.flush()
        return user, membership

    return create


@pytest.fixture
def active_policy(db, test_org):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.flush()


@pytest.mark.parametrize("role", V2_ROLE_DEFAULTS)
def test_defaults_ignore_legacy_role_denials_and_user_overrides(role):
    effective = resolve_effective_permissions(
        role,
        policy_version=2,
        role_overrides=[(key, False) for key in V2_DEFAULT_PERMISSIONS],
        user_overrides=[(key, "revoke") for key in V2_DEFAULT_PERMISSIONS],
    )
    assert V2_DEFAULT_PERMISSIONS <= effective
    disabled = resolve_effective_permissions(role, policy_version=2, ai_enabled=False)
    assert V2_PERSONAL_WORKSPACE_PERMISSIONS <= disabled
    assert not disabled & V2_AI_PERMISSIONS


@pytest.mark.parametrize("role", ["intake_specialist", "case_manager", "operations"])
def test_ai_settings_cannot_be_granted_outside_protected_roles(role):
    effective = resolve_effective_permissions(
        role,
        policy_version=2,
        role_overrides=[("manage_ai_settings", True)],
        user_overrides=[("manage_ai_settings", "grant")],
    )
    assert "manage_ai_settings" not in effective
    assert not effective & {"manage_team", "manage_roles"}


def test_v1_existing_feature_denials_remain_effective():
    effective = resolve_effective_permissions(
        "case_manager",
        role_overrides=[("use_ai_assistant", False), ("view_email_templates", False)],
        user_overrides=[("approve_ai_actions", "revoke")],
        ai_enabled=False,
    )
    assert not effective & {"use_ai_assistant", "approve_ai_actions", "view_email_templates"}
    assert "manage_ai_settings" in effective


def test_create_actions_are_independent_from_edit():
    for module in ("surrogates", "donors", "intended_parents"):
        create, edit = f"create_{module}", f"edit_{module}"
        effective = resolve_effective_permissions(
            "operations", policy_version=2, role_overrides=[(create, True), (edit, False)]
        )
        assert create in effective
        assert edit not in effective
        effective = resolve_effective_permissions(
            "case_manager", policy_version=2, role_overrides=[(create, False), (edit, True)]
        )
        assert edit in effective
        assert create not in effective


def test_every_permission_has_exactly_one_topic_and_short_label():
    assert list(PERMISSION_TOPIC_SECTIONS) == [
        "Surrogates",
        "Donors",
        "Intended Parents",
        "Operations",
        "Administration",
    ]
    keys = [
        key
        for sections in PERMISSION_TOPIC_SECTIONS.values()
        for permissions in sections.values()
        for key in permissions
    ]
    assert len(keys) == len(set(keys))
    assert set(keys) == set(PERMISSION_REGISTRY) == set(PERMISSION_PRESENTATION)
    for key in keys:
        metadata = get_permission_presentation(key, policy_version=2)
        assert all(metadata[name] for name in ("topic", "section", "short_label"))
        assert metadata["is_default"] == (key in V2_DEFAULT_PERMISSIONS)
        assert not get_permission_presentation(key)["is_default"]


@pytest.mark.parametrize("role", V2_ROLE_DEFAULTS)
def test_effective_defaults_require_live_membership_and_actual_organization(
    db, test_org, member_factory, active_policy, role
):
    user, membership = member_factory(role)
    assert V2_DEFAULT_PERMISSIONS <= permission_service.get_effective_permissions(
        db, test_org.id, user.id, role
    )
    membership.is_active = False
    db.flush()
    assert permission_service.get_effective_permissions(db, test_org.id, user.id, role) == set()
    membership.is_active = True
    user.is_active = False
    db.flush()
    assert permission_service.get_effective_permissions(db, test_org.id, user.id, role) == set()
    user.is_active = True
    other = Organization(name="Other", slug=f"other-{uuid.uuid4().hex}")
    db.add(other)
    db.flush()
    db.add(OrganizationPermissionPolicy(organization_id=other.id, version=2))
    db.flush()
    assert permission_service.get_effective_permissions(db, other.id, user.id, role) == set()
    assert not permission_service.check_permission(db, other.id, user.id, "developer", "send_email")


def test_v2_effective_permissions_do_not_trust_a_stale_developer_role(
    db, test_org, member_factory, active_policy
):
    user, _ = member_factory("operations")
    effective = permission_service.get_effective_permissions(db, test_org.id, user.id, "developer")
    assert V2_DEFAULT_PERMISSIONS <= effective
    assert "manage_ai_settings" not in effective
    assert "send_email" not in effective


def test_v2_developer_checks_require_registered_permission_and_active_membership(
    db, test_org, member_factory, active_policy
):
    user, membership = member_factory("developer")
    assert permission_service.check_permission(db, test_org.id, user.id, "developer", "send_email")
    assert not permission_service.check_permission(
        db, test_org.id, user.id, "developer", "any_random_permission"
    )
    membership.is_active = False
    db.flush()
    assert not permission_service.check_permission(
        db, test_org.id, user.id, "developer", "send_email"
    )


@pytest.mark.parametrize("permission", sorted(V2_DEFAULT_PERMISSIONS))
def test_default_configuration_and_grants_are_rejected_but_old_rows_can_be_removed(
    db, test_org, test_user, member_factory, active_policy, permission
):
    target, _ = member_factory()
    for value in (False, True):
        with pytest.raises(ValueError, match="Included features"):
            permission_service.set_role_default(
                db, test_org.id, "intake_specialist", permission, value, test_user.id
            )
        with pytest.raises(ValueError, match="Included features"):
            policy.update_configuration(
                db,
                test_org.id,
                test_user.id,
                PermissionPolicyChanges(
                    role_permissions={"intake_specialist": {permission: value}}
                ),
            )
    with pytest.raises(ValueError, match="Included features"):
        permission_service.set_user_override(
            db, test_org.id, target.id, test_user.id, permission, "grant"
        )
    legacy = UserPermissionOverride(
        organization_id=test_org.id, user_id=target.id, permission=permission, override_type="grant"
    )
    db.add(legacy)
    db.flush()
    permission_service.set_user_override(db, test_org.id, target.id, test_user.id, permission, None)
    db.flush()
    assert db.get(UserPermissionOverride, legacy.id) is None


@pytest.mark.parametrize("permission", sorted(V2_DEFAULT_PERMISSIONS))
def test_activation_reviews_default_denials_as_removal_only(
    db, test_org, test_user, member_factory, monkeypatch, permission
):
    monkeypatch.setattr(policy, "get_scope_review", lambda *_: {"ready": True})
    monkeypatch.setattr(policy, "get_execution_review", lambda *_: [])
    user, _ = member_factory()
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role="intake_specialist",
            permission=permission,
            is_granted=False,
        )
    )
    revoke = UserPermissionOverride(
        organization_id=test_org.id, user_id=user.id, permission=permission, override_type="revoke"
    )
    db.add(revoke)
    db.flush()
    unresolved = policy.preview(db, test_org.id, PermissionPolicyChanges())
    assert not unresolved.ready
    assert not unresolved.revokes[0].can_deny_for_role
    with pytest.raises(ValueError, match="explicitly removed"):
        policy.preview(
            db,
            test_org.id,
            PermissionPolicyChanges(
                revoke_resolutions=[RevokeResolution(override_id=revoke.id, action="deny_for_role")]
            ),
        )
    changes = PermissionPolicyChanges(
        revoke_resolutions=[RevokeResolution(override_id=revoke.id, action="remove")]
    )
    reviewed = policy.preview(db, test_org.id, changes)
    assert reviewed.ready
    difference = next(row for row in reviewed.members if row.user_id == user.id)
    assert permission in difference.gained
    assert permission not in reviewed.role_permissions.get("intake_specialist", {})
    policy.activate(db, test_org.id, test_user.id, changes, reviewed.digest)
    assert permission in permission_service.get_effective_permissions(
        db, test_org.id, user.id, "intake_specialist"
    )
    assert db.get(UserPermissionOverride, revoke.id) is None


def test_ai_availability_change_invalidates_activation_preview(
    db, test_org, test_user, monkeypatch
):
    monkeypatch.setattr(policy, "get_scope_review", lambda *_: {"ready": True})
    monkeypatch.setattr(policy, "get_execution_review", lambda *_: [])
    changes = PermissionPolicyChanges()
    before = policy.preview(db, test_org.id, changes)
    test_org.ai_enabled = False
    db.flush()
    after = policy.preview(db, test_org.id, changes)
    assert before.digest != after.digest
    assert all(not V2_AI_PERMISSIONS & set(member.proposed) for member in after.members)
    with pytest.raises(policy.PermissionPolicyConflict, match="fresh preview"):
        policy.activate(db, test_org.id, test_user.id, changes, before.digest)


@pytest.mark.asyncio
@pytest.mark.parametrize("ai_enabled", [True, False])
async def test_catalog_role_and_member_preview_describe_effective_features(
    db, test_org, member_factory, active_policy, authed_client, ai_enabled
):
    test_org.ai_enabled = ai_enabled
    user, member = member_factory("operations")
    db.flush()
    expected = {"personal_workspace": True, "ai_assistant": ai_enabled}
    available = await authed_client.get("/settings/permissions/available")
    assert available.status_code == 200, available.text
    rows = {row["key"]: row for row in available.json()}
    assert set(rows) == set(PERMISSION_REGISTRY) - {"view_post_approval_surrogates"}
    assert {row["topic"] for row in rows.values()} == set(PERMISSION_TOPIC_SECTIONS)
    for permission in V2_DEFAULT_PERMISSIONS:
        assert rows[permission]["is_default"]
        assert not rows[permission]["assignable"]
        assert not rows[permission]["configurable"]
    role = await authed_client.get("/settings/permissions/roles/operations")
    assert role.status_code == 200, role.text
    assert role.json()["included_features"] == expected
    role_rows = {
        row["key"]: row
        for group in role.json()["permissions_by_category"].values()
        for row in group
    }
    assert "view_post_approval_surrogates" not in role_rows
    assert not role_rows["manage_ai_settings"]["is_granted"]
    for permission in V2_AI_PERMISSIONS:
        assert role_rows[permission]["is_granted"] == ai_enabled
    detail = await authed_client.get(f"/settings/permissions/members/{member.id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["included_features"] == expected
    for permission in V2_PERSONAL_WORKSPACE_PERMISSIONS:
        assert detail.json()["access_sources"][permission] == ["included_feature"]
    member.is_active = False
    db.flush()
    inactive = await authed_client.get(f"/settings/permissions/members/{member.id}")
    assert inactive.status_code == 200, inactive.text
    assert inactive.json()["effective_permissions"] == []
    assert inactive.json()["included_features"] == {
        "personal_workspace": False,
        "ai_assistant": False,
    }


@pytest.mark.asyncio
async def test_legacy_catalog_still_exposes_existing_configurable_features(
    db, test_org, authed_client
):
    result = await authed_client.get("/settings/permissions/roles/intake_specialist")
    assert result.status_code == 200, result.text
    assert result.json()["included_features"] == {
        "personal_workspace": False,
        "ai_assistant": False,
    }
    rows = {
        row["key"]: row
        for group in result.json()["permissions_by_category"].values()
        for row in group
    }
    assert "view_post_approval_surrogates" in rows
    assert rows["manage_automation"]["configurable"]
    assert not rows["manage_automation"]["is_default"]
    assert "create_surrogates" not in rows


def test_activation_preview_excludes_inactive_users_and_binds_their_state(
    db, test_org, test_user, member_factory, monkeypatch
):
    monkeypatch.setattr(policy, "get_scope_review", lambda *_: {"ready": True})
    monkeypatch.setattr(policy, "get_execution_review", lambda *_: [])
    target, _ = member_factory()
    changes = PermissionPolicyChanges()
    before = policy.preview(db, test_org.id, changes)
    assert any(member.user_id == target.id for member in before.members)
    target.is_active = False
    db.flush()
    after = policy.preview(db, test_org.id, changes)
    assert all(member.user_id != target.id for member in after.members)
    with pytest.raises(policy.PermissionPolicyConflict, match="fresh preview"):
        policy.activate(db, test_org.id, test_user.id, changes, before.digest)
