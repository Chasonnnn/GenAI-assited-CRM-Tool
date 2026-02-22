"""Service functions for shared/public form intake links."""

from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import hash_email, hash_phone
from app.db.enums import (
    FormLinkMode,
    FormStatus,
    FormSubmissionMatchStatus,
    FormSubmissionStatus,
    IntakeLeadStatus,
)
from app.db.models import (
    Form,
    FormIntakeDraft,
    FormIntakeLink,
    FormSubmission,
    FormSubmissionMatchCandidate,
    IntakeLead,
    Surrogate,
)
from app.schemas.surrogate import SurrogateCreate
from app.services import form_submission_service
from app.utils.normalization import normalize_email, normalize_name, normalize_phone, normalize_search_text

IDENTITY_SURROGATE_FIELDS = ("full_name", "date_of_birth", "phone", "email")


def build_shared_application_link(base_url: str | None, slug: str) -> str:
    cleaned_base = (base_url or "").strip().rstrip("/")
    if not cleaned_base:
        return f"/intake/{slug}"
    return f"{cleaned_base}/intake/{slug}"


def _generate_intake_slug(db: Session) -> str:
    slug = secrets.token_urlsafe(12).replace("_", "-")
    while db.query(FormIntakeLink).filter(FormIntakeLink.slug == slug).first() is not None:
        slug = secrets.token_urlsafe(12).replace("_", "-")
    return slug


def create_intake_link(
    db: Session,
    *,
    org_id: uuid.UUID,
    form: Form,
    user_id: uuid.UUID | None,
    campaign_name: str | None,
    event_name: str | None,
    expires_at: datetime | None,
    max_submissions: int | None,
    utm_defaults: dict[str, str] | None,
) -> FormIntakeLink:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form must be published before creating shared links")
    slug = _generate_intake_slug(db)
    record = FormIntakeLink(
        organization_id=org_id,
        form_id=form.id,
        slug=slug,
        campaign_name=(campaign_name or "").strip() or None,
        event_name=(event_name or "").strip() or None,
        expires_at=expires_at,
        max_submissions=max_submissions,
        utm_defaults=utm_defaults or None,
        created_by_user_id=user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_intake_links(
    db: Session,
    *,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
    include_inactive: bool = False,
) -> list[FormIntakeLink]:
    query = db.query(FormIntakeLink).filter(
        FormIntakeLink.organization_id == org_id,
        FormIntakeLink.form_id == form_id,
    )
    if not include_inactive:
        query = query.filter(FormIntakeLink.is_active.is_(True))
    return query.order_by(FormIntakeLink.created_at.desc()).all()


def get_intake_link(
    db: Session,
    *,
    org_id: uuid.UUID,
    intake_link_id: uuid.UUID,
) -> FormIntakeLink | None:
    return (
        db.query(FormIntakeLink)
        .filter(
            FormIntakeLink.organization_id == org_id,
            FormIntakeLink.id == intake_link_id,
        )
        .first()
    )


def get_intake_link_by_slug(db: Session, slug: str) -> FormIntakeLink | None:
    return db.query(FormIntakeLink).filter(FormIntakeLink.slug == slug).first()


def get_active_intake_link_by_slug(db: Session, slug: str) -> FormIntakeLink | None:
    link = get_intake_link_by_slug(db, slug)
    if not link:
        return None
    if not link.is_active:
        return None
    now = datetime.now(timezone.utc)
    if link.expires_at:
        expires_at = link.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            return None
    if link.max_submissions is not None and link.submissions_count >= link.max_submissions:
        return None
    return link


def update_intake_link(
    db: Session,
    *,
    link: FormIntakeLink,
    campaign_name: str | None = None,
    event_name: str | None = None,
    expires_at: datetime | None = None,
    max_submissions: int | None = None,
    utm_defaults: dict[str, str] | None = None,
    is_active: bool | None = None,
    fields_set: set[str] | None = None,
) -> FormIntakeLink:
    fields_set = fields_set or set()
    if "campaign_name" in fields_set:
        link.campaign_name = (campaign_name or "").strip() or None
    if "event_name" in fields_set:
        link.event_name = (event_name or "").strip() or None
    if "expires_at" in fields_set:
        link.expires_at = expires_at
    if "max_submissions" in fields_set:
        link.max_submissions = max_submissions
    if "utm_defaults" in fields_set:
        link.utm_defaults = utm_defaults or None
    if "is_active" in fields_set:
        link.is_active = bool(is_active)
    db.commit()
    db.refresh(link)
    return link


def rotate_intake_link(
    db: Session,
    *,
    link: FormIntakeLink,
) -> FormIntakeLink:
    link.slug = _generate_intake_slug(db)
    link.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(link)
    return link


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("date_of_birth must be YYYY-MM-DD")


def _build_form_mapping_lookup(db: Session, form_id: uuid.UUID) -> dict[str, str]:
    return {
        m.surrogate_field: m.field_key
        for m in form_submission_service.list_field_mappings(db, form_id)
        if m.surrogate_field in IDENTITY_SURROGATE_FIELDS
    }


def _extract_identity(
    *,
    answers: dict[str, Any],
    mapping_lookup: dict[str, str],
) -> dict[str, Any]:
    def _from_answer(surrogate_field: str) -> Any:
        mapped_key = mapping_lookup.get(surrogate_field)
        if mapped_key and mapped_key in answers:
            return answers.get(mapped_key)
        return answers.get(surrogate_field)

    full_name_raw = _from_answer("full_name")
    dob_raw = _from_answer("date_of_birth")
    phone_raw = _from_answer("phone")
    email_raw = _from_answer("email")

    full_name = normalize_name(str(full_name_raw)) if full_name_raw not in (None, "") else None
    dob = _parse_date(dob_raw)
    phone = normalize_phone(str(phone_raw)) if phone_raw not in (None, "") else None
    email = normalize_email(str(email_raw)) if email_raw not in (None, "") else None

    if not full_name:
        raise ValueError("Missing required field: full_name")
    if dob is None:
        raise ValueError("Missing required field: date_of_birth")
    if not phone:
        raise ValueError("Missing required field: phone")
    if not email:
        raise ValueError("Missing required field: email")

    return {
        "full_name": full_name,
        "full_name_normalized": normalize_search_text(full_name),
        "date_of_birth": dob,
        "phone": phone,
        "phone_hash": hash_phone(phone),
        "email": email,
        "email_hash": hash_email(email),
    }


def _match_rule_phone(
    db: Session,
    *,
    org_id: uuid.UUID,
    identity: dict[str, Any],
) -> list[Surrogate]:
    query = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            Surrogate.phone_hash == identity["phone_hash"],
            Surrogate.full_name_normalized == identity["full_name_normalized"],
        )
        .order_by(Surrogate.created_at.asc())
    )
    candidates = query.all()
    target_dob = identity.get("date_of_birth")
    return [candidate for candidate in candidates if candidate.date_of_birth == target_dob]


def _match_rule_email(
    db: Session,
    *,
    org_id: uuid.UUID,
    identity: dict[str, Any],
) -> list[Surrogate]:
    query = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            Surrogate.email_hash == identity["email_hash"],
            Surrogate.full_name_normalized == identity["full_name_normalized"],
        )
        .order_by(Surrogate.created_at.asc())
    )
    candidates = query.all()
    target_dob = identity.get("date_of_birth")
    return [candidate for candidate in candidates if candidate.date_of_birth == target_dob]


def _detect_duplicate_recent_submission(
    db: Session,
    *,
    link: FormIntakeLink,
    identity: dict[str, Any],
    mapping_lookup: dict[str, str],
) -> bool:
    window_seconds = max(0, int(settings.FORMS_SHARED_DUPLICATE_WINDOW_SECONDS or 0))
    if window_seconds <= 0:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    recent = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.intake_link_id == link.id,
            FormSubmission.submitted_at >= cutoff,
        )
        .order_by(FormSubmission.submitted_at.desc())
        .limit(50)
        .all()
    )
    for submission in recent:
        answers = submission.answers_json if isinstance(submission.answers_json, dict) else {}
        if not isinstance(answers, dict):
            continue
        try:
            existing_identity = _extract_identity(answers=answers, mapping_lookup=mapping_lookup)
        except Exception:
            continue
        if (
            existing_identity.get("full_name_normalized") == identity.get("full_name_normalized")
            and existing_identity.get("date_of_birth") == identity.get("date_of_birth")
            and existing_identity.get("phone_hash") == identity.get("phone_hash")
            and existing_identity.get("email_hash") == identity.get("email_hash")
        ):
            return True
    return False


def _create_intake_lead(
    db: Session,
    *,
    org_id: uuid.UUID,
    form: Form,
    link: FormIntakeLink | None,
    identity: dict[str, Any],
    source_metadata: dict[str, Any] | None,
    user_id: uuid.UUID | None = None,
) -> IntakeLead:
    lead = IntakeLead(
        organization_id=org_id,
        form_id=form.id,
        intake_link_id=link.id if link else None,
        full_name=identity["full_name"],
        full_name_normalized=identity["full_name_normalized"],
        email=identity["email"],
        email_hash=identity["email_hash"],
        phone=identity["phone"],
        phone_hash=identity["phone_hash"],
        date_of_birth=identity["date_of_birth"],
        status=IntakeLeadStatus.PENDING_REVIEW.value,
        source_metadata=source_metadata or None,
        created_by_user_id=user_id,
    )
    db.add(lead)
    db.flush()
    return lead


def _create_shared_submission(
    db: Session,
    *,
    form: Form,
    link: FormIntakeLink,
    answers: dict[str, Any],
    files: list[UploadFile],
    file_field_keys: list[str] | None,
    surrogate_id: uuid.UUID | None,
    intake_lead_id: uuid.UUID | None,
    match_status: str,
    match_reason: str | None,
    matched_at: datetime | None,
) -> FormSubmission:
    schema = form_submission_service.parse_schema(form.published_schema_json or {})
    form_submission_service._validate_answers(schema, answers)  # type: ignore[attr-defined]
    file_fields = form_submission_service._get_file_fields(schema, answers)  # type: ignore[attr-defined]
    resolved_file_field_keys = form_submission_service._resolve_file_field_keys(  # type: ignore[attr-defined]
        file_fields=file_fields,
        files=files or [],
        file_field_keys=file_field_keys,
    )
    form_submission_service._validate_required_file_fields(  # type: ignore[attr-defined]
        file_fields, resolved_file_field_keys
    )
    form_submission_service._validate_file_field_limits(  # type: ignore[attr-defined]
        file_fields, resolved_file_field_keys
    )
    validated_content_types = form_submission_service._validate_files(form, files or [])  # type: ignore[attr-defined]
    mapping_snapshot = form_submission_service._snapshot_mappings(db, form.id)  # type: ignore[attr-defined]
    now = datetime.now(timezone.utc)

    submission = FormSubmission(
        organization_id=form.organization_id,
        form_id=form.id,
        surrogate_id=surrogate_id,
        intake_link_id=link.id,
        intake_lead_id=intake_lead_id,
        source_mode=FormLinkMode.SHARED.value,
        status=FormSubmissionStatus.PENDING_REVIEW.value,
        match_status=match_status,
        match_reason=match_reason,
        matched_at=matched_at,
        answers_json=answers,
        schema_snapshot=form.published_schema_json,
        mapping_snapshot=mapping_snapshot,
        submitted_at=now,
    )
    db.add(submission)
    db.flush()

    for idx, file in enumerate(files or []):
        field_key = resolved_file_field_keys[idx] if resolved_file_field_keys else None
        form_submission_service._store_submission_file(  # type: ignore[attr-defined]
            db=db,
            submission=submission,
            file=file,
            form=form,
            field_key=field_key,
            content_type=validated_content_types[idx],
        )

    link.submissions_count = (link.submissions_count or 0) + 1
    return submission


def create_shared_submission(
    db: Session,
    *,
    link: FormIntakeLink,
    form: Form,
    answers: dict[str, Any],
    files: list[UploadFile] | None = None,
    file_field_keys: list[str] | None = None,
    source_metadata: dict[str, Any] | None = None,
    challenge_token: str | None = None,
) -> tuple[FormSubmission, str]:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form is not published")
    if not form.published_schema_json:
        raise ValueError("Published form schema missing")

    expected_challenge = (settings.FORMS_SHARED_CHALLENGE_SECRET or "").strip()
    if expected_challenge and challenge_token != expected_challenge:
        raise ValueError("Challenge verification failed")

    mapping_lookup = _build_form_mapping_lookup(db, form.id)
    identity = _extract_identity(answers=answers, mapping_lookup=mapping_lookup)

    if _detect_duplicate_recent_submission(
        db,
        link=link,
        identity=identity,
        mapping_lookup=mapping_lookup,
    ):
        raise ValueError("Duplicate submission detected. Please contact support if this is unexpected.")

    auto_match_enabled = bool(settings.FORMS_AUTO_MATCH)
    phone_matches: list[Surrogate] = []
    email_matches: list[Surrogate] = []
    if auto_match_enabled:
        phone_matches = _match_rule_phone(db, org_id=link.organization_id, identity=identity)
        if not phone_matches:
            email_matches = _match_rule_email(db, org_id=link.organization_id, identity=identity)

    if len(phone_matches) == 1:
        matched = phone_matches[0]
        submission = _create_shared_submission(
            db,
            form=form,
            link=link,
            answers=answers,
            files=files or [],
            file_field_keys=file_field_keys,
            surrogate_id=matched.id,
            intake_lead_id=None,
            match_status=FormSubmissionMatchStatus.LINKED.value,
            match_reason="phone_dob_name_exact",
            matched_at=datetime.now(timezone.utc),
        )
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.LINKED.value

    if len(phone_matches) > 1 or len(email_matches) > 1:
        reason = "phone_dob_name_ambiguous" if len(phone_matches) > 1 else "email_dob_name_ambiguous"
        submission = _create_shared_submission(
            db,
            form=form,
            link=link,
            answers=answers,
            files=files or [],
            file_field_keys=file_field_keys,
            surrogate_id=None,
            intake_lead_id=None,
            match_status=FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value,
            match_reason=reason,
            matched_at=None,
        )
        candidates = phone_matches or email_matches
        for surrogate in candidates:
            db.add(
                FormSubmissionMatchCandidate(
                    organization_id=link.organization_id,
                    submission_id=submission.id,
                    surrogate_id=surrogate.id,
                    reason=reason,
                )
            )
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value

    if len(email_matches) == 1:
        matched = email_matches[0]
        submission = _create_shared_submission(
            db,
            form=form,
            link=link,
            answers=answers,
            files=files or [],
            file_field_keys=file_field_keys,
            surrogate_id=matched.id,
            intake_lead_id=None,
            match_status=FormSubmissionMatchStatus.LINKED.value,
            match_reason="email_dob_name_exact",
            matched_at=datetime.now(timezone.utc),
        )
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.LINKED.value

    lead = _create_intake_lead(
        db,
        org_id=link.organization_id,
        form=form,
        link=link,
        identity=identity,
        source_metadata=source_metadata,
        user_id=None,
    )
    submission = _create_shared_submission(
        db,
        form=form,
        link=link,
        answers=answers,
        files=files or [],
        file_field_keys=file_field_keys,
        surrogate_id=None,
        intake_lead_id=lead.id,
        match_status=FormSubmissionMatchStatus.LEAD_CREATED.value,
        match_reason="no_deterministic_match",
        matched_at=None,
    )
    db.commit()
    db.refresh(submission)
    return submission, FormSubmissionMatchStatus.LEAD_CREATED.value


def get_shared_draft(
    db: Session,
    *,
    link: FormIntakeLink,
    draft_session_id: str,
) -> FormIntakeDraft | None:
    return (
        db.query(FormIntakeDraft)
        .filter(
            FormIntakeDraft.intake_link_id == link.id,
            FormIntakeDraft.draft_session_id == draft_session_id,
        )
        .first()
    )


def upsert_shared_draft(
    db: Session,
    *,
    link: FormIntakeLink,
    form: Form,
    draft_session_id: str,
    answers: dict[str, Any],
) -> FormIntakeDraft:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form is not published")
    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object")
    if not form.published_schema_json:
        raise ValueError("Published form schema missing")

    schema = form_submission_service.parse_schema(form.published_schema_json)
    fields = form_submission_service.flatten_fields(schema)
    for key in answers:
        if key not in fields:
            raise ValueError(f"Unknown field key: {key}")

    for key, value in answers.items():
        if value in (None, ""):
            continue
        form_submission_service._validate_field_value(fields[key], value)  # type: ignore[attr-defined]

    draft = get_shared_draft(db, link=link, draft_session_id=draft_session_id)
    now = datetime.now(timezone.utc)
    if not draft:
        draft = FormIntakeDraft(
            organization_id=link.organization_id,
            intake_link_id=link.id,
            form_id=form.id,
            draft_session_id=draft_session_id,
            answers_json={},
        )
        db.add(draft)
        db.flush()

    merged = dict(draft.answers_json or {})
    merged.update(answers)
    draft.answers_json = merged
    draft.updated_at = now
    if draft.started_at is None and any(v not in (None, "", [], {}) for v in merged.values()):
        draft.started_at = now

    db.commit()
    db.refresh(draft)
    return draft


def delete_shared_draft(
    db: Session,
    *,
    link: FormIntakeLink,
    draft_session_id: str,
) -> bool:
    draft = get_shared_draft(db, link=link, draft_session_id=draft_session_id)
    if not draft:
        return False
    db.delete(draft)
    db.commit()
    return True


def list_match_candidates(
    db: Session,
    *,
    org_id: uuid.UUID,
    submission_id: uuid.UUID,
) -> list[FormSubmissionMatchCandidate]:
    return (
        db.query(FormSubmissionMatchCandidate)
        .filter(
            FormSubmissionMatchCandidate.organization_id == org_id,
            FormSubmissionMatchCandidate.submission_id == submission_id,
        )
        .order_by(FormSubmissionMatchCandidate.created_at.asc())
        .all()
    )


def resolve_submission_match(
    db: Session,
    *,
    submission: FormSubmission,
    surrogate_id: uuid.UUID | None,
    create_intake_lead: bool,
    reviewer_id: uuid.UUID | None,
    review_notes: str | None = None,
) -> tuple[FormSubmission, str]:
    if submission.source_mode != FormLinkMode.SHARED.value:
        raise ValueError("Only shared submissions can be match-resolved")

    if surrogate_id:
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.organization_id == submission.organization_id,
                Surrogate.id == surrogate_id,
            )
            .first()
        )
        if not surrogate:
            raise ValueError("Surrogate not found")
        submission.surrogate_id = surrogate.id
        submission.match_status = FormSubmissionMatchStatus.LINKED.value
        submission.match_reason = "manually_linked"
        submission.matched_at = datetime.now(timezone.utc)
        if review_notes is not None:
            submission.review_notes = review_notes.strip() or None
        db.query(FormSubmissionMatchCandidate).filter(
            FormSubmissionMatchCandidate.submission_id == submission.id
        ).delete(synchronize_session=False)
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.LINKED.value

    if not create_intake_lead:
        raise ValueError("Provide surrogate_id or set create_intake_lead=true")

    if submission.intake_lead_id:
        submission.match_status = FormSubmissionMatchStatus.LEAD_CREATED.value
        submission.match_reason = "existing_lead_retained"
        submission.matched_at = None
        if review_notes is not None:
            submission.review_notes = review_notes.strip() or None
        db.query(FormSubmissionMatchCandidate).filter(
            FormSubmissionMatchCandidate.submission_id == submission.id
        ).delete(synchronize_session=False)
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.LEAD_CREATED.value

    answers = submission.answers_json if isinstance(submission.answers_json, dict) else {}
    mapping_lookup = _build_form_mapping_lookup(db, submission.form_id)
    identity = _extract_identity(answers=answers, mapping_lookup=mapping_lookup)
    link = db.query(FormIntakeLink).filter(FormIntakeLink.id == submission.intake_link_id).first()
    form = db.query(Form).filter(Form.id == submission.form_id).first()
    if not form:
        raise ValueError("Form not found")

    lead = _create_intake_lead(
        db,
        org_id=submission.organization_id,
        form=form,
        link=link,
        identity=identity,
        source_metadata={
            "resolved_by_user_id": str(reviewer_id) if reviewer_id else None,
            "review_notes": review_notes.strip() if review_notes else None,
        },
        user_id=reviewer_id,
    )
    submission.intake_lead_id = lead.id
    submission.match_status = FormSubmissionMatchStatus.LEAD_CREATED.value
    submission.match_reason = "manual_lead_creation"
    submission.matched_at = None
    if review_notes is not None:
        submission.review_notes = review_notes.strip() or None
    db.query(FormSubmissionMatchCandidate).filter(
        FormSubmissionMatchCandidate.submission_id == submission.id
    ).delete(synchronize_session=False)
    db.commit()
    db.refresh(submission)
    return submission, FormSubmissionMatchStatus.LEAD_CREATED.value


def get_intake_lead(
    db: Session,
    *,
    org_id: uuid.UUID,
    lead_id: uuid.UUID,
) -> IntakeLead | None:
    return (
        db.query(IntakeLead)
        .filter(
            IntakeLead.organization_id == org_id,
            IntakeLead.id == lead_id,
        )
        .first()
    )


def promote_intake_lead(
    db: Session,
    *,
    lead: IntakeLead,
    user_id: uuid.UUID | None,
    source: str | None = None,
    is_priority: bool = False,
    assign_to_user: bool | None = None,
) -> tuple[Surrogate, int]:
    if lead.status == IntakeLeadStatus.PROMOTED.value and lead.promoted_surrogate_id:
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.organization_id == lead.organization_id,
                Surrogate.id == lead.promoted_surrogate_id,
            )
            .first()
        )
        if surrogate:
            linked_count = (
                db.query(FormSubmission)
                .filter(FormSubmission.intake_lead_id == lead.id, FormSubmission.surrogate_id == surrogate.id)
                .count()
            )
            return surrogate, linked_count

    if not lead.email:
        raise ValueError("Intake lead is missing email")

    source_value = source or "manual"
    surrogate_payload = SurrogateCreate(
        full_name=lead.full_name,
        email=lead.email,
        phone=lead.phone,
        date_of_birth=lead.date_of_birth,
        source=source_value,
        is_priority=is_priority,
        assign_to_user=assign_to_user,
    )
    from app.services import surrogate_service

    surrogate = surrogate_service.create_surrogate(
        db=db,
        org_id=lead.organization_id,
        user_id=user_id,
        data=surrogate_payload,
    )

    lead.status = IntakeLeadStatus.PROMOTED.value
    lead.promoted_surrogate_id = surrogate.id
    lead.promoted_at = datetime.now(timezone.utc)

    linked_count = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == lead.organization_id,
            FormSubmission.intake_lead_id == lead.id,
            FormSubmission.surrogate_id.is_(None),
        )
        .update(
            {
                FormSubmission.surrogate_id: surrogate.id,
                FormSubmission.match_status: FormSubmissionMatchStatus.LINKED.value,
                FormSubmission.match_reason: "lead_promoted_to_surrogate",
                FormSubmission.matched_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
    )
    submission_ids = [
        row[0]
        for row in db.query(FormSubmission.id).filter(FormSubmission.intake_lead_id == lead.id).all()
    ]
    if submission_ids:
        db.query(FormSubmissionMatchCandidate).filter(
            FormSubmissionMatchCandidate.submission_id.in_(submission_ids)
        ).delete(synchronize_session=False)

    db.commit()
    db.refresh(lead)
    return surrogate, int(linked_count or 0)
