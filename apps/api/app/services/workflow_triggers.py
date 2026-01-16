"""Workflow triggers - hooks into core services to trigger workflows."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Surrogate, Task, Match, Attachment, EntityNote, Appointment
from app.db.enums import WorkflowTriggerType, WorkflowEventSource, TaskType
from app.services.workflow_engine import engine


# =============================================================================
# Surrogate Triggers (called from surrogate_service.py)
# =============================================================================


def trigger_surrogate_created(db: Session, surrogate: Surrogate) -> None:
    """Trigger workflows when a new surrogate is created."""
    from app.services import pipeline_service

    stage = pipeline_service.get_stage_by_id(db, surrogate.stage_id)
    stage_slug = stage.slug if stage else None
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
        entity_type="surrogate",
        entity_id=surrogate.id,
        event_data={
            "surrogate_id": str(surrogate.id),
            "surrogate_number": surrogate.surrogate_number,
            "source": surrogate.source,
            "stage_id": str(surrogate.stage_id),
            "stage_slug": stage_slug,
            "status_label": surrogate.status_label,
        },
        org_id=surrogate.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_status_changed(
    db: Session,
    surrogate: Surrogate,
    old_stage_id: UUID | None,
    new_stage_id: UUID | None,
    old_stage_slug: str | None,
    new_stage_slug: str | None,
    effective_at: datetime | None = None,
    recorded_at: datetime | None = None,
    is_undo: bool = False,
    request_id: UUID | None = None,
    approved_by_user_id: UUID | None = None,
    approved_at: datetime | None = None,
    requested_at: datetime | None = None,
    changed_by_user_id: UUID | None = None,
) -> None:
    """Trigger workflows when surrogate status changes."""
    if old_stage_id == new_stage_id:
        return

    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        entity_type="surrogate",
        entity_id=surrogate.id,
        event_data={
            "surrogate_id": str(surrogate.id),
            "old_stage_id": str(old_stage_id) if old_stage_id else None,
            "new_stage_id": str(new_stage_id) if new_stage_id else None,
            "old_status": old_stage_slug,
            "new_status": new_stage_slug,
            "effective_at": effective_at.isoformat() if effective_at else None,
            "recorded_at": recorded_at.isoformat() if recorded_at else None,
            "is_undo": is_undo,
            "request_id": str(request_id) if request_id else None,
            "approved_by_user_id": str(approved_by_user_id) if approved_by_user_id else None,
            "approved_at": approved_at.isoformat() if approved_at else None,
            "requested_at": requested_at.isoformat() if requested_at else None,
            "changed_by_user_id": str(changed_by_user_id) if changed_by_user_id else None,
        },
        org_id=surrogate.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_surrogate_assigned(
    db: Session,
    surrogate: Surrogate,
    old_owner_id: UUID | None,
    new_owner_id: UUID | None,
    old_owner_type: str | None = None,
    new_owner_type: str | None = None,
) -> None:
    """Trigger workflows when surrogate is assigned."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.SURROGATE_ASSIGNED,
        entity_type="surrogate",
        entity_id=surrogate.id,
        event_data={
            "surrogate_id": str(surrogate.id),
            "old_owner_id": str(old_owner_id) if old_owner_id else None,
            "new_owner_id": str(new_owner_id) if new_owner_id else None,
            "old_owner_type": old_owner_type,
            "new_owner_type": new_owner_type,
        },
        org_id=surrogate.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_surrogate_updated(
    db: Session,
    surrogate: Surrogate,
    changed_fields: list[str],
    old_values: dict,
    new_values: dict,
) -> None:
    """Trigger workflows when specific surrogate fields change."""
    if not changed_fields:
        return

    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.SURROGATE_UPDATED,
        entity_type="surrogate",
        entity_id=surrogate.id,
        event_data={
            "surrogate_id": str(surrogate.id),
            "changed_fields": changed_fields,
            "old_values": old_values,
            "new_values": new_values,
        },
        org_id=surrogate.organization_id,
        source=WorkflowEventSource.USER,
    )


# =============================================================================
# Task Triggers (called from worker sweep)
# =============================================================================


def trigger_task_due(db: Session, task: Task) -> None:
    """Trigger workflows when a task is about to be due."""
    surrogate = task.surrogate if hasattr(task, "surrogate") else None
    org_id = (
        task.organization_id
        if hasattr(task, "organization_id")
        else (surrogate.organization_id if surrogate else None)
    )

    if not org_id:
        return

    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.TASK_DUE,
        entity_type="task",
        entity_id=task.id,
        event_data={
            "task_id": str(task.id),
            "task_title": task.title,
            "due_date": str(task.due_date) if task.due_date else None,
            "surrogate_id": str(task.surrogate_id) if task.surrogate_id else None,
        },
        org_id=org_id,
        source=WorkflowEventSource.SYSTEM,
    )


def trigger_task_overdue(db: Session, task: Task) -> None:
    """Trigger workflows when a task is overdue."""
    surrogate = task.surrogate if hasattr(task, "surrogate") else None
    org_id = (
        task.organization_id
        if hasattr(task, "organization_id")
        else (surrogate.organization_id if surrogate else None)
    )

    if not org_id:
        return

    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.TASK_OVERDUE,
        entity_type="task",
        entity_id=task.id,
        event_data={
            "task_id": str(task.id),
            "task_title": task.title,
            "due_date": str(task.due_date) if task.due_date else None,
            "surrogate_id": str(task.surrogate_id) if task.surrogate_id else None,
        },
        org_id=org_id,
        source=WorkflowEventSource.SYSTEM,
    )


# =============================================================================
# Sweep Triggers (called from worker.py)
# =============================================================================


def trigger_scheduled_workflows(db: Session, org_id: UUID) -> None:
    """Trigger scheduled workflows for an org (called by daily sweep)."""
    from datetime import datetime, timezone
    from app.db.models import AutomationWorkflow

    now = datetime.now(timezone.utc)

    workflows = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.trigger_type == WorkflowTriggerType.SCHEDULED.value,
            AutomationWorkflow.is_enabled.is_(True),
        )
        .all()
    )

    for workflow in workflows:
        config = workflow.trigger_config
        cron = config.get("cron", "")
        tz = config.get("timezone", "America/Los_Angeles")

        # Simple cron matching (for daily/weekly schedules)
        # Full cron parsing would require croniter library
        if _should_run_cron(cron, now, tz):
            for surrogate in _iter_surrogates(db, org_id):
                engine.trigger(
                    db=db,
                    trigger_type=WorkflowTriggerType.SCHEDULED,
                    entity_type="surrogate",
                    entity_id=surrogate.id,
                    event_data={
                        "schedule_time": now.isoformat(),
                        "cron": cron,
                    },
                    org_id=org_id,
                    source=WorkflowEventSource.SYSTEM,
                )


def trigger_inactivity_workflows(db: Session, org_id: UUID) -> None:
    """Trigger inactivity workflows for surrogates with no recent activity."""
    from datetime import datetime, timezone, timedelta
    from app.db.models import AutomationWorkflow

    now = datetime.now(timezone.utc)

    workflows = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.trigger_type == WorkflowTriggerType.INACTIVITY.value,
            AutomationWorkflow.is_enabled.is_(True),
        )
        .all()
    )

    for workflow in workflows:
        days = workflow.trigger_config.get("days", 7)
        threshold = now - timedelta(days=days)

        # Find surrogates with no activity since threshold
        # Using updated_at as proxy for activity
        for surrogate in _iter_surrogates(db, org_id, updated_before=threshold):
            engine.trigger(
                db=db,
                trigger_type=WorkflowTriggerType.INACTIVITY,
                entity_type="surrogate",
                entity_id=surrogate.id,
                event_data={
                    "days_inactive": days,
                    "last_activity": surrogate.updated_at.isoformat()
                    if surrogate.updated_at
                    else None,
                },
                org_id=org_id,
                source=WorkflowEventSource.SYSTEM,
            )


def _iter_surrogates(
    db: Session,
    org_id: UUID,
    updated_before: datetime | None = None,
    batch_size: int = 500,
):
    """Iterate through active surrogates in batches to avoid truncating large orgs."""
    from app.db.models import Surrogate

    last_id = None
    while True:
        query = db.query(Surrogate).filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
        )
        if updated_before is not None:
            query = query.filter(Surrogate.updated_at < updated_before)
        if last_id:
            query = query.filter(Surrogate.id > last_id)
        batch = query.order_by(Surrogate.id).limit(batch_size).all()
        if not batch:
            break
        for surrogate in batch:
            yield surrogate
        last_id = batch[-1].id


def trigger_task_due_sweep(db: Session, org_id: UUID) -> None:
    """Find and trigger task_due workflows for tasks due soon."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from app.db.models import AutomationWorkflow, Task, Surrogate, Organization

    org = db.query(Organization).filter(Organization.id == org_id).first()
    tz_name = org.timezone if org and org.timezone else "UTC"
    try:
        org_tz = ZoneInfo(tz_name)
    except Exception:
        org_tz = ZoneInfo("UTC")
    now = datetime.now(org_tz)

    workflows = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.trigger_type == WorkflowTriggerType.TASK_DUE.value,
            AutomationWorkflow.is_enabled.is_(True),
        )
        .all()
    )

    for workflow in workflows:
        hours_before = workflow.trigger_config.get("hours_before", 24)
        window_start = now + timedelta(hours=hours_before - 1)
        window_end = now + timedelta(hours=hours_before + 1)

        # Find tasks due within the window
        tasks = (
            db.query(Task)
            .join(Surrogate)
            .filter(
                Surrogate.organization_id == org_id,
                Task.due_date.isnot(None),
                Task.is_completed.is_(False),
                Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
            )
            .all()
        )

        for task in tasks:
            if task.due_date:
                from datetime import datetime as dt

                due_dt = dt.combine(task.due_date, task.due_time or dt.min.time())
                due_dt = due_dt.replace(tzinfo=org_tz)

                if window_start <= due_dt <= window_end:
                    trigger_task_due(db, task)


def trigger_task_overdue_sweep(db: Session, org_id: UUID) -> None:
    """Find and trigger task_overdue workflows for overdue tasks."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.db.models import Task, Surrogate, Organization

    org = db.query(Organization).filter(Organization.id == org_id).first()
    tz_name = org.timezone if org and org.timezone else "UTC"
    try:
        org_tz = ZoneInfo(tz_name)
    except Exception:
        org_tz = ZoneInfo("UTC")
    now = datetime.now(org_tz)
    today = now.date()

    overdue_tasks = (
        db.query(Task)
        .join(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Task.due_date.isnot(None),
            Task.due_date < today,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
        )
        .all()
    )

    for task in overdue_tasks:
        trigger_task_overdue(db, task)


# =============================================================================
# Match Triggers (called from match_service.py)
# =============================================================================


def trigger_match_proposed(db: Session, match: Match) -> None:
    """Trigger workflows when a match is proposed."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.MATCH_PROPOSED,
        entity_type="match",
        entity_id=match.id,
        event_data={
            "match_id": str(match.id),
            "surrogate_id": str(match.surrogate_id),
            "intended_parent_id": str(match.intended_parent_id)
            if match.intended_parent_id
            else None,
            "status": match.status,
        },
        org_id=match.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_match_accepted(db: Session, match: Match) -> None:
    """Trigger workflows when a match is accepted."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.MATCH_ACCEPTED,
        entity_type="match",
        entity_id=match.id,
        event_data={
            "match_id": str(match.id),
            "surrogate_id": str(match.surrogate_id),
            "intended_parent_id": str(match.intended_parent_id)
            if match.intended_parent_id
            else None,
            "status": match.status,
            "accepted_at": match.accepted_at.isoformat() if match.accepted_at else None,
        },
        org_id=match.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_match_rejected(db: Session, match: Match) -> None:
    """Trigger workflows when a match is rejected."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.MATCH_REJECTED,
        entity_type="match",
        entity_id=match.id,
        event_data={
            "match_id": str(match.id),
            "surrogate_id": str(match.surrogate_id),
            "intended_parent_id": str(match.intended_parent_id)
            if match.intended_parent_id
            else None,
            "status": match.status,
        },
        org_id=match.organization_id,
        source=WorkflowEventSource.USER,
    )


# =============================================================================
# Document Triggers (called from attachment_service.py AFTER scan passes)
# =============================================================================


def trigger_document_uploaded(db: Session, attachment: Attachment) -> None:
    """
    Trigger workflows when a document is uploaded and passed virus scan.

    Note: Only call this after scan_status = 'clean', not on initial upload.
    Skip if file is quarantined.
    """
    # Get org_id from the related entity
    org_id = None
    surrogate_id = None

    if attachment.surrogate_id:
        surrogate = db.query(Surrogate).filter(Surrogate.id == attachment.surrogate_id).first()
        if surrogate:
            org_id = surrogate.organization_id
            surrogate_id = surrogate.id

    # Fallback: check intended_parent_id for IP attachments
    if not org_id and hasattr(attachment, "intended_parent_id") and attachment.intended_parent_id:
        from app.db.models import IntendedParent

        ip = (
            db.query(IntendedParent)
            .filter(IntendedParent.id == attachment.intended_parent_id)
            .first()
        )
        if ip:
            org_id = ip.organization_id

    if not org_id:
        return

    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.DOCUMENT_UPLOADED,
        entity_type="document",
        entity_id=attachment.id,
        event_data={
            "attachment_id": str(attachment.id),
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "surrogate_id": str(surrogate_id) if surrogate_id else None,
            "uploaded_by": str(attachment.uploaded_by_user_id)
            if attachment.uploaded_by_user_id
            else None,
        },
        org_id=org_id,
        source=WorkflowEventSource.USER,
    )


# =============================================================================
# Note Triggers (called from note_service.py)
# High-volume trigger - consider throttling
# =============================================================================


def trigger_note_added(db: Session, note: EntityNote) -> None:
    """
    Trigger workflows when a note is added to an entity.

    Warning: This is a high-volume trigger. Workflows using this trigger
    should have conditions to avoid excessive execution.
    """
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.NOTE_ADDED,
        entity_type="note",
        entity_id=note.id,
        event_data={
            "note_id": str(note.id),
            "entity_type": note.entity_type,
            "entity_id": str(note.entity_id),
            "author_id": str(note.author_id) if note.author_id else None,
        },
        org_id=note.organization_id,
        source=WorkflowEventSource.USER,
    )


# =============================================================================
# Appointment Triggers (called from appointment_service.py)
# =============================================================================


def trigger_appointment_scheduled(db: Session, appointment: Appointment) -> None:
    """Trigger workflows when an appointment is scheduled/approved."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.APPOINTMENT_SCHEDULED,
        entity_type="appointment",
        entity_id=appointment.id,
        event_data={
            "appointment_id": str(appointment.id),
            "surrogate_id": str(appointment.surrogate_id) if appointment.surrogate_id else None,
            "intended_parent_id": str(appointment.intended_parent_id)
            if appointment.intended_parent_id
            else None,
            "user_id": str(appointment.user_id),
            "scheduled_start": appointment.scheduled_start.isoformat()
            if appointment.scheduled_start
            else None,
            "scheduled_end": appointment.scheduled_end.isoformat()
            if appointment.scheduled_end
            else None,
            "appointment_type": appointment.appointment_type.name
            if appointment.appointment_type
            else None,
            "status": appointment.status,
        },
        org_id=appointment.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_appointment_completed(db: Session, appointment: Appointment) -> None:
    """Trigger workflows when an appointment is marked as completed."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.APPOINTMENT_COMPLETED,
        entity_type="appointment",
        entity_id=appointment.id,
        event_data={
            "appointment_id": str(appointment.id),
            "surrogate_id": str(appointment.surrogate_id) if appointment.surrogate_id else None,
            "intended_parent_id": str(appointment.intended_parent_id)
            if appointment.intended_parent_id
            else None,
            "user_id": str(appointment.user_id),
            "scheduled_start": appointment.scheduled_start.isoformat()
            if appointment.scheduled_start
            else None,
            "scheduled_end": appointment.scheduled_end.isoformat()
            if appointment.scheduled_end
            else None,
            "status": appointment.status,
        },
        org_id=appointment.organization_id,
        source=WorkflowEventSource.USER,
    )


def _should_run_cron(cron: str, now, tz: str) -> bool:
    """
    Simple cron matching for common patterns.

    Supports:
    - "0 9 * * *" = daily at 9am
    - "0 9 * * 1" = Monday at 9am
    - "0 9 * * 1-5" = weekdays at 9am

    For full cron support, install croniter.
    """
    try:
        from zoneinfo import ZoneInfo

        local_tz = ZoneInfo(tz)
        local_now = now.astimezone(local_tz)
    except Exception:
        local_now = now

    parts = cron.split()
    if len(parts) != 5:
        return False

    minute, hour, dom, month, dow = parts

    # Check hour (simple exact match)
    if hour != "*" and int(hour) != local_now.hour:
        return False

    # Check minute (simple exact match)
    if minute != "*" and int(minute) != local_now.minute:
        return False

    # Check day of week
    if dow != "*":
        if "-" in dow:
            start, end = map(int, dow.split("-"))
            if not (start <= local_now.weekday() <= end):
                return False
        elif int(dow) != local_now.weekday():
            return False

    return True
