"""Profile service for case profile card overrides and hidden fields."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.enums import CaseActivityType
from app.db.models import (
    CaseProfileOverride,
    CaseProfileHiddenField,
    CaseProfileState,
    FormSubmission,
)
from app.services import activity_service


def get_profile_data(
    db: Session,
    org_id: uuid.UUID,
    case_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Get merged profile data for a case.

    Returns:
        {
            "base_submission_id": UUID or None,
            "base_answers": dict,
            "overrides": dict,
            "hidden_fields": list[str],
            "merged_view": dict,  # base + overrides applied
            "schema_snapshot": dict or None,
        }
    """
    # Resolve base submission (stored base > first submission)
    base_state = (
        db.query(CaseProfileState)
        .filter(
            CaseProfileState.case_id == case_id,
            CaseProfileState.organization_id == org_id,
        )
        .first()
    )
    base_submission_id = base_state.base_submission_id if base_state else None
    submission = _get_base_submission(db, org_id, case_id, base_submission_id)

    base_answers: dict[str, Any] = {}
    schema_snapshot = None

    if submission:
        base_submission_id = submission.id
        base_answers = submission.answers_json or {}
        schema_snapshot = submission.schema_snapshot

    # Get overrides
    overrides_list = (
        db.query(CaseProfileOverride)
        .filter(
            CaseProfileOverride.case_id == case_id,
            CaseProfileOverride.organization_id == org_id,
        )
        .all()
    )
    overrides = {o.field_key: o.value for o in overrides_list}

    # Get hidden fields
    hidden_list = (
        db.query(CaseProfileHiddenField)
        .filter(
            CaseProfileHiddenField.case_id == case_id,
            CaseProfileHiddenField.organization_id == org_id,
        )
        .all()
    )
    hidden_fields = [h.field_key for h in hidden_list]

    # Merge: base + overrides
    merged_view = {**base_answers, **overrides}

    return {
        "base_submission_id": base_submission_id,
        "base_answers": base_answers,
        "overrides": overrides,
        "hidden_fields": hidden_fields,
        "merged_view": merged_view,
        "schema_snapshot": schema_snapshot,
    }


def _get_base_submission(
    db: Session,
    org_id: uuid.UUID,
    case_id: uuid.UUID,
    base_submission_id: uuid.UUID | None = None,
) -> FormSubmission | None:
    """Resolve base submission (explicit base or first submission)."""
    if base_submission_id:
        base = (
            db.query(FormSubmission)
            .filter(
                FormSubmission.id == base_submission_id,
                FormSubmission.case_id == case_id,
                FormSubmission.organization_id == org_id,
            )
            .first()
        )
        if base:
            return base

    return (
        db.query(FormSubmission)
        .filter(
            FormSubmission.case_id == case_id,
            FormSubmission.organization_id == org_id,
        )
        .order_by(FormSubmission.submitted_at.desc())
        .first()
    )


def get_sync_diff(
    db: Session,
    org_id: uuid.UUID,
    case_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """
    Get staged changes for syncing from latest submission.

    Compares current merged view against latest submission.

    Returns list of:
        { "field_key": str, "old_value": Any, "new_value": Any }
    """
    # Get current profile data
    profile = get_profile_data(db, org_id, case_id)
    current_merged = profile["merged_view"]

    # Get latest submission
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.case_id == case_id,
            FormSubmission.organization_id == org_id,
        )
        .order_by(FormSubmission.submitted_at.desc())
        .first()
    )

    if not submission:
        return []

    latest_answers = submission.answers_json or {}
    staged_changes: list[dict[str, Any]] = []

    # Compare all keys from latest submission
    all_keys = set(latest_answers.keys()) | set(current_merged.keys())

    for key in all_keys:
        old_val = current_merged.get(key)
        new_val = latest_answers.get(key)

        if old_val != new_val:
            staged_changes.append({
                "field_key": key,
                "old_value": old_val,
                "new_value": new_val,
            })

    return staged_changes


def save_profile_overrides(
    db: Session,
    org_id: uuid.UUID,
    case_id: uuid.UUID,
    user_id: uuid.UUID,
    overrides: dict[str, Any],
    new_base_submission_id: uuid.UUID | None = None,
) -> None:
    """
    Save profile overrides and optionally update base submission ID.

    After Sync + Save, pass new_base_submission_id to update the base.
    """
    # Resolve base submission for diff filtering
    base_state = (
        db.query(CaseProfileState)
        .filter(
            CaseProfileState.case_id == case_id,
            CaseProfileState.organization_id == org_id,
        )
        .first()
    )
    base_submission_id = new_base_submission_id or (
        base_state.base_submission_id if base_state else None
    )
    base_submission = _get_base_submission(db, org_id, case_id, base_submission_id)
    base_answers = base_submission.answers_json if base_submission else {}

    if new_base_submission_id is not None and (
        not base_submission or base_submission.id != new_base_submission_id
    ):
        raise ValueError("Invalid base submission")

    # Get current overrides for diff logging
    current_overrides = (
        db.query(CaseProfileOverride)
        .filter(
            CaseProfileOverride.case_id == case_id,
            CaseProfileOverride.organization_id == org_id,
        )
        .all()
    )
    old_values = {o.field_key: o.value for o in current_overrides}

    # Filter overrides that match base values
    filtered_overrides = {
        key: value
        for key, value in overrides.items()
        if base_answers.get(key) != value
    }

    # Clear existing overrides
    db.query(CaseProfileOverride).filter(
        CaseProfileOverride.case_id == case_id,
        CaseProfileOverride.organization_id == org_id,
    ).delete()

    # Add new overrides
    for field_key, value in filtered_overrides.items():
        override = CaseProfileOverride(
            case_id=case_id,
            organization_id=org_id,
            field_key=field_key,
            value=value,
            updated_by_user_id=user_id,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(override)

    # Update base submission state (on Sync + Save)
    if new_base_submission_id is not None:
        if base_state:
            base_state.base_submission_id = new_base_submission_id
            base_state.updated_by_user_id = user_id
            base_state.updated_at = datetime.now(timezone.utc)
        else:
            db.add(
                CaseProfileState(
                    id=uuid.uuid4(),
                    case_id=case_id,
                    organization_id=org_id,
                    base_submission_id=new_base_submission_id,
                    updated_by_user_id=user_id,
                    updated_at=datetime.now(timezone.utc),
                )
            )

    # Log activity
    changes = {}
    all_keys = set(old_values.keys()) | set(filtered_overrides.keys())
    for key in all_keys:
        old = old_values.get(key)
        new = filtered_overrides.get(key)
        if old != new:
            changes[key] = {"old": old, "new": new}

    if changes:
        activity_service.log_activity(
            db=db,
            case_id=case_id,
            organization_id=org_id,
            activity_type=CaseActivityType.PROFILE_EDITED,
            actor_user_id=user_id,
            details={
                "changes": changes,
                "source": "sync" if new_base_submission_id else "manual",
                "base_submission_id": str(new_base_submission_id)
                if new_base_submission_id
                else None,
            },
        )

    db.commit()


def set_field_hidden(
    db: Session,
    org_id: uuid.UUID,
    case_id: uuid.UUID,
    user_id: uuid.UUID,
    field_key: str,
    hidden: bool,
) -> None:
    """Toggle hidden state for a profile field."""
    existing = (
        db.query(CaseProfileHiddenField)
        .filter(
            CaseProfileHiddenField.case_id == case_id,
            CaseProfileHiddenField.organization_id == org_id,
            CaseProfileHiddenField.field_key == field_key,
        )
        .first()
    )

    if hidden and not existing:
        # Add hidden field
        hidden_field = CaseProfileHiddenField(
            id=uuid.uuid4(),
            case_id=case_id,
            organization_id=org_id,
            field_key=field_key,
            hidden_by_user_id=user_id,
            hidden_at=datetime.now(timezone.utc),
        )
        db.add(hidden_field)
        activity_service.log_activity(
            db=db,
            case_id=case_id,
            organization_id=org_id,
            activity_type=CaseActivityType.PROFILE_HIDDEN,
            actor_user_id=user_id,
            details={
                "field_key": field_key,
                "hidden": True,
            },
        )
        db.commit()
    elif not hidden and existing:
        # Remove hidden field
        db.delete(existing)
        activity_service.log_activity(
            db=db,
            case_id=case_id,
            organization_id=org_id,
            activity_type=CaseActivityType.PROFILE_HIDDEN,
            actor_user_id=user_id,
            details={
                "field_key": field_key,
                "hidden": False,
            },
        )
        db.commit()


def get_hidden_fields(
    db: Session,
    org_id: uuid.UUID,
    case_id: uuid.UUID,
) -> list[str]:
    """Get list of hidden field keys for a case."""
    hidden_list = (
        db.query(CaseProfileHiddenField)
        .filter(
            CaseProfileHiddenField.case_id == case_id,
            CaseProfileHiddenField.organization_id == org_id,
        )
        .all()
    )
    return [h.field_key for h in hidden_list]
