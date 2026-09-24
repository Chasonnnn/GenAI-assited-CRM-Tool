"""Intake workflow actions; matching and promotion transactions stay with intake."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import FormSubmission, IntakeLead


def promote_intake_lead(db: Session, action: dict, entity: IntakeLead) -> dict:
    """Promote an intake lead into a surrogate or donor record."""
    from app.services import form_intake_service

    source = action.get("source")
    if source is not None and not isinstance(source, str):
        source = None

    assign_to_user = action.get("assign_to_user")
    if not isinstance(assign_to_user, bool):
        assign_to_user = None

    record, linked_submission_count = form_intake_service.promote_intake_lead(
        db=db,
        lead=entity,
        user_id=entity.created_by_user_id,
        source=source,
        is_priority=bool(action.get("is_priority", False)),
        assign_to_user=assign_to_user,
    )
    return {
        "success": True,
        "description": "Promoted intake lead to donor"
        if entity.promoted_donor_id
        else "Promoted intake lead to surrogate",
        "donor_id" if entity.promoted_donor_id else "surrogate_id": str(record.id),
        "linked_submission_count": int(linked_submission_count),
    }


def auto_match_submission(db: Session, entity: FormSubmission) -> dict:
    """Run deterministic matching for a shared form submission."""
    from app.services import form_intake_service

    submission, outcome = form_intake_service.auto_match_submission(db=db, submission=entity)
    if outcome == "linked":
        return {
            "success": True,
            "description": "Matched submission to existing donor"
            if submission.donor_id
            else "Matched submission to existing surrogate",
            "submission_id": str(submission.id),
            "donor_id" if submission.donor_id else "surrogate_id": str(
                submission.donor_id or submission.surrogate_id
            ),
            "match_status": outcome,
        }
    return {
        "success": True,
        "description": "Submission requires review after auto-match",
        "submission_id": str(submission.id),
        "match_status": outcome,
    }


def create_intake_lead(
    db: Session,
    action: dict,
    entity: FormSubmission,
    *,
    workflow_execution_id: UUID | None = None,
) -> dict:
    """Create an intake lead when no deterministic match exists."""
    from app.services import form_intake_service

    source = action.get("source")
    if source is not None and not isinstance(source, str):
        source = None

    submission, lead = form_intake_service.create_intake_lead_for_submission(
        db=db,
        submission=entity,
        user_id=None,
        source=source,
        auto_promote=action.get("auto_promote") is True,
        workflow_execution_id=workflow_execution_id,
    )
    if not lead:
        return {
            "success": True,
            "description": "Skipped intake lead creation",
            "submission_id": str(submission.id),
            "match_status": submission.match_status,
        }
    return {
        "success": True,
        "description": "Created intake lead from submission",
        "submission_id": str(submission.id),
        "intake_lead_id": str(lead.id),
        "match_status": submission.match_status,
    }
