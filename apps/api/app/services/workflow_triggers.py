"""Workflow triggers - hooks into core services to trigger workflows."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import OwnerType, WorkflowEventSource, WorkflowTriggerType
from app.db.models import (
    Appointment,
    Attachment,
    Donor,
    EntityNote,
    FormSubmission,
    IntakeLead,
    Match,
    PipelineStage,
    Surrogate,
    Task,
)
from app.schemas.workflow import is_supported_simple_cron
from app.services.workflow_engine import engine


def _get_entity_owner_id(surrogate: Surrogate) -> UUID | None:
    """Get owner_id if surrogate is owned by a user (not queue/unassigned)."""
    if surrogate.owner_type == OwnerType.USER.value and surrogate.owner_id:
        return surrogate.owner_id
    return None


def _get_donor_owner_id(donor: Donor) -> UUID | None:
    if donor.owner_type == OwnerType.USER.value and donor.owner_id:
        return donor.owner_id
    return None


def _workflow_applies_to_owner(workflow, entity_owner_id: UUID | None) -> bool:
    """Return whether one org or personal workflow applies to an entity owner."""
    if workflow.scope == "org":
        return True
    return workflow.scope == "personal" and workflow.owner_user_id == entity_owner_id


def _workflow_applies_to_surrogate(workflow, surrogate: Surrogate) -> bool:
    """Return whether one org or personal workflow applies to this surrogate."""
    return _workflow_applies_to_owner(workflow, _get_entity_owner_id(surrogate))


def _get_owner_id_for_surrogate_id(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID | None,
) -> UUID | None:
    """Lookup surrogate owner_id for scope filtering on non-surrogate entities."""
    if not surrogate_id:
        return None
    surrogate = (
        db.query(Surrogate)
        .filter(
            Surrogate.id == surrogate_id,
            Surrogate.organization_id == org_id,
        )
        .first()
    )
    if not surrogate:
        return None
    return _get_entity_owner_id(surrogate)


def _get_donor_by_id(db: Session, org_id: UUID, donor_id: UUID | None) -> Donor | None:
    if not donor_id:
        return None
    return db.query(Donor).filter(Donor.id == donor_id, Donor.organization_id == org_id).first()


def _task_subject_context(db: Session, task: Task) -> tuple[str | None, UUID | None, UUID | None]:
    donor = _get_donor_by_id(db, task.organization_id, getattr(task, "donor_id", None))
    if donor:
        return donor.pipeline_entity_type, donor.id, _get_donor_owner_id(donor)
    surrogate_id = getattr(task, "surrogate_id", None)
    if surrogate_id:
        return (
            "surrogate",
            surrogate_id,
            _get_owner_id_for_surrogate_id(db, task.organization_id, surrogate_id),
        )
    return None, None, None


# =============================================================================
# Donor Triggers (called from donor_service.py)
# =============================================================================


def trigger_donor_created(db: Session, donor: Donor) -> None:
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.DONOR_CREATED,
        entity_type="donor",
        entity_id=donor.id,
        subject_type=donor.pipeline_entity_type,
        subject_id=donor.id,
        event_data={
            "donor_id": str(donor.id),
            "donor_number": donor.donor_number,
            "donor_type": donor.donor_type,
            "stage_id": str(donor.stage_id),
            "stage_key": donor.stage_key,
            "stage_slug": donor.stage_slug,
            "source": donor.source,
        },
        org_id=donor.organization_id,
        source=WorkflowEventSource.USER,
        entity_owner_id=_get_donor_owner_id(donor),
    )


def trigger_donor_stage_changed(
    db: Session,
    donor: Donor,
    *,
    old_stage: PipelineStage,
    new_stage: PipelineStage,
) -> None:
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED,
        entity_type="donor",
        entity_id=donor.id,
        subject_type=donor.pipeline_entity_type,
        subject_id=donor.id,
        event_data={
            "donor_id": str(donor.id),
            "old_stage_id": str(old_stage.id),
            "new_stage_id": str(new_stage.id),
            "old_stage_key": old_stage.stage_key,
            "new_stage_key": new_stage.stage_key,
            "old_status": old_stage.slug,
            "new_status": new_stage.slug,
        },
        org_id=donor.organization_id,
        source=WorkflowEventSource.USER,
        entity_owner_id=_get_donor_owner_id(donor),
    )


def trigger_donor_assigned(
    db: Session,
    donor: Donor,
    *,
    old_owner_type: str | None,
    old_owner_id: UUID | None,
) -> None:
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.DONOR_ASSIGNED,
        entity_type="donor",
        entity_id=donor.id,
        subject_type=donor.pipeline_entity_type,
        subject_id=donor.id,
        event_data={
            "donor_id": str(donor.id),
            "old_owner_type": old_owner_type,
            "old_owner_id": str(old_owner_id) if old_owner_id else None,
            "new_owner_type": donor.owner_type,
            "new_owner_id": str(donor.owner_id) if donor.owner_id else None,
        },
        org_id=donor.organization_id,
        source=WorkflowEventSource.USER,
        entity_owner_id=_get_donor_owner_id(donor),
    )


def trigger_donor_updated(db: Session, donor: Donor, changed_fields: list[str]) -> None:
    if not changed_fields:
        return
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.DONOR_UPDATED,
        entity_type="donor",
        entity_id=donor.id,
        subject_type=donor.pipeline_entity_type,
        subject_id=donor.id,
        event_data={
            "donor_id": str(donor.id),
            "changed_fields": changed_fields,
        },
        org_id=donor.organization_id,
        source=WorkflowEventSource.USER,
        entity_owner_id=_get_donor_owner_id(donor),
    )


# =============================================================================
# Surrogate Triggers (called from surrogate_service.py)
# =============================================================================


def trigger_surrogate_created(db: Session, surrogate: Surrogate) -> None:
    """Trigger workflows when a new surrogate is created."""
    from app.services import pipeline_service

    stage = pipeline_service.get_stage_by_id(db, surrogate.stage_id)
    stage_slug = stage.slug if stage else None
    stage_key = stage.stage_key if stage else None
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
            "stage_key": stage_key,
            "status_label": surrogate.status_label,
        },
        org_id=surrogate.organization_id,
        source=WorkflowEventSource.USER,
        entity_owner_id=_get_entity_owner_id(surrogate),
    )


def trigger_status_changed(
    db: Session,
    surrogate: Surrogate,
    old_stage_id: UUID | None,
    new_stage_id: UUID | None,
    old_stage_slug: str | None,
    new_stage_slug: str | None,
    old_stage_key: str | None = None,
    new_stage_key: str | None = None,
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
            "old_stage_key": old_stage_key,
            "new_stage_key": new_stage_key,
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
        entity_owner_id=_get_entity_owner_id(surrogate),
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
        entity_owner_id=_get_entity_owner_id(surrogate),
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
        entity_owner_id=_get_entity_owner_id(surrogate),
    )


def trigger_form_started(
    db: Session,
    surrogate: Surrogate,
    form_id: UUID,
    draft_id: UUID,
    started_at: datetime | None,
    updated_at: datetime | None,
) -> None:
    """Trigger workflows when an applicant starts a form draft."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.FORM_STARTED,
        entity_type="surrogate",
        entity_id=surrogate.id,
        event_data={
            "surrogate_id": str(surrogate.id),
            "form_id": str(form_id),
            "draft_id": str(draft_id),
            "started_at": started_at.isoformat() if started_at else None,
            "updated_at": updated_at.isoformat() if updated_at else None,
        },
        org_id=surrogate.organization_id,
        source=WorkflowEventSource.SYSTEM,
        entity_owner_id=_get_entity_owner_id(surrogate),
    )


def trigger_form_submitted(
    db: Session,
    *,
    org_id: UUID,
    form_id: UUID,
    submission_id: UUID,
    submitted_at: datetime | None,
    surrogate_id: UUID | None = None,
    source_mode: str | None = None,
    entity_owner_id: UUID | None = None,
) -> None:
    """Trigger workflows when an applicant submits a form."""
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.id == submission_id,
            FormSubmission.organization_id == org_id,
        )
        .first()
    )
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.FORM_SUBMITTED,
        entity_type="form_submission",
        entity_id=submission_id,
        event_data={
            "surrogate_id": str(surrogate_id) if surrogate_id else None,
            "form_id": str(form_id),
            "submission_id": str(submission_id),
            "source_mode": source_mode,
            "lead_kind": submission.lead_kind if submission else None,
            "submitted_at": submitted_at.isoformat() if submitted_at else None,
        },
        org_id=org_id,
        source=WorkflowEventSource.SYSTEM,
        entity_owner_id=entity_owner_id,
    )


def trigger_intake_lead_created(
    db: Session,
    lead: IntakeLead,
    *,
    form_id: UUID | None,
    submission_id: UUID | None,
) -> None:
    """Trigger workflows when shared intake creates a provisional lead."""
    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.INTAKE_LEAD_CREATED,
        entity_type="intake_lead",
        entity_id=lead.id,
        event_data={
            "intake_lead_id": str(lead.id),
            "form_id": str(form_id) if form_id else None,
            "intake_link_id": str(lead.intake_link_id) if lead.intake_link_id else None,
            "submission_id": str(submission_id) if submission_id else None,
            "status": lead.status,
            "lead_type": lead.lead_type,
        },
        org_id=lead.organization_id,
        source=WorkflowEventSource.SYSTEM,
        entity_owner_id=lead.created_by_user_id,
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

    subject_type, subject_id, entity_owner_id = _task_subject_context(db, task)
    if subject_type is None or subject_id is None:
        return
    donor_subject = subject_type in {"egg_donor", "sperm_donor"}

    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.TASK_DUE,
        entity_type="task",
        entity_id=task.id,
        event_data={
            "task_id": str(task.id),
            "task_title": None if donor_subject else task.title,
            "due_date": str(task.due_date) if task.due_date else None,
            "surrogate_id": str(task.surrogate_id) if task.surrogate_id else None,
            "donor_id": str(task.donor_id) if task.donor_id else None,
        },
        org_id=org_id,
        source=WorkflowEventSource.SYSTEM,
        entity_owner_id=entity_owner_id,
        subject_type=subject_type,
        subject_id=subject_id,
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

    subject_type, subject_id, entity_owner_id = _task_subject_context(db, task)
    if subject_type is None or subject_id is None:
        return
    donor_subject = subject_type in {"egg_donor", "sperm_donor"}

    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.TASK_OVERDUE,
        entity_type="task",
        entity_id=task.id,
        event_data={
            "task_id": str(task.id),
            "task_title": None if donor_subject else task.title,
            "due_date": str(task.due_date) if task.due_date else None,
            "surrogate_id": str(task.surrogate_id) if task.surrogate_id else None,
            "donor_id": str(task.donor_id) if task.donor_id else None,
        },
        org_id=org_id,
        source=WorkflowEventSource.SYSTEM,
        entity_owner_id=entity_owner_id,
        subject_type=subject_type,
        subject_id=subject_id,
    )


# =============================================================================
# Sweep Triggers (called from worker.py)
# =============================================================================


def get_enabled_workflow_trigger_types(db: Session, org_id: UUID) -> set[str]:
    """Return the configured trigger types for enabled workflows in one org."""
    from app.db.models import AutomationWorkflow

    rows = (
        db.query(AutomationWorkflow.trigger_type)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.is_enabled.is_(True),
        )
        .distinct()
        .all()
    )
    return {trigger_type for (trigger_type,) in rows}


def has_due_scheduled_workflows(
    db: Session,
    org_id: UUID,
    *,
    evaluated_at: datetime,
) -> bool:
    """Return whether an org has an enabled scheduled workflow due now."""
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")

    from app.db.models import AutomationWorkflow

    workflows = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.trigger_type == WorkflowTriggerType.SCHEDULED.value,
            AutomationWorkflow.is_enabled.is_(True),
        )
        .all()
    )
    return any(
        _should_run_cron(
            (workflow.trigger_config or {}).get("cron", ""),
            evaluated_at,
            (workflow.trigger_config or {}).get("timezone", "America/Los_Angeles"),
        )
        for workflow in workflows
    )


def trigger_scheduled_workflows(
    db: Session,
    org_id: UUID,
    *,
    evaluated_at: datetime | None = None,
) -> None:
    """Trigger scheduled workflows for an org (called by daily sweep)."""

    from app.db.models import AutomationWorkflow

    now = evaluated_at or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")

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
            if workflow.subject_type in {"egg_donor", "sperm_donor"}:
                for donor in _iter_donors(db, org_id, workflow.subject_type):
                    if not _workflow_applies_to_owner(workflow, _get_donor_owner_id(donor)):
                        continue
                    engine.execute_workflow(
                        db=db,
                        workflow=workflow,
                        entity_type="donor",
                        entity_id=donor.id,
                        subject_type=workflow.subject_type,
                        subject_id=donor.id,
                        event_data={"schedule_time": now.isoformat(), "cron": cron},
                        source=WorkflowEventSource.SYSTEM,
                    )
            elif workflow.subject_type == "surrogate":
                for surrogate in _iter_surrogates(db, org_id):
                    if not _workflow_applies_to_surrogate(workflow, surrogate):
                        continue
                    engine.execute_workflow(
                        db=db,
                        workflow=workflow,
                        entity_type="surrogate",
                        entity_id=surrogate.id,
                        event_data={
                            "schedule_time": now.isoformat(),
                            "cron": cron,
                        },
                        source=WorkflowEventSource.SYSTEM,
                    )


def trigger_inactivity_workflows(db: Session, org_id: UUID) -> None:
    """Trigger inactivity workflows for surrogates with no recent activity."""
    from datetime import datetime, timedelta

    from app.db.models import AutomationWorkflow

    now = datetime.now(UTC)

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

        if workflow.subject_type in {"egg_donor", "sperm_donor"}:
            for donor in _iter_donors(db, org_id, workflow.subject_type, updated_before=threshold):
                if not _workflow_applies_to_owner(workflow, _get_donor_owner_id(donor)):
                    continue
                engine.execute_workflow(
                    db=db,
                    workflow=workflow,
                    entity_type="donor",
                    entity_id=donor.id,
                    subject_type=workflow.subject_type,
                    subject_id=donor.id,
                    event_data={
                        "days_inactive": days,
                        "last_activity": donor.updated_at.isoformat() if donor.updated_at else None,
                    },
                    source=WorkflowEventSource.SYSTEM,
                )
        elif workflow.subject_type == "surrogate":
            for surrogate in _iter_surrogates(db, org_id, updated_before=threshold):
                if not _workflow_applies_to_surrogate(workflow, surrogate):
                    continue
                engine.execute_workflow(
                    db=db,
                    workflow=workflow,
                    entity_type="surrogate",
                    entity_id=surrogate.id,
                    event_data={
                        "days_inactive": days,
                        "last_activity": surrogate.updated_at.isoformat()
                        if surrogate.updated_at
                        else None,
                    },
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
        yield from batch
        last_id = batch[-1].id


def _iter_donors(
    db: Session,
    org_id: UUID,
    subject_type: str,
    updated_before: datetime | None = None,
    batch_size: int = 500,
):
    """Iterate active donors for one exact subtype without cross-pipeline fallback."""
    donor_type = subject_type.removesuffix("_donor")
    if donor_type not in {"egg", "sperm"}:
        return
    last_id = None
    while True:
        query = db.query(Donor).filter(
            Donor.organization_id == org_id,
            Donor.donor_type == donor_type,
            Donor.is_archived.is_(False),
        )
        if updated_before is not None:
            query = query.filter(Donor.updated_at < updated_before)
        if last_id:
            query = query.filter(Donor.id > last_id)
        batch = query.order_by(Donor.id).limit(batch_size).all()
        if not batch:
            break
        yield from batch
        last_id = batch[-1].id


def trigger_task_due_sweep(db: Session, org_id: UUID) -> None:
    """Find and trigger task_due workflows for tasks due soon."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from app.db.models import AutomationWorkflow, Organization
    from app.services import task_service

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

        for task in task_service.iter_tasks_due_in_window(
            db,
            org_id,
            window_start,
            window_end,
        ):
            subject_type, subject_id, entity_owner_id = _task_subject_context(db, task)
            if subject_type is None and workflow.subject_type == "surrogate":
                subject_type, subject_id = "surrogate", task.id
            if subject_type != workflow.subject_type or subject_id is None:
                continue
            if not _workflow_applies_to_owner(workflow, entity_owner_id):
                continue
            donor_subject = subject_type in {"egg_donor", "sperm_donor"}
            engine.execute_workflow(
                db=db,
                workflow=workflow,
                entity_type="task",
                entity_id=task.id,
                event_data={
                    "task_id": str(task.id),
                    "task_title": None if donor_subject else task.title,
                    "due_date": str(task.due_date) if task.due_date else None,
                    "surrogate_id": str(task.surrogate_id) if task.surrogate_id else None,
                    "donor_id": (str(task.donor_id) if getattr(task, "donor_id", None) else None),
                },
                source=WorkflowEventSource.SYSTEM,
                subject_type=subject_type,
                subject_id=subject_id,
            )


def trigger_task_overdue_sweep(db: Session, org_id: UUID) -> None:
    """Find and trigger task_overdue workflows for overdue tasks."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.db.models import Organization
    from app.services import task_service

    org = db.query(Organization).filter(Organization.id == org_id).first()
    tz_name = org.timezone if org and org.timezone else "UTC"
    try:
        org_tz = ZoneInfo(tz_name)
    except Exception:
        org_tz = ZoneInfo("UTC")
    now = datetime.now(org_tz)
    today = now.date()

    for task in task_service.iter_overdue_tasks(db, org_id, today):
        trigger_task_overdue(db, task)


# =============================================================================
# Match Triggers (called from match_service.py)
# =============================================================================


def trigger_match_proposed(db: Session, match: Match) -> None:
    """Trigger workflows when a match is proposed."""
    entity_owner_id = _get_owner_id_for_surrogate_id(db, match.organization_id, match.surrogate_id)
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
        entity_owner_id=entity_owner_id,
    )


def trigger_match_accepted(db: Session, match: Match) -> None:
    """Trigger workflows when a match is accepted."""
    accepted_at = match.reviewed_at or match.updated_at
    entity_owner_id = _get_owner_id_for_surrogate_id(db, match.organization_id, match.surrogate_id)
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
            "accepted_at": accepted_at.isoformat() if accepted_at else None,
        },
        org_id=match.organization_id,
        source=WorkflowEventSource.USER,
        entity_owner_id=entity_owner_id,
    )


def trigger_match_rejected(db: Session, match: Match) -> None:
    """Trigger workflows when a match is rejected."""
    entity_owner_id = _get_owner_id_for_surrogate_id(db, match.organization_id, match.surrogate_id)
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
        entity_owner_id=entity_owner_id,
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
    org_id = attachment.organization_id
    surrogate_id = None
    donor = None
    entity_owner_id = None
    subject_type = None
    subject_id = None

    if attachment.surrogate_id:
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.id == attachment.surrogate_id,
                Surrogate.organization_id == org_id,
            )
            .first()
        )
        if not surrogate:
            return
        surrogate_id = surrogate.id
        entity_owner_id = _get_entity_owner_id(surrogate)
        subject_type = "surrogate"
        subject_id = surrogate.id

    if not attachment.surrogate_id:
        donor_id = getattr(attachment, "donor_id", None)
        donor = _get_donor_by_id(db, org_id, donor_id)
        if donor is None:
            donor = (
                db.query(Donor)
                .filter(
                    Donor.organization_id == org_id,
                    Donor.profile_photo_attachment_id == attachment.id,
                )
                .first()
            )
        if donor:
            subject_type = donor.pipeline_entity_type
            subject_id = donor.id
            entity_owner_id = _get_donor_owner_id(donor)

    # Fallback: check intended_parent_id for IP attachments
    if not attachment.surrogate_id and not donor and attachment.intended_parent_id:
        from app.db.models import IntendedParent

        ip = (
            db.query(IntendedParent)
            .filter(
                IntendedParent.id == attachment.intended_parent_id,
                IntendedParent.organization_id == org_id,
            )
            .first()
        )
        if not ip:
            return

    if not org_id:
        return

    engine.trigger(
        db=db,
        trigger_type=WorkflowTriggerType.DOCUMENT_UPLOADED,
        entity_type="document",
        entity_id=attachment.id,
        event_data={
            "attachment_id": str(attachment.id),
            "filename": None if donor else attachment.filename,
            "content_type": attachment.content_type,
            "surrogate_id": str(surrogate_id) if surrogate_id else None,
            "donor_id": str(donor.id) if donor else None,
            "uploaded_by": str(attachment.uploaded_by_user_id)
            if attachment.uploaded_by_user_id
            else None,
        },
        org_id=org_id,
        source=WorkflowEventSource.USER,
        entity_owner_id=entity_owner_id,
        subject_type=subject_type,
        subject_id=subject_id,
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
    entity_owner_id = None
    subject_type = None
    subject_id = None
    if note.entity_type == "donor":
        donor = _get_donor_by_id(db, note.organization_id, note.entity_id)
        if not donor:
            return
        subject_type = donor.pipeline_entity_type
        subject_id = donor.id
        entity_owner_id = _get_donor_owner_id(donor)
    elif note.entity_type == "surrogate":
        subject_type = "surrogate"
        subject_id = note.entity_id
        entity_owner_id = _get_owner_id_for_surrogate_id(db, note.organization_id, note.entity_id)
    elif note.entity_type == "match":
        match = (
            db.query(Match)
            .filter(
                Match.id == note.entity_id,
                Match.organization_id == note.organization_id,
            )
            .first()
        )
        if match:
            entity_owner_id = _get_owner_id_for_surrogate_id(
                db, note.organization_id, match.surrogate_id
            )

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
        entity_owner_id=entity_owner_id,
        subject_type=subject_type,
        subject_id=subject_id,
    )


# =============================================================================
# Appointment Triggers (called from appointment_service.py)
# =============================================================================


def trigger_appointment_scheduled(db: Session, appointment: Appointment) -> None:
    """Trigger workflows when an appointment is scheduled/approved."""
    entity_owner_id = _get_owner_id_for_surrogate_id(
        db, appointment.organization_id, appointment.surrogate_id
    )
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
        entity_owner_id=entity_owner_id,
    )


def trigger_appointment_completed(db: Session, appointment: Appointment) -> None:
    """Trigger workflows when an appointment is marked as completed."""
    entity_owner_id = _get_owner_id_for_surrogate_id(
        db, appointment.organization_id, appointment.surrogate_id
    )
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
        entity_owner_id=entity_owner_id,
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
    if not is_supported_simple_cron(cron):
        return False

    try:
        from zoneinfo import ZoneInfo

        local_tz = ZoneInfo(tz)
        local_now = now.astimezone(local_tz)
    except Exception:
        return False

    parts = cron.split()
    minute, hour, dom, month, dow = parts

    def _cron_dow_to_py(value: int) -> int:
        if value in (0, 7):
            return 6
        return (value - 1) % 7

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
            cron_range = range(start, end + 1)
            valid_days = {_cron_dow_to_py(value) for value in cron_range}
            if local_now.weekday() not in valid_days:
                return False
        elif _cron_dow_to_py(int(dow)) != local_now.weekday():
            return False

    return True
