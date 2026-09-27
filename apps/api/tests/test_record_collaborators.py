"""Explicit record collaborations share one grant and preserve action permissions."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.csrf import CSRF_HEADER
from app.db.enums import Role
from app.db.models import Membership, Organization, User
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.db.models.record_access import RecordCollaborator
from app.schemas.record_scope import RecordScopeRule
from app.services import permission_service
from app.services import record_scope_service as scopes
from app.services.record_access_service import get_record_with_access
from tests.test_email_templates_personal_scope import authed_client_for_user
from tests.test_record_scopes_v2 import _member, _record


@pytest.fixture
def context(db, test_org):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    admin, _ = _member(db, test_org.id, "admin")
    manager, _ = _member(db, test_org.id, "case_manager")
    intake, _ = _member(db, test_org.id, "intake_specialist")
    return SimpleNamespace(org=test_org, admin=admin, manager=manager, intake=intake)


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
@pytest.mark.parametrize("role", list(Role))
def test_any_active_staff_can_receive_only_the_explicit_record(db, context, kind, role):
    recipient, _ = _member(db, context.org.id, role.value)
    record = _record(db, context.manager, kind)
    other_record = _record(db, context.manager, kind, suffix=2)
    before = permission_service.get_effective_permissions(
        db, recipient.org_id, recipient.user_id, role.value
    )
    assert not scopes.can_access_record(db, recipient, kind, record, personal_only=True)

    grant = scopes.grant_collaborator(db, context.admin, kind, record.id, recipient.user_id)
    same = scopes.grant_collaborator(db, context.admin, kind, record.id, recipient.user_id)

    assert grant.id == same.id
    assert scopes.can_access_record(db, recipient, kind, record, personal_only=True)
    assert not scopes.can_access_record(db, recipient, kind, other_record, personal_only=True)
    assert "collaborator" in scopes.explain_record_access(db, recipient, kind, record).sources
    assert (
        permission_service.get_effective_permissions(
            db, recipient.org_id, recipient.user_id, role.value
        )
        == before
    )


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
@pytest.mark.parametrize("role", [Role.CASE_MANAGER, Role.INTAKE_SPECIALIST, Role.OPERATIONS])
@pytest.mark.parametrize("operation", ["grant", "remove", "options"])
def test_record_owner_cannot_manage_collaboration_without_admin(db, context, kind, role, operation):
    actor, _ = _member(db, context.org.id, role.value)
    record = _record(db, actor, kind, key="approved" if role == Role.CASE_MANAGER else None)
    scopes.grant_collaborator(db, context.admin, kind, record.id, context.intake.user_id)
    assert get_record_with_access(db, actor, kind, record.id).id == record.id

    with pytest.raises(PermissionError):
        if operation == "options":
            scopes.collaborator_options(db, actor, kind, record.id)
        elif operation == "grant":
            scopes.grant_collaborator(db, actor, kind, record.id, actor.user_id)
        else:
            scopes.remove_collaborator(db, actor, kind, record.id, context.intake.user_id)
    assert db.query(RecordCollaborator).filter_by(user_id=context.intake.user_id).count() == 1
    assert db.query(RecordCollaborator).filter_by(user_id=actor.user_id).count() == 0


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
def test_collaborator_options_include_all_active_tenant_staff(db, context, kind):
    record = _record(db, context.manager, kind)
    recipients = [_member(db, context.org.id, role.value) for role in Role]
    inactive_member, inactive_membership = _member(db, context.org.id, "operations")
    inactive_user, _ = _member(db, context.org.id, "case_manager")
    inactive_membership.is_active = False
    db.get(User, inactive_user.user_id).is_active = False
    other_org = Organization(id=uuid4(), name="Other", slug=f"collaborator-{uuid4()}")
    db.add(other_org)
    db.flush()
    foreign, _ = _member(db, other_org.id, "admin")

    options = scopes.collaborator_options(db, context.admin, kind, record.id)
    ids = {option["user_id"] for option in options}
    assert {recipient.user_id for recipient, _ in recipients} <= ids
    assert ids.isdisjoint({inactive_member.user_id, inactive_user.user_id, foreign.user_id})
    assert all(option["display_name"] for option in options)
    for invalid in (inactive_member, inactive_user, foreign):
        with pytest.raises(LookupError):
            scopes.grant_collaborator(db, context.admin, kind, record.id, invalid.user_id)
    foreign_record = _record(db, foreign, kind)
    with pytest.raises(HTTPException) as error:
        scopes.grant_collaborator(
            db, context.admin, kind, foreign_record.id, context.intake.user_id
        )
    assert error.value.status_code == 404


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
def test_collaboration_never_grants_edit_send_or_approval(db, context, kind):
    recipient, _ = _member(db, context.org.id, "operations")
    record = _record(db, context.manager, kind)
    scopes.save_role_scope(
        db, context.admin, "operations", scopes.RECORDS[kind][1], RecordScopeRule(assignment="none")
    )
    assert not scopes.can_access_record(db, recipient, kind, record)
    scopes.grant_collaborator(db, context.admin, kind, record.id, recipient.user_id)
    assert get_record_with_access(db, recipient, kind, record.id).id == record.id
    with pytest.raises(HTTPException) as error:
        get_record_with_access(db, recipient, kind, record.id, action="edit")
    assert error.value.status_code == 403
    for action in ("send_email", "send_sms", "approve_surrogates", "approve_donors"):
        assert not permission_service.check_permission(
            db, recipient.org_id, recipient.user_id, recipient.role.value, action
        )


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
def test_inactive_grant_is_readable_and_removable_but_does_not_grant_access(db, context, kind):
    recipient, member = _member(db, context.org.id, "case_manager")
    record = _record(db, context.intake, kind)
    grant = scopes.grant_collaborator(db, context.admin, kind, record.id, recipient.user_id)
    member.is_active = False
    db.flush()

    details = scopes.collaborator_details(db, context.admin, kind, record.id)
    assert [(row.id, row.display_name) for row in details] == [(grant.id, "Staff")]
    assert not scopes.can_access_record(db, recipient, kind, record, personal_only=True)
    scopes.remove_collaborator(db, context.admin, kind, record.id, recipient.user_id)
    assert scopes.collaborator_details(db, context.admin, kind, record.id) == []


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
def test_remove_collaboration_preserves_role_access(db, context, kind):
    record = _record(db, context.intake, kind, key="approved")
    scopes.grant_collaborator(db, context.admin, kind, record.id, context.manager.user_id)
    assert scopes.can_access_record(db, context.manager, kind, record, personal_only=True)
    scopes.remove_collaborator(db, context.admin, kind, record.id, context.manager.user_id)
    assert scopes.can_access_record(db, context.manager, kind, record)
    assert not scopes.can_access_record(db, context.manager, kind, record, personal_only=True)


@pytest.mark.parametrize("change", ["role", "membership", "user"])
@pytest.mark.parametrize("operation", ["grant", "remove", "options"])
def test_collaborator_management_rechecks_stale_admin(db, context, change, operation):
    record = _record(db, context.manager, "surrogate", key="approved")
    scopes.grant_collaborator(db, context.admin, "surrogate", record.id, context.intake.user_id)
    membership = db.query(Membership).filter_by(user_id=context.admin.user_id).one()
    if change == "role":
        membership.role = "case_manager"
    elif change == "membership":
        membership.is_active = False
    else:
        db.get(User, context.admin.user_id).is_active = False
    db.flush()
    with pytest.raises(PermissionError):
        if operation == "options":
            scopes.collaborator_options(db, context.admin, "surrogate", record.id)
        elif operation == "grant":
            scopes.grant_collaborator(
                db, context.admin, "surrogate", record.id, context.manager.user_id
            )
        else:
            scopes.remove_collaborator(
                db, context.admin, "surrogate", record.id, context.intake.user_id
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["surrogate", "donor"])
async def test_record_and_member_views_share_the_same_grant(db, context, kind):
    record = _record(db, context.manager, kind)
    admin = db.get(User, context.admin.user_id)
    async with authed_client_for_user(db, context.org.id, admin, Role.ADMIN) as client:
        path = f"/record-scopes/records/{kind}/{record.id}/collaborators"
        created = await client.post(path, json={"user_id": str(context.manager.user_id)})
        assert created.status_code == 201, created.text
        grant_id = created.json()["id"]
        records = await client.get(path)
        members = await client.get("/record-scopes/migration-review")
        assert records.status_code == members.status_code == 200
        assert records.json()[0]["id"] == grant_id
        assert [row["id"] for row in members.json()["collaborators"]] == [grant_id]
        assert (await client.delete(f"{path}/{context.manager.user_id}")).status_code == 204
        assert (await client.get(path)).json() == []
        assert (await client.get("/record-scopes/migration-review")).json()["collaborators"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(Role))
async def test_member_collaboration_capabilities_are_independent_of_role_edit(db, context, role):
    target, member = _member(db, context.org.id, role.value)
    admin = db.get(User, context.admin.user_id)
    async with authed_client_for_user(db, context.org.id, admin, Role.ADMIN) as client:
        response = await client.get(f"/settings/permissions/members/{member.id}")
        assert response.status_code == 200, response.text
        capabilities = response.json()["capabilities"]
        assert capabilities["can_manage_collaborations"] is True
        assert capabilities["can_receive_collaboration"] is True
        member.is_active = False
        db.flush()
        response = await client.get(f"/settings/permissions/members/{member.id}")
        assert response.status_code == 200, response.text
        capabilities = response.json()["capabilities"]
        assert capabilities["can_manage_collaborations"] is True
        assert capabilities["can_receive_collaboration"] is False


@pytest.mark.asyncio
async def test_admin_self_collaboration_capability_and_csrf(db, context):
    record = _record(db, context.manager, "surrogate")
    admin = db.get(User, context.admin.user_id)
    member = db.query(Membership).filter_by(user_id=admin.id).one()
    async with authed_client_for_user(db, context.org.id, admin, Role.ADMIN) as client:
        response = await client.get(f"/settings/permissions/members/{member.id}")
        capabilities = response.json()["capabilities"]
        assert capabilities["can_add_permissions"] is False
        assert capabilities["can_receive_collaboration"] is True
        client.headers.pop(CSRF_HEADER)
        path = f"/record-scopes/records/surrogate/{record.id}/collaborators"
        response = await client.post(path, json={"user_id": str(context.intake.user_id)})
        assert response.status_code == 403
        assert (await client.delete(f"{path}/{context.intake.user_id}")).status_code == 403
