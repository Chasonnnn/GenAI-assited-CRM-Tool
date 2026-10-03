"""Per-trigger workflow condition fields and the fields they read at run time."""

from __future__ import annotations

import uuid

import pytest

from app.db.enums import WorkflowTriggerType
from app.db.models import EntityNote, WorkflowExecution
from app.schemas.surrogate import SurrogateCreate, SurrogateUpdate
from app.schemas.workflow import (
    APPOINTMENT_CONDITION_FIELDS,
    DONOR_ALLOWED_CONDITION_FIELDS,
    FORM_SUBMISSION_CONDITION_FIELDS,
    MATCH_CONDITION_FIELDS,
    SURROGATE_CONDITION_FIELDS,
    WorkflowCreate,
    WorkflowUpdate,
)
from app.services import surrogate_service, workflow_service, workflow_triggers


def _workflow(db, org_id, user_id, trigger_type, conditions, actions=None, **extra):
    return workflow_service.create_workflow(
        db,
        org_id,
        user_id,
        WorkflowCreate(
            name=f"{trigger_type.value} {uuid.uuid4()}",
            trigger_type=trigger_type,
            trigger_config=extra.pop("trigger_config", {}),
            conditions=conditions,
            actions=actions or [{"action_type": "send_notification", "title": "Workflow ran"}],
            **extra,
        ),
    )


@pytest.mark.parametrize(
    ("trigger_type", "subject_type", "expected"),
    [
        ("surrogate_created", "surrogate", SURROGATE_CONDITION_FIELDS),
        ("task_due", "surrogate", SURROGATE_CONDITION_FIELDS),
        ("note_added", "surrogate", SURROGATE_CONDITION_FIELDS),
        ("form_submitted", "surrogate", FORM_SUBMISSION_CONDITION_FIELDS),
        ("match_proposed", "surrogate", MATCH_CONDITION_FIELDS),
        ("appointment_no_show", "surrogate", APPOINTMENT_CONDITION_FIELDS),
        ("donor_created", "egg_donor", DONOR_ALLOWED_CONDITION_FIELDS),
        ("task_due", "egg_donor", DONOR_ALLOWED_CONDITION_FIELDS),
    ],
)
def test_condition_fields_follow_the_record_the_trigger_reads(trigger_type, subject_type, expected):
    assert workflow_service.condition_fields_for_trigger(trigger_type, subject_type) == expected


def test_retired_surrogate_fields_are_not_condition_fields():
    assert {"age", "bmi"}.isdisjoint(SURROGATE_CONDITION_FIELDS)


def test_create_rejects_condition_fields_from_another_record(db, test_org, test_user):
    with pytest.raises(ValueError, match="do not apply to match_proposed: is_priority"):
        _workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowTriggerType.MATCH_PROPOSED,
            [{"field": "is_priority", "operator": "equals", "value": True}],
        )

    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.MATCH_PROPOSED,
        [{"field": "match_kind", "operator": "equals", "value": "surrogate"}],
    )
    assert workflow.conditions[0]["field"] == "match_kind"


def test_update_revalidates_conditions_only_when_they_or_the_trigger_change(
    db, test_org, test_user
):
    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.SURROGATE_CREATED,
        [{"field": "is_priority", "operator": "equals", "value": True}],
    )
    # A condition field from an older field list stays stored until it is edited.
    workflow.conditions = [{"field": "bmi", "operator": "greater_than", "value": 30}]
    db.commit()

    renamed = workflow_service.update_workflow(
        db, workflow, test_user.id, WorkflowUpdate(name="Renamed workflow")
    )
    assert renamed.name == "Renamed workflow"

    with pytest.raises(ValueError, match="do not apply to match_proposed"):
        workflow_service.update_workflow(
            db,
            workflow,
            test_user.id,
            WorkflowUpdate(trigger_type=WorkflowTriggerType.MATCH_PROPOSED),
        )


def test_update_field_action_accepts_contact_status_values_only(db, test_org, test_user):
    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.SURROGATE_CREATED,
        [],
        actions=[{"action_type": "update_field", "field": "contact_status", "value": "reached"}],
    )
    assert workflow.actions[0]["value"] == "reached"

    with pytest.raises(ValueError, match="Contact status must be reached or unreached"):
        _workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowTriggerType.SURROGATE_CREATED,
            [],
            actions=[{"action_type": "update_field", "field": "contact_status", "value": "lost"}],
        )


def test_options_list_condition_fields_per_trigger(db, test_org, test_user):
    options = workflow_service.get_workflow_options(db, test_org.id, user_id=test_user.id)
    by_trigger = options.condition_fields_by_trigger
    assert by_trigger["match_proposed"] == sorted(MATCH_CONDITION_FIELDS)
    assert by_trigger["note_added"] == sorted(SURROGATE_CONDITION_FIELDS)
    assert "form_started" not in by_trigger
    assert "age" not in options.condition_fields


def test_note_trigger_conditions_read_the_subject_surrogate(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=SurrogateCreate(
            full_name="Condition Subject",
            email=f"condition-subject-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )
    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.NOTE_ADDED,
        [{"field": "is_priority", "operator": "equals", "value": True}],
    )

    def add_note() -> EntityNote:
        note = EntityNote(
            organization_id=test_org.id,
            entity_type="surrogate",
            entity_id=surrogate.id,
            content="Condition source note",
            author_id=test_user.id,
        )
        db.add(note)
        db.commit()
        workflow_triggers.trigger_note_added(db, note)
        return note

    def ran_for(note: EntityNote) -> bool:
        execution = (
            db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.organization_id == test_org.id,
                WorkflowExecution.workflow_id == workflow.id,
                WorkflowExecution.entity_id == note.id,
            )
            .one()
        )
        return execution.status != "skipped"

    assert not ran_for(add_note())

    surrogate_service.update_surrogate(
        db,
        surrogate,
        SurrogateUpdate(is_priority=True),
        user_id=test_user.id,
        org_id=test_org.id,
    )
    assert ran_for(add_note())
