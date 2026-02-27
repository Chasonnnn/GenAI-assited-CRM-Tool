"""Profile service for surrogate profile card overrides and hidden fields."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.enums import SurrogateActivityType
from app.db.models import (
    SurrogateProfileOverride,
    SurrogateProfileHiddenField,
    SurrogateProfileState,
    FormSubmission,
)
from app.services import activity_service

PROFILE_HEADER_NAME_KEY = "__profile_header_name"
PROFILE_HEADER_NOTE_KEY = "__profile_header_note"
PROFILE_CUSTOM_QAS_KEY = "__profile_custom_qas"
PROFILE_META_KEYS = {
    PROFILE_HEADER_NAME_KEY,
    PROFILE_HEADER_NOTE_KEY,
    PROFILE_CUSTOM_QAS_KEY,
}


def _coerce_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_custom_qas(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not question and not answer:
            continue
        normalized.append(
            {
                "id": str(item.get("id") or f"qa_{i}"),
                "section_key": str(item.get("section_key") or "default"),
                "question": question,
                "answer": answer,
                "order": int(item.get("order") or i),
            }
        )
    return normalized


def get_profile_data(
    db: Session,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Get merged profile data for a surrogate.

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
        db.query(SurrogateProfileState)
        .filter(
            SurrogateProfileState.surrogate_id == surrogate_id,
            SurrogateProfileState.organization_id == org_id,
        )
        .first()
    )
    base_submission_id = base_state.base_submission_id if base_state else None
    submission = _get_base_submission(db, org_id, surrogate_id, base_submission_id)

    base_answers: dict[str, Any] = {}
    schema_snapshot = None

    if submission:
        base_submission_id = submission.id
        base_answers = submission.answers_json or {}
        schema_snapshot = submission.schema_snapshot

    # Get overrides
    overrides_list = (
        db.query(SurrogateProfileOverride)
        .filter(
            SurrogateProfileOverride.surrogate_id == surrogate_id,
            SurrogateProfileOverride.organization_id == org_id,
        )
        .all()
    )
    overrides = {o.field_key: o.value for o in overrides_list}
    header_name_override = _coerce_optional_text(overrides.get(PROFILE_HEADER_NAME_KEY))
    header_note = _coerce_optional_text(overrides.get(PROFILE_HEADER_NOTE_KEY))
    custom_qas = _coerce_custom_qas(overrides.get(PROFILE_CUSTOM_QAS_KEY))
    display_overrides = {k: v for k, v in overrides.items() if k not in PROFILE_META_KEYS}

    # Get hidden fields
    hidden_list = (
        db.query(SurrogateProfileHiddenField)
        .filter(
            SurrogateProfileHiddenField.surrogate_id == surrogate_id,
            SurrogateProfileHiddenField.organization_id == org_id,
        )
        .all()
    )
    hidden_fields = [h.field_key for h in hidden_list]

    # Merge: base + overrides
    merged_view = {**base_answers, **display_overrides}

    return {
        "base_submission_id": base_submission_id,
        "base_answers": base_answers,
        "overrides": display_overrides,
        "hidden_fields": hidden_fields,
        "merged_view": merged_view,
        "schema_snapshot": schema_snapshot,
        "header_name_override": header_name_override,
        "header_note": header_note,
        "custom_qas": custom_qas,
    }


def _get_base_submission(
    db: Session,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID,
    base_submission_id: uuid.UUID | None = None,
) -> FormSubmission | None:
    """Resolve base submission (explicit base or first submission)."""
    if base_submission_id:
        base = (
            db.query(FormSubmission)
            .filter(
                FormSubmission.id == base_submission_id,
                FormSubmission.surrogate_id == surrogate_id,
                FormSubmission.organization_id == org_id,
            )
            .first()
        )
        if base:
            return base

    return (
        db.query(FormSubmission)
        .filter(
            FormSubmission.surrogate_id == surrogate_id,
            FormSubmission.organization_id == org_id,
        )
        .order_by(FormSubmission.submitted_at.desc())
        .first()
    )


def get_sync_diff(
    db: Session,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """
    Get staged changes for syncing from latest submission.

    Compares current merged view against latest submission.

    Returns list of:
        { "field_key": str, "old_value": Any, "new_value": Any }
    """
    # Get current profile data
    profile = get_profile_data(db, org_id, surrogate_id)
    current_merged = profile["merged_view"]

    # Get latest submission
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.surrogate_id == surrogate_id,
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
    all_keys.difference_update(PROFILE_META_KEYS)

    for key in all_keys:
        old_val = current_merged.get(key)
        new_val = latest_answers.get(key)

        if old_val != new_val:
            staged_changes.append(
                {
                    "field_key": key,
                    "old_value": old_val,
                    "new_value": new_val,
                }
            )

    return staged_changes


def get_latest_submission_id(
    db: Session,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID,
) -> uuid.UUID | None:
    """Get the latest submission ID for a surrogate (org-scoped)."""
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.surrogate_id == surrogate_id,
            FormSubmission.organization_id == org_id,
        )
        .order_by(FormSubmission.submitted_at.desc())
        .first()
    )
    return submission.id if submission else None


def save_profile_overrides(
    db: Session,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID,
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
        db.query(SurrogateProfileState)
        .filter(
            SurrogateProfileState.surrogate_id == surrogate_id,
            SurrogateProfileState.organization_id == org_id,
        )
        .first()
    )
    base_submission_id = new_base_submission_id or (
        base_state.base_submission_id if base_state else None
    )
    base_submission = _get_base_submission(db, org_id, surrogate_id, base_submission_id)
    base_answers = base_submission.answers_json if base_submission else {}

    if new_base_submission_id is not None and (
        not base_submission or base_submission.id != new_base_submission_id
    ):
        raise ValueError("Invalid base submission")

    # Get current overrides for diff logging
    current_overrides = (
        db.query(SurrogateProfileOverride)
        .filter(
            SurrogateProfileOverride.surrogate_id == surrogate_id,
            SurrogateProfileOverride.organization_id == org_id,
        )
        .all()
    )
    old_values = {o.field_key: o.value for o in current_overrides}

    # Filter overrides that match base values
    filtered_overrides = {
        key: value for key, value in overrides.items() if base_answers.get(key) != value
    }

    # Clear existing overrides
    db.query(SurrogateProfileOverride).filter(
        SurrogateProfileOverride.surrogate_id == surrogate_id,
        SurrogateProfileOverride.organization_id == org_id,
    ).delete()

    # Add new overrides
    for field_key, value in filtered_overrides.items():
        override = SurrogateProfileOverride(
            surrogate_id=surrogate_id,
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
                SurrogateProfileState(
                    id=uuid.uuid4(),
                    surrogate_id=surrogate_id,
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
            surrogate_id=surrogate_id,
            organization_id=org_id,
            activity_type=SurrogateActivityType.PROFILE_EDITED,
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
    surrogate_id: uuid.UUID,
    user_id: uuid.UUID,
    field_key: str,
    hidden: bool,
) -> None:
    """Toggle hidden state for a profile field."""
    existing = (
        db.query(SurrogateProfileHiddenField)
        .filter(
            SurrogateProfileHiddenField.surrogate_id == surrogate_id,
            SurrogateProfileHiddenField.organization_id == org_id,
            SurrogateProfileHiddenField.field_key == field_key,
        )
        .first()
    )

    if hidden and not existing:
        # Add hidden field
        hidden_field = SurrogateProfileHiddenField(
            id=uuid.uuid4(),
            surrogate_id=surrogate_id,
            organization_id=org_id,
            field_key=field_key,
            hidden_by_user_id=user_id,
            hidden_at=datetime.now(timezone.utc),
        )
        db.add(hidden_field)
        activity_service.log_activity(
            db=db,
            surrogate_id=surrogate_id,
            organization_id=org_id,
            activity_type=SurrogateActivityType.PROFILE_HIDDEN,
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
            surrogate_id=surrogate_id,
            organization_id=org_id,
            activity_type=SurrogateActivityType.PROFILE_HIDDEN,
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
    surrogate_id: uuid.UUID,
) -> list[str]:
    """Get list of hidden field keys for a surrogate."""
    hidden_list = (
        db.query(SurrogateProfileHiddenField)
        .filter(
            SurrogateProfileHiddenField.surrogate_id == surrogate_id,
            SurrogateProfileHiddenField.organization_id == org_id,
        )
        .all()
    )
    return [h.field_key for h in hidden_list]
