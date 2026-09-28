"""Generated intake routing must route donors like the donor fixture and survive republish.

Republishing never re-enables a paused routing workflow; only a new one starts enabled.
"""

import json
import uuid
from pathlib import Path

import pytest

from app.core.config import settings
from app.db.models import AutomationWorkflow, Donor, FormSubmission, IntakeLead, Job
from tests.test_hosted_donor_forms import _create_donor_form, _submit_donor_form

DONOR_DEFAULT_ACTIONS = [
    {"action_type": "auto_match_submission", "requires_approval": False},
    {
        "action_type": "create_intake_lead",
        "source": "website",
        "auto_promote": True,
        "requires_approval": False,
    },
]


@pytest.fixture(autouse=True)
def _local_unscanned_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)


def _routing_workflow(db, org_id, form_id) -> AutomationWorkflow:
    return (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.system_key == f"shared_intake_routing:{form_id}",
        )
        .one()
    )


def _fixture_actions() -> list[dict]:
    path = Path(__file__).resolve().parents[3] / "scripts/fixtures/donor-intake-workflow.json"
    return json.loads(path.read_text())["actions"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["egg_donor", "sperm_donor"])
async def test_generated_donor_routing_matches_fixture_and_creates_donor(
    authed_client, db, test_org, kind
):
    from app.jobs.handlers.form_submissions import process_donor_intake_promote

    form_id, slug = await _create_donor_form(authed_client, lead_kind=kind)
    workflow = _routing_workflow(db, test_org.id, form_id)
    assert workflow.actions == DONOR_DEFAULT_ACTIONS
    assert workflow.actions == _fixture_actions()
    assert workflow.subject_type == "form_submission"
    assert workflow.is_enabled is True

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
async def test_republish_keeps_admin_edits_and_disabled_routing(authed_client, db, test_org):
    form_id, _ = await _create_donor_form(authed_client)
    workflow = _routing_workflow(db, test_org.id, form_id)
    edited_actions = [
        {"action_type": "auto_match_submission", "requires_approval": False},
        {"action_type": "create_intake_lead", "requires_approval": True},
    ]
    workflow.actions = edited_actions
    workflow.conditions = [{"field": "source_mode", "operator": "equals", "value": "shared"}]
    workflow.is_enabled = False
    db.commit()

    republished = await authed_client.post(f"/forms/{form_id}/publish")
    assert republished.status_code == 200, republished.text

    db.refresh(workflow)
    assert workflow.actions == edited_actions
    assert workflow.conditions == [
        {"field": "source_mode", "operator": "equals", "value": "shared"}
    ]
    assert workflow.is_enabled is False


@pytest.mark.asyncio
async def test_republish_upgrades_unedited_legacy_donor_routing(authed_client, db, test_org):
    form_id, _ = await _create_donor_form(authed_client)
    workflow = _routing_workflow(db, test_org.id, form_id)
    workflow.actions = [{"action_type": "create_intake_lead", "requires_approval": True}]
    db.commit()

    republished = await authed_client.post(f"/forms/{form_id}/publish")
    assert republished.status_code == 200, republished.text

    db.refresh(workflow)
    assert workflow.actions == DONOR_DEFAULT_ACTIONS


@pytest.mark.asyncio
async def test_surrogate_subject_form_workflow_does_not_suppress_routing_repair(
    authed_client, db, test_org, test_user
):
    """CRIT-5: a builder workflow saved with subject 'surrogate' never runs for submissions."""
    form_id, _ = await _create_donor_form(authed_client)
    db.delete(_routing_workflow(db, test_org.id, form_id))
    db.add(
        AutomationWorkflow(
            organization_id=test_org.id,
            name=f"Builder form workflow {uuid.uuid4().hex[:6]}",
            subject_type="surrogate",
            trigger_type="form_submitted",
            trigger_config={"form_id": form_id},
            conditions=[],
            condition_logic="AND",
            actions=[{"action_type": "auto_match_submission"}],
            is_enabled=True,
            scope="org",
            owner_user_id=None,
            created_by_user_id=test_user.id,
        )
    )
    db.commit()

    republished = await authed_client.post(f"/forms/{form_id}/publish")
    assert republished.status_code == 200, republished.text

    routing = _routing_workflow(db, test_org.id, form_id)
    assert routing.is_enabled is True
    assert routing.actions == DONOR_DEFAULT_ACTIONS


@pytest.mark.asyncio
async def test_enabled_form_submission_workflow_still_suppresses_generated_routing(
    authed_client, db, test_org, test_user
):
    form_id, _ = await _create_donor_form(authed_client)
    routing = _routing_workflow(db, test_org.id, form_id)
    routing.is_enabled = False
    db.add(
        AutomationWorkflow(
            organization_id=test_org.id,
            name=f"Donor routing {uuid.uuid4().hex[:6]}",
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={"form_id": form_id},
            conditions=[],
            condition_logic="AND",
            actions=DONOR_DEFAULT_ACTIONS,
            is_enabled=True,
            scope="org",
            owner_user_id=None,
            created_by_user_id=test_user.id,
        )
    )
    db.commit()

    republished = await authed_client.post(f"/forms/{form_id}/publish")
    assert republished.status_code == 200, republished.text

    db.refresh(routing)
    assert routing.is_enabled is False


@pytest.mark.asyncio
async def test_other_org_workflow_does_not_suppress_routing(authed_client, db, test_org):
    from app.db.models import Organization

    form_id, _ = await _create_donor_form(authed_client)
    db.delete(_routing_workflow(db, test_org.id, form_id))
    other_org = Organization(name="Other agency", slug=f"routing-{uuid.uuid4().hex}")
    db.add(other_org)
    db.flush()
    db.add(
        AutomationWorkflow(
            organization_id=other_org.id,
            name="Foreign routing",
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={"form_id": form_id},
            conditions=[],
            condition_logic="AND",
            actions=DONOR_DEFAULT_ACTIONS,
            is_enabled=True,
            scope="org",
            owner_user_id=None,
        )
    )
    db.commit()

    republished = await authed_client.post(f"/forms/{form_id}/publish")
    assert republished.status_code == 200, republished.text

    assert _routing_workflow(db, test_org.id, form_id).is_enabled is True
