"""Versioned permission activation, administration, and tenant boundaries."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.csrf import CSRF_HEADER
from app.db.models import (
    AuditLog,
    Membership,
    Organization,
    RolePermission,
    User,
    UserPermissionOverride,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.schemas.permission_policy import PermissionPolicyChanges, RevokeResolution
from app.services import permission_policy_service as policy_service
from app.services import permission_service


def add_member(db, org_id, role="intake_specialist"):
    user = User(
        id=uuid.uuid4(),
        email=f"permission-{uuid.uuid4().hex}@example.test",
        display_name="Permission Test",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    membership = Membership(organization_id=org_id, user_id=user.id, role=role)
    db.add(membership)
    db.flush()
    return user, membership


@pytest.fixture
def ready_review(monkeypatch):
    monkeypatch.setattr(policy_service, "get_scope_review", lambda *_: {"ready": True})
    monkeypatch.setattr(policy_service, "get_execution_review", lambda *_: [])


def test_missing_policy_preserves_legacy_resolution_and_is_org_scoped(db, test_org):
    user, _ = add_member(db, test_org.id)
    assert policy_service.get_version(db, test_org.id) == 1
    assert "approve_donors" not in permission_service.get_effective_permissions(
        db, test_org.id, user.id, "intake_specialist"
    )
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.flush()
    assert policy_service.is_enabled(db, test_org.id)
    assert not policy_service.is_enabled(db, uuid.uuid4())
    assert "approve_donors" in permission_service.get_effective_permissions(
        db, test_org.id, user.id, "intake_specialist"
    )


def test_empty_organization_activates_through_real_scope_and_execution_review(
    db, test_org, test_user
):
    changes = PermissionPolicyChanges()
    reviewed = policy_service.preview(db, test_org.id, changes)
    assert reviewed.ready
    assert reviewed.scope_review["ready"]
    assert reviewed.execution_review == []
    result = policy_service.activate(db, test_org.id, test_user.id, changes, reviewed.digest)
    assert result.version == 2


@pytest.mark.parametrize("review_type", ["scope", "execution"])
def test_activation_blocks_unresolved_scope_and_work_review(
    db, test_org, test_user, ready_review, monkeypatch, review_type
):
    if review_type == "scope":
        monkeypatch.setattr(
            policy_service,
            "get_scope_review",
            lambda *_: {"ready": False, "unresolved_handoffs": ["record"]},
        )
    else:
        monkeypatch.setattr(
            policy_service,
            "get_execution_review",
            lambda *_: [{"item_type": "workflow", "id": "00000000-0000-0000-0000-000000000001"}],
        )
    changes = PermissionPolicyChanges()
    reviewed = policy_service.preview(db, test_org.id, changes)
    assert not reviewed.ready
    with pytest.raises(policy_service.PermissionPolicyConflict, match="Resolve all"):
        policy_service.activate(db, test_org.id, test_user.id, changes, reviewed.digest)
    assert policy_service.get_version(db, test_org.id) == 1


@pytest.mark.parametrize(("version", "revision"), [(0, 1), (3, 1), (2, 0)])
def test_policy_schema_rejects_invalid_versions_and_revisions(db, test_org, version, revision):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            OrganizationPermissionPolicy(
                organization_id=test_org.id, version=version, configuration_revision=revision
            )
        )
        db.flush()


def test_activation_requires_every_revoke_and_previews_role_wide_impact(
    db, test_org, test_user, ready_review
):
    first, _ = add_member(db, test_org.id)
    second, _ = add_member(db, test_org.id)
    revoke = UserPermissionOverride(
        organization_id=test_org.id,
        user_id=first.id,
        permission="edit_surrogates",
        override_type="revoke",
    )
    db.add(revoke)
    db.flush()
    incomplete = policy_service.preview(db, test_org.id, PermissionPolicyChanges())
    assert not incomplete.ready
    assert incomplete.unresolved_revoke_ids == [revoke.id]
    with pytest.raises(policy_service.PermissionPolicyConflict, match="Resolve all"):
        policy_service.activate(
            db, test_org.id, test_user.id, PermissionPolicyChanges(), incomplete.digest
        )
    assert policy_service.get_version(db, test_org.id) == 1
    assert db.get(UserPermissionOverride, revoke.id) is not None

    changes = PermissionPolicyChanges(
        revoke_resolutions=[RevokeResolution(override_id=revoke.id, action="deny_for_role")]
    )
    reviewed = policy_service.preview(db, test_org.id, changes)
    assert reviewed.ready
    assert (
        "edit_surrogates"
        in next(item for item in reviewed.members if item.user_id == second.id).lost
    )
    result = policy_service.activate(db, test_org.id, test_user.id, changes, reviewed.digest)
    assert result.version == 2
    assert db.get(UserPermissionOverride, revoke.id) is None
    for user in (first, second):
        assert "edit_surrogates" not in permission_service.get_effective_permissions(
            db, test_org.id, user.id, "intake_specialist"
        )
    audit = (
        db.query(AuditLog)
        .filter_by(organization_id=test_org.id, target_type="permission_policy")
        .one()
    )
    assert audit.details["review_digest"] == reviewed.digest
    with pytest.raises(policy_service.PermissionPolicyConflict, match="already active"):
        policy_service.activate(db, test_org.id, test_user.id, changes, reviewed.digest)


def test_explicit_revoke_removal_displays_access_gain(db, test_org, test_user, ready_review):
    member, _ = add_member(db, test_org.id)
    revoke = UserPermissionOverride(
        organization_id=test_org.id,
        user_id=member.id,
        permission="edit_surrogates",
        override_type="revoke",
    )
    db.add(revoke)
    db.flush()
    changes = PermissionPolicyChanges(
        revoke_resolutions=[RevokeResolution(override_id=revoke.id, action="remove")]
    )
    reviewed = policy_service.preview(db, test_org.id, changes)
    assert (
        "edit_surrogates"
        in next(item for item in reviewed.members if item.user_id == member.id).gained
    )
    policy_service.activate(db, test_org.id, test_user.id, changes, reviewed.digest)
    assert db.get(UserPermissionOverride, revoke.id) is None


@pytest.mark.parametrize("changed", ["role", "member", "scope", "execution"])
def test_activation_rejects_state_changed_after_preview(
    db, test_org, test_user, ready_review, monkeypatch, changed
):
    changes = PermissionPolicyChanges()
    reviewed = policy_service.preview(db, test_org.id, changes)
    if changed == "role":
        db.add(
            RolePermission(
                organization_id=test_org.id,
                role="intake_specialist",
                permission="view_reports",
                is_granted=True,
            )
        )
    elif changed == "member":
        add_member(db, test_org.id)
    elif changed == "scope":
        monkeypatch.setattr(
            policy_service, "get_scope_review", lambda *_: {"ready": True, "revision": 2}
        )
    else:
        monkeypatch.setattr(
            policy_service,
            "get_execution_review",
            lambda *_: [{"item_type": "workflow", "id": str(uuid.uuid4())}],
        )
    db.flush()
    with pytest.raises(policy_service.PermissionPolicyConflict, match="fresh preview"):
        policy_service.activate(db, test_org.id, test_user.id, changes, reviewed.digest)
    assert policy_service.get_version(db, test_org.id) == 1


def test_cross_org_revoke_and_review_digest_are_rejected(db, test_org, test_user, ready_review):
    other_org = Organization(name="Other", slug=f"other-{uuid.uuid4().hex}")
    db.add(other_org)
    db.flush()
    other_user, _ = add_member(db, other_org.id, "admin")
    revoke = UserPermissionOverride(
        organization_id=other_org.id,
        user_id=other_user.id,
        permission="view_reports",
        override_type="revoke",
    )
    db.add(revoke)
    db.flush()
    with pytest.raises(ValueError, match="this organization's"):
        policy_service.preview(
            db,
            test_org.id,
            PermissionPolicyChanges(
                revoke_resolutions=[RevokeResolution(override_id=revoke.id, action="remove")]
            ),
        )
    reviewed = policy_service.preview(db, test_org.id, PermissionPolicyChanges())
    with pytest.raises(policy_service.PermissionPolicyConflict, match="fresh preview"):
        policy_service.activate(
            db, other_org.id, other_user.id, PermissionPolicyChanges(), reviewed.digest
        )
    assert not policy_service.is_enabled(db, other_org.id)
    with pytest.raises(ValueError, match="active organization Admin"):
        policy_service.activate(
            db, other_org.id, test_user.id, PermissionPolicyChanges(), reviewed.digest
        )


def test_activation_audit_failure_rolls_back_policy_and_revoke_changes(
    db, test_org, test_user, ready_review, monkeypatch
):
    user, _ = add_member(db, test_org.id)
    revoke = UserPermissionOverride(
        organization_id=test_org.id,
        user_id=user.id,
        permission="edit_surrogates",
        override_type="revoke",
    )
    db.add(revoke)
    db.flush()
    changes = PermissionPolicyChanges(
        revoke_resolutions=[RevokeResolution(override_id=revoke.id, action="remove")]
    )
    reviewed = policy_service.preview(db, test_org.id, changes)

    def fail_audit(**_):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(policy_service.audit_service, "log_event", fail_audit)
    with pytest.raises(RuntimeError, match="Audit unavailable"), db.begin_nested():
        policy_service.activate(db, test_org.id, test_user.id, changes, reviewed.digest)
    assert policy_service.get_version(db, test_org.id) == 1
    assert db.get(UserPermissionOverride, revoke.id) is not None


@pytest.mark.parametrize("role", ["admin", "developer"])
def test_v2_protected_role_configuration_is_rejected(db, test_org, test_user, role):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.flush()
    with pytest.raises(ValueError, match="protected"):
        permission_service.set_role_default(
            db, test_org.id, role, "view_reports", False, test_user.id
        )
    with pytest.raises(ValueError, match="protected"):
        policy_service.update_configuration(
            db,
            test_org.id,
            test_user.id,
            PermissionPolicyChanges(role_permissions={role: {"view_reports": False}}),
        )


def test_v2_only_admin_can_grant_additions_and_no_one_can_add_individual_denials(db, test_org):
    admin, _ = add_member(db, test_org.id, "admin")
    operations, _ = add_member(db, test_org.id, "operations")
    target, _ = add_member(db, test_org.id)
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.flush()
    with pytest.raises(ValueError, match="Only Admin"):
        permission_service.set_user_override(
            db, test_org.id, target.id, operations.id, "view_reports", "grant"
        )
    with pytest.raises(ValueError, match="additions only"):
        permission_service.set_user_override(
            db, test_org.id, target.id, admin.id, "edit_surrogates", "revoke"
        )
    with pytest.raises(ValueError, match="reserved for Admin"):
        permission_service.set_user_override(
            db, test_org.id, operations.id, admin.id, "manage_roles", "grant"
        )
    permission_service.set_user_override(
        db, test_org.id, operations.id, admin.id, "send_campaigns", "grant"
    )
    db.flush()
    assert "send_campaigns" in permission_service.get_effective_permissions(
        db, test_org.id, operations.id, "operations"
    )


@pytest.mark.asyncio
async def test_policy_api_requires_admin_and_csrf(
    db, test_org, test_user, authed_client, ready_review
):
    membership = (
        db.query(Membership).filter_by(user_id=test_user.id, organization_id=test_org.id).one()
    )
    membership.role = "operations"
    db.flush()
    denied = await authed_client.get("/settings/permissions/policy")
    assert denied.status_code == 403
    denied_preview = await authed_client.post("/settings/permissions/policy/preview", json={})
    assert denied_preview.status_code == 403
    membership.role = "admin"
    db.flush()
    no_csrf = await authed_client.post(
        "/settings/permissions/policy/preview", json={}, headers={CSRF_HEADER: ""}
    )
    assert no_csrf.status_code == 403
    preview = await authed_client.post("/settings/permissions/policy/preview", json={})
    assert preview.status_code == 200, preview.text
    forged_org = await authed_client.post(
        "/settings/permissions/policy/activate",
        json={"digest": preview.json()["digest"], "org_id": str(uuid.uuid4())},
    )
    assert forged_org.status_code == 422
    activated = await authed_client.post(
        "/settings/permissions/policy/activate", json={"digest": preview.json()["digest"]}
    )
    assert activated.status_code == 200, activated.text
    roles = await authed_client.get("/settings/permissions/roles")
    assert "operations" in {role["role"] for role in roles.json()}
    role_update = await authed_client.patch(
        "/settings/permissions/roles/operations", json={"permissions": {"send_campaigns": True}}
    )
    assert role_update.status_code == 200, role_update.text
    protected = await authed_client.patch(
        "/settings/permissions/roles/admin", json={"permissions": {"view_reports": False}}
    )
    assert protected.status_code == 400


@pytest.mark.asyncio
async def test_v2_member_api_requires_role_change_review_and_denies_other_org_targets(
    db, test_org, test_user, authed_client
):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    target, membership = add_member(db, test_org.id)
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=target.id,
            permission="view_reports",
            override_type="grant",
        )
    )
    db.flush()
    denied = await authed_client.patch(
        f"/settings/permissions/members/{membership.id}", json={"role": "case_manager"}
    )
    assert denied.status_code == 409
    assert membership.role == "intake_specialist"
    approved = await authed_client.patch(
        f"/settings/permissions/members/{membership.id}",
        json={
            "role": "case_manager",
            "access_reviewed": True,
            "retain_additions": False,
            "retain_collaborators": False,
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["overrides"] == []
    assert approved.json()["policy_version"] == 2
    denied_revoke = await authed_client.patch(
        f"/settings/permissions/members/{membership.id}",
        json={"add_overrides": [{"permission": "edit_surrogates", "override_type": "revoke"}]},
    )
    assert denied_revoke.status_code == 400
    other_org = Organization(name="Other", slug=f"other-{uuid.uuid4().hex}")
    db.add(other_org)
    db.flush()
    _, other_membership = add_member(db, other_org.id)
    other = await authed_client.patch(
        f"/settings/permissions/members/{other_membership.id}",
        json={"add_overrides": [{"permission": "view_reports", "override_type": "grant"}]},
    )
    assert other.status_code == 404


@pytest.mark.asyncio
async def test_role_save_updates_actions_and_scope_atomically(db, test_org, authed_client):
    from app.db.models import RoleRecordScope

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.flush()
    response = await authed_client.patch(
        "/settings/permissions/roles/case_manager",
        json={
            "permissions": {"send_campaigns": True},
            "scope_rules": {
                "donors": {"assignment": "assigned", "phase": "post_approval", "stage_ids": []}
            },
        },
    )
    assert response.status_code == 200, response.text
    assert (
        db.query(RoleRecordScope)
        .filter_by(organization_id=test_org.id, role="case_manager", module="donors")
        .one()
        .assignment
        == "assigned"
    )
    assert (
        db.query(RolePermission)
        .filter_by(organization_id=test_org.id, role="case_manager", permission="send_campaigns")
        .one()
        .is_granted
    )


def test_policy_rechecks_actor_after_waiting_for_configuration_lock(
    db, test_org, test_user, ready_review, monkeypatch
):
    changes = PermissionPolicyChanges()
    reviewed = policy_service.preview(db, test_org.id, changes)
    real_lock = policy_service.lock_configuration

    def revoke_while_waiting(db, org_id):
        member = db.query(Membership).filter_by(organization_id=org_id, user_id=test_user.id).one()
        member.role = "operations"
        db.flush()
        real_lock(db, org_id)

    monkeypatch.setattr(policy_service, "lock_configuration", revoke_while_waiting)
    with pytest.raises(ValueError, match="active organization Admin"):
        policy_service.activate(db, test_org.id, test_user.id, changes, reviewed.digest)
    assert policy_service.get_version(db, test_org.id) == 1


def test_delegated_team_action_cannot_invite_admin_under_v2(db, test_org):
    from app.services import invite_service

    actor, _ = add_member(db, test_org.id, "operations")
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=actor.id,
            permission="manage_team",
            override_type="grant",
        )
    )
    db.flush()
    assert not permission_service.check_permission(
        db, test_org.id, actor.id, "operations", "manage_team"
    )
    with pytest.raises(ValueError, match="active organization Admin"):
        invite_service.create_invite(db, test_org.id, "synthetic@test.invalid", "admin", actor.id)


@pytest.mark.asyncio
async def test_returning_member_role_requires_review_without_restoring_access(
    db, test_org, authed_client
):
    from app.db.models import RecordCollaborator

    user, membership = add_member(db, test_org.id, "intake_specialist")
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=user.id,
            permission="view_reports",
            override_type="grant",
        )
    )
    membership.is_active = False
    db.flush()
    response = await authed_client.get("/settings/permissions/members?include_inactive=true")
    assert response.status_code == 200
    assert any(row["user_id"] == str(user.id) and not row["is_active"] for row in response.json())
    rejected = await authed_client.patch(
        f"/settings/permissions/members/{membership.id}", json={"role": "operations"}
    )
    assert rejected.status_code == 409
    changed = await authed_client.patch(
        f"/settings/permissions/members/{membership.id}",
        json={
            "role": "operations",
            "access_reviewed": True,
            "retain_additions": False,
            "retain_collaborators": False,
        },
    )
    assert changed.status_code == 200, changed.text
    assert not membership.is_active
    assert membership.role == "operations"
    assert (
        db.query(UserPermissionOverride)
        .filter_by(organization_id=test_org.id, user_id=user.id)
        .count()
        == 0
    )
    assert (
        db.query(RecordCollaborator).filter_by(organization_id=test_org.id, user_id=user.id).count()
        == 0
    )


def test_role_deny_resolution_must_change_role_authority(db, test_org, ready_review):
    user, _ = add_member(db, test_org.id)
    revoke = UserPermissionOverride(
        organization_id=test_org.id,
        user_id=user.id,
        permission="manage_integrations",
        override_type="revoke",
    )
    db.add(revoke)
    db.flush()
    changes = PermissionPolicyChanges(
        revoke_resolutions=[RevokeResolution(override_id=revoke.id, action="deny_for_role")]
    )
    with pytest.raises(ValueError, match="Role already denies"):
        policy_service.preview(db, test_org.id, changes)
