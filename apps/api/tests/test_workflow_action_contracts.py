"""Workflow actions preserve actor, subject, and event transaction contracts."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.constants import SYSTEM_USER_ID
from app.db.models import Donor, Surrogate
from app.services import donor_service, note_service, task_service, workflow_execution_authority
from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter


def subject(kind):
    values = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "owner_type": "user",
        "owner_id": uuid4(),
    }
    if kind == "surrogate":
        return Surrogate(**values, created_by_user_id=uuid4())
    return Donor(**values, donor_type="egg" if kind == "egg_donor" else "sperm")


def dispatch(db, record, kind, action, **kwargs):
    db.query.return_value.filter.return_value.first.return_value = record
    db.query.return_value.filter.return_value.populate_existing.return_value.first.return_value = (
        record
    )
    return DefaultWorkflowDomainAdapter().execute_action(
        db,
        action,
        record,
        "surrogate" if kind == "surrogate" else "donor",
        event_id=kwargs.pop("event_id", uuid4()),
        depth=2,
        subject_type=kind,
        subject_id=record.id,
        **kwargs,
    )


@pytest.mark.parametrize("kind", ["surrogate", "egg_donor", "sperm_donor"])
@pytest.mark.parametrize("scope", ["personal", "org"])
def test_task_action_uses_execution_actor_and_exact_subject(monkeypatch, kind, scope):
    db = Mock()
    record = subject(kind)
    actor_id = uuid4()
    task_id = uuid4()
    create = Mock(return_value=Mock(id=task_id))
    monkeypatch.setattr(task_service, "create_task", create)
    monkeypatch.setattr(workflow_execution_authority, "enabled", lambda *_: True)

    result = dispatch(
        db,
        record,
        kind,
        {"action_type": "create_task", "title": "Review", "assignee": "owner"},
        workflow_scope=scope,
        workflow_owner_id=actor_id,
        workflow_creator_user_id=uuid4(),
        workflow_execution_id=uuid4(),
    )

    assert result == {
        "success": True,
        "task_id": str(task_id),
        "description": "Created task: Review",
        "action_type": "create_task",
    }
    arguments = create.call_args.kwargs
    assert arguments["org_id"] == record.organization_id
    assert arguments["user_id"] == (actor_id if scope == "personal" else SYSTEM_USER_ID)
    assert arguments["data"].owner_id == record.owner_id
    assert arguments["data"].surrogate_id == (record.id if kind == "surrogate" else None)
    assert arguments["data"].donor_id == (record.id if kind != "surrogate" else None)
    db.commit.assert_not_called()


@pytest.mark.parametrize("kind", ["surrogate", "egg_donor", "sperm_donor"])
def test_note_action_preserves_execution_author_and_outer_transaction(monkeypatch, kind):
    db = Mock()
    record = subject(kind)
    actor_id, note_id = uuid4(), uuid4()
    create = Mock(return_value=Mock(id=note_id))
    monkeypatch.setattr(note_service, "create_note", create)
    monkeypatch.setattr(workflow_execution_authority, "enabled", lambda *_: True)

    result = dispatch(
        db,
        record,
        kind,
        {"action_type": "add_note", "content": "Reviewed"},
        workflow_scope="personal",
        workflow_owner_id=actor_id,
        workflow_execution_id=uuid4(),
    )

    assert result["success"] is True
    assert result["note_id"] == str(note_id)
    create.assert_called_once_with(
        db,
        org_id=record.organization_id,
        entity_type="surrogate" if kind == "surrogate" else "donor",
        entity_id=record.id,
        content="Reviewed",
        author_id=actor_id,
        commit=False,
        emit_events=False,
    )
    db.commit.assert_not_called()


@pytest.mark.parametrize("kind", ["surrogate", "egg_donor", "sperm_donor"])
def test_assignment_action_preserves_event_and_domain_boundary(monkeypatch, kind):
    db = Mock()
    record = subject(kind)
    old_owner_id, new_owner_id, event_id = record.owner_id, uuid4(), uuid4()
    callback = Mock()

    def update(_db, donor, _actor, data, **kwargs):
        donor.owner_type = data.owner_type
        donor.owner_id = data.owner_id
        return donor

    update_donor = Mock(side_effect=update)
    monkeypatch.setattr(donor_service, "update_donor", update_donor)
    result = dispatch(
        db,
        record,
        kind,
        {
            "action_type": "assign_surrogate" if kind == "surrogate" else "assign_donor",
            "owner_type": "user",
            "owner_id": str(new_owner_id),
        },
        event_id=event_id,
        trigger_callback=callback,
    )

    assert result["success"] is True
    assert record.owner_id == new_owner_id
    callback.assert_called_once()
    event = callback.call_args.kwargs
    assert event["org_id"] == record.organization_id
    assert event["event_id"] == event_id
    assert event["depth"] == 3
    assert event["event_data"]["old_owner_id"] == str(old_owner_id)
    assert event["event_data"]["new_owner_id"] == str(new_owner_id)
    if kind == "surrogate":
        db.commit.assert_called_once()
        update_donor.assert_not_called()
    else:
        assert event["subject_type"] == kind
        assert event["subject_id"] == record.id
        assert update_donor.call_args.kwargs == {"emit_workflow_events": False}
        db.commit.assert_not_called()
