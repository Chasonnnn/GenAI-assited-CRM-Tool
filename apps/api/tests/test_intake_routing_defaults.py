"""Kind defaults, donor promotion, and publish isolation for module routing."""

import uuid

import pytest

from app.core.config import settings
from app.db.models import AutomationWorkflow, Donor, FormSubmission, IntakeLead, Job, Organization
from tests.test_hosted_donor_forms import _create_donor_form, _submit_donor_form


@pytest.fixture(autouse=True)
def _local_unscanned_storage(monkeypatch, tmp_path):
    from app.core.rate_limit import limiter

    limiter.reset()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["egg_donor", "sperm_donor"])
async def test_module_donor_defaults_create_donor(authed_client, db, test_org, kind):
    from app.jobs.handlers.form_submissions import process_donor_intake_promote

    form_id, slug = await _create_donor_form(authed_client, lead_kind=kind)
    routing = await authed_client.get(f"/forms/{form_id}/routing")
    assert routing.status_code == 200, routing.text
    assert (
        routing.json().items()
        >= {
            "lead_kind": kind,
            "exact_match": "auto",
            "no_match": "auto",
            "lead_source": "website",
            "auto_create_donor": True,
        }.items()
    )
    assert (
        db.query(AutomationWorkflow)
        .filter_by(organization_id=test_org.id, system_key=f"custom_notice:{form_id}")
        .count()
        == 0
    )

    response = await _submit_donor_form(authed_client, slug=slug, email="default@example.com")
    assert response.status_code == 200, response.text
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    lead = db.get(IntakeLead, submission.intake_lead_id)
    assert lead is not None
    assert lead.source == "website"
    assert (lead.source_metadata or {}).get("auto_create_donor") is True
    job = (
        db.query(Job).filter_by(organization_id=test_org.id, job_type="donor_intake_promote").one()
    )
    await process_donor_intake_promote(db, job)
    db.refresh(submission)
    donor = db.get(Donor, submission.donor_id)
    assert donor is not None
    assert donor.donor_type == kind.removesuffix("_donor")
    assert donor.source == "website"


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("foreign", [False, True])
async def test_publish_preserves_existing_workflows(
    authed_client, db, test_org, test_user, enabled, foreign
):
    form_id, _ = await _create_donor_form(authed_client)
    org_id = test_org.id
    if foreign:
        org = Organization(name="Other agency", slug=uuid.uuid4().hex)
        db.add(org)
        db.flush()
        org_id = org.id
    actions = [{"action_type": "send_notification", "title": "Notice", "requires_approval": True}]
    conditions = [{"field": "source_mode", "operator": "equals", "value": "shared"}]
    grant = {"authorized_by_user_id": str(test_user.id)}
    workflow = AutomationWorkflow(
        organization_id=org_id,
        name="Existing notification",
        subject_type="form_submission",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=conditions,
        condition_logic="AND",
        actions=actions,
        is_enabled=enabled,
        scope="org",
        system_key=f"custom_notice:{form_id}",
        execution_authority=grant,
    )
    db.add(workflow)
    db.commit()
    saved = await authed_client.put(
        f"/forms/{form_id}/routing",
        json={
            "exact_match": "review",
            "no_match": "off",
            "lead_source": "form_embed",
            "auto_create_donor": False,
        },
    )
    assert saved.status_code == 200, saved.text
    response = await authed_client.post(f"/forms/{form_id}/publish")
    assert response.status_code == 200, response.text
    db.refresh(workflow)
    assert workflow.actions == actions
    assert workflow.conditions == conditions
    assert workflow.is_enabled is enabled
    assert workflow.execution_authority == grant
    routing = (await authed_client.get(f"/forms/{form_id}/routing")).json()
    assert {k: v for k, v in routing.items() if k != "updated_at"} == {
        k: v for k, v in saved.json().items() if k != "updated_at"
    }
    assert (
        db.query(AutomationWorkflow).filter_by(system_key=f"custom_notice:{form_id}").count() == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["surrogate", "egg_donor", "sperm_donor"])
async def test_new_forms_and_kind_changes_reset_defaults(authed_client, kind):
    response = await authed_client.post("/forms", json={"name": "Kind defaults", "lead_kind": kind})
    assert response.status_code == 200, response.text
    form_id = response.json()["id"]
    expected = (
        ("review", "review", None, False)
        if kind == "surrogate"
        else ("auto", "auto", "website", True)
    )
    routing = (await authed_client.get(f"/forms/{form_id}/routing")).json()
    assert (
        tuple(routing[k] for k in ("exact_match", "no_match", "lead_source", "auto_create_donor"))
        == expected
    )
    for next_kind in ["egg_donor" if kind == "surrogate" else "surrogate", kind]:
        saved = await authed_client.put(
            f"/forms/{form_id}/routing",
            json={
                "exact_match": "review",
                "no_match": "off",
                "lead_source": "form_embed",
                "auto_create_donor": False,
            },
        )
        assert saved.status_code == 200, saved.text
        changed = await authed_client.patch(f"/forms/{form_id}", json={"lead_kind": next_kind})
        assert changed.status_code == 200, changed.text
        expected = (
            ("review", "review", None, False)
            if next_kind == "surrogate"
            else ("auto", "auto", "website", True)
        )
        routing = (await authed_client.get(f"/forms/{form_id}/routing")).json()
        assert (
            tuple(
                routing[k] for k in ("exact_match", "no_match", "lead_source", "auto_create_donor")
            )
            == expected
        )
