"""Per-form routing and human review, independent of workflow definitions."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_USER_ID, WORKFLOW_APPROVAL_TIMEOUT_HOURS
from app.core.record_creation import check_record_creation
from app.db.enums import AuditEventType, FormLeadKind, OwnerType, Role, TaskStatus, TaskType
from app.db.models import (
    Donor,
    Form,
    FormSubmission,
    Membership,
    Organization,
    Surrogate,
    Task,
    User,
)
from app.schemas.auth import UserSession
from app.schemas.forms import FormRoutingRead, FormRoutingUpdate, FormWorkflowSummary
from app.services import audit_service, form_intake_service, notification_service
from app.utils.business_hours import calculate_approval_due_date

DONOR_KINDS = {FormLeadKind.EGG_DONOR.value, FormLeadKind.SPERM_DONOR.value}
logger = logging.getLogger(__name__)


class RoutingReviewConflict(ValueError):
    """The requested review transition no longer applies."""


def reset_kind_defaults(form: Form, user_id: UUID | None) -> None:
    donor = form.lead_kind in DONOR_KINDS
    form.routing_exact_match = "auto" if donor else "review"
    form.routing_no_match = "auto" if donor else "review"
    form.routing_lead_source = "website" if donor else None
    form.routing_auto_create_donor = donor
    form.routing_updated_by_user_id = user_id


def routing_read(form: Form) -> FormRoutingRead:
    return FormRoutingRead(
        form_id=form.id,
        lead_kind=form.lead_kind,
        exact_match=form.routing_exact_match,
        no_match=form.routing_no_match,
        lead_source=form.routing_lead_source,
        auto_create_donor=form.routing_auto_create_donor,
        updated_at=form.updated_at,
    )


def update_routing(
    db: Session, *, form: Form, body: FormRoutingUpdate, session: UserSession
) -> FormRoutingRead:
    if body.auto_create_donor and form.lead_kind == "surrogate":
        raise ValueError("auto_create_donor is only available for donor forms")
    if "auto" in (body.exact_match, body.no_match):
        check_record_creation(
            db, session, "donors" if form.lead_kind in DONOR_KINDS else "surrogates", v2_only=True
        )
    try:
        for key, value in body.model_dump().items():
            setattr(form, f"routing_{key}", value)
        form.routing_updated_by_user_id = session.user_id
        form.updated_by_user_id = session.user_id
        audit_service.log_event(
            db,
            org_id=session.org_id,
            actor_user_id=session.user_id,
            event_type=AuditEventType.SETTINGS_ORG_UPDATED,
            target_type="form",
            target_id=form.id,
            details={"action": "update_routing", **body.model_dump()},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(form)
    return routing_read(form)


def list_form_workflows(
    db: Session, *, form: Form, session: UserSession
) -> list[FormWorkflowSummary]:
    from app.services import workflow_access, workflow_execution_authority, workflow_service

    workflows = workflow_service.list_workflows(
        db,
        org_id=session.org_id,
        user_id=session.user_id,
        has_manage_permission=workflow_access.can_inspect_personal(db, session),
    )
    result = []
    for workflow in workflows:
        if workflow.trigger_type not in {
            "form_submitted",
            "form_submission_approved",
            "form_submission_rejected",
        } or (workflow.trigger_config or {}).get("form_id") != str(form.id):
            continue
        if not workflow_access.can_view(
            db,
            session,
            workflow,
            workflow_service.get_workflow_effective_subject_type(db, workflow),
        ):
            continue
        workflow_execution_authority.audit_private_access(db, workflow, session.user_id, "list")
        result.append(
            FormWorkflowSummary(
                id=workflow.id,
                name=workflow.name,
                trigger_type=workflow.trigger_type,
                is_enabled=workflow.is_enabled,
                scope=workflow.scope,
            )
        )
    db.commit()
    return result


def lock_submission(db: Session, org_id: UUID, submission_id: UUID) -> FormSubmission:
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.id == submission_id,
        )
        .with_for_update()
        .populate_existing()
        .first()
    )
    if submission is None:
        raise ValueError("Submission not found")
    return submission


def _form(db: Session, submission: FormSubmission) -> Form:
    return (
        db.query(Form)
        .filter(
            Form.organization_id == submission.organization_id,
            Form.id == submission.form_id,
        )
        .one()
    )


def _review_owner(db: Session, form: Form, submission: FormSubmission) -> User | None:
    # Unlinked form workflow approvals use the editor/creator, then the oldest active admin.
    active_members = (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == form.organization_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
    )
    model, record_id = (
        (Donor, submission.donor_id)
        if submission.donor_id
        else (Surrogate, submission.surrogate_id)
    )
    if record_id:
        record = (
            db.query(model)
            .filter(model.organization_id == form.organization_id, model.id == record_id)
            .first()
        )
        owner = (
            active_members.filter(User.id == record.owner_id).first()
            if record is not None and record.owner_type == OwnerType.USER.value
            else None
        )
        return owner
    for user_id in (
        form.routing_updated_by_user_id,
        form.updated_by_user_id,
        form.created_by_user_id,
    ):
        if user_id:
            owner = active_members.filter(User.id == user_id).first()
            if owner:
                return owner
    owner = (
        active_members.filter(
            Membership.role.in_([Role.ADMIN.value, Role.DEVELOPER.value]),
        )
        .order_by(User.created_at.asc())
        .first()
    )
    return owner


def _open_tasks(db: Session, submission: FormSubmission):
    return db.query(Task).filter(
        Task.organization_id == submission.organization_id,
        Task.form_submission_id == submission.id,
        Task.task_type == TaskType.REVIEW.value,
        Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
    )


def finish_review(db: Session, submission: FormSubmission, actor_id: UUID | None) -> None:
    """Supersede a review inside the caller's locked submission transaction."""
    if not submission.routing_review_step:
        return
    submission.routing_review_step = None
    submission.match_status = "ambiguous_review"
    submission.match_reason = "routing_review_dismissed"
    for task in _open_tasks(db, submission).all():
        task.status = TaskStatus.COMPLETED.value
        task.is_completed = True
        task.completed_at = datetime.now(UTC)
        task.completed_by_user_id = actor_id or SYSTEM_USER_ID
    _audit(db, submission, "routing_review_closed", actor_id or SYSTEM_USER_ID)
    # Donor helpers reload the locked row with populate_existing; autoflush is disabled.
    db.flush()


def run_after_commit(
    db: Session, submission: FormSubmission, callbacks: list[Callable[[], None]]
) -> None:
    """Keep failures in committed routing side effects from suppressing later work."""
    submission_id, org_id = submission.id, submission.organization_id
    for callback in callbacks:
        try:
            callback()
        except Exception as exc:
            db.rollback()
            logger.error(
                "Submission callback failed: exception=%s submission_id=%s organization_id=%s",
                type(exc).__name__,
                submission_id,
                org_id,
            )


def _request_review(
    db: Session,
    submission: FormSubmission,
    form: Form,
    step: str,
    after_commit: list[Callable[[], None]],
) -> None:
    submission.match_status = "routing_review"
    submission.routing_review_step = step
    if _open_tasks(db, submission).first():
        return
    owner = _review_owner(db, form, submission)
    if owner is None:
        logger.warning(
            "Routing reviewer unavailable: submission_id=%s organization_id=%s",
            submission.id,
            submission.organization_id,
        )
        return
    org = db.get(Organization, form.organization_id)
    due_at = calculate_approval_due_date(
        start_utc=datetime.now(UTC),
        owner=owner,
        org=org,
        timeout_hours=WORKFLOW_APPROVAL_TIMEOUT_HOURS,
    )
    task = Task(
        organization_id=submission.organization_id,
        form_submission_id=submission.id,
        surrogate_id=submission.surrogate_id,
        donor_id=submission.donor_id,
        task_type=TaskType.REVIEW.value,
        title=f"Review submission: {form.name}",
        owner_type=OwnerType.USER.value,
        owner_id=owner.id,
        status=TaskStatus.PENDING.value,
        created_by_user_id=SYSTEM_USER_ID,
        due_at=due_at,
        due_date=due_at.date(),
        due_time=due_at.time(),
    )
    db.add(task)
    db.flush()
    # The notification helper commits; invoke it only after the routing transaction.
    after_commit.append(
        lambda: notification_service.notify_submission_routing_review(
            db=db,
            task_id=task.id,
            form_id=form.id,
            org_id=submission.organization_id,
            assignee_id=owner.id,
        )
    )


def _create_lead(
    db: Session,
    submission: FormSubmission,
    form: Form,
    after_commit: list[Callable[[], None]],
    session: UserSession | None,
) -> None:
    if session is not None:
        check_record_creation(
            db,
            session,
            "donors" if submission.lead_kind in DONOR_KINDS else "surrogates",
            v2_only=True,
        )
    form_intake_service.create_intake_lead_for_submission(
        db,
        submission=submission,
        user_id=session.user_id if session else None,
        session=session,
        source=form.routing_lead_source,
        auto_promote=form.routing_auto_create_donor and submission.lead_kind in DONOR_KINDS,
        commit=False,
        after_commit=after_commit,
    )


def _match_and_route(
    db: Session,
    submission: FormSubmission,
    form: Form,
    after_commit: list[Callable[[], None]],
    session: UserSession | None = None,
) -> None:
    form_intake_service.auto_match_submission(
        db, submission=submission, session=session, commit=False
    )
    if not form_intake_service.can_create_intake_lead(db, submission) or submission.intake_lead_id:
        return
    if form.routing_no_match == "review":
        _request_review(db, submission, form, "create_lead", after_commit)
    elif form.routing_no_match == "auto":
        _create_lead(db, submission, form, after_commit, session)


def _audit(db: Session, submission: FormSubmission, action: str, user_id: UUID | None) -> None:
    audit_service.log_event(
        db,
        org_id=submission.organization_id,
        actor_user_id=user_id,
        event_type=AuditEventType.FORM_SUBMISSION_MATCHED,
        target_type="form_submission",
        target_id=submission.id,
        details={
            "action": action,
            "match_status": submission.match_status,
            "routing_review_step": submission.routing_review_step,
        },
    )


def route_submission(db: Session, *, org_id: UUID, submission_id: UUID) -> FormSubmission:
    after_commit: list[Callable[[], None]] = []
    try:
        submission = lock_submission(db, org_id, submission_id)
        if submission.source_mode != "shared" or submission.match_status != "workflow_pending":
            db.commit()
            return submission
        form = _form(db, submission)
        if form.routing_exact_match == "review":
            _request_review(db, submission, form, "match", after_commit)
        else:
            _match_and_route(db, submission, form, after_commit)
        _audit(db, submission, "route_submission", None)
        db.commit()
    except Exception:
        db.rollback()
        raise
    run_after_commit(db, submission, after_commit)
    db.refresh(submission)
    return submission


def _review(
    db: Session,
    *,
    submission_id: UUID,
    session: UserSession,
    operation: Literal["run_match", "create_lead", "dismiss"],
) -> tuple[FormSubmission, str]:
    from app.services import form_submission_access

    after_commit: list[Callable[[], None]] = []
    # Reject before any write so a refused request leaves the review and its task untouched.
    submission = lock_submission(db, session.org_id, submission_id)
    form_submission_access.check_submission(db, session, submission, write=True)
    step = submission.routing_review_step
    expected = {"run_match": "match", "create_lead": "create_lead"}.get(operation)
    if submission.match_status != "routing_review" or not step or (expected and step != expected):
        raise RoutingReviewConflict("Submission is not waiting for this routing review step")
    if operation != "dismiss" and submission.status != "pending_review":
        raise RoutingReviewConflict("Submission is not pending review")
    form = _form(db, submission)
    if operation == "create_lead" or (operation == "run_match" and form.routing_no_match == "auto"):
        check_record_creation(
            db,
            session,
            "donors" if submission.lead_kind in DONOR_KINDS else "surrogates",
            v2_only=True,
        )
    try:
        finish_review(db, submission, session.user_id)
        if operation == "dismiss":
            submission.match_reason = "routing_review_dismissed"
        elif operation == "run_match":
            _match_and_route(db, submission, form, after_commit, session)
        else:
            _create_lead(db, submission, form, after_commit, session)
        _audit(db, submission, f"routing_{operation}", session.user_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    run_after_commit(db, submission, after_commit)
    db.refresh(submission)
    return submission, submission.match_status


def run_match(
    db: Session, *, submission_id: UUID, session: UserSession
) -> tuple[FormSubmission, str]:
    return _review(db, submission_id=submission_id, session=session, operation="run_match")


def create_lead(
    db: Session, *, submission_id: UUID, session: UserSession
) -> tuple[FormSubmission, str]:
    return _review(db, submission_id=submission_id, session=session, operation="create_lead")


def dismiss(
    db: Session, *, submission_id: UUID, session: UserSession
) -> tuple[FormSubmission, str]:
    return _review(db, submission_id=submission_id, session=session, operation="dismiss")
