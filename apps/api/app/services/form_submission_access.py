"""Application review authorization, independent of form builder permissions."""

from fastapi import HTTPException
from sqlalchemy import and_, or_, true

from app.db.models import FormSubmission
from app.services import permission_policy_service, permission_service, record_scope_service

QUEUE_ROLES = {"intake_specialist", "admin", "developer"}


def require_action(db, session, *, write=False, legacy_permission="manage_forms"):
    permission = (
        ("review_form_submissions" if write else "view_form_submissions")
        if permission_policy_service.is_enabled(db, session.org_id)
        else legacy_permission
    )
    if not permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, permission
    ):
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")


def visibility_filter(db, session):
    if not permission_policy_service.is_enabled(db, session.org_id):
        return true()
    return and_(
        record_scope_service.build_linked_visibility_filter(db, session, FormSubmission),
        or_(
            FormSubmission.surrogate_id.isnot(None),
            FormSubmission.donor_id.isnot(None),
            session.role.value in QUEUE_ROLES,
        ),
    )


def check_submission(db, session, submission, *, write=False):
    """V2 submission action and linked-record scope; legacy callers retain old checks."""
    if not permission_policy_service.is_enabled(db, session.org_id):
        return
    require_action(db, session, write=write)
    if (
        not db.query(FormSubmission.id)
        .filter(
            FormSubmission.organization_id == session.org_id,
            FormSubmission.id == submission.id,
            visibility_filter(db, session),
        )
        .first()
    ):
        raise HTTPException(status_code=403, detail="You don't have access to this submission")
    if write:
        kind = "donor" if submission.donor_id else "surrogate" if submission.surrogate_id else None
        if kind:
            from app.services.record_access_service import get_record_with_access

            get_record_with_access(
                db, session, kind, getattr(submission, f"{kind}_id"), action="edit"
            )


def check_intake_lead(db, session, lead, *, write=False):
    if not permission_policy_service.is_enabled(db, session.org_id):
        return
    require_action(db, session, write=write)
    if lead.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Intake lead not found")
    kind = (
        "donor" if lead.promoted_donor_id else "surrogate" if lead.promoted_surrogate_id else None
    )
    if kind:
        from app.services.record_access_service import get_record_with_access

        get_record_with_access(
            db,
            session,
            kind,
            getattr(lead, f"promoted_{kind}_id"),
            action="edit" if write else "view",
        )
    elif session.role.value not in QUEUE_ROLES:
        raise HTTPException(status_code=403, detail="You don't have access to the intake queue")


def list_review_forms(db, session):
    from sqlalchemy import select

    from app.db.models import Form

    return (
        db.query(Form)
        .filter(
            Form.organization_id == session.org_id,
            Form.id.in_(select(FormSubmission.form_id).where(visibility_filter(db, session))),
        )
        .order_by(Form.name)
        .all()
    )
