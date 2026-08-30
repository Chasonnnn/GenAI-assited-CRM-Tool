"""Workflow service - CRUD operations for automation workflows."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import String, and_, cast, exists, func, or_
from sqlalchemy.orm import Session

from app.db.enums import OwnerType, WorkflowExecutionStatus, WorkflowTriggerType
from app.db.models import (
    AutomationWorkflow,
    Donor,
    EmailTemplate,
    Form,
    FormSubmission,
    IntakeLead,
    MessageTemplate,
    Pipeline,
    Queue,
    Surrogate,
    Task,
    User,
    UserWorkflowPreference,
    WorkflowExecution,
)
from app.schemas.workflow import (
    ALLOWED_CONDITION_FIELDS,
    ALLOWED_EMAIL_VARIABLES,
    DONOR_ALLOWED_CONDITION_FIELDS,
    DONOR_ALLOWED_UPDATE_FIELDS,
    SURROGATE_ALLOWED_UPDATE_FIELDS,
    AddNoteActionConfig,
    AssignDonorActionConfig,
    AssignSurrogateActionConfig,
    AutoMatchSubmissionActionConfig,
    Condition,
    CreateIntakeLeadActionConfig,
    CreateTaskActionConfig,
    ExecutionRead,
    FormStartedTriggerConfig,
    FormSubmittedTriggerConfig,
    InactivityTriggerConfig,
    IntakeLeadCreatedTriggerConfig,
    PromoteIntakeLeadActionConfig,
    ScheduledTriggerConfig,
    SendEmailActionConfig,
    SendMessageActionConfig,
    SendNotificationActionConfig,
    SendZapierConversionEventActionConfig,
    StatusChangeTriggerConfig,
    SurrogateUpdatedTriggerConfig,
    TaskDueTriggerConfig,
    UpdateFieldActionConfig,
    WorkflowCreate,
    WorkflowOptions,
    WorkflowRead,
    WorkflowStats,
    WorkflowUpdate,
)
from app.services import user_service
from app.services.workflow_email_provider import validate_email_provider
from app.utils.pagination import paginate_query_by_offset

# =============================================================================
# Constants
# =============================================================================


TRIGGER_ENTITY_TYPES = {
    "surrogate_created": "surrogate",
    "status_changed": "surrogate",
    "surrogate_assigned": "surrogate",
    "surrogate_updated": "surrogate",
    "donor_created": "donor",
    "donor_stage_changed": "donor",
    "donor_assigned": "donor",
    "donor_updated": "donor",
    "form_started": "surrogate",
    "form_submitted": "form_submission",
    "intake_lead_created": "intake_lead",
    "task_due": "task",
    "task_overdue": "task",
    "scheduled": "surrogate",
    "inactivity": "surrogate",
    "match_proposed": "match",
    "match_accepted": "match",
    "match_rejected": "match",
    "appointment_scheduled": "appointment",
    "appointment_completed": "appointment",
    "note_added": "note",
    "document_uploaded": "document",
}

DONOR_SUBJECT_TYPES = {"egg_donor", "sperm_donor"}
DONOR_PERMISSION_CONTEXT = "donor"
SUPPORTED_WORKFLOW_SUBJECT_TYPES = {
    "surrogate",
    "form_submission",
    "intake_lead",
    "match",
    "appointment",
    *DONOR_SUBJECT_TYPES,
}
DONOR_TRIGGER_TYPES = {
    WorkflowTriggerType.DONOR_CREATED,
    WorkflowTriggerType.DONOR_STAGE_CHANGED,
    WorkflowTriggerType.DONOR_ASSIGNED,
    WorkflowTriggerType.DONOR_UPDATED,
    WorkflowTriggerType.TASK_DUE,
    WorkflowTriggerType.TASK_OVERDUE,
    WorkflowTriggerType.SCHEDULED,
    WorkflowTriggerType.INACTIVITY,
    WorkflowTriggerType.NOTE_ADDED,
    WorkflowTriggerType.DOCUMENT_UPLOADED,
}


def resolve_effective_workflow_subject_type(
    db: Session,
    org_id: UUID,
    *,
    subject_type: str | None,
    trigger_type: WorkflowTriggerType | str,
    trigger_config: dict[str, object] | None,
) -> str | None:
    """Resolve donor-sensitive generic intake workflows without changing execution subjects."""
    if subject_type in DONOR_SUBJECT_TYPES:
        return subject_type

    trigger_value = (
        trigger_type.value if isinstance(trigger_type, WorkflowTriggerType) else trigger_type
    )
    context_key = {
        WorkflowTriggerType.FORM_SUBMITTED.value: "lead_kind",
        WorkflowTriggerType.INTAKE_LEAD_CREATED.value: "lead_type",
    }.get(trigger_value)
    if context_key is None:
        return subject_type

    config = trigger_config or {}
    configured_kind = config.get(context_key)
    form_id = config.get("form_id")
    form_kind = None
    if form_id:
        try:
            parsed_form_id = UUID(str(form_id))
        except (TypeError, ValueError):
            parsed_form_id = None
        if parsed_form_id is not None:
            form_kind = (
                db.query(Form.lead_kind)
                .filter(
                    Form.id == parsed_form_id,
                    Form.organization_id == org_id,
                )
                .scalar()
            )

    if configured_kind in DONOR_SUBJECT_TYPES:
        return str(configured_kind)
    if form_kind in DONOR_SUBJECT_TYPES:
        return str(form_kind)
    if configured_kind == "surrogate" or form_kind == "surrogate":
        return subject_type
    if form_id and form_kind is None and configured_kind is None:
        # A deleted, foreign, or malformed form reference no longer proves this
        # legacy workflow was surrogate-only. Keep it donor-protected.
        return DONOR_PERMISSION_CONTEXT
    if not form_id and configured_kind is None:
        # An unscoped form/intake workflow can consume both surrogate and donor events.
        return DONOR_PERMISSION_CONTEXT
    return subject_type


def get_workflow_effective_subject_type(
    db: Session,
    workflow: AutomationWorkflow,
) -> str | None:
    return resolve_effective_workflow_subject_type(
        db,
        workflow.organization_id,
        subject_type=workflow.subject_type,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
    )


def _workflow_is_donor_related():
    """Match workflows that directly or indirectly can consume donor records."""
    scoped_form = (
        exists()
        .where(
            Form.organization_id == AutomationWorkflow.organization_id,
            cast(Form.id, String) == AutomationWorkflow.trigger_config["form_id"].astext,
        )
        .correlate(AutomationWorkflow)
    )
    donor_form = (
        exists()
        .where(
            Form.organization_id == AutomationWorkflow.organization_id,
            cast(Form.id, String) == AutomationWorkflow.trigger_config["form_id"].astext,
            Form.lead_kind.in_(DONOR_SUBJECT_TYPES),
        )
        .correlate(AutomationWorkflow)
    )
    return or_(
        AutomationWorkflow.subject_type.in_(DONOR_SUBJECT_TYPES),
        and_(
            AutomationWorkflow.trigger_type == WorkflowTriggerType.FORM_SUBMITTED.value,
            or_(
                AutomationWorkflow.trigger_config["lead_kind"].astext.in_(
                    DONOR_SUBJECT_TYPES
                ),
                donor_form,
                and_(
                    AutomationWorkflow.trigger_config["lead_kind"].astext.is_(None),
                    or_(
                        AutomationWorkflow.trigger_config["form_id"].astext.is_(None),
                        ~scoped_form,
                    ),
                ),
            ),
        ),
        and_(
            AutomationWorkflow.trigger_type == WorkflowTriggerType.INTAKE_LEAD_CREATED.value,
            or_(
                AutomationWorkflow.trigger_config["lead_type"].astext.in_(
                    DONOR_SUBJECT_TYPES
                ),
                donor_form,
                and_(
                    AutomationWorkflow.trigger_config["lead_type"].astext.is_(None),
                    or_(
                        AutomationWorkflow.trigger_config["form_id"].astext.is_(None),
                        ~scoped_form,
                    ),
                ),
            ),
        ),
    )


def _execution_is_donor_related():
    """Match direct and indirect donor workflow execution subjects."""
    return or_(
        and_(
            WorkflowExecution.subject_type.is_not(None),
            WorkflowExecution.subject_type.in_(DONOR_SUBJECT_TYPES),
        ),
        WorkflowExecution.trigger_event["lead_kind"].astext.in_(DONOR_SUBJECT_TYPES),
        WorkflowExecution.trigger_event["lead_type"].astext.in_(DONOR_SUBJECT_TYPES),
        exists()
        .where(
            AutomationWorkflow.id == WorkflowExecution.workflow_id,
            AutomationWorkflow.organization_id == WorkflowExecution.organization_id,
            _workflow_is_donor_related(),
        )
        .correlate(WorkflowExecution),
        and_(
            WorkflowExecution.entity_type == "form_submission",
            exists()
            .where(
                FormSubmission.id == WorkflowExecution.entity_id,
                FormSubmission.organization_id == WorkflowExecution.organization_id,
                FormSubmission.lead_kind.in_(DONOR_SUBJECT_TYPES),
            )
            .correlate(WorkflowExecution),
        ),
        and_(
            WorkflowExecution.entity_type == "intake_lead",
            exists()
            .where(
                IntakeLead.id == WorkflowExecution.entity_id,
                IntakeLead.organization_id == WorkflowExecution.organization_id,
                IntakeLead.lead_type.in_(DONOR_SUBJECT_TYPES),
            )
            .correlate(WorkflowExecution),
        ),
        and_(
            WorkflowExecution.entity_type == "task",
            exists()
            .where(
                Task.id == WorkflowExecution.entity_id,
                Task.organization_id == WorkflowExecution.organization_id,
                Task.donor_id.is_not(None),
            )
            .correlate(WorkflowExecution),
        ),
    )


def _exact_donor_execution_identity_match():
    """Join only the donor matching the execution tenant and explicit subtype."""
    return and_(
        WorkflowExecution.subject_id == Donor.id,
        Donor.organization_id == WorkflowExecution.organization_id,
        or_(
            and_(
                WorkflowExecution.subject_type == "egg_donor",
                Donor.donor_type == "egg",
            ),
            and_(
                WorkflowExecution.subject_type == "sperm_donor",
                Donor.donor_type == "sperm",
            ),
        ),
    )


LEGACY_TRIGGER_SUBJECT_TYPES = {
    WorkflowTriggerType.FORM_SUBMITTED.value: "form_submission",
    WorkflowTriggerType.INTAKE_LEAD_CREATED.value: "intake_lead",
    WorkflowTriggerType.MATCH_PROPOSED.value: "match",
    WorkflowTriggerType.MATCH_ACCEPTED.value: "match",
    WorkflowTriggerType.MATCH_REJECTED.value: "match",
    WorkflowTriggerType.APPOINTMENT_SCHEDULED.value: "appointment",
    WorkflowTriggerType.APPOINTMENT_COMPLETED.value: "appointment",
}


def _validate_subject_trigger(
    subject_type: str,
    trigger_type: WorkflowTriggerType,
) -> None:
    if subject_type not in SUPPORTED_WORKFLOW_SUBJECT_TYPES:
        raise ValueError(f"Unsupported workflow subject type: {subject_type}")
    if subject_type in DONOR_SUBJECT_TYPES:
        if trigger_type not in DONOR_TRIGGER_TYPES:
            raise ValueError(f"Trigger {trigger_type.value} does not support {subject_type}")
        return
    if trigger_type in {
        WorkflowTriggerType.DONOR_CREATED,
        WorkflowTriggerType.DONOR_STAGE_CHANGED,
        WorkflowTriggerType.DONOR_ASSIGNED,
        WorkflowTriggerType.DONOR_UPDATED,
    }:
        raise ValueError(f"Trigger {trigger_type.value} requires a donor subject")


def _validate_subject_conditions(subject_type: str, conditions: list[dict]) -> None:
    if subject_type not in DONOR_SUBJECT_TYPES:
        return
    invalid = sorted(
        condition.get("field")
        for condition in conditions
        if condition.get("field") not in DONOR_ALLOWED_CONDITION_FIELDS
    )
    if invalid:
        raise ValueError(f"Condition fields do not support {subject_type}: {', '.join(invalid)}")


def _resolve_stage_ref(
    db: Session,
    org_id: UUID,
    value: object | None,
    *,
    entity_type: str | None = None,
) -> tuple[str, str] | None:
    if value in (None, ""):
        return None

    from app.services import pipeline_service

    stage = None
    try:
        stage_uuid = UUID(str(value))
    except TypeError, ValueError:
        stage_uuid = None

    if stage_uuid is not None:
        stage = pipeline_service.get_stage_by_id(db, stage_uuid)
    else:
        default_pipeline_ids = [
            pipeline_id
            for (pipeline_id,) in (
                db.query(Pipeline.id)
                .filter(
                    Pipeline.organization_id == org_id,
                    Pipeline.is_default.is_(True),
                    Pipeline.entity_type == entity_type if entity_type else True,
                )
                .all()
            )
        ]
        if not default_pipeline_ids and entity_type:
            pipeline = pipeline_service.get_or_create_default_pipeline(
                db,
                org_id,
                entity_type=entity_type,
            )
            default_pipeline_ids = [pipeline.id]

        if len(default_pipeline_ids) == 1:
            stage = pipeline_service.resolve_stage(db, default_pipeline_ids[0], str(value))
        elif len(default_pipeline_ids) > 1:
            matches = [
                resolved
                for pipeline_id in default_pipeline_ids
                if (resolved := pipeline_service.resolve_stage(db, pipeline_id, str(value)))
                is not None
            ]
            if len(matches) == 1:
                stage = matches[0]

    if (
        not stage
        or stage.pipeline.organization_id != org_id
        or (entity_type is not None and stage.pipeline.entity_type != entity_type)
    ):
        return None
    return str(stage.id), stage.stage_key


def _canonicalize_trigger_config(
    db: Session,
    org_id: UUID,
    trigger_type: WorkflowTriggerType,
    trigger_config: dict[str, object],
    *,
    entity_type: str | None = None,
) -> dict[str, object]:
    config = deepcopy(trigger_config or {})
    intake_context_key = {
        WorkflowTriggerType.FORM_SUBMITTED: "lead_kind",
        WorkflowTriggerType.INTAKE_LEAD_CREATED: "lead_type",
    }.get(trigger_type)
    if intake_context_key is not None and config.get("form_id"):
        try:
            form_id = UUID(str(config["form_id"]))
        except (TypeError, ValueError) as exc:
            raise ValueError("Workflow form_id is invalid") from exc
        form = (
            db.query(Form)
            .filter(
                Form.id == form_id,
                Form.organization_id == org_id,
            )
            .first()
        )
        if not form:
            raise ValueError("Workflow form not found in organization")
        configured_kind = config.get(intake_context_key)
        if configured_kind is not None and configured_kind != form.lead_kind:
            raise ValueError(
                f"Workflow {intake_context_key} must match the selected form"
            )
        config[intake_context_key] = form.lead_kind

    if trigger_type not in {
        WorkflowTriggerType.STATUS_CHANGED,
        WorkflowTriggerType.DONOR_STAGE_CHANGED,
    }:
        return config

    effective_entity_type = entity_type or TRIGGER_ENTITY_TYPES.get(str(trigger_type))
    for prefix in ("from", "to"):
        ref = (
            config.get(f"{prefix}_stage_key")
            or config.get(f"{prefix}_stage_id")
            or config.get(f"{prefix}_status")
        )
        resolved = _resolve_stage_ref(db, org_id, ref, entity_type=effective_entity_type)
        config.pop(f"{prefix}_status", None)
        if resolved:
            config[f"{prefix}_stage_id"] = resolved[0]
            config[f"{prefix}_stage_key"] = resolved[1]
        else:
            if ref not in (None, "") and effective_entity_type in DONOR_SUBJECT_TYPES:
                raise ValueError(f"Stage {ref} not found in {effective_entity_type} pipeline")
            config.pop(f"{prefix}_stage_id", None)
            config.pop(f"{prefix}_stage_key", None)
    return config


def _canonicalize_conditions(
    db: Session,
    org_id: UUID,
    conditions: list[Condition] | list[dict] | None,
    *,
    entity_type: str | None = None,
) -> list[dict]:
    normalized: list[dict] = []
    for raw_condition in conditions or []:
        condition = (
            raw_condition.model_dump(mode="json")
            if isinstance(raw_condition, Condition)
            else deepcopy(raw_condition)
        )
        if condition.get("field") != "stage_id":
            normalized.append(condition)
            continue

        value = condition.get("value")
        if isinstance(value, list):
            resolved_ids: list[str] = []
            resolved_keys: list[str] = []
            for item in value:
                resolved = _resolve_stage_ref(db, org_id, item, entity_type=entity_type)
                if not resolved:
                    continue
                stage_id, stage_key = resolved
                if stage_id not in resolved_ids:
                    resolved_ids.append(stage_id)
                if stage_key not in resolved_keys:
                    resolved_keys.append(stage_key)
            condition["value"] = resolved_ids
            condition["stage_keys"] = resolved_keys
        else:
            resolved = _resolve_stage_ref(db, org_id, value, entity_type=entity_type)
            if resolved:
                condition["value"] = resolved[0]
                condition["stage_key"] = resolved[1]
        normalized.append(condition)
    return normalized


def _canonicalize_actions(
    db: Session,
    org_id: UUID,
    actions: list[dict[str, object]] | None,
    *,
    entity_type: str | None = None,
) -> list[dict]:
    normalized: list[dict] = []
    for raw_action in actions or []:
        action = deepcopy(raw_action)
        if action.get("action_type") == "update_status":
            stage_id = action.get("stage_id")
            if not stage_id:
                raise ValueError("update_status requires stage_id")
            action["action_type"] = "update_field"
            action["field"] = "stage_id"
            action["value"] = stage_id
            action.pop("stage_id", None)

        if action.get("action_type") == "update_field" and action.get("field") == "stage_id":
            resolved = _resolve_stage_ref(
                db,
                org_id,
                action.get("value_stage_key") or action.get("value"),
                entity_type=entity_type,
            )
            if resolved:
                action["value"] = resolved[0]
                action["value_stage_key"] = resolved[1]
        normalized.append(action)
    return normalized


def remap_workflow_stage_references(
    db: Session,
    org_id: UUID,
    workflow: AutomationWorkflow,
    remap_by_key: dict[str, str | None],
    *,
    entity_type: str | None = None,
) -> None:
    if not remap_by_key:
        return

    effective_entity_type = entity_type or TRIGGER_ENTITY_TYPES.get(workflow.trigger_type)
    trigger_config = deepcopy(workflow.trigger_config or {})
    if workflow.trigger_type in {
        WorkflowTriggerType.STATUS_CHANGED.value,
        WorkflowTriggerType.DONOR_STAGE_CHANGED.value,
    }:
        for prefix in ("from", "to"):
            current_key = trigger_config.get(f"{prefix}_stage_key")
            if isinstance(current_key, str) and current_key in remap_by_key:
                replacement = remap_by_key[current_key]
                if replacement:
                    trigger_config[f"{prefix}_stage_key"] = replacement
                else:
                    trigger_config.pop(f"{prefix}_stage_key", None)
                    trigger_config.pop(f"{prefix}_stage_id", None)
            legacy_status = trigger_config.get(f"{prefix}_status")
            if isinstance(legacy_status, str):
                normalized_status = legacy_status.strip().lower()
                if normalized_status in remap_by_key:
                    replacement = remap_by_key[normalized_status]
                    if replacement:
                        trigger_config[f"{prefix}_stage_key"] = replacement
                    trigger_config.pop(f"{prefix}_status", None)
        workflow.trigger_config = _canonicalize_trigger_config(
            db,
            org_id,
            WorkflowTriggerType.STATUS_CHANGED,
            trigger_config,
            entity_type=effective_entity_type,
        )

    remapped_conditions: list[dict] = []
    for raw_condition in workflow.conditions or []:
        condition = deepcopy(raw_condition)
        if condition.get("field") == "stage_id":
            stage_key = condition.get("stage_key")
            stage_keys = condition.get("stage_keys")
            value = condition.get("value")
            if isinstance(stage_key, str) and stage_key in remap_by_key:
                replacement = remap_by_key[stage_key]
                if replacement:
                    condition["stage_key"] = replacement
                    condition["value"] = replacement
                else:
                    continue
            if isinstance(stage_keys, list):
                remapped_stage_keys = [
                    remap_by_key.get(str(item), str(item))
                    for item in stage_keys
                    if remap_by_key.get(str(item), str(item))
                ]
                condition["stage_keys"] = remapped_stage_keys
                condition["value"] = remapped_stage_keys
            elif stage_key is None:
                resolved = _resolve_stage_ref(
                    db,
                    org_id,
                    value,
                    entity_type=effective_entity_type,
                )
                current_key = resolved[1] if resolved else None
                if current_key in remap_by_key:
                    replacement = remap_by_key[current_key]
                    if replacement:
                        condition["stage_key"] = replacement
                        condition["value"] = replacement
                    else:
                        continue
        remapped_conditions.append(condition)
    workflow.conditions = _canonicalize_conditions(
        db,
        org_id,
        remapped_conditions,
        entity_type=effective_entity_type,
    )

    remapped_actions: list[dict] = []
    for raw_action in workflow.actions or []:
        action = deepcopy(raw_action)
        if action.get("action_type") == "update_field" and action.get("field") == "stage_id":
            stage_key = action.get("value_stage_key")
            if isinstance(stage_key, str) and stage_key in remap_by_key:
                replacement = remap_by_key[stage_key]
                if replacement:
                    action["value_stage_key"] = replacement
                else:
                    continue
        elif action.get("action_type") == "update_status":
            stage_ref = action.get("stage_id")
            resolved = _resolve_stage_ref(
                db,
                org_id,
                stage_ref,
                entity_type=effective_entity_type,
            )
            if resolved and resolved[1] in remap_by_key:
                replacement = remap_by_key[resolved[1]]
                if replacement:
                    action["stage_id"] = replacement
                else:
                    continue
        remapped_actions.append(action)
    workflow.actions = _canonicalize_actions(
        db,
        org_id,
        remapped_actions,
        entity_type=effective_entity_type,
    )


# =============================================================================
# CRUD Operations
# =============================================================================


def create_workflow(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    data: WorkflowCreate,
) -> AutomationWorkflow:
    """Create a new workflow with validation."""
    subject_type = data.subject_type
    if "subject_type" not in data.model_fields_set:
        subject_type = LEGACY_TRIGGER_SUBJECT_TYPES.get(data.trigger_type.value, "surrogate")
    _validate_subject_trigger(subject_type, data.trigger_type)
    entity_type = subject_type
    trigger_config = _canonicalize_trigger_config(
        db,
        org_id,
        data.trigger_type,
        data.trigger_config,
        entity_type=entity_type,
    )
    effective_subject_type = resolve_effective_workflow_subject_type(
        db,
        org_id,
        subject_type=subject_type,
        trigger_type=data.trigger_type,
        trigger_config=trigger_config,
    )
    conditions = _canonicalize_conditions(db, org_id, data.conditions, entity_type=entity_type)
    _validate_subject_conditions(subject_type, conditions)

    # Validate trigger config
    _validate_trigger_config(data.trigger_type, trigger_config)

    actions = _canonicalize_actions(
        db,
        org_id,
        _normalize_actions_for_trigger(data.trigger_type, data.actions),
        entity_type=entity_type,
    )

    # Validate actions
    for action in actions:
        _validate_action_config(
            db,
            org_id,
            action,
            data.scope,
            user_id,
            data.trigger_type,
            subject_type=subject_type,
            effective_subject_type=effective_subject_type,
        )

    # Determine owner_user_id based on scope
    owner_user_id = user_id if data.scope == "personal" else None

    # Validate email provider if there's a send_email action
    if _has_send_email_action(actions):
        is_valid, error = validate_email_provider(db, data.scope, org_id, owner_user_id)
        if not is_valid:
            raise ValueError(error)

    workflow = AutomationWorkflow(
        organization_id=org_id,
        name=data.name,
        description=data.description,
        icon=data.icon,
        scope=data.scope,
        owner_user_id=owner_user_id,
        subject_type=subject_type,
        trigger_type=data.trigger_type.value,
        trigger_config=trigger_config,
        conditions=conditions,
        condition_logic=data.condition_logic,
        actions=actions,
        is_enabled=data.is_enabled,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )

    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def _has_send_email_action(actions: list[dict]) -> bool:
    """Check if actions list contains a send_email action."""
    return any(action.get("action_type") == "send_email" for action in actions)


def update_workflow(
    db: Session,
    workflow: AutomationWorkflow,
    user_id: UUID,
    data: WorkflowUpdate,
) -> AutomationWorkflow:
    """Update an existing workflow with validation."""
    trigger_type = data.trigger_type or WorkflowTriggerType(workflow.trigger_type)
    subject_type = workflow.subject_type
    _validate_subject_trigger(subject_type, trigger_type)
    entity_type = subject_type
    trigger_config = (
        _canonicalize_trigger_config(
            db,
            workflow.organization_id,
            trigger_type,
            data.trigger_config,
            entity_type=entity_type,
        )
        if data.trigger_config is not None
        else _canonicalize_trigger_config(
            db,
            workflow.organization_id,
            trigger_type,
            workflow.trigger_config,
            entity_type=entity_type,
        )
    )
    effective_subject_type = resolve_effective_workflow_subject_type(
        db,
        workflow.organization_id,
        subject_type=subject_type,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
    )
    normalized_conditions = (
        _canonicalize_conditions(
            db,
            workflow.organization_id,
            data.conditions,
            entity_type=entity_type,
        )
        if data.conditions is not None
        else _canonicalize_conditions(
            db,
            workflow.organization_id,
            workflow.conditions,
            entity_type=entity_type,
        )
    )
    _validate_subject_conditions(subject_type, normalized_conditions)

    if data.trigger_type is not None or data.trigger_config is not None:
        _validate_trigger_config(trigger_type, trigger_config)

    normalized_actions = data.actions
    effective_trigger_type = trigger_type
    if data.actions is not None:
        normalized_actions = _canonicalize_actions(
            db,
            workflow.organization_id,
            _normalize_actions_for_trigger(effective_trigger_type, data.actions),
            entity_type=entity_type,
        )
        for action in normalized_actions:
            _validate_action_config(
                db,
                workflow.organization_id,
                action,
                workflow.scope,
                workflow.owner_user_id,
                effective_trigger_type,
                subject_type=subject_type,
                effective_subject_type=effective_subject_type,
            )
        if _has_send_email_action(normalized_actions):
            is_valid, error = validate_email_provider(
                db,
                workflow.scope,
                workflow.organization_id,
                workflow.owner_user_id,
            )
            if not is_valid:
                raise ValueError(error)
    elif data.trigger_type is not None or data.trigger_config is not None:
        for action in workflow.actions or []:
            _validate_action_config(
                db,
                workflow.organization_id,
                dict(action),
                workflow.scope,
                workflow.owner_user_id,
                effective_trigger_type,
                subject_type=subject_type,
                effective_subject_type=effective_subject_type,
            )

    # Update fields
    if data.name is not None:
        workflow.name = data.name
    if data.description is not None:
        workflow.description = data.description
    if data.icon is not None:
        workflow.icon = data.icon
    if data.trigger_type is not None:
        workflow.trigger_type = data.trigger_type.value
    if data.trigger_config is not None:
        workflow.trigger_config = trigger_config
    if data.conditions is not None:
        workflow.conditions = normalized_conditions
    if data.condition_logic is not None:
        workflow.condition_logic = data.condition_logic
    if normalized_actions is not None:
        workflow.actions = normalized_actions
    if data.is_enabled is not None:
        workflow.is_enabled = data.is_enabled

    workflow.updated_by_user_id = user_id
    workflow.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(workflow)
    return workflow


def delete_workflow(db: Session, workflow: AutomationWorkflow) -> None:
    """Delete a workflow and all related data."""
    db.delete(workflow)
    db.commit()


def get_workflow(
    db: Session,
    workflow_id: UUID,
    org_id: UUID,
) -> AutomationWorkflow | None:
    """Get a workflow by ID, scoped to org."""
    return (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.id == workflow_id,
            AutomationWorkflow.organization_id == org_id,
        )
        .first()
    )


def list_workflows(
    db: Session,
    org_id: UUID,
    user_id: UUID | None = None,
    has_manage_permission: bool = False,
    scope_filter: str | None = None,
    enabled_only: bool = False,
    trigger_type: WorkflowTriggerType | None = None,
    subject_type: str | None = None,
) -> list[AutomationWorkflow]:
    """
    List workflows for an organization with scope-based filtering.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: Current user ID (for filtering personal workflows)
        has_manage_permission: If True, user can see all workflows
        scope_filter: Optional filter: 'org' or 'personal'
        enabled_only: Only return enabled workflows
        trigger_type: Filter by trigger type

    Returns:
        List of workflows the user can see
    """
    query = db.query(AutomationWorkflow).filter(AutomationWorkflow.organization_id == org_id)

    # Apply scope filter
    if scope_filter == "org":
        query = query.filter(AutomationWorkflow.scope == "org")
    elif scope_filter == "personal":
        # Personal scope: only show user's own personal workflows
        if user_id:
            query = query.filter(
                AutomationWorkflow.scope == "personal",
                AutomationWorkflow.owner_user_id == user_id,
            )
        else:
            # No user_id means no personal workflows visible
            query = query.filter(AutomationWorkflow.scope == "personal", False)
    else:
        # No scope filter: show based on permissions
        if has_manage_permission:
            # Admin sees all workflows (org + all personal)
            pass
        elif user_id:
            # Non-admin: org workflows + own personal workflows
            query = query.filter(
                or_(
                    AutomationWorkflow.scope == "org",
                    and_(
                        AutomationWorkflow.scope == "personal",
                        AutomationWorkflow.owner_user_id == user_id,
                    ),
                )
            )
        else:
            # No user_id: only org workflows
            query = query.filter(AutomationWorkflow.scope == "org")

    if enabled_only:
        query = query.filter(AutomationWorkflow.is_enabled.is_(True))

    if trigger_type:
        query = query.filter(AutomationWorkflow.trigger_type == trigger_type.value)
    if subject_type:
        if subject_type not in SUPPORTED_WORKFLOW_SUBJECT_TYPES:
            return []
        query = query.filter(AutomationWorkflow.subject_type == subject_type)

    return query.order_by(AutomationWorkflow.name).all()


def toggle_workflow(
    db: Session,
    workflow: AutomationWorkflow,
    user_id: UUID,
) -> AutomationWorkflow:
    """Toggle a workflow's enabled state."""
    workflow.is_enabled = not workflow.is_enabled
    workflow.updated_by_user_id = user_id
    workflow.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(workflow)
    return workflow


def duplicate_workflow(
    db: Session,
    workflow: AutomationWorkflow,
    user_id: UUID,
    new_scope: str | None = None,
) -> AutomationWorkflow:
    """
    Duplicate an existing workflow.

    Args:
        db: Database session
        workflow: Workflow to duplicate
        user_id: User creating the duplicate
        new_scope: Scope for the new workflow. If None:
            - Org workflows stay org (requires permission check upstream)
            - Personal workflows become owned by the duplicating user
    """
    # Determine scope and owner for duplicate
    scope = new_scope or workflow.scope
    owner_user_id = user_id if scope == "personal" else None

    # Find unique name
    base_name = f"{workflow.name} (Copy)"
    name = base_name
    counter = 1
    while (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == workflow.organization_id,
            AutomationWorkflow.name == name,
        )
        .first()
    ):
        counter += 1
        name = f"{base_name} {counter}"

    new_workflow = AutomationWorkflow(
        organization_id=workflow.organization_id,
        name=name,
        description=workflow.description,
        icon=workflow.icon,
        scope=scope,
        owner_user_id=owner_user_id,
        subject_type=workflow.subject_type,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        conditions=workflow.conditions,
        condition_logic=workflow.condition_logic,
        actions=workflow.actions,
        is_enabled=False,  # Start disabled
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )

    db.add(new_workflow)
    db.commit()
    db.refresh(new_workflow)
    return new_workflow


# =============================================================================
# Stats & Options
# =============================================================================


def get_workflow_stats(
    db: Session,
    org_id: UUID,
    *,
    include_donor_subjects: bool = True,
) -> WorkflowStats:
    """Get workflow statistics for dashboard."""
    from app.db.enums import TaskStatus, TaskType
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)
    workflow_filters = [AutomationWorkflow.organization_id == org_id]
    execution_filters = [
        WorkflowExecution.organization_id == org_id,
        WorkflowExecution.executed_at >= day_ago,
    ]
    approval_filters = [
        Task.organization_id == org_id,
        Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
    ]
    if not include_donor_subjects:
        workflow_filters.append(~_workflow_is_donor_related())
        execution_filters.append(~_execution_is_donor_related())
        approval_filters.append(Task.donor_id.is_(None))

    (
        total,
        enabled,
        org_workflows,
        personal_workflows,
    ) = (
        db.query(
            func.count(AutomationWorkflow.id),
            func.count(AutomationWorkflow.id).filter(AutomationWorkflow.is_enabled.is_(True)),
            func.count(AutomationWorkflow.id).filter(AutomationWorkflow.scope == "org"),
            func.count(AutomationWorkflow.id).filter(AutomationWorkflow.scope == "personal"),
        )
        .filter(*workflow_filters)
        .one()
    )

    executions_24h, successes = (
        db.query(
            func.count(WorkflowExecution.id),
            func.count(WorkflowExecution.id).filter(
                WorkflowExecution.status == WorkflowExecutionStatus.SUCCESS.value
            ),
        )
        .filter(*execution_filters)
        .one()
    )

    if executions_24h > 0:
        success_rate = round(successes / executions_24h * 100, 1)
    else:
        success_rate = 0.0

    # By trigger type
    by_trigger = {}
    trigger_counts = (
        db.query(AutomationWorkflow.trigger_type, func.count(AutomationWorkflow.id))
        .filter(*workflow_filters)
        .group_by(AutomationWorkflow.trigger_type)
        .all()
    )

    for trigger_type, count in trigger_counts:
        by_trigger[trigger_type] = count

    # ==========================================================================
    # Approval Metrics
    # ==========================================================================

    pending_statuses = [TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]
    approved_filter = and_(
        Task.status == TaskStatus.COMPLETED.value,
        Task.updated_at >= day_ago,
    )
    (
        pending_approvals,
        approved_24h,
        denied_24h,
        expired_24h,
        avg_latency,
    ) = (
        db.query(
            func.count(Task.id).filter(Task.status.in_(pending_statuses)),
            func.count(Task.id).filter(approved_filter),
            func.count(Task.id).filter(
                Task.status == TaskStatus.DENIED.value,
                Task.updated_at >= day_ago,
            ),
            func.count(Task.id).filter(
                Task.status == TaskStatus.EXPIRED.value,
                Task.updated_at >= day_ago,
            ),
            func.avg(func.extract("epoch", Task.completed_at - Task.created_at) / 3600).filter(
                approved_filter,
                Task.completed_at.isnot(None),
            ),
        )
        .filter(*approval_filters)
        .one()
    )

    total_resolved_24h = approved_24h + denied_24h + expired_24h

    if total_resolved_24h > 0:
        approval_rate = round(approved_24h / total_resolved_24h * 100, 1)
        denial_rate = round(denied_24h / total_resolved_24h * 100, 1)
        expiry_rate = round(expired_24h / total_resolved_24h * 100, 1)
    else:
        approval_rate = 0.0
        denial_rate = 0.0
        expiry_rate = 0.0

    return WorkflowStats(
        total_workflows=total,
        enabled_workflows=enabled,
        total_executions_24h=executions_24h,
        success_rate_24h=success_rate,
        by_trigger_type=by_trigger,
        org_workflows=org_workflows,
        personal_workflows=personal_workflows,
        # Approval metrics
        pending_approvals=pending_approvals,
        approvals_resolved_24h=total_resolved_24h,
        approval_rate_24h=approval_rate,
        denial_rate_24h=denial_rate,
        expiry_rate_24h=expiry_rate,
        avg_approval_latency_hours=round(avg_latency, 2) if avg_latency else None,
    )


def get_workflow_options(
    db: Session,
    org_id: UUID,
    workflow_scope: str | None = None,
    user_id: UUID | None = None,
    allow_messaging: bool = False,
    subject_type: str = "surrogate",
    include_donor_forms: bool = True,
) -> WorkflowOptions:
    """Get available options for workflow builder UI."""
    if subject_type not in SUPPORTED_WORKFLOW_SUBJECT_TYPES:
        raise ValueError(f"Unsupported workflow subject type: {subject_type}")
    is_donor_subject = subject_type in DONOR_SUBJECT_TYPES
    # Trigger types with descriptions
    trigger_types = [
        {
            "value": "surrogate_created",
            "label": "Surrogate Created",
            "description": "When a new case is created",
        },
        {
            "value": "status_changed",
            "label": "Status Changed",
            "description": "When case status changes",
        },
        {
            "value": "surrogate_assigned",
            "label": "Surrogate Assigned",
            "description": "When case is assigned",
        },
        {
            "value": "surrogate_updated",
            "label": "Surrogate Updated",
            "description": "When specific fields change",
        },
        {
            "value": "form_started",
            "label": "Form Started",
            "description": "When an applicant starts a form draft",
        },
        {
            "value": "form_submitted",
            "label": "Application Submitted",
            "description": "When an applicant submits a form",
        },
        {
            "value": "intake_lead_created",
            "label": "Intake Lead Created",
            "description": "When shared intake creates a provisional lead",
        },
        {
            "value": "task_due",
            "label": "Task Due",
            "description": "Before a task is due",
        },
        {
            "value": "task_overdue",
            "label": "Task Overdue",
            "description": "When a task becomes overdue",
        },
        {
            "value": "scheduled",
            "label": "Scheduled",
            "description": "On a recurring schedule",
        },
        {
            "value": "inactivity",
            "label": "Inactivity",
            "description": "When case has no activity",
        },
        {
            "value": "match_proposed",
            "label": "Match Proposed",
            "description": "When a match is proposed",
        },
        {
            "value": "match_accepted",
            "label": "Match Accepted",
            "description": "When a match is accepted",
        },
        {
            "value": "match_rejected",
            "label": "Match Rejected",
            "description": "When a match is rejected",
        },
        {
            "value": "appointment_scheduled",
            "label": "Appointment Scheduled",
            "description": "When an appointment is scheduled",
        },
        {
            "value": "appointment_completed",
            "label": "Appointment Completed",
            "description": "When an appointment is completed",
        },
        {
            "value": "note_added",
            "label": "Note Added",
            "description": "When a note is added to a case",
        },
        {
            "value": "document_uploaded",
            "label": "Document Uploaded",
            "description": "When a document is uploaded",
        },
    ]
    if is_donor_subject:
        trigger_types = [
            {
                "value": "donor_created",
                "label": "Donor Created",
                "description": "When a donor record is created",
            },
            {
                "value": "donor_stage_changed",
                "label": "Donor Stage Changed",
                "description": "When a donor changes pipeline stage",
            },
            {
                "value": "donor_assigned",
                "label": "Donor Assigned",
                "description": "When a donor is assigned",
            },
            {
                "value": "donor_updated",
                "label": "Donor Updated",
                "description": "When donor fields change",
            },
            {"value": "task_due", "label": "Task Due", "description": "Before a donor task is due"},
            {
                "value": "task_overdue",
                "label": "Task Overdue",
                "description": "When a donor task becomes overdue",
            },
            {"value": "scheduled", "label": "Scheduled", "description": "On a recurring schedule"},
            {
                "value": "inactivity",
                "label": "Inactivity",
                "description": "When a donor has no activity",
            },
            {
                "value": "note_added",
                "label": "Note Added",
                "description": "When a donor note is added",
            },
            {
                "value": "document_uploaded",
                "label": "Document Uploaded",
                "description": "When a donor document is uploaded",
            },
        ]

    # Action types
    action_types = [
        {
            "value": "send_email",
            "label": "Send Email",
            "description": "Send email using template",
        },
        {
            "value": "create_task",
            "label": "Create Task",
            "description": "Create a task on the case",
        },
        {
            "value": "assign_surrogate",
            "label": "Assign Surrogate",
            "description": "Assign to user or queue",
        },
        {
            "value": "send_notification",
            "label": "Send Notification",
            "description": "Send in-app notification",
        },
        {
            "value": "send_zapier_conversion_event",
            "label": "Send Zapier Conversion Event",
            "description": "Queue a conversion status update to Zapier outbound webhook",
        },
        {
            "value": "update_field",
            "label": "Update Field",
            "description": "Update a case field",
        },
        {
            "value": "add_note",
            "label": "Add Note",
            "description": "Add a note to the case",
        },
        {
            "value": "promote_intake_lead",
            "label": "Promote Intake Lead",
            "description": "Create surrogate case from intake lead",
        },
        {
            "value": "auto_match_submission",
            "label": "Auto-Match Submission",
            "description": "Try deterministic match to an existing surrogate",
        },
        {
            "value": "create_intake_lead",
            "label": "Create Intake Lead",
            "description": "Create provisional intake lead for unmatched submission",
        },
    ]

    messaging_available = allow_messaging and workflow_scope != "personal"
    if messaging_available:
        action_types.insert(
            1,
            {
                "value": "send_message",
                "label": "Send SMS/MMS",
                "description": "Queue a consent-gated message using a published template",
            },
        )

    if is_donor_subject:
        donor_values = {
            "send_email",
            "create_task",
            "send_notification",
            "update_field",
            "add_note",
        }
        action_types = [item for item in action_types if item["value"] in donor_values]
        action_types.insert(
            2,
            {
                "value": "assign_donor",
                "label": "Assign Donor",
                "description": "Assign to user or queue",
            },
        )

    surrogate_action_values = [
        "send_email",
        "create_task",
        "assign_surrogate",
        "send_notification",
        "update_field",
        "add_note",
    ]
    if messaging_available:
        surrogate_action_values.insert(1, "send_message")
    status_changed_action_values = [
        *surrogate_action_values,
        "send_zapier_conversion_event",
    ]
    form_submission_action_values = [
        "auto_match_submission",
        "create_intake_lead",
        *surrogate_action_values,
    ]
    action_types_by_trigger: dict[str, list[str]] = {}
    for trigger, entity_type in TRIGGER_ENTITY_TYPES.items():
        if trigger == WorkflowTriggerType.STATUS_CHANGED.value:
            action_types_by_trigger[trigger] = status_changed_action_values
        elif entity_type in ("surrogate", "task"):
            action_types_by_trigger[trigger] = surrogate_action_values
        elif entity_type == "form_submission":
            action_types_by_trigger[trigger] = form_submission_action_values
        elif entity_type == "intake_lead":
            action_types_by_trigger[trigger] = [
                "send_notification",
                "promote_intake_lead",
                *(["send_message"] if messaging_available else []),
            ]
        else:
            action_types_by_trigger[trigger] = ["send_notification"]
    trigger_entity_types = dict(TRIGGER_ENTITY_TYPES)
    if is_donor_subject:
        donor_action_values = [
            "send_email",
            "create_task",
            "assign_donor",
            "send_notification",
            "update_field",
            "add_note",
        ]
        donor_trigger_values = [item["value"] for item in trigger_types]
        action_types_by_trigger = {
            trigger: list(donor_action_values) for trigger in donor_trigger_values
        }
        trigger_entity_types = {trigger: subject_type for trigger in donor_trigger_values}

    # Condition operators
    condition_operators = [
        {"value": "equals", "label": "Equals"},
        {"value": "not_equals", "label": "Does not equal"},
        {"value": "contains", "label": "Contains"},
        {"value": "not_contains", "label": "Does not contain"},
        {"value": "is_empty", "label": "Is empty"},
        {"value": "is_not_empty", "label": "Is not empty"},
        {"value": "in", "label": "Is one of"},
        {"value": "not_in", "label": "Is not one of"},
        {"value": "greater_than", "label": "Greater than"},
        {"value": "less_than", "label": "Less than"},
    ]

    # Email templates - scope-aware filtering
    # For org workflows: only org + system templates
    # For personal workflows: personal (user's own) + org + system templates
    from sqlalchemy import and_, or_

    from app.services import system_email_template_service

    template_query = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org_id,
        EmailTemplate.is_active.is_(True),
    )

    platform_system_keys = set(system_email_template_service.DEFAULT_SYSTEM_TEMPLATES.keys())
    if platform_system_keys:
        template_query = template_query.filter(
            or_(
                EmailTemplate.system_key.is_(None),
                EmailTemplate.system_key.notin_(platform_system_keys),
            )
        )

    if workflow_scope == "org":
        # Org workflows can only use org templates (including system templates)
        template_query = template_query.filter(EmailTemplate.scope == "org")
    elif workflow_scope == "personal" and user_id:
        # Personal workflows can use user's personal templates + org templates
        template_query = template_query.filter(
            or_(
                EmailTemplate.scope == "org",
                and_(
                    EmailTemplate.scope == "personal",
                    EmailTemplate.owner_user_id == user_id,
                ),
            )
        )
    else:
        # Default: show all org templates (for backward compatibility)
        template_query = template_query.filter(EmailTemplate.scope == "org")

    templates = template_query.order_by(EmailTemplate.scope.desc(), EmailTemplate.name).all()
    email_templates = [{"id": str(t.id), "name": t.name, "scope": t.scope} for t in templates]

    message_templates: list[dict] = []
    if messaging_available:
        published_message_templates = (
            db.query(MessageTemplate)
            .filter(
                MessageTemplate.organization_id == org_id,
                MessageTemplate.status == "published",
            )
            .order_by(MessageTemplate.purpose, MessageTemplate.name, MessageTemplate.version.desc())
            .all()
        )
        message_templates = [
            {
                "id": str(template.id),
                "name": template.name,
                "purpose": template.purpose,
                "version": template.version,
            }
            for template in published_message_templates
        ]

    # Users in org
    from app.db.models import Membership

    user_rows = (
        db.query(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
        )
        .all()
    )
    users = [
        {"id": str(user_id), "display_name": display_name} for user_id, display_name in user_rows
    ]

    # Queues
    queues = db.query(Queue).filter(Queue.organization_id == org_id).all()
    queue_options = [{"id": str(q.id), "name": q.name} for q in queues]

    # Stages (status options)
    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type=subject_type if is_donor_subject else "surrogate",
    )
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    statuses = [
        {"id": str(s.id), "value": s.slug, "label": s.label, "is_active": s.is_active}
        for s in stages
    ]

    # Forms (published)
    from app.db.enums import FormStatus
    forms_query = db.query(Form).filter(
        Form.organization_id == org_id,
        Form.status == FormStatus.PUBLISHED.value,
    )
    if is_donor_subject:
        forms_query = forms_query.filter(Form.lead_kind == subject_type)
    elif not include_donor_forms:
        forms_query = forms_query.filter(Form.lead_kind == "surrogate")
    published_forms = forms_query.order_by(Form.name.asc()).all()
    forms = [{"id": str(f.id), "name": f.name} for f in published_forms]

    return WorkflowOptions(
        trigger_types=trigger_types,
        action_types=action_types,
        action_types_by_trigger=action_types_by_trigger,
        trigger_entity_types=trigger_entity_types,
        condition_operators=condition_operators,
        condition_fields=list(
            DONOR_ALLOWED_CONDITION_FIELDS if is_donor_subject else ALLOWED_CONDITION_FIELDS
        ),
        update_fields=list(
            DONOR_ALLOWED_UPDATE_FIELDS if is_donor_subject else SURROGATE_ALLOWED_UPDATE_FIELDS
        ),
        email_variables=list(ALLOWED_EMAIL_VARIABLES),
        email_templates=email_templates,
        message_templates=message_templates,
        users=users,
        queues=queue_options,
        statuses=statuses,
        forms=forms,
    )


# =============================================================================
# Execution History
# =============================================================================


def list_executions(
    db: Session,
    workflow_id: UUID,
    org_id: UUID,
    limit: int = 50,
    offset: int = 0,
    include_donor_subjects: bool = True,
) -> tuple[list[ExecutionRead], int]:
    """List tenant-scoped executions with exact donor subject identity."""
    query = (
        db.query(
            WorkflowExecution,
            Donor.full_name,
            Donor.donor_number,
        )
        .outerjoin(Donor, _exact_donor_execution_identity_match())
        .filter(
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.organization_id == org_id,
        )
    )
    if not include_donor_subjects:
        query = query.filter(~_execution_is_donor_related())

    items, total = paginate_query_by_offset(
        query.order_by(WorkflowExecution.executed_at.desc()),
        offset=offset,
        limit=limit,
        count_query=query,
    )

    return [
        ExecutionRead.model_validate(execution).model_copy(
            update={"entity_name": donor_name, "entity_number": donor_number}
        )
        for execution, donor_name, donor_number in items
    ], total


def list_org_executions(
    db: Session,
    org_id: UUID,
    status: str | None = None,
    workflow_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
    include_donor_subjects: bool = True,
) -> tuple[list[dict], int]:
    """
    List all workflow executions for an organization with filters.

    Returns executions with workflow name joined for display.
    """
    query = (
        db.query(
            WorkflowExecution,
            AutomationWorkflow.name,
            Surrogate.full_name,
            Surrogate.surrogate_number,
            Donor.full_name,
            Donor.donor_number,
        )
        .join(
            AutomationWorkflow,
            and_(
                WorkflowExecution.workflow_id == AutomationWorkflow.id,
                AutomationWorkflow.organization_id == WorkflowExecution.organization_id,
            ),
        )
        .outerjoin(
            Surrogate,
            and_(
                WorkflowExecution.entity_type == "surrogate",
                WorkflowExecution.entity_id == Surrogate.id,
                Surrogate.organization_id == WorkflowExecution.organization_id,
            ),
        )
        .outerjoin(
            Donor,
            _exact_donor_execution_identity_match(),
        )
        .filter(WorkflowExecution.organization_id == org_id)
    )

    if status:
        query = query.filter(WorkflowExecution.status == status)

    if workflow_id:
        query = query.filter(WorkflowExecution.workflow_id == workflow_id)

    if not include_donor_subjects:
        query = query.filter(~_execution_is_donor_related())

    items, total = paginate_query_by_offset(
        query.order_by(WorkflowExecution.executed_at.desc()),
        offset=offset,
        limit=limit,
        count_query=query,
    )

    # Build response with workflow name
    result = []
    for (
        exec,
        workflow_name,
        surrogate_name,
        surrogate_number,
        donor_name,
        donor_number,
    ) in items:
        is_donor_subject = exec.subject_type in DONOR_SUBJECT_TYPES
        result.append(
            {
                "id": exec.id,
                "workflow_id": exec.workflow_id,
                "workflow_name": workflow_name or "Unknown",
                "status": exec.status,
                "entity_type": exec.entity_type,
                "entity_id": exec.entity_id,
                "subject_type": exec.subject_type,
                "subject_id": exec.subject_id,
                "entity_name": donor_name if is_donor_subject else surrogate_name,
                "entity_number": donor_number if is_donor_subject else surrogate_number,
                "action_count": len(exec.actions_executed) if exec.actions_executed else 0,
                "duration_ms": exec.duration_ms or 0,
                "executed_at": exec.executed_at.isoformat(),
                "trigger_event": exec.trigger_event,
                "actions_executed": exec.actions_executed or [],
                "error_message": exec.error_message,
                "skip_reason": None if exec.matched_conditions else "Conditions not met",
            }
        )

    return result, total


def get_execution(db: Session, org_id: UUID, execution_id: UUID) -> WorkflowExecution | None:
    """Fetch a single execution scoped to an organization."""
    return (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.id == execution_id,
        )
        .first()
    )


def get_execution_stats(
    db: Session,
    org_id: UUID,
    *,
    include_donor_subjects: bool = True,
) -> dict:
    """Get execution statistics for the dashboard."""
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)

    query = db.query(
            func.count(WorkflowExecution.id),
            func.count(WorkflowExecution.id).filter(
                WorkflowExecution.status == WorkflowExecutionStatus.FAILED.value
            ),
            func.count(WorkflowExecution.id).filter(
                WorkflowExecution.status == WorkflowExecutionStatus.SUCCESS.value
            ),
            func.avg(WorkflowExecution.duration_ms).filter(
                WorkflowExecution.duration_ms.isnot(None)
            ),
        ).filter(
        WorkflowExecution.organization_id == org_id,
        WorkflowExecution.executed_at >= day_ago,
    )
    if not include_donor_subjects:
        query = query.filter(~_execution_is_donor_related())
    total_24h, failed_24h, successes, avg_duration = query.one()

    if total_24h > 0:
        success_rate = round(successes / total_24h * 100, 1)
    else:
        success_rate = 0.0

    return {
        "total_24h": total_24h,
        "failed_24h": failed_24h,
        "success_rate": success_rate,
        "avg_duration_ms": int(avg_duration or 0),
    }


# =============================================================================
# User Preferences
# =============================================================================


def get_user_preferences(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> list[UserWorkflowPreference]:
    """Get user's workflow preferences."""
    return (
        db.query(UserWorkflowPreference)
        .join(AutomationWorkflow)
        .filter(
            UserWorkflowPreference.user_id == user_id,
            AutomationWorkflow.organization_id == org_id,
        )
        .all()
    )


def update_user_preference(
    db: Session,
    user_id: UUID,
    workflow_id: UUID,
    is_opted_out: bool,
) -> UserWorkflowPreference:
    """Update user's preference for a workflow."""
    pref = (
        db.query(UserWorkflowPreference)
        .filter(
            UserWorkflowPreference.user_id == user_id,
            UserWorkflowPreference.workflow_id == workflow_id,
        )
        .first()
    )

    if pref:
        pref.is_opted_out = is_opted_out
    else:
        pref = UserWorkflowPreference(
            user_id=user_id,
            workflow_id=workflow_id,
            is_opted_out=is_opted_out,
        )
        db.add(pref)

    db.commit()
    db.refresh(pref)
    return pref


def is_user_opted_out(
    db: Session,
    user_id: UUID,
    workflow_id: UUID,
) -> bool:
    """Check if user has opted out of a workflow."""
    pref = (
        db.query(UserWorkflowPreference)
        .filter(
            UserWorkflowPreference.user_id == user_id,
            UserWorkflowPreference.workflow_id == workflow_id,
        )
        .first()
    )

    return pref.is_opted_out if pref else False


def to_workflow_read(
    db: Session,
    workflow: AutomationWorkflow,
    can_edit: bool = True,
) -> WorkflowRead:
    """Convert workflow model to read schema with user names."""
    created_by_name = None
    updated_by_name = None
    owner_name = None

    if workflow.created_by_user_id:
        user = user_service.get_user_by_id(db, workflow.created_by_user_id)
        created_by_name = user.display_name if user else None

    if workflow.updated_by_user_id:
        user = user_service.get_user_by_id(db, workflow.updated_by_user_id)
        updated_by_name = user.display_name if user else None

    if workflow.owner_user_id:
        user = user_service.get_user_by_id(db, workflow.owner_user_id)
        owner_name = user.display_name if user else None

    return WorkflowRead(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        icon=workflow.icon,
        schema_version=workflow.schema_version,
        scope=workflow.scope,
        owner_user_id=workflow.owner_user_id,
        owner_name=owner_name,
        subject_type=workflow.subject_type,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        conditions=workflow.conditions,
        condition_logic=workflow.condition_logic,
        actions=workflow.actions,
        is_enabled=workflow.is_enabled,
        run_count=workflow.run_count,
        last_run_at=workflow.last_run_at,
        last_error=workflow.last_error,
        created_by_name=created_by_name,
        updated_by_name=updated_by_name,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        can_edit=can_edit,
    )


def to_workflow_list_item(
    db: Session,
    workflow: AutomationWorkflow,
    can_edit: bool = True,
):
    """Convert workflow model to list item schema with owner name."""
    from app.schemas.workflow import WorkflowListItem

    owner_name = None
    if workflow.owner_user_id:
        user = user_service.get_user_by_id(db, workflow.owner_user_id)
        owner_name = user.display_name if user else None

    return WorkflowListItem(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        icon=workflow.icon,
        scope=workflow.scope,
        owner_user_id=workflow.owner_user_id,
        owner_name=owner_name,
        subject_type=workflow.subject_type,
        trigger_type=workflow.trigger_type,
        is_enabled=workflow.is_enabled,
        run_count=workflow.run_count,
        last_run_at=workflow.last_run_at,
        last_error=workflow.last_error,
        created_at=workflow.created_at,
        can_edit=can_edit,
    )


# =============================================================================
# Validation Helpers
# =============================================================================


def _normalize_actions_for_trigger(
    trigger_type: WorkflowTriggerType,
    actions: list[dict],
) -> list[dict]:
    """Normalize workflow actions for trigger-specific rules."""
    normalized = [dict(action) for action in actions]
    if trigger_type != WorkflowTriggerType.FORM_SUBMITTED:
        return normalized

    auto_match_indices = [
        idx
        for idx, action in enumerate(normalized)
        if action.get("action_type") == "auto_match_submission"
    ]
    create_lead_indices = [
        idx
        for idx, action in enumerate(normalized)
        if action.get("action_type") == "create_intake_lead"
    ]
    if auto_match_indices and create_lead_indices:
        first_match_idx = auto_match_indices[0]
        first_create_idx = create_lead_indices[0]
        if first_match_idx > first_create_idx:
            raise ValueError(
                "For form_submitted workflows, auto_match_submission must be placed before create_intake_lead"
            )

    return normalized


def _validate_trigger_config(trigger_type: WorkflowTriggerType, config: dict) -> None:
    """Validate trigger config matches the trigger type schema."""
    validators = {
        WorkflowTriggerType.STATUS_CHANGED: StatusChangeTriggerConfig,
        WorkflowTriggerType.DONOR_STAGE_CHANGED: StatusChangeTriggerConfig,
        WorkflowTriggerType.SCHEDULED: ScheduledTriggerConfig,
        WorkflowTriggerType.TASK_DUE: TaskDueTriggerConfig,
        WorkflowTriggerType.INACTIVITY: InactivityTriggerConfig,
        WorkflowTriggerType.SURROGATE_UPDATED: SurrogateUpdatedTriggerConfig,
        WorkflowTriggerType.DONOR_UPDATED: SurrogateUpdatedTriggerConfig,
        WorkflowTriggerType.FORM_STARTED: FormStartedTriggerConfig,
        WorkflowTriggerType.FORM_SUBMITTED: FormSubmittedTriggerConfig,
        WorkflowTriggerType.INTAKE_LEAD_CREATED: IntakeLeadCreatedTriggerConfig,
    }

    validator = validators.get(trigger_type)
    if validator:
        validator.model_validate(config)


def _validate_action_config(
    db: Session,
    org_id: UUID,
    action: dict,
    workflow_scope: str | None = None,
    owner_user_id: UUID | None = None,
    trigger_type: WorkflowTriggerType | None = None,
    subject_type: str = "surrogate",
    effective_subject_type: str | None = None,
) -> None:
    """Validate action config and referenced entities exist in org."""
    action_type = action.get("action_type")
    is_donor_subject = subject_type in DONOR_SUBJECT_TYPES
    is_donor_context = (
        effective_subject_type in {*DONOR_SUBJECT_TYPES, DONOR_PERMISSION_CONTEXT}
        if effective_subject_type is not None
        else is_donor_subject
    )
    donor_action_types = {
        "send_email",
        "create_task",
        "assign_donor",
        "send_notification",
        "update_field",
        "add_note",
    }
    if is_donor_subject and action_type not in donor_action_types:
        raise ValueError(f"Action {action_type} does not support donor workflows")
    if not is_donor_subject and action_type == "assign_donor":
        raise ValueError("assign_donor requires a donor workflow subject")
    if is_donor_context and action_type == "send_message":
        raise ValueError("Action send_message does not support donor workflows")
    if is_donor_context and action_type == "send_email":
        if action.get("requires_approval") is not True:
            raise ValueError("Donor email actions require review approval")

    if action_type == "update_status":
        stage_id = action.get("stage_id")
        if not stage_id:
            raise ValueError("update_status requires stage_id")
        action["action_type"] = "update_field"
        action["field"] = "stage_id"
        action["value"] = stage_id
        action.pop("stage_id", None)
        action_type = action.get("action_type")

    if action_type == "send_email":
        config = SendEmailActionConfig.model_validate(action)
        # Verify template exists in org
        template = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.id == config.template_id,
                EmailTemplate.organization_id == org_id,
            )
            .first()
        )
        if not template:
            raise ValueError(f"Email template {config.template_id} not found in organization")
        # Validate internal recipients (if explicit list)
        if isinstance(config.recipients, list):
            from app.db.models import Membership

            recipient_ids = set(config.recipients)
            rows = (
                db.query(Membership.user_id)
                .filter(
                    Membership.organization_id == org_id,
                    Membership.user_id.in_(recipient_ids),
                    Membership.is_active.is_(True),
                )
                .all()
            )
            found_ids = {row[0] for row in rows}
            missing_ids = recipient_ids - found_ids
            if missing_ids:
                missing_str = ", ".join(str(uid) for uid in sorted(missing_ids, key=str))
                raise ValueError(f"Missing recipients in organization: {missing_str}")
        # Enforce scope rules for workflow email templates
        if workflow_scope == "org":
            if template.scope != "org":
                raise ValueError("Org workflows cannot use personal email templates")
        elif workflow_scope == "personal":
            if template.scope == "personal" and template.owner_user_id != owner_user_id:
                raise ValueError("Personal email templates must be owned by the workflow owner")

    elif action_type == "send_message":
        config = SendMessageActionConfig.model_validate(action)
        if workflow_scope != "org":
            raise ValueError("send_message is only supported for org workflows")
        template = (
            db.query(MessageTemplate)
            .filter(
                MessageTemplate.id == config.message_template_version_id,
                MessageTemplate.organization_id == org_id,
                MessageTemplate.status == "published",
            )
            .first()
        )
        if template is None:
            raise ValueError("Published message template not found in organization")
        if template.purpose != config.purpose:
            raise ValueError("Message template purpose does not match action purpose")

    elif action_type == "create_task":
        config = CreateTaskActionConfig.model_validate(action)
        # If assignee is UUID, verify user exists in org
        if isinstance(config.assignee, UUID):
            from app.db.models import Membership

            membership = (
                db.query(Membership)
                .filter(
                    Membership.user_id == config.assignee,
                    Membership.organization_id == org_id,
                    Membership.is_active.is_(True),
                )
                .first()
            )
            if not membership:
                raise ValueError(f"User {config.assignee} not found in organization")

    elif action_type in {"assign_surrogate", "assign_donor"}:
        config = (
            AssignDonorActionConfig.model_validate(action)
            if action_type == "assign_donor"
            else AssignSurrogateActionConfig.model_validate(action)
        )
        # Verify owner exists in org
        if config.owner_type == OwnerType.USER:
            from app.db.models import Membership

            membership = (
                db.query(Membership)
                .filter(
                    Membership.user_id == config.owner_id,
                    Membership.organization_id == org_id,
                    Membership.is_active.is_(True),
                )
                .first()
            )
            if not membership:
                raise ValueError(f"User {config.owner_id} not found in organization")
        elif config.owner_type == OwnerType.QUEUE:
            queue = (
                db.query(Queue)
                .filter(
                    Queue.id == config.owner_id,
                    Queue.organization_id == org_id,
                )
                .first()
            )
            if not queue:
                raise ValueError(f"Queue {config.owner_id} not found in organization")

    elif action_type == "send_notification":
        config = SendNotificationActionConfig.model_validate(action)
        # If recipients is list of UUIDs, verify all exist
        if isinstance(config.recipients, list):
            from app.db.models import Membership

            recipient_ids = set(config.recipients)
            rows = (
                db.query(Membership.user_id)
                .filter(
                    Membership.organization_id == org_id,
                    Membership.user_id.in_(recipient_ids),
                    Membership.is_active.is_(True),
                )
                .all()
            )
            found_ids = {row[0] for row in rows}
            missing_ids = recipient_ids - found_ids
            if missing_ids:
                missing_list = ", ".join(str(user_id) for user_id in missing_ids)
                raise ValueError(f"Users not found in organization: {missing_list}")

    elif action_type == "send_zapier_conversion_event":
        SendZapierConversionEventActionConfig.model_validate(action)
        if workflow_scope == "personal":
            raise ValueError("send_zapier_conversion_event is only supported for org workflows")
        if trigger_type is not None and trigger_type != WorkflowTriggerType.STATUS_CHANGED:
            raise ValueError(
                "send_zapier_conversion_event is only supported for status_changed triggers"
            )

    elif action_type == "update_field":
        config = UpdateFieldActionConfig.model_validate(action)
        allowed_fields = (
            DONOR_ALLOWED_UPDATE_FIELDS if is_donor_subject else SURROGATE_ALLOWED_UPDATE_FIELDS
        )
        if config.field not in allowed_fields:
            raise ValueError(f"Field '{config.field}' is not allowed for {subject_type}")
        if config.field == "stage_id":
            resolved = _resolve_stage_ref(
                db,
                org_id,
                action.get("value_stage_key") or config.value,
                entity_type=subject_type,
            )
            if not resolved:
                raise ValueError(f"Stage {config.value} not found in {subject_type} pipeline")

    elif action_type == "add_note":
        AddNoteActionConfig.model_validate(action)

    elif action_type == "promote_intake_lead":
        PromoteIntakeLeadActionConfig.model_validate(action)
        if workflow_scope == "personal":
            raise ValueError("promote_intake_lead is only supported for org workflows")
        if action.get("requires_approval") is True:
            raise ValueError("promote_intake_lead does not support requires_approval")

    elif action_type == "auto_match_submission":
        AutoMatchSubmissionActionConfig.model_validate(action)
        if workflow_scope == "personal":
            raise ValueError("auto_match_submission is only supported for org workflows")

    elif action_type == "create_intake_lead":
        CreateIntakeLeadActionConfig.model_validate(action)
        if workflow_scope == "personal":
            raise ValueError("create_intake_lead is only supported for org workflows")

    else:
        raise ValueError(f"Unknown action type: {action_type}")

    # Validate requires_approval field (optional, defaults to False)
    requires_approval = action.get("requires_approval", False)
    if requires_approval is not None and not isinstance(requires_approval, bool):
        raise ValueError("requires_approval must be a boolean")
