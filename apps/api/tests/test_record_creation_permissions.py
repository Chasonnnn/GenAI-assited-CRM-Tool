"""Create is independent from editing or record scope after reviewed V2 activation."""

from uuid import UUID, uuid4

import pytest

from app.db.enums import Role
from app.db.models import (
    Donor,
    IntakeLead,
    IntendedParent,
    Organization,
    OrganizationPermissionPolicy,
    RolePermission,
    RoleRecordScope,
    Surrogate,
    User,
)
from tests.test_email_templates_personal_scope import authed_client_for_user
from tests.test_record_scopes_v2 import _member, _record
from tests.test_record_scopes_v2 import context as context

MODULES = ["surrogates", "donors", "intended_parents"]
MODELS = {"surrogates": Surrogate, "donors": Donor, "intended_parents": IntendedParent}


def _rule(db, org_id, module, action, granted, role="case_manager"):
    db.add(
        RolePermission(
            organization_id=org_id, role=role, permission=f"{action}_{module}", is_granted=granted
        )
    )
    db.flush()


def _payload(module):
    data = {"full_name": "New applicant", "email": f"create-{uuid4()}@example.com"}
    if module == "donors":
        data["donor_type"] = "egg"
    return data


@pytest.mark.asyncio
@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("create,edit", [(True, False), (False, True), (False, False)])
async def test_v2_create_permission_is_independent(db, context, module, create, edit):
    _rule(db, context.org.id, module, "create", create)
    _rule(db, context.org.id, module, "edit", edit)
    user = db.get(User, context.manager.user_id)
    before = db.query(MODELS[module]).filter_by(organization_id=context.org.id).count()
    async with authed_client_for_user(db, context.org.id, user, Role.CASE_MANAGER) as client:
        response = await client.post(f"/{module.replace('_', '-')}", json=_payload(module))
        assert response.status_code == (201 if create else 403), response.text
        if create:
            record = db.get(MODELS[module], UUID(response.json()["id"]))
            assert record.organization_id == context.org.id
            if module in {"surrogates", "donors"}:
                assert record.owner_type == "user"
                assert record.owner_id == user.id
            else:
                assert record.owner_type is None  # Existing IP creation remains unassigned.
                assert record.owner_id is None
    assert db.query(MODELS[module]).filter_by(
        organization_id=context.org.id
    ).count() == before + int(create)


@pytest.mark.asyncio
@pytest.mark.parametrize("module", MODULES)
async def test_legacy_create_still_uses_edit(db, context, module):
    db.query(OrganizationPermissionPolicy).filter_by(organization_id=context.org.id).delete()
    _rule(db, context.org.id, module, "create", False)
    user = db.get(User, context.manager.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.CASE_MANAGER) as client:
        response = await client.post(f"/{module.replace('_', '-')}", json=_payload(module))
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("module", MODULES)
async def test_create_keeps_csrf_and_authenticated_org(db, context, module):
    other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
    db.add(other)
    db.flush()
    user = db.get(User, context.manager.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.CASE_MANAGER) as client:
        payload = {**_payload(module), "organization_id": str(other.id)}
        client.headers.pop("X-CSRF-Token", None)
        response = await client.post(f"/{module.replace('_', '-')}", json=payload)
        assert response.status_code == 403, response.text
        response = await client.post(
            f"/{module.replace('_', '-')}",
            json=payload,
            headers={"X-CSRF-Token": client.cookies.get("crm_csrf")},
        )
        assert response.status_code in {201, 422}, response.text
    assert db.query(MODELS[module]).filter_by(organization_id=other.id).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module,kind",
    [("surrogates", "surrogate"), ("donors", "donor"), ("intended_parents", "intended_parent")],
)
async def test_create_does_not_expand_existing_record_scope(db, context, module, kind):
    db.add(
        RoleRecordScope(
            organization_id=context.org.id,
            role="case_manager",
            module=module,
            assignment="assigned",
            phase="all",
            stage_ids=[],
        )
    )
    record = _record(db, context.intake, kind)
    user = db.get(User, context.manager.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.CASE_MANAGER) as client:
        response = await client.get(f"/{module.replace('_', '-')}/{record.id}")
    assert response.status_code == (404 if module == "intended_parents" else 403), response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("module", ["donors", "intended_parents"])
@pytest.mark.parametrize("owner", ["foreign", "inactive", "incomplete"])
async def test_create_rejects_invalid_owner_relationships(db, context, module, owner):
    if owner == "foreign":
        other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
        db.add(other)
        db.flush()
        target, _ = _member(db, other.id, "admin")
    else:
        target, membership = _member(db, context.org.id, "case_manager")
        membership.is_active = False
        db.flush()
    user = db.get(User, context.admin.user_id)
    data = {**_payload(module), "owner_id": str(target.user_id)}
    if owner != "incomplete":
        data["owner_type"] = "user"
    async with authed_client_for_user(db, context.org.id, user, Role.ADMIN) as client:
        response = await client.post(f"/{module.replace('_', '-')}", json=data)
    assert response.status_code in {400, 422}, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["approve", "retry", "run-inline"])
async def test_import_execution_requires_create_before_queueing(db, context, operation):
    _rule(db, context.org.id, "surrogates", "create", False, role="intake_specialist")
    for permission in ["import_surrogates", "manage_org"]:
        db.add(
            RolePermission(
                organization_id=context.org.id,
                role="intake_specialist",
                permission=permission,
                is_granted=True,
            )
        )
    db.flush()
    user = db.get(User, context.intake.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.INTAKE_SPECIALIST) as client:
        response = await client.post(f"/surrogates/import/{uuid4()}/{operation}")
    assert response.status_code == 403, response.text
    assert "create_surrogates" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("create", [True, False])
async def test_intake_promotion_uses_create_without_edit(db, context, create):
    _rule(db, context.org.id, "surrogates", "create", create, role="intake_specialist")
    _rule(db, context.org.id, "surrogates", "edit", not create, role="intake_specialist")
    lead = IntakeLead(
        organization_id=context.org.id,
        lead_type="surrogate",
        full_name="Intake applicant",
        email=f"intake-{uuid4()}@example.com",
    )
    db.add(lead)
    db.flush()
    user = db.get(User, context.intake.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.INTAKE_SPECIALIST) as client:
        response = await client.post(f"/forms/intake-leads/{lead.id}/promote", json={})
    assert response.status_code == (200 if create else 403), response.text
    if create:
        surrogate = db.get(Surrogate, UUID(response.json()["surrogate_id"]))
        assert surrogate.organization_id == context.org.id
        assert surrogate.owner_id == user.id
    else:
        assert lead.promoted_surrogate_id is None


@pytest.mark.asyncio
async def test_intake_promotion_cannot_cross_org(db, context):
    other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
    db.add(other)
    db.flush()
    lead = IntakeLead(
        organization_id=other.id,
        lead_type="surrogate",
        full_name="Foreign intake applicant",
        email=f"intake-{uuid4()}@example.com",
    )
    db.add(lead)
    db.flush()
    user = db.get(User, context.intake.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.INTAKE_SPECIALIST) as client:
        response = await client.post(f"/forms/intake-leads/{lead.id}/promote", json={})
    assert response.status_code == 404, response.text
    assert lead.promoted_surrogate_id is None
