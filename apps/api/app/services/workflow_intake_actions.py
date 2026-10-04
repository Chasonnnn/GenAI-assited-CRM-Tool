"""Intake workflow actions; promotion transactions stay with intake."""

from sqlalchemy.orm import Session

from app.db.models import IntakeLead


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
