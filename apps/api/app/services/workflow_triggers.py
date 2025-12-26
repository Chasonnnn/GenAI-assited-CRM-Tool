"""Workflow triggers - hooks into core services to trigger workflows."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Case, Task, Match, Attachment, EntityNote, Appointment
from app.db.enums import WorkflowTriggerType, WorkflowEventSource
from app.services.workflow_engine import engine


# =============================================================================
# Case Triggers (called from case_service.py)
# =============================================================================

def trigger_case_created(db: Session, case: Case) -> None:
    """Trigger workflows when a new case is created."""
    from app.services import pipeline_service
    stage = pipeline_service.get_stage_by_id(db, case.stage_id)
    stage_slug = stage.slug if stage else None
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.CASE_CREATED,
        entity_type="case",
        entity_id=case.id,
        event_data={
            "case_id": str(case.id),
            "case_number": case.case_number,
            "source": case.source,
            "stage_id": str(case.stage_id),
            "stage_slug": stage_slug,
            "status_label": case.status_label,
        },
        org_id=case.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_status_changed(
    db: Session,
    case: Case,
    old_stage_id: UUID | None,
    new_stage_id: UUID | None,
    old_stage_slug: str | None,
    new_stage_slug: str | None,
) -> None:
    """Trigger workflows when case status changes."""
    if old_stage_id == new_stage_id:
        return
    
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        entity_type="case",
        entity_id=case.id,
        event_data={
            "case_id": str(case.id),
            "old_stage_id": str(old_stage_id) if old_stage_id else None,
            "new_stage_id": str(new_stage_id) if new_stage_id else None,
            "old_status": old_stage_slug,
            "new_status": new_stage_slug,
        },
        org_id=case.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_case_assigned(
    db: Session,
    case: Case,
    old_owner_id: UUID | None,
    new_owner_id: UUID | None,
    old_owner_type: str | None = None,
    new_owner_type: str | None = None,
) -> None:
    """Trigger workflows when case is assigned."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.CASE_ASSIGNED,
        entity_type="case",
        entity_id=case.id,
        event_data={
            "case_id": str(case.id),
            "old_owner_id": str(old_owner_id) if old_owner_id else None,
            "new_owner_id": str(new_owner_id) if new_owner_id else None,
            "old_owner_type": old_owner_type,
            "new_owner_type": new_owner_type,
        },
        org_id=case.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_case_updated(
    db: Session,
    case: Case,
    changed_fields: list[str],
    old_values: dict,
    new_values: dict,
) -> None:
    """Trigger workflows when specific case fields change."""
    if not changed_fields:
        return
    
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.CASE_UPDATED,
        entity_type="case",
        entity_id=case.id,
        event_data={
            "case_id": str(case.id),
            "changed_fields": changed_fields,
            "old_values": old_values,
            "new_values": new_values,
        },
        org_id=case.organization_id,
        source=WorkflowEventSource.USER,
    )


# =============================================================================
# Task Triggers (called from worker sweep)
# =============================================================================

def trigger_task_due(db: Session, task: Task) -> None:
    """Trigger workflows when a task is about to be due."""
    case = task.case if hasattr(task, 'case') else None
    org_id = task.organization_id if hasattr(task, 'organization_id') else (case.organization_id if case else None)
    
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
            "case_id": str(task.case_id) if task.case_id else None,
        },
        org_id=org_id,
        source=WorkflowEventSource.SYSTEM,
    )


def trigger_task_overdue(db: Session, task: Task) -> None:
    """Trigger workflows when a task is overdue."""
    case = task.case if hasattr(task, 'case') else None
    org_id = task.organization_id if hasattr(task, 'organization_id') else (case.organization_id if case else None)
    
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
            "case_id": str(task.case_id) if task.case_id else None,
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
    
    workflows = db.query(AutomationWorkflow).filter(
        AutomationWorkflow.organization_id == org_id,
        AutomationWorkflow.trigger_type == WorkflowTriggerType.SCHEDULED.value,
        AutomationWorkflow.is_enabled == True,
    ).all()
    
    for workflow in workflows:
        config = workflow.trigger_config
        cron = config.get("cron", "")
        tz = config.get("timezone", "America/Los_Angeles")
        
        # Simple cron matching (for daily/weekly schedules)
        # Full cron parsing would require croniter library
        if _should_run_cron(cron, now, tz):
            for case in _iter_cases(db, org_id):
                engine.trigger(
                    db=db,
                    trigger_type=WorkflowTriggerType.SCHEDULED,
                    entity_type="case",
                    entity_id=case.id,
                    event_data={
                        "schedule_time": now.isoformat(),
                        "cron": cron,
                    },
                    org_id=org_id,
                    source=WorkflowEventSource.SYSTEM,
                )


def trigger_inactivity_workflows(db: Session, org_id: UUID) -> None:
    """Trigger inactivity workflows for cases with no recent activity."""
    from datetime import datetime, timezone, timedelta
    from app.db.models import AutomationWorkflow, Case
    
    now = datetime.now(timezone.utc)
    
    workflows = db.query(AutomationWorkflow).filter(
        AutomationWorkflow.organization_id == org_id,
        AutomationWorkflow.trigger_type == WorkflowTriggerType.INACTIVITY.value,
        AutomationWorkflow.is_enabled == True,
    ).all()
    
    for workflow in workflows:
        days = workflow.trigger_config.get("days", 7)
        threshold = now - timedelta(days=days)
        
        # Find cases with no activity since threshold
        # Using updated_at as proxy for activity
        for case in _iter_cases(db, org_id, updated_before=threshold):
            engine.trigger(
                db=db,
                trigger_type=WorkflowTriggerType.INACTIVITY,
                entity_type="case",
                entity_id=case.id,
                event_data={
                    "days_inactive": days,
                    "last_activity": case.updated_at.isoformat() if case.updated_at else None,
                },
                org_id=org_id,
                source=WorkflowEventSource.SYSTEM,
            )


def _iter_cases(
    db: Session,
    org_id: UUID,
    updated_before: "datetime | None" = None,
    batch_size: int = 500,
):
    """Iterate through active cases in batches to avoid truncating large orgs."""
    from app.db.models import Case
    
    last_id = None
    while True:
        query = db.query(Case).filter(
            Case.organization_id == org_id,
            Case.is_archived == False,
        )
        if updated_before is not None:
            query = query.filter(Case.updated_at < updated_before)
        if last_id:
            query = query.filter(Case.id > last_id)
        batch = query.order_by(Case.id).limit(batch_size).all()
        if not batch:
            break
        for case in batch:
            yield case
        last_id = batch[-1].id


def trigger_task_due_sweep(db: Session, org_id: UUID) -> None:
    """Find and trigger task_due workflows for tasks due soon."""
    from datetime import datetime, timezone, timedelta
    from app.db.models import AutomationWorkflow, Task, Case
    
    now = datetime.now(timezone.utc)
    
    workflows = db.query(AutomationWorkflow).filter(
        AutomationWorkflow.organization_id == org_id,
        AutomationWorkflow.trigger_type == WorkflowTriggerType.TASK_DUE.value,
        AutomationWorkflow.is_enabled == True,
    ).all()
    
    for workflow in workflows:
        hours_before = workflow.trigger_config.get("hours_before", 24)
        window_start = now + timedelta(hours=hours_before - 1)
        window_end = now + timedelta(hours=hours_before + 1)
        
        # Find tasks due within the window
        tasks = db.query(Task).join(Case).filter(
            Case.organization_id == org_id,
            Task.due_date != None,
            Task.is_completed == False,
        ).all()
        
        for task in tasks:
            if task.due_date:
                from datetime import datetime as dt
                due_dt = dt.combine(task.due_date, task.due_time or dt.min.time())
                due_dt = due_dt.replace(tzinfo=timezone.utc)
                
                if window_start <= due_dt <= window_end:
                    trigger_task_due(db, task)


def trigger_task_overdue_sweep(db: Session, org_id: UUID) -> None:
    """Find and trigger task_overdue workflows for overdue tasks."""
    from datetime import datetime, timezone
    from app.db.models import Task, Case
    
    now = datetime.now(timezone.utc)
    today = now.date()
    
    overdue_tasks = db.query(Task).join(Case).filter(
        Case.organization_id == org_id,
        Task.due_date != None,
        Task.due_date < today,
        Task.is_completed == False,
    ).all()
    
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
            "case_id": str(match.case_id),
            "intended_parent_id": str(match.intended_parent_id) if match.intended_parent_id else None,
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
            "case_id": str(match.case_id),
            "intended_parent_id": str(match.intended_parent_id) if match.intended_parent_id else None,
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
            "case_id": str(match.case_id),
            "intended_parent_id": str(match.intended_parent_id) if match.intended_parent_id else None,
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
    case_id = None
    
    if attachment.case_id:
        case = db.query(Case).filter(Case.id == attachment.case_id).first()
        if case:
            org_id = case.organization_id
            case_id = case.id
    
    # Fallback: check intended_parent_id for IP attachments
    if not org_id and hasattr(attachment, 'intended_parent_id') and attachment.intended_parent_id:
        from app.db.models import IntendedParent
        ip = db.query(IntendedParent).filter(IntendedParent.id == attachment.intended_parent_id).first()
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
            "case_id": str(case_id) if case_id else None,
            "uploaded_by": str(attachment.uploaded_by_user_id) if attachment.uploaded_by_user_id else None,
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
            "case_id": str(appointment.case_id) if appointment.case_id else None,
            "intended_parent_id": str(appointment.intended_parent_id) if appointment.intended_parent_id else None,
            "user_id": str(appointment.user_id),
            "scheduled_start": appointment.scheduled_start.isoformat() if appointment.scheduled_start else None,
            "scheduled_end": appointment.scheduled_end.isoformat() if appointment.scheduled_end else None,
            "appointment_type": appointment.appointment_type.name if appointment.appointment_type else None,
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
            "case_id": str(appointment.case_id) if appointment.case_id else None,
            "intended_parent_id": str(appointment.intended_parent_id) if appointment.intended_parent_id else None,
            "user_id": str(appointment.user_id),
            "scheduled_start": appointment.scheduled_start.isoformat() if appointment.scheduled_start else None,
            "scheduled_end": appointment.scheduled_end.isoformat() if appointment.scheduled_end else None,
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
        import pytz
        local_tz = pytz.timezone(tz)
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
