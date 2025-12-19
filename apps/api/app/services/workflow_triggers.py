"""Workflow triggers - hooks into core services to trigger workflows."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Case, Task
from app.db.enums import WorkflowTriggerType, WorkflowEventSource
from app.services.workflow_engine import engine


# =============================================================================
# Case Triggers (called from case_service.py)
# =============================================================================

def trigger_case_created(db: Session, case: Case) -> None:
    """Trigger workflows when a new case is created."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.CASE_CREATED,
        entity_type="case",
        entity_id=case.id,
        event_data={
            "case_id": str(case.id),
            "case_number": case.case_number,
            "source": case.source,
            "status": case.status,
        },
        org_id=case.organization_id,
        source=WorkflowEventSource.USER,
    )


def trigger_status_changed(
    db: Session,
    case: Case,
    old_status: str,
    new_status: str,
) -> None:
    """Trigger workflows when case status changes."""
    if old_status == new_status:
        return
    
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        entity_type="case",
        entity_id=case.id,
        event_data={
            "case_id": str(case.id),
            "old_status": old_status,
            "new_status": new_status,
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
        tz = config.get("timezone", "America/New_York")
        
        # Simple cron matching (for daily/weekly schedules)
        # Full cron parsing would require croniter library
        if _should_run_cron(cron, now, tz):
            # For scheduled workflows, we need to run against all active cases
            # This is expensive - consider limiting or using pagination
            from app.db.models import Case
            cases = db.query(Case).filter(
                Case.organization_id == org_id,
                Case.is_archived == False,
            ).limit(1000).all()
            
            for case in cases:
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
        inactive_cases = db.query(Case).filter(
            Case.organization_id == org_id,
            Case.is_archived == False,
            Case.updated_at < threshold,
        ).limit(500).all()
        
        for case in inactive_cases:
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
