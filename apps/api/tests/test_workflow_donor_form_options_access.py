"""Workflow builder options list donor forms only to users who can save donor workflows."""

from __future__ import annotations

import uuid
from contextlib import contextmanager

import pytest

from app.core.deps import get_current_session
from app.db.enums import Role
from app.db.models import (
    Form,
    Membership,
    Organization,
    RolePermission,
    UserPermissionOverride,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.main import app
from app.schemas.auth import UserSession


def _form(db, org_id, lead_kind) -> Form:
    form = Form(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=f"Options {lead_kind} {uuid.uuid4().hex[:6]}",
        status="published",
        purpose="other",
        lead_kind=lead_kind,
        schema_json={"pages": []},
        published_schema_json={"pages": []},
    )
    db.add(form)
    db.flush()
    return form


@contextmanager
def _as(test_org, test_user, role: Role):
    session = UserSession(
        user_id=test_user.id,
        org_id=test_org.id,
        role=role,
        email=test_user.email,
        display_name=test_user.display_name,
    )
    app.dependency_overrides[get_current_session] = lambda: session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_session, None)


async def _option_form_ids(client) -> set[str]:
    response = await client.get("/workflows/options", params={"subject_type": "form_submission"})
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["forms"]}


async def _create_donor_form_workflow(client, form):
    return await client.post(
        "/workflows",
        json={
            "name": f"Donor form workflow {uuid.uuid4().hex[:6]}",
            "subject_type": "form_submission",
            "trigger_type": "form_submitted",
            "trigger_config": {"form_id": str(form.id)},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [{"action_type": "add_note", "content": "Donor applied"}],
            "is_enabled": False,
            "scope": "org",
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("can_edit", [False, True])
async def test_v1_donor_forms_follow_donor_edit_permission(
    authed_client, db, test_org, test_user, can_edit
):
    surrogate_form = _form(db, test_org.id, "surrogate")
    donor_form = _form(db, test_org.id, "egg_donor")
    if not can_edit:
        db.add(
            UserPermissionOverride(
                organization_id=test_org.id,
                user_id=test_user.id,
                permission="edit_donors",
                override_type="revoke",
            )
        )
    db.commit()

    with _as(test_org, test_user, Role.ADMIN):
        form_ids = await _option_form_ids(authed_client)
        created = await _create_donor_form_workflow(authed_client, donor_form)

    assert str(surrogate_form.id) in form_ids
    assert (str(donor_form.id) in form_ids) is can_edit
    assert created.status_code == (200 if can_edit else 403), created.text


@pytest.mark.asyncio
async def test_v2_donor_view_without_edit_still_lists_donor_forms(
    authed_client, db, test_org, test_user
):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    membership = (
        db.query(Membership)
        .filter(Membership.organization_id == test_org.id, Membership.user_id == test_user.id)
        .one()
    )
    membership.role = Role.CASE_MANAGER.value
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role=Role.CASE_MANAGER.value,
            permission="edit_donors",
            is_granted=False,
        )
    )
    donor_form = _form(db, test_org.id, "egg_donor")
    db.commit()

    with _as(test_org, test_user, Role.CASE_MANAGER):
        form_ids = await _option_form_ids(authed_client)

    assert str(donor_form.id) in form_ids


@pytest.mark.asyncio
async def test_options_never_list_another_org_forms(authed_client, db, test_org):
    other_org = Organization(
        id=uuid.uuid4(), name="Other Options Org", slug=f"options-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    foreign = [_form(db, other_org.id, kind) for kind in ("surrogate", "egg_donor")]
    own = _form(db, test_org.id, "egg_donor")
    db.commit()

    form_ids = await _option_form_ids(authed_client)

    assert str(own.id) in form_ids
    assert form_ids.isdisjoint({str(form.id) for form in foreign})
