"""Intake action contracts exercised through the workflow dispatcher."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.db.models import FormSubmission, IntakeLead
from app.services import form_intake_service, workflow_execution_authority
from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter


def execute(db, action, entity, **kwargs):
    return DefaultWorkflowDomainAdapter().execute_action(
        db,
        action,
        entity,
        "intake_lead" if isinstance(entity, IntakeLead) else "form_submission",
        event_id=uuid4(),
        depth=2,
        **kwargs,
    )


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
def test_promotion_keeps_creator_and_record_specific_result(monkeypatch, kind):
    db = Mock()
    creator_id, record_id = uuid4(), uuid4()
    lead = IntakeLead(
        id=uuid4(),
        organization_id=uuid4(),
        created_by_user_id=creator_id,
        promoted_donor_id=record_id if kind == "donor" else None,
    )
    promote = Mock(return_value=(Mock(id=record_id), 3))
    monkeypatch.setattr(form_intake_service, "promote_intake_lead", promote)

    result = execute(
        db,
        {
            "action_type": "promote_intake_lead",
            "source": 42,
            "assign_to_user": "true",
            "is_priority": True,
        },
        lead,
        workflow_owner_id=uuid4(),
    )

    promote.assert_called_once_with(
        db=db,
        lead=lead,
        user_id=creator_id,
        source=None,
        is_priority=True,
        assign_to_user=None,
    )
    assert result == {
        "success": True,
        "description": f"Promoted intake lead to {kind}",
        f"{kind}_id": str(record_id),
        "linked_submission_count": 3,
        "action_type": "promote_intake_lead",
    }
    db.commit.assert_not_called()


@pytest.mark.parametrize("kind", ["surrogate", "donor", None])
def test_matching_preserves_linked_and_review_outcomes(monkeypatch, kind):
    db = Mock()
    record_id = uuid4()
    submission = FormSubmission(
        id=uuid4(),
        organization_id=uuid4(),
        donor_id=record_id if kind == "donor" else None,
        surrogate_id=record_id if kind == "surrogate" else None,
    )
    outcome = "linked" if kind else "ambiguous"
    match = Mock(return_value=(submission, outcome))
    monkeypatch.setattr(form_intake_service, "auto_match_submission", match)

    result = execute(db, {"action_type": "auto_match_submission"}, submission)

    match.assert_called_once_with(db=db, submission=submission)
    assert result == {
        "success": True,
        "description": f"Matched submission to existing {kind}"
        if kind
        else "Submission requires review after auto-match",
        "submission_id": str(submission.id),
        "match_status": outcome,
        **({f"{kind}_id": str(record_id)} if kind else {}),
        "action_type": "auto_match_submission",
    }
    db.commit.assert_not_called()


@pytest.mark.parametrize("auto_promote,created", [(True, True), ("true", False)])
def test_creation_preserves_execution_binding_and_skip_result(monkeypatch, auto_promote, created):
    db = Mock()
    execution_id = uuid4()
    submission = FormSubmission(id=uuid4(), organization_id=uuid4(), match_status="unmatched")
    lead = IntakeLead(id=uuid4()) if created else None
    create = Mock(return_value=(submission, lead))
    monkeypatch.setattr(form_intake_service, "create_intake_lead_for_submission", create)
    monkeypatch.setattr(workflow_execution_authority, "enabled", lambda *_: True)

    result = execute(
        db,
        {
            "action_type": "create_intake_lead",
            "source": "website",
            "auto_promote": auto_promote,
        },
        submission,
        workflow_execution_id=execution_id,
        workflow_creator_user_id=uuid4(),
    )

    create.assert_called_once_with(
        db=db,
        submission=submission,
        user_id=None,
        source="website",
        auto_promote=created,
        workflow_execution_id=execution_id,
    )
    assert result == {
        "success": True,
        "description": "Created intake lead from submission"
        if created
        else "Skipped intake lead creation",
        "submission_id": str(submission.id),
        "match_status": "unmatched",
        **({"intake_lead_id": str(lead.id)} if created else {}),
        "action_type": "create_intake_lead",
    }
    db.commit.assert_not_called()
