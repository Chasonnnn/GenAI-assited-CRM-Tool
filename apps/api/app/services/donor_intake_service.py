"""Deterministic donor matching and scan-gated workflow promotion."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.encryption import hash_phone
from app.db.enums import (
    AuditEventType,
    FormSubmissionStatus,
    IntakeLeadStatus,
    JobType,
)
from app.db.models import Attachment, Donor, FormSubmission, FormSubmissionFile, IntakeLead
from app.utils.normalization import normalize_phone, normalize_search_text, normalize_state

logger = logging.getLogger(__name__)

CONFLICT_REASON = "donor_identity_conflict"
EXISTING_SUBMISSION_REASON = "existing_submission_for_donor"
PHOTO_REVIEW_REASON = "donor_photo_requires_review"
REVIEW_REQUIRED_REASONS = {CONFLICT_REASON, EXISTING_SUBMISSION_REASON}
MAX_DONOR_MATCH_CANDIDATES = 20


def _profile_photo_files(
    db: Session, submission: FormSubmission, *, lock: bool = False
) -> list[FormSubmissionFile]:
    from app.services import form_intake_service

    photo_key = form_intake_service._mapping_lookup_from_snapshot(
        submission.mapping_snapshot or []
    ).get("profile_photo")
    if not photo_key:
        return []
    query = (
        db.query(FormSubmissionFile)
        .filter(
            FormSubmissionFile.organization_id == submission.organization_id,
            FormSubmissionFile.submission_id == submission.id,
            FormSubmissionFile.field_key == photo_key,
            FormSubmissionFile.deleted_at.is_(None),
        )
        .order_by(FormSubmissionFile.id)
    )
    if lock:
        query = query.with_for_update().populate_existing()
    return query.all()


def _is_promotable_photo(photo: FormSubmissionFile) -> bool:
    from app.services import form_intake_service

    return (
        photo.scan_status == "clean"
        and not photo.quarantined
        and photo.content_type in form_intake_service.DONOR_PROFILE_PHOTO_CONTENT_TYPES
    )


def is_profile_photo(db: Session, submission: FormSubmission, file_id: UUID) -> bool:
    return any(photo.id == file_id for photo in _profile_photo_files(db, submission))


def _record_linked_submission_changes(
    db: Session,
    *,
    donor: Donor,
    submission: FormSubmission,
    changed_fields: list[str],
    actor_user_id: UUID | None,
) -> None:
    from app.services import audit_service, entity_activity_service

    now = datetime.now(UTC)
    donor.updated_at = now
    audit_service.log_event(
        db=db,
        org_id=donor.organization_id,
        event_type=AuditEventType.DONOR_UPDATED,
        actor_user_id=actor_user_id,
        target_type="donor",
        target_id=donor.id,
        details={
            "updated_fields": sorted(changed_fields),
            "source_submission_id": str(submission.id),
        },
    )
    entity_activity_service.record_activity(
        db,
        org_id=donor.organization_id,
        entity_type="donor",
        entity_id=donor.id,
        activity_type="info_edited",
        actor_user_id=actor_user_id,
        details={"changed_fields": sorted(changed_fields)},
        occurred_at=now,
    )


def _apply_linked_profile_photo(
    db: Session,
    *,
    submission: FormSubmission,
    donor: Donor,
    actor_user_id: UUID | None,
) -> bool:
    """Use a clean submitted photo as the donor photo; the previous attachment is kept."""
    photos = _profile_photo_files(db, submission)
    if len(photos) != 1 or not _is_promotable_photo(photos[0]):
        return False
    photo = photos[0]
    if donor.profile_photo_attachment_id is not None:
        current = (
            db.query(Attachment.checksum_sha256)
            .filter(
                Attachment.organization_id == donor.organization_id,
                Attachment.donor_id == donor.id,
                Attachment.id == donor.profile_photo_attachment_id,
            )
            .scalar()
        )
        if current and current == photo.checksum_sha256:
            return False
    from app.services import form_intake_service

    form_intake_service._copy_profile_photo_to_donor_attachment(
        db, donor=donor, source_file=photo, user_id=actor_user_id
    )
    return True


def _normalized_or_none(normalize, value) -> str | None:
    try:
        return normalize(str(value))
    except ValueError:
        return None


def apply_linked_submission(
    db: Session,
    *,
    submission: FormSubmission,
    donor: Donor,
    actor_user_id: UUID | None,
) -> list[str]:
    """Fill empty donor fields and apply a clean new photo from a linked submission.

    Public answers never overwrite existing donor details. The caller owns the donor
    lock and the transaction.
    """
    if donor.is_archived:
        return []
    from app.services import form_intake_service

    mapped = form_intake_service._mapped_donor_payload(submission)
    changed: list[str] = []
    if not donor.phone and mapped.get("phone"):
        phone = _normalized_or_none(normalize_phone, mapped["phone"])
        if phone:
            donor.phone = phone
            donor.phone_hash = hash_phone(phone)
            changed.append("phone")
    if not donor.state and mapped.get("state"):
        state = _normalized_or_none(normalize_state, mapped["state"])
        if state:
            donor.state = state
            changed.append("state")
    if not donor.education and mapped.get("education"):
        education = str(mapped["education"]).strip()[:255]
        if education:
            donor.education = education
            changed.append("education")
    if _apply_linked_profile_photo(
        db, submission=submission, donor=donor, actor_user_id=actor_user_id
    ):
        changed.append("profile_photo_attachment_id")
    if changed:
        _record_linked_submission_changes(
            db,
            donor=donor,
            submission=submission,
            changed_fields=changed,
            actor_user_id=actor_user_id,
        )
    return changed


def mark_submission_approved(submission: FormSubmission, *, reviewer_id: UUID | None) -> None:
    now = datetime.now(UTC)
    submission.status = FormSubmissionStatus.APPROVED.value
    submission.reviewed_at = now
    submission.reviewed_by_user_id = reviewer_id
    submission.applied_at = now


def mark_submission_linked(
    db: Session,
    *,
    submission: FormSubmission,
    donor: Donor,
    reviewer_id: UUID | None,
) -> None:
    """A donor link is the donor equivalent of approving a linked surrogate submission."""
    if submission.status != FormSubmissionStatus.PENDING_REVIEW.value:
        return
    mark_submission_approved(submission, reviewer_id=reviewer_id)
    apply_linked_submission(db, submission=submission, donor=donor, actor_user_id=reviewer_id)


def apply_linked_photo_after_scan(db: Session, submission: FormSubmission) -> None:
    """Apply a newly clean photo to the linked donor without failing the scan result."""
    if (
        submission.lead_kind not in {"egg_donor", "sperm_donor"}
        or not submission.donor_id
        or submission.status != FormSubmissionStatus.APPROVED.value
    ):
        return
    try:
        with db.begin_nested():
            donor = (
                db.query(Donor)
                .filter(
                    Donor.organization_id == submission.organization_id,
                    Donor.id == submission.donor_id,
                    Donor.is_archived.is_(False),
                )
                .with_for_update()
                .populate_existing()
                .first()
            )
            if donor is not None and _apply_linked_profile_photo(
                db, submission=submission, donor=donor, actor_user_id=None
            ):
                _record_linked_submission_changes(
                    db,
                    donor=donor,
                    submission=submission,
                    changed_fields=["profile_photo_attachment_id"],
                    actor_user_id=None,
                )
    except Exception as exc:
        logger.error(
            "Linked donor profile photo could not be applied",
            extra={
                "submission_id": str(submission.id),
                "donor_id": str(submission.donor_id),
                "error_class": type(exc).__name__,
            },
        )


def hold_for_photo_review(db: Session, submission: FormSubmission) -> None:
    """An unusable photo keeps the submission out of promotion and lets the applicant retry."""
    if (
        submission.lead_kind not in {"egg_donor", "sperm_donor"}
        or submission.donor_id
        or submission.status != FormSubmissionStatus.PENDING_REVIEW.value
    ):
        return
    submission.match_status = "ambiguous_review"
    submission.match_reason = PHOTO_REVIEW_REASON
    submission.matched_at = None
    db.flush()


def list_match_candidates(
    db: Session,
    submission: FormSubmission,
    *,
    session=None,
) -> list[tuple[Donor, str]]:
    """Active donors of the submission's subtype in its organization sharing email or phone."""
    from app.services import form_intake_service

    if submission.lead_kind not in form_intake_service.DONOR_LEAD_KINDS:
        return []
    try:
        identity = form_intake_service.extract_submission_identity(submission)
    except ValueError:
        return []
    contacts = [Donor.email_hash == identity["email_hash"]]
    if identity.get("phone_hash"):
        contacts.append(Donor.phone_hash == identity["phone_hash"])
    query = db.query(Donor).filter(
        Donor.organization_id == submission.organization_id,
        Donor.donor_type == submission.lead_kind.removesuffix("_donor"),
        Donor.is_archived.is_(False),
        or_(*contacts),
    )
    if session is not None:
        from app.services import permission_policy_service, record_scope_service

        if permission_policy_service.is_enabled(db, session.org_id):
            query = query.filter(
                record_scope_service.build_visibility_filter(db, session, "donor", model=Donor)
            )
    donors = query.order_by(Donor.created_at.asc()).limit(MAX_DONOR_MATCH_CANDIDATES).all()
    candidates: list[tuple[Donor, str]] = []
    for donor in donors:
        email_match = donor.email_hash == identity["email_hash"]
        phone_match = bool(identity.get("phone_hash")) and donor.phone_hash == identity.get(
            "phone_hash"
        )
        if email_match and phone_match:
            reason = "donor_email_phone_match"
        elif email_match:
            reason = "donor_email_match"
        else:
            reason = "donor_phone_match"
        candidates.append((donor, reason))
    return candidates


def match_submission(db: Session, submission: FormSubmission, *, session=None) -> str:
    """Caller owns the submission lock and transaction; never overwrite donor details."""
    from app.services import audit_service, form_intake_service

    if submission.donor_id:
        return "linked"
    identity = form_intake_service.extract_submission_identity(submission)
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
    if session is not None:
        from app.services import permission_policy_service, record_scope_service

        if permission_policy_service.is_enabled(db, session.org_id) and any(
            not record_scope_service.can_access_record(db, session, "donor", candidate)
            for candidate in candidates
        ):
            submission.match_status = "ambiguous_review"
            submission.match_reason = "manual_review_required"
            submission.matched_at = None
            return submission.match_status

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
        existing_submission = (
            db.query(FormSubmission.id)
            .filter(
                FormSubmission.organization_id == submission.organization_id,
                FormSubmission.form_id == submission.form_id,
                FormSubmission.donor_id == matched.id,
                FormSubmission.id != submission.id,
            )
            .first()
        )
        if existing_submission is not None:
            submission.match_status = "ambiguous_review"
            submission.match_reason = EXISTING_SUBMISSION_REASON
            submission.matched_at = None
            return submission.match_status
        submission.donor_id = matched.id
        submission.match_status = "linked"
        submission.match_reason = "donor_email_name_type_exact"
        submission.matched_at = datetime.now(UTC)
        mark_submission_linked(db, submission=submission, donor=matched, reviewer_id=None)
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

    if (
        submission.lead_kind not in form_intake_service.DONOR_LEAD_KINDS
        or submission.status == FormSubmissionStatus.REJECTED.value
    ):
        return
    photos = _profile_photo_files(db, submission, lock=True)
    if len(photos) != 1 or not _is_promotable_photo(photos[0]):
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
        or submission.status == FormSubmissionStatus.REJECTED.value
    ):
        return
    from app.services import workflow_execution_authority

    workflow_execution_authority.authorize_donor_intake_promotion(db, lead)
    match_submission(db, submission)
    if submission.donor_id:
        lead.status = IntakeLeadStatus.PROMOTED.value
        lead.promoted_donor_id = submission.donor_id
        lead.promoted_at = datetime.now(UTC)
        db.commit()
        return
    if submission.match_reason in REVIEW_REQUIRED_REASONS:
        db.commit()
        return
    try:
        form_intake_service._profile_photo_for_donor_lead(
            db, lead=lead, linked_submissions=[submission]
        )
    except ValueError:
        submission.match_status = "ambiguous_review"
        submission.match_reason = PHOTO_REVIEW_REASON
        db.commit()
        return
    # This service owns the atomic donor/attachment/lead/audit transaction and workflow events.
    form_intake_service.promote_intake_lead(db, lead=lead, user_id=None, source=lead.source)
