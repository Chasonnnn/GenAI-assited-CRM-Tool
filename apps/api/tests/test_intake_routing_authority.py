"""Generated intake routing gets a system execution grant under permission v2."""

from __future__ import annotations

import json
import uuid

import pytest

from app.core.config import settings
from app.db.enums import AuditEventType, Role, WorkflowExecutionStatus
from app.db.models import (
    AuditLog,
    AutomationWorkflow,
    Form,
    FormSubmission,
    IntakeLead,
    Membership,
    Organization,
    RolePermission,
    User,
    WorkflowExecution,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.schemas.workflow import WorkflowUpdate
from app.services import form_intake_service, workflow_service
from app.services import workflow_execution_authority as authority
from tests.test_forms_public_shared_intake import _create_published_form_and_shared_link
from tests.test_hosted_donor_forms import _create_donor_form, _submit_donor_form

SYSTEM_AUTHORIZER = "system:shared_intake_routing"


@pytest.fixture(autouse=True)
def _local_unscanned_storage(monkeypatch, tmp_path):
    from app.core.rate_limit import limiter

    limiter.reset()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)


@pytest.fixture
def v2(db, test_org):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.commit()


def _routing(db, org_id, form_id) -> AutomationWorkflow:
    return (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.system_key == f"shared_intake_routing:{form_id}",
        )
        .one()
    )


def _executions(db, workflow) -> list[WorkflowExecution]:
    return (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == workflow.organization_id,
            WorkflowExecution.workflow_id == workflow.id,
        )
        .all()
    )


def _system_grants(db, workflow) -> list[AuditLog]:
    return [
        log
        for log in db.query(AuditLog)
        .filter(
            AuditLog.organization_id == workflow.organization_id,
            AuditLog.event_type == AuditEventType.WORKFLOW_CONFIG_CHANGED.value,
            AuditLog.target_id == workflow.id,
        )
        .all()
        if (log.details or {}).get("operation") == "system_authorize"
    ]


def _assert_system_grant(db, workflow):
    grant = workflow.execution_authority
    assert grant is not None
    assert grant["authorized_by"] == SYSTEM_AUTHORIZER
    assert grant["authorized_by_user_id"] is None
    assert grant["configuration_digest"] == authority.configuration_digest(workflow)
    expected = set()
    for action in workflow.actions:
        expected |= authority.action_permissions(db, workflow, action)
    assert set(grant["permissions"]) == expected
    authority.execution_snapshot(db, workflow)
    (log,) = _system_grants(db, workflow)
    assert log.details == {"operation": "system_authorize", "scope": "org"}


def _form(db, org_id, user_id, lead_kind) -> Form:
    form = Form(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=f"Routing {lead_kind} {uuid.uuid4().hex[:6]}",
        status="published",
        purpose="other",
        lead_kind=lead_kind,
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=user_id,
    )
    db.add(form)
    db.flush()
    return form


def _member(db, org_id, role=Role.INTAKE_SPECIALIST) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"routing-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Routing Staff",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            organization_id=org_id,
            user_id=user.id,
            role=role.value,
            is_active=True,
        )
    )
    db.flush()
    return user


@pytest.mark.asyncio
async def test_v2_publish_grants_surrogate_routing_and_submissions_route(
    authed_client, db, test_org, v2
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)
    workflow = _routing(db, test_org.id, form_id)
    assert workflow.trigger_config == {"form_id": form_id, "lead_kind": "surrogate"}
    _assert_system_grant(db, workflow)

    response = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Routed Candidate",
                    "date_of_birth": "1993-04-12",
                    "phone": "+1 (555) 100-2000",
                    "email": "routed@example.com",
                }
            )
        },
    )
    assert response.status_code == 200, response.text

    (execution,) = _executions(db, workflow)
    assert execution.status == WorkflowExecutionStatus.PAUSED.value, execution.error_message
    assert execution.authority_snapshot["authorized_by"] == SYSTEM_AUTHORIZER


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["egg_donor", "sperm_donor"])
async def test_v2_publish_grants_donor_routing_and_submissions_route(
    authed_client, db, test_org, v2, kind
):
    form_id, slug = await _create_donor_form(authed_client, lead_kind=kind)
    workflow = _routing(db, test_org.id, form_id)
    assert workflow.trigger_config == {"form_id": form_id, "lead_kind": kind}
    _assert_system_grant(db, workflow)
    assert "create_donors" in workflow.execution_authority["permissions"]

    response = await _submit_donor_form(authed_client, slug=slug, email="granted@example.com")
    assert response.status_code == 200, response.text

    (execution,) = _executions(db, workflow)
    assert execution.status == WorkflowExecutionStatus.SUCCESS.value, execution.error_message
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    lead = db.get(IntakeLead, submission.intake_lead_id)
    assert lead is not None
    assert (lead.source_metadata or {}).get("auto_create_donor") is True


@pytest.mark.asyncio
async def test_shared_donor_form_routing_keeps_both_subtypes(authed_client, db, test_org, v2):
    form_id, _slug = await _create_donor_form(authed_client, shared_donor=True)
    workflow = _routing(db, test_org.id, form_id)
    assert workflow.trigger_config == {"form_id": form_id}
    _assert_system_grant(db, workflow)


@pytest.mark.parametrize(
    ("lead_kind", "permission"),
    [("surrogate", "create_surrogates"), ("egg_donor", "create_donors")],
)
def test_publisher_without_create_permission_gets_no_grant(
    db, test_org, test_user, v2, lead_kind, permission
):
    publisher = _member(db, test_org.id)
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role=Role.INTAKE_SPECIALIST.value,
            permission=permission,
            is_granted=False,
        )
    )
    form = _form(db, test_org.id, test_user.id, lead_kind)

    workflow = form_intake_service.ensure_default_intake_routing_workflow(
        db, org_id=test_org.id, form=form, user_id=publisher.id
    )

    assert workflow is not None
    assert workflow.is_enabled is True
    assert workflow.execution_authority is None
    assert _system_grants(db, workflow) == []


@pytest.mark.parametrize("lead_kind", ["surrogate", "egg_donor"])
def test_publisher_with_create_permission_gets_the_grant(db, test_org, test_user, v2, lead_kind):
    publisher = _member(db, test_org.id)
    form = _form(db, test_org.id, test_user.id, lead_kind)

    workflow = form_intake_service.ensure_default_intake_routing_workflow(
        db, org_id=test_org.id, form=form, user_id=publisher.id
    )

    _assert_system_grant(db, workflow)


def test_publisher_from_another_org_gets_no_grant(db, test_org, test_user, v2):
    other_org = Organization(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    outsider = _member(db, other_org.id, Role.ADMIN)
    form = _form(db, test_org.id, test_user.id, "egg_donor")

    workflow = form_intake_service.ensure_default_intake_routing_workflow(
        db, org_id=test_org.id, form=form, user_id=outsider.id
    )

    assert workflow.execution_authority is None


@pytest.mark.asyncio
async def test_publish_does_not_touch_another_org_routing_workflow(
    authed_client, db, test_org, test_user, v2
):
    other_org = Organization(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    db.add(OrganizationPermissionPolicy(organization_id=other_org.id, version=2))
    form_id, _slug = await _create_donor_form(authed_client)
    foreign = AutomationWorkflow(
        organization_id=other_org.id,
        name="Foreign routing",
        scope="org",
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[],
        condition_logic="AND",
        actions=form_intake_service._default_intake_routing_actions(
            db.get(Form, uuid.UUID(form_id))
        ),
        is_enabled=False,
        is_system_workflow=True,
        system_key=f"shared_intake_routing:{form_id}",
    )
    db.add(foreign)
    db.commit()

    republished = await authed_client.post(f"/forms/{form_id}/publish")
    assert republished.status_code == 200, republished.text

    db.refresh(foreign)
    assert foreign.execution_authority is None
    assert foreign.trigger_config == {"form_id": form_id}
    assert foreign.is_enabled is False
    _assert_system_grant(db, _routing(db, test_org.id, form_id))


@pytest.mark.asyncio
async def test_edit_voids_the_system_grant_and_republish_does_not_restore_it(
    authed_client, db, test_org, v2
):
    form_id, slug = await _create_donor_form(authed_client)
    workflow = _routing(db, test_org.id, form_id)
    grant = dict(workflow.execution_authority)
    workflow.conditions = [{"field": "source_mode", "operator": "equals", "value": "shared"}]
    db.commit()

    with pytest.raises(authority.WorkflowAuthorityError):
        authority.execution_snapshot(db, workflow)
    republished = await authed_client.post(f"/forms/{form_id}/publish")
    assert republished.status_code == 200, republished.text

    db.refresh(workflow)
    assert workflow.execution_authority == grant
    assert workflow.conditions == [
        {"field": "source_mode", "operator": "equals", "value": "shared"}
    ]
    response = await _submit_donor_form(authed_client, slug=slug, email="voided@example.com")
    assert response.status_code == 200, response.text
    (execution,) = _executions(db, workflow)
    assert execution.status == WorkflowExecutionStatus.SKIPPED.value


@pytest.mark.asyncio
async def test_republish_keeps_an_admin_grant_and_a_paused_workflow(
    authed_client, db, test_org, test_user, v2
):
    form_id, _slug = await _create_donor_form(authed_client)
    workflow = _routing(db, test_org.id, form_id)
    workflow = workflow_service.update_workflow(
        db,
        workflow,
        test_user.id,
        WorkflowUpdate(
            conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}]
        ),
    )
    admin_grant = dict(workflow.execution_authority)
    assert admin_grant["authorized_by_user_id"] == str(test_user.id)
    workflow.is_enabled = False
    db.commit()

    republished = await authed_client.post(f"/forms/{form_id}/publish")
    assert republished.status_code == 200, republished.text

    db.refresh(workflow)
    assert workflow.is_enabled is False
    assert workflow.execution_authority == admin_grant
    authority.execution_snapshot(db, workflow)


@pytest.mark.asyncio
async def test_republish_does_not_enable_a_paused_generated_workflow(
    authed_client, db, test_org, v2
):
    form_id, _slug = await _create_donor_form(authed_client)
    workflow = _routing(db, test_org.id, form_id)
    workflow.is_enabled = False
    db.commit()

    republished = await authed_client.post(f"/forms/{form_id}/publish")
    assert republished.status_code == 200, republished.text

    db.refresh(workflow)
    assert workflow.is_enabled is False
    authority.execution_snapshot(db, workflow)
    assert len(_system_grants(db, workflow)) == 1


@pytest.mark.asyncio
async def test_noop_builder_save_keeps_the_generated_digest(authed_client, db, test_org, v2):
    form_id, _slug = await _create_donor_form(authed_client)
    workflow = _routing(db, test_org.id, form_id)
    digest = authority.configuration_digest(workflow)

    response = await authed_client.patch(
        f"/workflows/{workflow.id}",
        json={
            "trigger_config": {"form_id": form_id},
            "conditions": [],
            "condition_logic": "AND",
            "actions": workflow.actions,
        },
    )
    assert response.status_code == 200, response.text

    db.refresh(workflow)
    assert authority.configuration_digest(workflow) == digest


@pytest.mark.asyncio
async def test_v1_publish_issues_no_grant(authed_client, db, test_org):
    form_id, _slug = await _create_donor_form(authed_client)
    workflow = _routing(db, test_org.id, form_id)

    assert workflow.execution_authority is None
    assert workflow.is_enabled is True
    assert _system_grants(db, workflow) == []
