"""Workflow templates carry exact donor subjects and enforce donor access."""

import uuid

import pytest

from app.core.permissions import PermissionKey
from app.db.enums import WorkflowTriggerType
from app.db.models import WorkflowTemplate
from app.schemas.workflow import WorkflowCreate
from app.services import permission_service, template_service, workflow_service


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


def _deny_donor_view(monkeypatch):
    original_check = permission_service.check_permission

    def deny(db, org_id, user_id, role, permission):
        if permission in {
            PermissionKey.DONORS_VIEW.value,
            PermissionKey.DONORS_EDIT.value,
        }:
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
async def test_create_template_donor_trigger_requires_explicit_subject(
    authed_client, db, test_org
):
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
    donor_template = _insert_template(
        db,
        test_org.id,
        test_user.id,
        subject_type="egg_donor",
        trigger_type="donor_created",
    )
    db.commit()

    _deny_donor_view(monkeypatch)

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

    assert module.LEGACY_TRIGGER_SUBJECT_TYPES == workflow_service.LEGACY_TRIGGER_SUBJECT_TYPES
    assert set(module.DONOR_ONLY_TRIGGER_TYPES) == template_service.DONOR_ONLY_TRIGGER_TYPES
