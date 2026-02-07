"""Form draft service for public applicant autosave/resume."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Form, FormSubmissionDraft, FormSubmissionToken, Surrogate
from app.services import form_submission_service


def _is_empty_value(value: object) -> bool:
    """Treat empty strings/collections as empty; counts False/0 as non-empty."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (int, float, bool)):
        return False
    if isinstance(value, dict):
        if not value:
            return True
        return all(_is_empty_value(v) for v in value.values())
    if isinstance(value, list):
        if not value:
            return True
        return all(_is_empty_value(v) for v in value)
    return False


def _has_non_empty_answer(answers: dict[str, Any]) -> bool:
    return any(not _is_empty_value(v) for v in (answers or {}).values())


def get_draft_by_surrogate_form(
    db: Session,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
    surrogate_id: uuid.UUID,
) -> FormSubmissionDraft | None:
    return (
        db.query(FormSubmissionDraft)
        .filter(
            FormSubmissionDraft.organization_id == org_id,
            FormSubmissionDraft.form_id == form_id,
            FormSubmissionDraft.surrogate_id == surrogate_id,
        )
        .first()
    )


def delete_draft(
    db: Session,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
    surrogate_id: uuid.UUID,
) -> bool:
    draft = get_draft_by_surrogate_form(db, org_id, form_id, surrogate_id)
    if not draft:
        return False
    db.delete(draft)
    db.commit()
    return True


def upsert_public_draft(
    db: Session,
    token_record: FormSubmissionToken,
    form: Form,
    answers: dict[str, Any],
) -> FormSubmissionDraft:
    """Create or update a draft for a public token."""
    if form.status != "published":
        raise ValueError("Form is not published")
    if not form.published_schema_json:
        raise ValueError("Published form schema missing")
    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object")

    schema = form_submission_service.parse_schema(form.published_schema_json)
    fields = form_submission_service.flatten_fields(schema)

    for key in answers:
        if key not in fields:
            raise ValueError(f"Unknown field key: {key}")

    # Validate only values that are materially present (drafts don't enforce required).
    for key, value in answers.items():
        if _is_empty_value(value):
            continue
        form_submission_service._validate_field_value(fields[key], value)  # type: ignore[attr-defined]

    org_id = token_record.organization_id
    surrogate_id = token_record.surrogate_id
    form_id = token_record.form_id

    draft = get_draft_by_surrogate_form(db, org_id, form_id, surrogate_id)
    merged: dict[str, Any] = {}
    if draft and isinstance(draft.answers_json, dict):
        merged.update(draft.answers_json)
    merged.update(answers)

    now = datetime.now(timezone.utc)
    started_now = False

    if not draft:
        draft = FormSubmissionDraft(
            organization_id=org_id,
            form_id=form_id,
            surrogate_id=surrogate_id,
            answers_json={},
        )
        db.add(draft)
        db.flush()

    draft.answers_json = merged
    draft.updated_at = now
    if draft.started_at is None and _has_non_empty_answer(merged):
        draft.started_at = now
        started_now = True

    db.commit()
    db.refresh(draft)

    if started_now:
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.id == surrogate_id,
                Surrogate.organization_id == org_id,
            )
            .first()
        )
        if surrogate:
            from app.services import workflow_triggers

            workflow_triggers.trigger_form_started(
                db=db,
                surrogate=surrogate,
                form_id=form_id,
                draft_id=draft.id,
                started_at=draft.started_at,
                updated_at=draft.updated_at,
            )

    return draft
