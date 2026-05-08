"""Form draft service for public applicant autosave/resume."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import FormSubmissionDraft


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
