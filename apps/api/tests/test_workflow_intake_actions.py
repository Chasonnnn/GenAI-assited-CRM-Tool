"""Intake action contracts exercised through the workflow dispatcher."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.db.models import IntakeLead
from app.services import form_intake_service
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
