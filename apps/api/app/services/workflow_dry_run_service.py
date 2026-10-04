"""Workflow dry runs: evaluate a definition against one record without side effects.

Serves the saved-workflow test and the editor's draft test. Neither path writes; callers
own authorization of the workflow itself, this module authorizes the record.
"""

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.auth import UserSession
from app.schemas.workflow import (
    WorkflowTestActionPreview,
    WorkflowTestConditionResult,
    WorkflowTestResponse,
)
from app.services import (
    appointment_service,
    attachment_service,
    form_intake_service,
    form_submission_service,
    match_queries,
    note_service,
    record_access_service,
    task_service,
    workflow_access,
    workflow_service,
)
from app.services.workflow_action_preview import build_action_preview
from app.services.workflow_engine import engine


def expected_entity_type(subject_type: str | None, trigger_type: str) -> str:
    """The record type a dry run reads for this subject and trigger."""
    if subject_type in workflow_service.DONOR_SUBJECT_TYPES:
        return subject_type
    return workflow_service.TRIGGER_ENTITY_TYPES.get(trigger_type, "surrogate")


def _require_subject_view(db: Session, session: UserSession, subject_type: str | None) -> None:
    if not workflow_access.can_view_subject(db, session, subject_type):
        raise HTTPException(status_code=403, detail="Missing permission: view_donors")


def resolve_test_entity(
    db: Session,
    session: UserSession,
    *,
    entity_type: str,
    entity_id: UUID,
) -> Any:
    """Load the record under the caller's organization and record-level access."""
    if entity_type in workflow_service.DONOR_SUBJECT_TYPES:
        donor = record_access_service.get_record_with_access(db, session, "donor", entity_id)
        if donor.pipeline_entity_type != entity_type:
            raise HTTPException(status_code=404, detail="Donor not found")
        return donor
    if entity_type == "surrogate":
        return record_access_service.get_record_with_access(db, session, "surrogate", entity_id)

    if entity_type == "task":
        entity = task_service.get_task(db, entity_id, session.org_id)
    elif entity_type == "match":
        entity = match_queries.get_match(db, entity_id, session.org_id)
    elif entity_type == "appointment":
        entity = appointment_service.get_appointment(db, entity_id, session.org_id)
    elif entity_type == "note":
        entity = note_service.get_note(db, entity_id, session.org_id)
    elif entity_type == "document":
        entity = attachment_service.get_attachment(db, session.org_id, entity_id)
    elif entity_type == "form_submission":
        entity = form_submission_service.get_submission(
            db, org_id=session.org_id, submission_id=entity_id
        )
    elif entity_type == "intake_lead":
        entity = form_intake_service.get_intake_lead(db, org_id=session.org_id, lead_id=entity_id)
    else:
        raise HTTPException(status_code=422, detail="Unsupported entity type for test")

    if not entity or getattr(entity, "organization_id", session.org_id) != session.org_id:
        raise HTTPException(status_code=404, detail=f"{entity_type.capitalize()} not found")
    if entity_type == "task":
        task_service.check_task_subject_access(db, entity, session)
    elif entity_type == "form_submission":
        _require_subject_view(db, session, entity.lead_kind)
    elif entity_type == "intake_lead":
        _require_subject_view(db, session, entity.lead_type)
    return entity


def evaluate(
    db: Session,
    entity: Any,
    *,
    conditions: list[dict],
    condition_logic: str,
    actions: list[dict],
) -> WorkflowTestResponse:
    """Evaluate filters against the record and describe each action; writes nothing."""
    evaluated: list[WorkflowTestConditionResult] = []
    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        entity_value = engine.condition_value(db, entity, field)
        evaluated.append(
            WorkflowTestConditionResult(
                field=str(field),
                operator=str(operator),
                expected=value,
                actual=str(entity_value),
                result=engine._evaluate_condition(operator, entity_value, value),
            )
        )

    results = [item.result for item in evaluated]
    if not results:
        matched = True
    elif condition_logic == "AND":
        matched = all(results)
    else:
        matched = any(results)

    return WorkflowTestResponse(
        # A dry run starts from the chosen record, so the trigger is taken as fired.
        would_trigger=True,
        conditions_matched=matched,
        conditions_evaluated=evaluated,
        actions_preview=[
            WorkflowTestActionPreview(
                action_type=str(action.get("action_type") or ""),
                description=build_action_preview(db, action, entity),
                requires_approval=bool(action.get("requires_approval")),
            )
            for action in actions
        ],
    )
