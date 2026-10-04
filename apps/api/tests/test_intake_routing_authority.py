"""Module routing uses form permissions and tenant scope under permission v2."""

from uuid import uuid4

import pytest

from app.core.csrf import CSRF_HEADER
from app.db.enums import Role
from app.db.models import (
    AutomationWorkflow,
    IntakeLead,
    Organization,
    RolePermission,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.services import form_routing_service
from tests.test_email_templates_personal_scope import authed_client_for_user, create_user_with_role
from tests.test_form_routing import KINDS, routing_submission, tasks

REVIEW_SETTINGS = {
    "exact_match": "review",
    "no_match": "review",
    "lead_source": None,
    "auto_create_donor": False,
}


@pytest.fixture
def v2(db, test_org):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("auto_field", ["exact_match", "no_match"])
async def test_auto_settings_require_create_permission(
    db, test_org, test_user, v2, kind, auto_field
):
    actor = create_user_with_role(db, test_org.id, Role.INTAKE_SPECIALIST)
    permission = "create_surrogates" if kind == "surrogate" else "create_donors"
    db.add_all(
        [
            RolePermission(
                organization_id=test_org.id,
                role="intake_specialist",
                permission="manage_forms",
                is_granted=True,
            ),
            RolePermission(
                organization_id=test_org.id,
                role="intake_specialist",
                permission=permission,
                is_granted=False,
            ),
        ]
    )
    form, _ = routing_submission(db, test_org.id, test_user.id, kind=kind)
    async with authed_client_for_user(db, test_org.id, actor, Role.INTAKE_SPECIALIST) as client:
        response = await client.put(
            f"/forms/{form.id}/routing", json={**REVIEW_SETTINGS, auto_field: "auto"}
        )
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == f"Missing permission: {permission}"
        response = await client.put(f"/forms/{form.id}/routing", json=REVIEW_SETTINGS)
        assert response.status_code == 200, response.text
    db.refresh(form)
    assert form.routing_exact_match == form.routing_no_match == "review"
    assert form.routing_updated_by_user_id == actor.id


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("operation", ["create-lead", "run-match"])
async def test_review_creation_requires_create_permission(
    db, test_org, test_user, v2, kind, operation
):
    actor = create_user_with_role(db, test_org.id, Role.INTAKE_SPECIALIST)
    permission = "create_surrogates" if kind == "surrogate" else "create_donors"
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role="intake_specialist",
            permission=permission,
            is_granted=False,
        )
    )
    form, submission = routing_submission(
        db,
        test_org.id,
        test_user.id,
        kind=kind,
        exact="auto" if operation == "create-lead" else "review",
    )
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    if operation == "run-match":
        form.routing_no_match = "auto"
        db.commit()
    original_step = submission.routing_review_step
    task_id = tasks(db, submission)[0].id
    async with authed_client_for_user(db, test_org.id, actor, Role.INTAKE_SPECIALIST) as client:
        response = await client.post(f"/forms/submissions/{submission.id}/routing/{operation}")
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == f"Missing permission: {permission}"
    db.refresh(submission)
    assert submission.routing_review_step == original_step
    assert submission.intake_lead_id is None
    assert [(t.id, t.status) for t in tasks(db, submission)] == [(task_id, "pending")]
    assert db.query(IntakeLead).filter_by(form_id=form.id).count() == 0


@pytest.mark.asyncio
async def test_surrogate_cannot_enable_donor_creation(authed_client, db, test_org, test_user):
    form, _ = routing_submission(db, test_org.id, test_user.id)
    response = await authed_client.put(
        f"/forms/{form.id}/routing", json={**REVIEW_SETTINGS, "auto_create_donor": True}
    )
    assert response.status_code == 422, response.text
    db.refresh(form)
    assert form.routing_auto_create_donor is False


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["read", "update", "workflows"])
async def test_form_routing_cross_org_is_not_found(authed_client, db, test_user, operation):
    org = Organization(name="Other", slug=uuid4().hex)
    db.add(org)
    db.flush()
    form, _ = routing_submission(db, org.id, test_user.id)
    if operation == "update":
        response = await authed_client.put(f"/forms/{form.id}/routing", json=REVIEW_SETTINGS)
    else:
        response = await authed_client.get(
            f"/forms/{form.id}/{'workflows' if operation == 'workflows' else 'routing'}"
        )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_routing_update_requires_csrf(authed_client, db, test_org, test_user):
    form, _ = routing_submission(db, test_org.id, test_user.id)
    token = authed_client.headers.pop(CSRF_HEADER)
    try:
        response = await authed_client.put(f"/forms/{form.id}/routing", json=REVIEW_SETTINGS)
    finally:
        authed_client.headers[CSRF_HEADER] = token
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_donor_settings_require_donor_edit(db, test_org, test_user):
    from tests.test_hosted_donor_form_lifecycle_permissions import _admin_with_revokes, _client_for

    actor = _admin_with_revokes(db, test_org.id, "edit_donors")
    form, _ = routing_submission(db, test_org.id, test_user.id, kind="egg_donor")
    async with _client_for(db, test_org.id, actor) as client:
        response = await client.put(f"/forms/{form.id}/routing", json=REVIEW_SETTINGS)
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Missing permission: edit_donors"


@pytest.mark.asyncio
async def test_workflows_filters_form_trigger_org_and_visibility(db, test_org, test_user, v2):
    actor = create_user_with_role(db, test_org.id, Role.INTAKE_SPECIALIST)
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role="intake_specialist",
            permission="manage_forms",
            is_granted=True,
        )
    )
    form, _ = routing_submission(db, test_org.id, test_user.id)
    foreign = Organization(name="Other", slug=uuid4().hex)
    db.add(foreign)
    db.flush()
    expected = []
    for index, (trigger, form_id, org_id, scope, owner_id) in enumerate(
        [
            ("form_submitted", form.id, test_org.id, "org", None),
            ("form_submission_approved", form.id, test_org.id, "org", None),
            ("form_submission_rejected", form.id, test_org.id, "personal", actor.id),
            ("form_submitted", uuid4(), test_org.id, "org", None),
            ("form_submitted", form.id, foreign.id, "org", None),
            ("form_submitted", form.id, test_org.id, "personal", test_user.id),
            ("surrogate_created", form.id, test_org.id, "org", None),
            ("form_submitted", None, test_org.id, "org", None),
        ]
    ):
        workflow = AutomationWorkflow(
            organization_id=org_id,
            name=f"Workflow {index}",
            trigger_type=trigger,
            subject_type="form_submission" if trigger.startswith("form_") else "surrogate",
            trigger_config={"form_id": str(form_id)} if form_id else {},
            conditions=[],
            condition_logic="AND",
            actions=[],
            is_enabled=index != 1,
            scope=scope,
            owner_user_id=owner_id,
        )
        db.add(workflow)
        db.flush()
        if index < 3:
            expected.append(
                {
                    "id": str(workflow.id),
                    "name": workflow.name,
                    "trigger_type": trigger,
                    "is_enabled": index != 1,
                    "scope": scope,
                }
            )
    db.commit()
    async with authed_client_for_user(db, test_org.id, actor, Role.INTAKE_SPECIALIST) as client:
        response = await client.get(f"/forms/{form.id}/workflows")
    assert response.status_code == 200, response.text
    assert response.json() == expected


@pytest.mark.asyncio
async def test_form_workflows_hide_donor_workflows_without_donor_view(db, test_org, test_user, v2):
    actor = create_user_with_role(db, test_org.id, Role.INTAKE_SPECIALIST)
    db.add_all(
        [
            RolePermission(
                organization_id=test_org.id,
                role="intake_specialist",
                permission="manage_forms",
                is_granted=True,
            ),
            RolePermission(
                organization_id=test_org.id,
                role="intake_specialist",
                permission="view_donors",
                is_granted=False,
            ),
        ]
    )
    form, _ = routing_submission(db, test_org.id, test_user.id, kind="egg_donor")
    db.add(
        AutomationWorkflow(
            organization_id=test_org.id,
            name="Donor application",
            trigger_type="form_submitted",
            subject_type="form_submission",
            trigger_config={"form_id": str(form.id)},
            conditions=[],
            condition_logic="AND",
            actions=[],
            is_enabled=True,
            scope="org",
        )
    )
    db.commit()
    async with authed_client_for_user(db, test_org.id, actor, Role.INTAKE_SPECIALIST) as client:
        response = await client.get(f"/forms/{form.id}/workflows")
    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["egg_donor", "sperm_donor"])
@pytest.mark.parametrize("operation", ["create", "change_kind", "template"])
async def test_donor_defaults_cannot_bypass_create_permission(
    db, test_org, test_user, v2, kind, operation
):
    from app.db.models import Form
    from tests.test_hosted_donor_form_lifecycle_permissions import _published_donor_template

    actor = create_user_with_role(db, test_org.id, Role.INTAKE_SPECIALIST)
    db.add_all(
        [
            RolePermission(
                organization_id=test_org.id,
                role="intake_specialist",
                permission="manage_forms",
                is_granted=True,
            ),
            RolePermission(
                organization_id=test_org.id,
                role="intake_specialist",
                permission="create_donors",
                is_granted=False,
            ),
        ]
    )
    form = Form(
        organization_id=test_org.id,
        name="Draft",
        lead_kind="surrogate",
        created_by_user_id=test_user.id,
    )
    db.add(form)
    template = _published_donor_template(db)
    template.published_settings_json = {**template.published_settings_json, "lead_kind": kind}
    db.commit()
    async with authed_client_for_user(db, test_org.id, actor, Role.INTAKE_SPECIALIST) as client:
        if operation == "create":
            response = await client.post(
                "/forms", json={"name": "New donor form", "lead_kind": kind}
            )
        elif operation == "template":
            response = await client.post(
                f"/forms/templates/{template.id}/use", json={"name": "Template donor form"}
            )
        else:
            response = await client.patch(f"/forms/{form.id}", json={"lead_kind": kind})
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Missing permission: create_donors"
    db.refresh(form)
    assert form.lead_kind == "surrogate"
    assert db.query(Form).filter_by(organization_id=test_org.id).count() == 1
