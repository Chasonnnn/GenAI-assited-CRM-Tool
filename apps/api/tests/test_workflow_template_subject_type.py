"""Workflow templates carry exact donor subjects and enforce donor access."""

import uuid

import pytest
from sqlalchemy import event

from app.core.permissions import PermissionKey
from app.db.enums import WorkflowTriggerType
from app.db.models import Form, Organization, User, WorkflowTemplate
from app.schemas.workflow import WorkflowCreate
from app.services import permission_service, template_service, workflow_access, workflow_service


def _create_donor_workflow(db, org_id, user_id, subject_type: str):
    return workflow_service.create_workflow(
        db,
        org_id,
        user_id,
        WorkflowCreate(
            name=f"Donor workflow {subject_type} {uuid.uuid4().hex[:8]}",
            scope="org",
            subject_type=subject_type,
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            trigger_config={},
            actions=[{"action_type": "add_note", "content": "Welcome"}],
        ),
    )


def _insert_template(db, org_id, user_id, **overrides) -> WorkflowTemplate:
    values = {
        "id": uuid.uuid4(),
        "name": f"Template {uuid.uuid4().hex[:8]}",
        "description": "Subject-type test template",
        "icon": "template",
        "category": "general",
        "subject_type": None,
        "trigger_type": "surrogate_created",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [{"action_type": "add_note", "content": "Hello"}],
        "is_global": False,
        "organization_id": org_id,
        "created_by_user_id": user_id,
    }
    values.update(overrides)
    template = WorkflowTemplate(**values)
    db.add(template)
    db.flush()
    return template


def _insert_form(db, org_id, lead_kind: str) -> Form:
    form = Form(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=f"{lead_kind} form {uuid.uuid4().hex[:8]}",
        lead_kind=lead_kind,
        status="published",
    )
    db.add(form)
    db.flush()
    return form


def _deny_donor_permissions(monkeypatch, *denied_permissions: PermissionKey):
    original_check = permission_service.check_permission
    denied_values = {permission.value for permission in denied_permissions}

    def deny(db, org_id, user_id, role, permission):
        if permission in denied_values:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny)


@pytest.mark.asyncio
@pytest.mark.parametrize("subject_type", ["egg_donor", "sperm_donor"])
async def test_template_roundtrip_preserves_exact_donor_subject(
    authed_client, db, test_org, test_user, subject_type
):
    workflow = _create_donor_workflow(db, test_org.id, test_user.id, subject_type)

    created = await authed_client.post(
        "/templates/from-workflow",
        json={
            "workflow_id": str(workflow.id),
            "name": f"Donor template {subject_type} {uuid.uuid4().hex[:8]}",
            "description": "Donor onboarding",
        },
    )
    assert created.status_code == 200, created.text
    template_body = created.json()
    assert template_body["subject_type"] == subject_type

    detail = await authed_client.get(f"/templates/{template_body['id']}")
    assert detail.status_code == 200
    assert detail.json()["subject_type"] == subject_type

    used = await authed_client.post(
        f"/templates/{template_body['id']}/use",
        json={"name": f"From template {uuid.uuid4().hex[:8]}", "is_enabled": False},
    )
    assert used.status_code == 200, used.text
    assert used.json()["subject_type"] == subject_type
    assert used.json()["trigger_type"] == "donor_created"


@pytest.mark.asyncio
async def test_create_template_donor_trigger_requires_explicit_subject(authed_client, db, test_org):
    payload = {
        "name": f"Donor stage template {uuid.uuid4().hex[:8]}",
        "trigger_type": "donor_stage_changed",
        "trigger_config": {},
        "actions": [{"action_type": "add_note", "content": "Stage moved"}],
    }
    denied = await authed_client.post("/templates", json=payload)
    assert denied.status_code == 400
    assert "explicit subject type" in denied.json()["detail"]

    accepted = await authed_client.post(
        "/templates", json={**payload, "subject_type": "sperm_donor"}
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["subject_type"] == "sperm_donor"
    stored = db.get(WorkflowTemplate, uuid.UUID(accepted.json()["id"]))
    assert stored.subject_type == "sperm_donor"


@pytest.mark.asyncio
async def test_legacy_donor_template_requires_repair_never_guesses(
    authed_client, db, test_org, test_user
):
    legacy = _insert_template(
        db,
        test_org.id,
        test_user.id,
        subject_type=None,
        trigger_type="donor_created",
    )
    db.commit()

    used = await authed_client.post(
        f"/templates/{legacy.id}/use",
        json={"name": "Repair required", "is_enabled": False},
    )
    assert used.status_code == 400
    assert "needs repair" in used.json()["detail"]
    assert db.get(WorkflowTemplate, legacy.id).usage_count == 0


@pytest.mark.asyncio
async def test_legacy_surrogate_template_keeps_legacy_subject_fallback(
    authed_client, db, test_org, test_user
):
    legacy = _insert_template(db, test_org.id, test_user.id, subject_type=None)
    db.commit()

    used = await authed_client.post(
        f"/templates/{legacy.id}/use",
        json={"name": f"Legacy surrogate {uuid.uuid4().hex[:8]}", "is_enabled": False},
    )
    assert used.status_code == 200, used.text
    assert used.json()["subject_type"] == "surrogate"
    assert db.get(WorkflowTemplate, legacy.id).usage_count == 1


@pytest.mark.asyncio
async def test_donor_templates_denied_without_donor_permissions(
    authed_client, db, test_org, test_user, monkeypatch
):
    donor_workflow = _create_donor_workflow(db, test_org.id, test_user.id, "egg_donor")
    donor_form_workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Donor form workflow {uuid.uuid4().hex[:8]}",
            scope="org",
            subject_type="form_submission",
            trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
            trigger_config={"lead_kind": "egg_donor"},
            actions=[{"action_type": "add_note", "content": "Welcome"}],
        ),
    )
    donor_template = _insert_template(
        db,
        test_org.id,
        test_user.id,
        subject_type="egg_donor",
        trigger_type="donor_created",
    )
    db.commit()

    _deny_donor_permissions(
        monkeypatch,
        PermissionKey.DONORS_VIEW,
        PermissionKey.DONORS_EDIT,
    )

    listed = await authed_client.get("/templates")
    assert listed.status_code == 200
    assert str(donor_template.id) not in {item["id"] for item in listed.json()}

    detail = await authed_client.get(f"/templates/{donor_template.id}")
    assert detail.status_code == 403

    used = await authed_client.post(
        f"/templates/{donor_template.id}/use",
        json={"name": "Denied donor use", "is_enabled": False},
    )
    assert used.status_code == 403

    from_workflow = await authed_client.post(
        "/templates/from-workflow",
        json={"workflow_id": str(donor_workflow.id), "name": "Denied donor template"},
    )
    assert from_workflow.status_code == 403

    from_donor_form_workflow = await authed_client.post(
        "/templates/from-workflow",
        json={
            "workflow_id": str(donor_form_workflow.id),
            "name": "Denied donor form template",
        },
    )
    assert from_donor_form_workflow.status_code == 403

    created = await authed_client.post(
        "/templates",
        json={
            "name": "Denied donor create",
            "subject_type": "egg_donor",
            "trigger_type": "donor_created",
            "actions": [{"action_type": "add_note", "content": "Hi"}],
        },
    )
    assert created.status_code == 403

    configured_donor = await authed_client.post(
        "/templates",
        json={
            "name": "Denied configured donor create",
            "subject_type": "form_submission",
            "trigger_type": "form_submitted",
            "trigger_config": {"lead_kind": "sperm_donor"},
            "actions": [{"action_type": "add_note", "content": "Hi"}],
        },
    )
    assert configured_donor.status_code == 403

    missing_form_with_surrogate_hint = await authed_client.post(
        "/templates",
        json={
            "name": "Denied unresolved form create",
            "subject_type": "form_submission",
            "trigger_type": "form_submitted",
            "trigger_config": {
                "form_id": str(uuid.uuid4()),
                "lead_kind": "surrogate",
            },
            "actions": [{"action_type": "add_note", "content": "Hi"}],
        },
    )
    assert missing_form_with_surrogate_hint.status_code == 403


@pytest.mark.asyncio
async def test_donor_authorized_template_list_skips_effective_subject_resolution(
    authed_client, db, test_org, test_user, monkeypatch
):
    template = _insert_template(
        db,
        test_org.id,
        test_user.id,
        subject_type="egg_donor",
        trigger_type="donor_created",
    )
    db.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("authorized template list should not resolve effective subjects")

    monkeypatch.setattr(
        template_service,
        "get_templates_effective_subject_types",
        fail_if_called,
    )

    listed = await authed_client.get("/templates")
    assert listed.status_code == 200
    assert str(template.id) in {item["id"] for item in listed.json()}


@pytest.mark.asyncio
async def test_template_from_workflow_rejects_another_users_personal_workflow(
    authed_client, db, test_org, monkeypatch
):
    owner = User(
        id=uuid.uuid4(),
        email=f"personal-workflow-owner-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Personal Workflow Owner",
        token_version=1,
        is_active=True,
    )
    db.add(owner)
    db.flush()
    personal_workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        owner.id,
        WorkflowCreate(
            name="Private personal workflow",
            scope="personal",
            trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
            actions=[{"action_type": "add_note", "content": "Private config"}],
        ),
    )

    monkeypatch.setattr(
        workflow_access,
        "_has_manage_automation",
        lambda db, session: False,
    )

    response = await authed_client.post(
        "/templates/from-workflow",
        json={
            "workflow_id": str(personal_workflow.id),
            "name": "Cloned private workflow",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot view this workflow"
    assert (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.organization_id == test_org.id,
            WorkflowTemplate.name == "Cloned private workflow",
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_indirect_donor_template_reads_and_delete_fail_closed(
    authed_client, db, test_org, test_user, monkeypatch
):
    foreign_org = Organization(
        id=uuid.uuid4(),
        name="Foreign template org",
        slug=f"foreign-template-{uuid.uuid4().hex[:8]}",
    )
    db.add(foreign_org)
    db.flush()
    donor_form = _insert_form(db, test_org.id, "egg_donor")
    surrogate_form = _insert_form(db, test_org.id, "surrogate")
    foreign_form = _insert_form(db, foreign_org.id, "sperm_donor")

    protected_templates = [
        _insert_template(
            db,
            test_org.id,
            test_user.id,
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={"lead_kind": "egg_donor"},
        ),
        _insert_template(
            db,
            test_org.id,
            test_user.id,
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={"form_id": str(donor_form.id)},
        ),
        _insert_template(
            db,
            test_org.id,
            test_user.id,
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={"form_id": str(uuid.uuid4())},
        ),
        _insert_template(
            db,
            test_org.id,
            test_user.id,
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={
                "form_id": str(uuid.uuid4()),
                "lead_kind": "surrogate",
            },
        ),
        _insert_template(
            db,
            test_org.id,
            test_user.id,
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={"form_id": str(foreign_form.id)},
        ),
        _insert_template(
            db,
            test_org.id,
            test_user.id,
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={
                "form_id": str(foreign_form.id),
                "lead_kind": "surrogate",
            },
        ),
        _insert_template(
            db,
            test_org.id,
            test_user.id,
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={
                "form_id": str(surrogate_form.id),
                "lead_kind": "egg_donor",
            },
        ),
        _insert_template(
            db,
            test_org.id,
            test_user.id,
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={
                "form_id": str(donor_form.id),
                "lead_kind": "surrogate",
            },
        ),
        _insert_template(
            db,
            test_org.id,
            test_user.id,
            subject_type=None,
            trigger_type="donor_created",
        ),
    ]
    surrogate_template = _insert_template(
        db,
        test_org.id,
        test_user.id,
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"form_id": str(surrogate_form.id)},
    )
    db.commit()

    _deny_donor_permissions(
        monkeypatch,
        PermissionKey.DONORS_VIEW,
        PermissionKey.DONORS_EDIT,
    )

    statements = []

    def capture_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.lower().split()))

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_statement)
    try:
        listed = await authed_client.get("/templates")
    finally:
        event.remove(engine, "before_cursor_execute", capture_statement)
    assert listed.status_code == 200
    form_reads = [statement for statement in statements if " from forms " in statement]
    assert len(form_reads) == 1
    assert "forms.organization_id =" in form_reads[0]
    listed_ids = {item["id"] for item in listed.json()}
    assert str(surrogate_template.id) in listed_ids
    assert not {str(template.id) for template in protected_templates} & listed_ids

    for template in protected_templates:
        detail = await authed_client.get(f"/templates/{template.id}")
        assert detail.status_code == 403
        deleted = await authed_client.delete(f"/templates/{template.id}")
        assert deleted.status_code == 403
        assert db.get(WorkflowTemplate, template.id) is not None

    surrogate_detail = await authed_client.get(f"/templates/{surrogate_template.id}")
    assert surrogate_detail.status_code == 200
    surrogate_deleted = await authed_client.delete(f"/templates/{surrogate_template.id}")
    assert surrogate_deleted.status_code == 200


@pytest.mark.asyncio
async def test_indirect_donor_template_mutations_require_edit_permission(
    authed_client, db, test_org, test_user, monkeypatch
):
    donor_workflow = _create_donor_workflow(db, test_org.id, test_user.id, "sperm_donor")
    template = _insert_template(
        db,
        test_org.id,
        test_user.id,
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"lead_kind": "sperm_donor"},
    )
    db.commit()

    _deny_donor_permissions(monkeypatch, PermissionKey.DONORS_EDIT)

    listed = await authed_client.get("/templates")
    assert str(template.id) in {item["id"] for item in listed.json()}
    assert (await authed_client.get(f"/templates/{template.id}")).status_code == 200

    created = await authed_client.post(
        "/templates",
        json={
            "name": "View-only donor create",
            "subject_type": "form_submission",
            "trigger_type": "form_submitted",
            "trigger_config": {"lead_kind": "sperm_donor"},
            "actions": [{"action_type": "add_note", "content": "Hi"}],
        },
    )
    assert created.status_code == 403
    derived = await authed_client.post(
        "/templates/from-workflow",
        json={"workflow_id": str(donor_workflow.id), "name": "View-only donor derive"},
    )
    assert derived.status_code == 403
    used = await authed_client.post(
        f"/templates/{template.id}/use",
        json={"name": "View-only donor use", "is_enabled": False},
    )
    assert used.status_code == 403
    deleted = await authed_client.delete(f"/templates/{template.id}")
    assert deleted.status_code == 403
    assert db.get(WorkflowTemplate, template.id) is not None


def test_seeded_global_templates_have_explicit_subject(db):
    template_service.seed_global_templates(db)
    seeded_names = [
        "Welcome New Lead",
        "Follow Up After Inactivity",
        "Owner Assignment Notification",
        "Status Change Alert",
        "Task Due Reminder",
    ]
    seeded = (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.is_global.is_(True),
            WorkflowTemplate.name.in_(seeded_names),
        )
        .all()
    )
    assert len(seeded) == len(seeded_names)
    assert all(template.subject_type == "surrogate" for template in seeded)


def test_migration_backfill_map_matches_service_contract():
    import importlib.util
    from pathlib import Path

    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260920_0100_workflow_template_subject_type.py"
    )
    spec = importlib.util.spec_from_file_location("wf_template_subject_mig", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    historical = dict(module.LEGACY_TRIGGER_SUBJECT_TYPES)
    historical["match_declined"] = historical.pop("match_rejected")
    historical["match_cancelled"] = "match"
    assert historical == workflow_service.LEGACY_TRIGGER_SUBJECT_TYPES
    assert set(module.DONOR_ONLY_TRIGGER_TYPES) == template_service.DONOR_ONLY_TRIGGER_TYPES
