"""Intake workflow conditions read the linked record's stage and the lead's kind.

Form submissions and intake leads have no stage of their own. A stage condition
compares the current stage of the linked surrogate or donor; an unlinked source has
no stage, so only negative and empty operators match.
"""

from __future__ import annotations

import uuid

import pytest

from app.db.enums import WorkflowTriggerType
from app.db.models import IntakeLead, Organization, PipelineStage
from app.services.workflow_engine import engine
from tests.test_workflow_intake_record_updates import (
    _donor,
    _form,
    _intake_workflow,
    _stage,
    _submission,
    _surrogate,
)

NOTE = {"action_type": "add_note", "content": "Stage matched"}


def _condition(operator: str, *stages) -> dict[str, object]:
    value = [str(stage.id) for stage in stages] if operator in {"in", "not_in"} else None
    if operator in {"equals", "not_equals"}:
        value = str(stages[0].id)
    return {"field": "stage_id", "operator": operator, "value": value}


def _run_submission(db, workflow, submission):
    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="form_submission",
        entity_id=submission.id,
        subject_type="form_submission",
        subject_id=submission.id,
        event_data={"form_id": str(submission.form_id)},
    )
    assert execution is not None
    return execution.matched_conditions


def _run_lead(db, workflow, lead):
    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="intake_lead",
        entity_id=lead.id,
        subject_type="intake_lead",
        subject_id=lead.id,
        event_data={"lead_type": lead.lead_type},
    )
    assert execution is not None
    return execution.matched_conditions


def _lead(db, org_id, form, *, lead_type, surrogate_id=None, donor_id=None) -> IntakeLead:
    lead = IntakeLead(
        id=uuid.uuid4(),
        organization_id=org_id,
        form_id=form.id,
        source="shared_intake",
        lead_type=lead_type,
        full_name="Stage Condition Lead",
        status="promoted" if surrogate_id or donor_id else "pending_review",
        promoted_surrogate_id=surrogate_id,
        promoted_donor_id=donor_id,
    )
    db.add(lead)
    db.flush()
    return lead


@pytest.mark.parametrize(
    ("operator", "matched"),
    [("in", True), ("equals", True), ("not_in", False), ("not_equals", False)],
)
def test_submission_stage_condition_reads_the_linked_surrogate_stage(
    db, test_org, test_user, operator, matched
):
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    surrogate = _surrogate(db, test_org.id, test_user.id, contacted)
    form = _form(db, test_org.id, test_user.id, "surrogate")
    submission = _submission(db, test_org.id, form, surrogate_id=surrogate.id)
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        conditions=[_condition(operator, contacted)],
        actions=[NOTE],
    )

    assert _run_submission(db, workflow, submission) is matched


def test_submission_stage_condition_does_not_match_another_surrogate_stage(db, test_org, test_user):
    new_stage = _stage(db, test_org.id, "surrogate", "new_unread")
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    surrogate = _surrogate(db, test_org.id, test_user.id, new_stage)
    form = _form(db, test_org.id, test_user.id, "surrogate")
    submission = _submission(db, test_org.id, form, surrogate_id=surrogate.id)
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        conditions=[_condition("in", contacted)],
        actions=[NOTE],
    )

    assert _run_submission(db, workflow, submission) is False


@pytest.mark.parametrize(
    ("operator", "matched"),
    [
        ("in", False),
        ("equals", False),
        ("not_in", True),
        ("not_equals", True),
        ("is_empty", True),
        ("is_not_empty", False),
    ],
)
def test_unlinked_submission_has_no_stage(db, test_org, test_user, operator, matched):
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    form = _form(db, test_org.id, test_user.id, "surrogate")
    submission = _submission(db, test_org.id, form)
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        conditions=[_condition(operator, contacted)],
        actions=[NOTE],
    )

    assert _run_submission(db, workflow, submission) is matched


def test_submission_stage_condition_reads_the_linked_donor_stage(db, test_org, test_user):
    donor = _donor(db, test_org.id, test_user.id, "egg")
    form = _form(db, test_org.id, test_user.id, "egg_donor")
    submission = _submission(db, test_org.id, form, donor_id=donor.id)
    current = db.get(PipelineStage, donor.stage_id)
    contacted = _stage(db, test_org.id, "egg_donor", "contacted")

    matching = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        conditions=[_condition("in", current)],
        actions=[NOTE],
    )
    other = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        conditions=[_condition("in", contacted)],
        actions=[NOTE],
    )

    assert _run_submission(db, matching, submission) is True
    assert _run_submission(db, other, submission) is False


def test_donor_link_of_another_subtype_has_no_stage(db, test_org, test_user):
    sperm_donor = _donor(db, test_org.id, test_user.id, "sperm")
    form = _form(db, test_org.id, test_user.id, "egg_donor")
    submission = _submission(db, test_org.id, form, donor_id=sperm_donor.id)
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        conditions=[{"field": "stage_id", "operator": "is_empty"}],
        actions=[NOTE],
    )

    assert _run_submission(db, workflow, submission) is True


def test_link_to_another_org_record_has_no_stage(db, test_org, test_user):
    other_org = Organization(
        id=uuid.uuid4(), name="Other Stage Org", slug=f"other-stage-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    foreign_stage = _stage(db, other_org.id, "surrogate", "new_unread")
    foreign_surrogate = _surrogate(db, other_org.id, test_user.id, foreign_stage)
    form = _form(db, test_org.id, test_user.id, "surrogate")
    submission = _submission(db, test_org.id, form, surrogate_id=foreign_surrogate.id)
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        conditions=[{"field": "stage_id", "operator": "is_empty"}],
        actions=[NOTE],
    )

    assert _run_submission(db, workflow, submission) is True


@pytest.mark.parametrize("linked", ["surrogate", "donor", None])
def test_intake_lead_stage_condition_reads_the_promoted_record_stage(
    db, test_org, test_user, linked
):
    if linked == "donor":
        record = _donor(db, test_org.id, test_user.id, "sperm")
        current = db.get(PipelineStage, record.stage_id)
        form = _form(db, test_org.id, test_user.id, "sperm_donor")
        lead = _lead(db, test_org.id, form, lead_type="sperm_donor", donor_id=record.id)
    else:
        current = _stage(db, test_org.id, "surrogate", "contacted")
        form = _form(db, test_org.id, test_user.id, "surrogate")
        record = _surrogate(db, test_org.id, test_user.id, current) if linked else None
        lead = _lead(
            db, test_org.id, form, lead_type="surrogate", surrogate_id=record and record.id
        )
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
        subject_type="intake_lead",
        form=form,
        conditions=[_condition("in", current)],
        actions=[NOTE],
    )

    assert _run_lead(db, workflow, lead) is (linked is not None)


@pytest.mark.parametrize(("lead_type", "matched"), [("egg_donor", True), ("surrogate", False)])
def test_intake_lead_kind_condition_reads_the_lead_type(
    db, test_org, test_user, lead_type, matched
):
    form = _form(db, test_org.id, test_user.id, lead_type)
    lead = _lead(db, test_org.id, form, lead_type=lead_type)
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
        subject_type="intake_lead",
        conditions=[{"field": "lead_kind", "operator": "in", "value": ["egg_donor"]}],
        actions=[{"action_type": "send_notification", "title": "Lead", "recipients": "all_admins"}],
    )

    assert _run_lead(db, workflow, lead) is matched


@pytest.mark.asyncio
@pytest.mark.parametrize("linked", [True, False])
async def test_dry_run_reads_the_linked_record_stage(
    authed_client, db, test_org, test_user, linked
):
    contacted = _stage(db, test_org.id, "surrogate", "contacted")
    form = _form(db, test_org.id, test_user.id, "surrogate")
    surrogate = _surrogate(db, test_org.id, test_user.id, contacted) if linked else None
    submission = _submission(db, test_org.id, form, surrogate_id=surrogate and surrogate.id)
    workflow = _intake_workflow(
        db,
        test_org.id,
        test_user.id,
        form=form,
        conditions=[_condition("in", contacted)],
        actions=[NOTE],
    )
    db.commit()

    response = await authed_client.post(
        f"/workflows/{workflow.id}/test",
        json={"entity_id": str(submission.id), "entity_type": "form_submission"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conditions_matched"] is linked
    (evaluated,) = body["conditions_evaluated"]
    assert evaluated["actual"] == (str(contacted.id) if linked else "None")
