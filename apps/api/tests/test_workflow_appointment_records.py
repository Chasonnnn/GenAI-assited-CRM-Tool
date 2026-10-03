"""Appointment workflows act on the linked surrogate or donor, notify hosts, and filter types."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.enums import JobType, MeetingMode, WorkflowTriggerType
from app.db.models import (
    Appointment,
    AppointmentType,
    EmailTemplate,
    EntityNote,
    Job,
    Notification,
    Organization,
    PipelineStage,
    Surrogate,
    WorkflowExecution,
)
from app.schemas.donor import DonorCreate
from app.schemas.surrogate import SurrogateCreate
from app.schemas.workflow import WorkflowCreate
from app.services import (
    donor_service,
    surrogate_service,
    workflow_email_provider,
    workflow_service,
    workflow_triggers,
)

COMPLETED = WorkflowTriggerType.APPOINTMENT_COMPLETED


def _appointment_type(db, org_id, user_id, name="Initial Interview") -> AppointmentType:
    appointment_type = AppointmentType(
        organization_id=org_id,
        user_id=user_id,
        name=name,
        slug=f"type-{uuid.uuid4().hex[:8]}",
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        meeting_mode=MeetingMode.PHONE.value,
        meeting_modes=[MeetingMode.PHONE.value],
        auto_approve=False,
        reminder_hours_before=0,
        is_active=True,
    )
    db.add(appointment_type)
    db.flush()
    return appointment_type


def _appointment(db, org_id, user_id, *, type_name="Initial Interview", start=None, **links):
    appointment_type = _appointment_type(db, org_id, user_id, type_name)
    start = start or datetime.now(UTC) - timedelta(hours=1)
    appointment = Appointment(
        organization_id=org_id,
        user_id=user_id,
        appointment_type_id=appointment_type.id,
        client_name="Linked Client",
        client_email="linked-client@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.PHONE.value,
        dial_in_number="555-0199",
        status="completed",
        reschedule_token=f"r-{uuid.uuid4().hex}",
        cancel_token=f"c-{uuid.uuid4().hex}",
        **links,
    )
    db.add(appointment)
    db.flush()
    return appointment


def _surrogate(db, org_id, user_id) -> Surrogate:
    return surrogate_service.create_surrogate(
        db=db,
        org_id=org_id,
        user_id=user_id,
        data=SurrogateCreate(
            full_name="Appointment Surrogate",
            email=f"appointment-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )


def _workflow(db, org_id, user_id, actions, trigger_config=None, trigger_type=COMPLETED):
    return workflow_service.create_workflow(
        db,
        org_id,
        user_id,
        WorkflowCreate(
            name=f"appointment {uuid.uuid4()}",
            trigger_type=trigger_type,
            trigger_config=trigger_config or {},
            actions=actions,
            is_enabled=True,
        ),
    )


def _results(db, org_id, workflow_id) -> list[dict]:
    execution = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.workflow_id == workflow_id,
        )
        .one()
    )
    return execution.actions_executed


def _other_stage(db, stage) -> PipelineStage:
    return (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == stage.pipeline_id,
            PipelineStage.id != stage.id,
            PipelineStage.is_active.is_(True),
            PipelineStage.stage_type == "intake",
        )
        .order_by(PipelineStage.order)
        .first()
    )


def test_completed_appointment_updates_notes_and_tasks_the_linked_surrogate(
    db, test_org, test_user
):
    surrogate = _surrogate(db, test_org.id, test_user.id)
    target_stage = _other_stage(db, surrogate.stage)
    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        [
            {"action_type": "update_field", "field": "stage_id", "value": str(target_stage.id)},
            {"action_type": "add_note", "content": "Interview done"},
            {"action_type": "create_task", "title": "Send next steps"},
        ],
    )
    appointment = _appointment(db, test_org.id, test_user.id, surrogate_id=surrogate.id)

    workflow_triggers.trigger_appointment_event(db, appointment, COMPLETED)

    assert all(result["success"] for result in _results(db, test_org.id, workflow.id))
    db.refresh(surrogate)
    assert surrogate.stage_id == target_stage.id
    assert (
        db.query(EntityNote)
        .filter(
            EntityNote.organization_id == test_org.id,
            EntityNote.entity_type == "surrogate",
            EntityNote.entity_id == surrogate.id,
        )
        .count()
        == 1
    )


def test_unlinked_appointment_skips_record_actions_and_notifies_the_host(db, test_org, test_user):
    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        [
            {"action_type": "add_note", "content": "Interview done"},
            {"action_type": "send_notification", "title": "Booking done", "recipients": "host"},
        ],
    )
    appointment = _appointment(db, test_org.id, test_user.id)

    workflow_triggers.trigger_appointment_event(db, appointment, COMPLETED)

    note, notify = _results(db, test_org.id, workflow.id)
    assert note["skipped"] is True
    assert note["error"] == "Appointment is not linked to a surrogate"
    assert notify["success"] is True
    notification = (
        db.query(Notification)
        .filter(
            Notification.organization_id == test_org.id,
            Notification.user_id == test_user.id,
            Notification.entity_id == appointment.id,
        )
        .one()
    )
    assert notification.entity_type == "appointment"


def test_appointment_linked_to_another_org_surrogate_is_never_touched(db, test_org, test_user):
    other_org = Organization(name="Other Org", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    foreign = _surrogate(db, test_org.id, test_user.id)
    foreign.organization_id = other_org.id
    db.flush()
    workflow = _workflow(
        db, test_org.id, test_user.id, [{"action_type": "add_note", "content": "Leak"}]
    )
    appointment = _appointment(db, test_org.id, test_user.id, surrogate_id=foreign.id)

    workflow_triggers.trigger_appointment_event(db, appointment, COMPLETED)

    [result] = _results(db, test_org.id, workflow.id)
    assert result["skipped"] is True
    assert db.query(EntityNote).filter(EntityNote.entity_id == foreign.id).count() == 0


@pytest.mark.parametrize("record_type", ["egg_donor", "surrogate"])
def test_donor_linked_appointment_runs_only_donor_record_workflows(
    db, test_org, test_user, record_type
):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Appointment Donor",
            email=f"donor-{uuid.uuid4().hex[:8]}@example.com",
        ),
        emit_workflow_events=False,
    )
    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        [{"action_type": "add_note", "content": "Donor interview done"}],
        trigger_config={"record_type": record_type},
    )
    appointment = _appointment(db, test_org.id, test_user.id, donor_id=donor.id)

    workflow_triggers.trigger_appointment_event(db, appointment, COMPLETED)

    [result] = _results(db, test_org.id, workflow.id)
    notes = db.query(EntityNote).filter(
        EntityNote.organization_id == test_org.id,
        EntityNote.entity_type == "donor",
        EntityNote.entity_id == donor.id,
    )
    if record_type == "egg_donor":
        assert result["success"] is True, result
        assert notes.count() == 1
    else:
        assert result["skipped"] is True
        assert notes.count() == 0


def test_type_filter_matches_names_across_hosts_ignoring_case(db, test_org, test_user):
    surrogate = _surrogate(db, test_org.id, test_user.id)
    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        [{"action_type": "send_notification", "title": "Interview", "recipients": "host"}],
        trigger_config={"appointment_type_names": [" initial interview ", "Initial Interview"]},
    )
    assert workflow.trigger_config["appointment_type_names"] == ["initial interview"]
    other = _appointment(
        db, test_org.id, test_user.id, type_name="Follow-up", surrogate_id=surrogate.id
    )
    matching = _appointment(
        db, test_org.id, test_user.id, type_name="INITIAL INTERVIEW", surrogate_id=surrogate.id
    )

    workflow_triggers.trigger_appointment_event(db, other, COMPLETED)
    workflow_triggers.trigger_appointment_event(db, matching, COMPLETED)

    executions = db.query(WorkflowExecution).filter(
        WorkflowExecution.organization_id == test_org.id,
        WorkflowExecution.workflow_id == workflow.id,
    )
    assert [execution.entity_id for execution in executions] == [matching.id]


@pytest.mark.asyncio
async def test_list_filters_appointment_workflows_by_type_name(
    authed_client, db, test_org, test_user
):
    notify = [{"action_type": "send_notification", "title": "Booked", "recipients": "host"}]
    named = _workflow(
        db,
        test_org.id,
        test_user.id,
        notify,
        trigger_config={"appointment_type_names": ["Initial Interview"]},
    )
    _workflow(
        db,
        test_org.id,
        test_user.id,
        notify,
        trigger_config={"appointment_type_names": ["Follow-up"]},
    )
    _workflow(db, test_org.id, test_user.id, notify)
    other_org = Organization(name="Other Org", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    _workflow(
        db,
        other_org.id,
        test_user.id,
        notify,
        trigger_config={"appointment_type_names": ["Initial Interview"]},
    )

    response = await authed_client.get(
        "/workflows", params={"appointment_type_name": " initial INTERVIEW "}
    )

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [str(named.id)]


def test_appointment_email_describes_the_triggering_appointment(
    db, test_org, test_user, monkeypatch
):
    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda *_args, **_kwargs: ("resend", {"from_email": "care@example.com"}),
    )
    template = EmailTemplate(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Thanks",
        subject="Thanks",
        body="<p>{{appointment_date}}</p>",
        scope="org",
        is_active=True,
    )
    db.add(template)
    surrogate = _surrogate(db, test_org.id, test_user.id)
    past_start = datetime(2026, 3, 2, 15, tzinfo=UTC)
    _appointment(
        db,
        test_org.id,
        test_user.id,
        start=datetime.now(UTC) + timedelta(days=3),
        surrogate_id=surrogate.id,
    ).status = "confirmed"
    appointment = _appointment(
        db, test_org.id, test_user.id, start=past_start, surrogate_id=surrogate.id
    )
    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        [{"action_type": "send_email", "template_id": str(template.id)}],
    )

    workflow_triggers.trigger_appointment_event(db, appointment, COMPLETED)

    [result] = _results(db, test_org.id, workflow.id)
    assert result["success"] is True, result
    job = db.get(Job, uuid.UUID(result["job_ids"][0]))
    assert job.job_type == JobType.WORKFLOW_EMAIL.value
    assert job.payload["recipient_email"] == surrogate.email
    assert job.payload["variables"]["appointment_date"] == "Monday, March 02, 2026"
    assert job.payload["variables"]["appointment_location"] == "555-0199"


@pytest.mark.parametrize(
    ("trigger_type", "action", "message"),
    [
        (
            WorkflowTriggerType.MATCH_PROPOSED,
            {"action_type": "add_note", "content": "No record"},
            "not available for match_proposed",
        ),
        (
            WorkflowTriggerType.SURROGATE_CREATED,
            {"action_type": "send_notification", "title": "Hi", "recipients": "host"},
            "appointment host",
        ),
    ],
)
def test_api_rejects_actions_the_trigger_cannot_run(
    db, test_org, test_user, trigger_type, action, message
):
    with pytest.raises(ValueError, match=message):
        _workflow(db, test_org.id, test_user.id, [action], trigger_type=trigger_type)


def test_api_rejects_sms_for_donor_appointment_workflows(db, test_org, test_user):
    with pytest.raises(ValueError, match="send_message does not support donor"):
        _workflow(
            db,
            test_org.id,
            test_user.id,
            [{"action_type": "send_message", "template_id": str(uuid.uuid4())}],
            trigger_config={"record_type": "sperm_donor"},
        )


def test_options_offer_record_actions_and_org_type_names_for_appointments(db, test_org, test_user):
    _appointment_type(db, test_org.id, test_user.id, "Initial Interview")
    _appointment_type(db, test_org.id, test_user.id, "initial interview ")
    options = workflow_service.get_workflow_options(db, test_org.id, "org", test_user.id)

    assert options.action_types_by_trigger["appointment_completed"] == [
        "send_email",
        "create_task",
        "send_notification",
        "update_field",
        "add_note",
    ]
    assert options.appointment_type_names in (["Initial Interview"], ["initial interview"])


TIME = WorkflowTriggerType.APPOINTMENT_TIME


def _executions(db, org_id, workflow_id) -> list[uuid.UUID]:
    return [
        execution.entity_id
        for execution in db.query(WorkflowExecution).filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.workflow_id == workflow_id,
        )
    ]


def test_time_sweep_runs_hours_before_start_once_per_appointment_time(db, test_org, test_user):
    now = datetime.now(UTC).replace(microsecond=0)
    surrogate = _surrogate(db, test_org.id, test_user.id)
    notify = [{"action_type": "send_notification", "title": "Tomorrow", "recipients": "host"}]
    day_before = _workflow(
        db,
        test_org.id,
        test_user.id,
        notify,
        trigger_config={"when": "before_start", "hours": 24},
        trigger_type=TIME,
    )
    hour_before = _workflow(
        db,
        test_org.id,
        test_user.id,
        notify,
        trigger_config={"when": "before_start", "hours": 1},
        trigger_type=TIME,
    )
    due = _appointment(
        db,
        test_org.id,
        test_user.id,
        start=now + timedelta(hours=23),
        surrogate_id=surrogate.id,
    )
    later = _appointment(
        db,
        test_org.id,
        test_user.id,
        start=now + timedelta(hours=30),
        surrogate_id=surrogate.id,
    )
    pending = _appointment(
        db,
        test_org.id,
        test_user.id,
        start=now + timedelta(hours=23),
        surrogate_id=surrogate.id,
    )
    for appointment in (due, later):
        appointment.status = "confirmed"
    pending.status = "pending"
    db.flush()

    workflow_triggers.trigger_appointment_time_sweep(db, test_org.id, now=now)
    workflow_triggers.trigger_appointment_time_sweep(db, test_org.id, now=now)

    assert _executions(db, test_org.id, day_before.id) == [due.id]
    assert _executions(db, test_org.id, hour_before.id) == []

    # A reschedule into the window earns a new run for the new time.
    due.scheduled_start = now + timedelta(hours=22, minutes=30)
    due.scheduled_end = due.scheduled_start + timedelta(minutes=30)
    db.flush()
    workflow_triggers.trigger_appointment_time_sweep(db, test_org.id, now=now)
    assert _executions(db, test_org.id, day_before.id) == [due.id, due.id]


def test_time_sweep_runs_hours_after_end_for_held_appointments_of_the_type(db, test_org, test_user):
    now = datetime.now(UTC).replace(microsecond=0)
    surrogate = _surrogate(db, test_org.id, test_user.id)
    workflow = _workflow(
        db,
        test_org.id,
        test_user.id,
        [{"action_type": "add_note", "content": "Follow up"}],
        trigger_config={
            "when": "after_end",
            "hours": 2,
            "appointment_type_names": ["Initial Interview"],
        },
        trigger_type=TIME,
    )
    ended = now - timedelta(hours=3)
    completed = _appointment(db, test_org.id, test_user.id, start=ended, surrogate_id=surrogate.id)
    cancelled = _appointment(db, test_org.id, test_user.id, start=ended, surrogate_id=surrogate.id)
    cancelled.status = "cancelled"
    other_type = _appointment(
        db,
        test_org.id,
        test_user.id,
        type_name="Follow-up",
        start=ended,
        surrogate_id=surrogate.id,
    )
    other_org = Organization(name="Other Org", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    for appointment in (completed, other_type):
        appointment.scheduled_end = now - timedelta(hours=2, minutes=30)
    cancelled.scheduled_end = now - timedelta(hours=2, minutes=30)
    db.flush()

    workflow_triggers.trigger_appointment_time_sweep(db, other_org.id, now=now)
    assert _executions(db, test_org.id, workflow.id) == []

    workflow_triggers.trigger_appointment_time_sweep(db, test_org.id, now=now)

    assert _executions(db, test_org.id, workflow.id) == [completed.id]
    assert all(result["success"] for result in _results(db, test_org.id, workflow.id))


@pytest.mark.parametrize(
    "trigger_config",
    [{"when": "during", "hours": 2}, {"when": "after_end", "hours": 0}, {"hours": 169}],
)
def test_time_trigger_rejects_invalid_timing(db, test_org, test_user, trigger_config):
    with pytest.raises(ValueError):
        _workflow(
            db,
            test_org.id,
            test_user.id,
            [{"action_type": "add_note", "content": "Follow up"}],
            trigger_config=trigger_config,
            trigger_type=TIME,
        )
