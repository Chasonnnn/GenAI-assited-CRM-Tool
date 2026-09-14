"""Deterministic donor matching and scan-gated workflow promotion."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.enums import AuditEventType, IntakeLeadStatus, JobType
from app.db.models import Donor, FormSubmission, FormSubmissionFile, IntakeLead
from app.utils.normalization import normalize_search_text

CONFLICT_REASON = "donor_identity_conflict"


def match_submission(db: Session, submission: FormSubmission) -> str:
    """Caller owns the submission lock and transaction; never overwrite donor details."""
    from app.services import audit_service, form_intake_service

    if submission.donor_id:
        return "linked"
    identity = form_intake_service._extract_donor_identity(
        answers=submission.answers_json or {},
        mapping_lookup=form_intake_service._mapping_lookup_from_snapshot(
            submission.mapping_snapshot or []
        ),
    )
    contacts = [Donor.email_hash == identity["email_hash"]]
    if identity.get("phone_hash"):
        contacts.append(Donor.phone_hash == identity["phone_hash"])
    candidates = (
        db.query(Donor)
        .filter(
            Donor.organization_id == submission.organization_id,
            Donor.is_archived.is_(False),
            or_(*contacts),
        )
        .order_by(Donor.id)
        .with_for_update()
        .populate_existing()
        .all()
    )
    matched = candidates[0] if len(candidates) == 1 else None
    expected_type = submission.lead_kind.removesuffix("_donor")
    if matched and (
        matched.email_hash == identity["email_hash"]
        and matched.donor_type == expected_type
        and normalize_search_text(matched.full_name) == identity["full_name_normalized"]
        and (
            not matched.phone_hash
            or not identity.get("phone_hash")
            or matched.phone_hash == identity["phone_hash"]
        )
    ):
        submission.donor_id = matched.id
        submission.match_status = "linked"
        submission.match_reason = "donor_email_name_type_exact"
        submission.matched_at = datetime.now(UTC)
        audit_service.log_event(
            db,
            org_id=submission.organization_id,
            event_type=AuditEventType.FORM_SUBMISSION_MATCHED,
            target_type="form_submission",
            target_id=submission.id,
            details={"donor_id": str(matched.id), "reason": submission.match_reason},
        )
        return "linked"
    submission.match_status = "ambiguous_review"
    submission.match_reason = CONFLICT_REASON if candidates else "donor_no_deterministic_match"
    submission.matched_at = None
    return submission.match_status


def enqueue_promotion(db: Session, *, submission: FormSubmission) -> None:
    """Serialize enqueue with scan completion on the source photo row; caller commits."""
    from app.services import form_intake_service, job_service

    if submission.lead_kind not in form_intake_service.DONOR_LEAD_KINDS:
        return
    photo_key = form_intake_service._mapping_lookup_from_snapshot(
        submission.mapping_snapshot or []
    ).get("profile_photo")
    if not photo_key:
        return
    photos = (
        db.query(FormSubmissionFile)
        .filter(
            FormSubmissionFile.organization_id == submission.organization_id,
            FormSubmissionFile.submission_id == submission.id,
            FormSubmissionFile.field_key == photo_key,
            FormSubmissionFile.deleted_at.is_(None),
        )
        .order_by(FormSubmissionFile.id)
        .with_for_update()
        .populate_existing()
        .all()
    )
    if len(photos) != 1:
        return
    photo = photos[0]
    if (
        photo.scan_status != "clean"
        or photo.quarantined
        or photo.content_type not in form_intake_service.DONOR_PROFILE_PHOTO_CONTENT_TYPES
    ):
        return
    # Read after the file lock so a scanner waiting on the workflow sees its committed lead.
    lead = (
        db.query(IntakeLead)
        .filter(
            IntakeLead.organization_id == submission.organization_id,
            IntakeLead.form_submission_id == submission.id,
            IntakeLead.lead_type == submission.lead_kind,
        )
        .first()
    )
    if (
        not lead
        or lead.status != IntakeLeadStatus.PENDING_REVIEW.value
        or not (lead.source_metadata or {}).get("auto_create_donor")
    ):
        return
    key = f"donor_intake_promote:{lead.id}"
    if job_service.get_job_by_idempotency_key(db, org_id=lead.organization_id, idempotency_key=key):
        return
    job_service.enqueue_job(
        db,
        org_id=lead.organization_id,
        job_type=JobType.DONOR_INTAKE_PROMOTE,
        payload={"intake_lead_id": str(lead.id)},
        idempotency_key=key,
        commit=False,
    )


def promote_queued_lead(db: Session, *, org_id: UUID, lead_id: UUID) -> None:
    """Recheck identity and scan state before creating a donor; retries reuse the lead."""
    from app.services import form_intake_service

    lead = (
        db.query(IntakeLead)
        .filter(
            IntakeLead.organization_id == org_id,
            IntakeLead.id == lead_id,
        )
        .first()
    )
    if not lead:
        raise ValueError("Donor intake lead not found")
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.id == lead.form_submission_id,
            FormSubmission.intake_lead_id == lead.id,
            FormSubmission.lead_kind == lead.lead_type,
        )
        .with_for_update(nowait=True)
        .populate_existing()
        .first()
    )
    if not submission:
        raise ValueError("Donor source submission not found")
    lead = (
        db.query(IntakeLead)
        .filter(
            IntakeLead.organization_id == org_id,
            IntakeLead.id == lead_id,
        )
        .with_for_update(nowait=True)
        .populate_existing()
        .one()
    )
    if (
        lead.lead_type not in form_intake_service.DONOR_LEAD_KINDS
        or lead.status != IntakeLeadStatus.PENDING_REVIEW.value
        or not (lead.source_metadata or {}).get("auto_create_donor")
    ):
        return
    match_submission(db, submission)
    if submission.donor_id:
        lead.status = IntakeLeadStatus.PROMOTED.value
        lead.promoted_donor_id = submission.donor_id
        lead.promoted_at = datetime.now(UTC)
        db.commit()
        return
    if submission.match_reason == CONFLICT_REASON:
        db.commit()
        return
    try:
        form_intake_service._profile_photo_for_donor_lead(
            db, lead=lead, linked_submissions=[submission]
        )
    except ValueError:
        submission.match_status = "ambiguous_review"
        submission.match_reason = "donor_photo_requires_review"
        db.commit()
        return
    # This service owns the atomic donor/attachment/lead/audit transaction and workflow events.
    form_intake_service.promote_intake_lead(db, lead=lead, user_id=None, source=lead.source)
