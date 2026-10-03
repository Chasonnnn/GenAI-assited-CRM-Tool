"""Workflow triggers fired by platform events outside the workflow engine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

import pytest

from app.core.config import settings
from app.db.enums import AppointmentStatus, MeetingMode, WorkflowTriggerType
from app.db.models import AppointmentType, AvailabilityRule, WorkflowExecution
from app.schemas.surrogate import SurrogateCreate, SurrogateUpdate
from app.schemas.workflow import WorkflowCreate
from app.services import scheduling_v2_service, surrogate_service, workflow_service


def _note_workflow(db, org_id, user_id, trigger_type, trigger_config=None, **extra):
    return workflow_service.create_workflow(
        db,
        org_id,
        user_id,
        WorkflowCreate(
            name=f"{trigger_type.value} {uuid.uuid4()}",
            trigger_type=trigger_type,
            trigger_config=trigger_config or {},
            actions=[{"action_type": "add_note", "content": "Workflow ran"}],
            **extra,
        ),
    )


def _executed_workflow_ids(db, org_id, entity_id) -> set[uuid.UUID]:
    return {
        execution.workflow_id
        for execution in db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.entity_id == entity_id,
        )
        .all()
    }


def _create_surrogate(db, org_id, user_id):
    return surrogate_service.create_surrogate(
        db=db,
        org_id=org_id,
        user_id=user_id,
        data=SurrogateCreate(
            full_name="Workflow Trigger Surrogate",
            email=f"workflow-trigger-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )


def test_user_edit_fires_surrogate_updated_for_watched_fields_only(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    watches_state = _note_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.SURROGATE_UPDATED,
        {"fields": ["state"]},
    )
    watches_priority = _note_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.SURROGATE_UPDATED,
        {"fields": ["is_priority"]},
    )

    surrogate_service.update_surrogate(
        db,
        surrogate,
        SurrogateUpdate(state="TX"),
        user_id=test_user.id,
        org_id=test_org.id,
    )

    executed = _executed_workflow_ids(db, test_org.id, surrogate.id)
    assert watches_state.id in executed
    assert watches_priority.id not in executed

    surrogate_service.update_surrogate(
        db,
        surrogate,
        SurrogateUpdate(is_priority=True),
        user_id=test_user.id,
        org_id=test_org.id,
    )
    assert watches_priority.id in _executed_workflow_ids(db, test_org.id, surrogate.id)


def test_unchanged_or_uncommitted_edit_does_not_fire_surrogate_updated(db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    surrogate_service.update_surrogate(
        db, surrogate, SurrogateUpdate(state="CA"), user_id=test_user.id, org_id=test_org.id
    )
    workflow = _note_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowTriggerType.SURROGATE_UPDATED,
        {"fields": ["state"]},
    )

    surrogate_service.update_surrogate(
        db, surrogate, SurrogateUpdate(state="CA"), user_id=test_user.id, org_id=test_org.id
    )
    surrogate_service.update_surrogate(
        db,
        surrogate,
        SurrogateUpdate(state="NV"),
        user_id=test_user.id,
        org_id=test_org.id,
        commit=False,
    )

    assert workflow.id not in _executed_workflow_ids(db, test_org.id, surrogate.id)


def _notify_workflow(db, org_id, user_id, trigger_type):
    return workflow_service.create_workflow(
        db,
        org_id,
        user_id,
        WorkflowCreate(
            name=f"{trigger_type.value} {uuid.uuid4()}",
            trigger_type=trigger_type,
            actions=[
                {
                    "action_type": "send_notification",
                    "title": "Appointment changed",
                    "recipients": "all_admins",
                }
            ],
        ),
    )


def _execution_count(db, org_id, workflow_id) -> int:
    return (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.workflow_id == workflow_id,
        )
        .count()
    )


@pytest.fixture
def v2_booking_type(db, test_org, test_user, monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    start = (datetime.now(UTC) + timedelta(days=14)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    appointment_type = AppointmentType(
        organization_id=test_org.id,
        user_id=test_user.id,
        name="Workflow trigger phone",
        slug=f"workflow-trigger-{uuid.uuid4().hex[:8]}",
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        meeting_mode=MeetingMode.PHONE.value,
        meeting_modes=[MeetingMode.PHONE.value],
        auto_approve=False,
        reminder_hours_before=0,
        is_active=True,
    )
    db.add_all(
        [
            appointment_type,
            AvailabilityRule(
                organization_id=test_org.id,
                user_id=test_user.id,
                day_of_week=start.weekday(),
                start_time=time(8),
                end_time=time(18),
                timezone="UTC",
            ),
        ]
    )
    db.commit()
    return appointment_type, start


def _create_booking(db, org_id, owner_id, appointment_type_id, start, request_id):
    return scheduling_v2_service.create_booking(
        db,
        org_id=org_id,
        user_id=owner_id,
        appointment_type_id=appointment_type_id,
        client_name="Workflow Trigger Client",
        client_email="workflow-trigger-client@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=start,
        client_notes=None,
        idempotency_key=None,
        meeting_mode=MeetingMode.PHONE.value,
        record_links=None,
        actor_scope="test-public-booking",
        actor_user_id=None,
        request_id=request_id,
        expected_revision=0,
        override_availability=False,
        override_reason=None,
    )


def _started(db, appointment):
    """Move a confirmed test appointment so it began five minutes ago."""
    shift = appointment.scheduled_start - (datetime.now(UTC) - timedelta(minutes=5))
    appointment.scheduled_start -= shift
    appointment.scheduled_end -= shift
    db.commit()
    return appointment


def _approve(db, appointment, user_id, request_id):
    return scheduling_v2_service.approve_booking(
        db,
        appointment,
        approved_by_user_id=user_id,
        expected_revision=appointment.revision,
        request_id=request_id,
    )


def test_v2_approval_and_completion_fire_appointment_workflows_once(
    db, test_org, test_user, v2_booking_type
):
    appointment_type, start = v2_booking_type
    scheduled = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_SCHEDULED
    )
    completed = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_COMPLETED
    )
    no_show = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_NO_SHOW
    )

    appointment = _create_booking(
        db, test_org.id, test_user.id, appointment_type.id, start, "trigger-create"
    )
    assert _execution_count(db, test_org.id, scheduled.id) == 0

    appointment = _approve(db, appointment, test_user.id, "trigger-approve")
    assert _execution_count(db, test_org.id, scheduled.id) == 1
    appointment = _started(db, appointment)

    complete_args = {
        "status": AppointmentStatus.COMPLETED.value,
        "actor_user_id": test_user.id,
        "expected_revision": appointment.revision,
        "request_id": "trigger-complete",
    }
    appointment = scheduling_v2_service.complete_booking(db, appointment, **complete_args)
    scheduling_v2_service.complete_booking(db, appointment, **complete_args)

    assert _execution_count(db, test_org.id, completed.id) == 1
    assert _execution_count(db, test_org.id, no_show.id) == 0


def test_v2_no_show_and_cancel_fire_their_own_workflows(db, test_org, test_user, v2_booking_type):
    appointment_type, start = v2_booking_type
    no_show = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_NO_SHOW
    )
    cancelled = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_CANCELLED
    )

    first = _approve(
        db,
        _create_booking(
            db, test_org.id, test_user.id, appointment_type.id, start, "no-show-create"
        ),
        test_user.id,
        "no-show-approve",
    )
    first = _started(db, first)
    scheduling_v2_service.complete_booking(
        db,
        first,
        status=AppointmentStatus.NO_SHOW.value,
        actor_user_id=test_user.id,
        expected_revision=first.revision,
        request_id="no-show-complete",
    )
    second = _create_booking(
        db,
        test_org.id,
        test_user.id,
        appointment_type.id,
        start + timedelta(hours=1),
        "cancel-create",
    )
    scheduling_v2_service.cancel_booking(
        db,
        second,
        reason=None,
        by_client=False,
        token=None,
        actor_user_id=test_user.id,
        expected_revision=second.revision,
        request_id="cancel-one",
        actor_scope=scheduling_v2_service.staff_actor_scope(test_user.id),
    )

    assert _execution_count(db, test_org.id, no_show.id) == 1
    assert _execution_count(db, test_org.id, cancelled.id) == 1


def test_appointment_workflow_failure_keeps_committed_booking(
    db, test_org, test_user, v2_booking_type, monkeypatch
):
    from app.services import workflow_triggers

    appointment_type, start = v2_booking_type
    appointment = _create_booking(
        db, test_org.id, test_user.id, appointment_type.id, start, "failure-create"
    )

    def fail(*_args, **_kwargs):
        raise RuntimeError("workflow engine unavailable")

    monkeypatch.setattr(workflow_triggers, "trigger_appointment_event", fail)
    appointment = _approve(db, appointment, test_user.id, "failure-approve")

    db.expire_all()
    assert appointment.status == AppointmentStatus.CONFIRMED.value


def _pending_submission(db, org_id, user_id, stage):
    from tests.test_form_submission_service import (
        _answers,
        _create_published_form,
        _create_shared_submission,
        _create_surrogate,
    )

    surrogate = _create_surrogate(db, org_id, user_id, stage)
    form = _create_published_form(db, org_id, user_id)
    submission = _create_shared_submission(
        db, form=form, surrogate=surrogate, user_id=user_id, answers=_answers()
    )
    return form, submission


@pytest.mark.parametrize(
    ("review", "trigger_type", "other_trigger_type"),
    [
        (
            "approve",
            WorkflowTriggerType.FORM_SUBMISSION_APPROVED,
            WorkflowTriggerType.FORM_SUBMISSION_REJECTED,
        ),
        (
            "reject",
            WorkflowTriggerType.FORM_SUBMISSION_REJECTED,
            WorkflowTriggerType.FORM_SUBMISSION_APPROVED,
        ),
    ],
)
def test_submission_review_fires_matching_form_workflows_only(
    db, test_org, test_user, default_stage, review, trigger_type, other_trigger_type
):
    from app.services import form_submission_service

    form, submission = _pending_submission(db, test_org.id, test_user.id, default_stage)
    _other_form, other_submission = _pending_submission(
        db, test_org.id, test_user.id, default_stage
    )
    matching = _note_workflow(
        db, test_org.id, test_user.id, trigger_type, {"form_id": str(form.id)}
    )
    opposite = _note_workflow(
        db, test_org.id, test_user.id, other_trigger_type, {"form_id": str(form.id)}
    )
    assert matching.subject_type == "form_submission"

    review_fn = getattr(form_submission_service, f"{review}_submission")
    review_fn(db=db, submission=submission, reviewer_id=test_user.id, review_notes=None)
    review_fn(db=db, submission=other_submission, reviewer_id=test_user.id, review_notes=None)

    assert _execution_count(db, test_org.id, matching.id) == 1
    assert _execution_count(db, test_org.id, opposite.id) == 0
    assert matching.id in _executed_workflow_ids(db, test_org.id, submission.id)


def test_v2_request_reschedule_and_expiry_fire_their_own_workflows(
    db, test_org, test_user, v2_booking_type
):
    appointment_type, start = v2_booking_type
    requested = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_REQUESTED
    )
    scheduled = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_SCHEDULED
    )
    rescheduled = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_RESCHEDULED
    )
    expired = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_EXPIRED
    )

    appointment = _create_booking(
        db, test_org.id, test_user.id, appointment_type.id, start, "request-create"
    )
    assert _execution_count(db, test_org.id, requested.id) == 1
    assert _execution_count(db, test_org.id, scheduled.id) == 0

    appointment = scheduling_v2_service.reschedule_booking(
        db,
        appointment,
        start + timedelta(hours=1),
        by_client=False,
        token=None,
        actor_user_id=test_user.id,
        expected_revision=appointment.revision,
        request_id="request-reschedule",
        actor_scope=scheduling_v2_service.staff_actor_scope(test_user.id),
        override_availability=False,
        override_reason=None,
    )
    assert _execution_count(db, test_org.id, rescheduled.id) == 1

    appointment.pending_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert scheduling_v2_service.expire_booking(
        db, appointment_id=appointment.id, org_id=test_org.id, revision=appointment.revision
    )
    assert _execution_count(db, test_org.id, expired.id) == 1


def test_stage_booked_interview_changes_fire_appointment_workflows(
    db, test_org, test_user, v2_booking_type
):
    from app.db.enums import Role
    from app.db.models import Appointment
    from app.schemas.interview_appointment import SurrogateInterviewAppointmentAction
    from app.services import (
        pipeline_service,
        surrogate_interview_appointment_service,
        surrogate_status_service,
    )

    _appointment_type, start = v2_booking_type
    scheduled = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_SCHEDULED
    )
    rescheduled = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_RESCHEDULED
    )
    cancelled = _notify_workflow(
        db, test_org.id, test_user.id, WorkflowTriggerType.APPOINTMENT_CANCELLED
    )
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, "interview_scheduled")

    surrogate_status_service.change_status(
        db, surrogate, stage.id, test_user.id, Role.DEVELOPER, interview_scheduled_at=start
    )
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == test_org.id, Appointment.surrogate_id == surrogate.id
        )
        .one()
    )
    assert _execution_count(db, test_org.id, scheduled.id) == 1

    for action, request_id in (("reschedule", "interview-move"), ("cancel", "interview-cancel")):
        surrogate_interview_appointment_service.manage(
            db,
            org_id=test_org.id,
            surrogate_id=surrogate.id,
            actor_user_id=test_user.id,
            actor_role=Role.DEVELOPER,
            data=SurrogateInterviewAppointmentAction(
                action=action,
                scheduled_start=start + timedelta(days=7) if action == "reschedule" else None,
                move_stage=False,
                expected_stage_id=surrogate.stage_id,
                expected_appointment_id=appointment.id,
                expected_scheduled_start=appointment.scheduled_start,
                expected_revision=appointment.revision,
                request_id=request_id,
            ),
        )
        db.refresh(appointment)

    assert _execution_count(db, test_org.id, rescheduled.id) == 1
    assert _execution_count(db, test_org.id, cancelled.id) == 1
