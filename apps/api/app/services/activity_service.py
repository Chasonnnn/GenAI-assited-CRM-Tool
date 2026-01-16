"""Activity logging service - centralized surrogate activity tracking."""

import re
from uuid import UUID
from sqlalchemy.orm import Session

from app.db.enums import SurrogateActivityType
from app.db.models import SurrogateActivityLog


REDACTED_VALUE = "[redacted]"


def _sanitize_preview(html: str, max_chars: int = 120) -> str:
    """Strip HTML, preserve line breaks as ' • ', truncate for activity log display."""
    if not html:
        return ""
    # Replace <br>, </p>, </div> with line break marker
    text = re.sub(r"<br\s*/?>", " • ", html)
    text = re.sub(r"</(?:p|div)>", " • ", text)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]*>", "", text)
    # Decode common HTML entities
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    )
    # Normalize whitespace around markers
    text = re.sub(r"\s*•\s*", " • ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" •")
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _redact_changes(changes: dict[str, any]) -> dict[str, str]:
    """Redact all change values to avoid logging raw PII."""
    return {field: REDACTED_VALUE for field in changes.keys()}


def log_activity(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    activity_type: SurrogateActivityType,
    actor_user_id: UUID | None = None,
    details: dict | None = None,
) -> SurrogateActivityLog:
    """
    Log a surrogate activity.

    Args:
        db: Database session
        surrogate_id: The surrogate this activity is for
        organization_id: Organization context
        activity_type: Type of activity (from SurrogateActivityType enum)
        actor_user_id: User who performed the action (None for system)
        details: Type-specific details as JSON

    Returns:
        The created activity log entry
    """
    activity = SurrogateActivityLog(
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=activity_type.value,
        actor_user_id=actor_user_id,
        details=details,
    )
    db.add(activity)
    db.flush()  # Don't commit - let caller control transaction
    return activity


def log_surrogate_created(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
) -> SurrogateActivityLog:
    """Log surrogate creation."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.SURROGATE_CREATED,
        actor_user_id=actor_user_id,
    )


def log_info_edited(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    changes: dict[str, any],  # {"field_name": "new_value"}
) -> SurrogateActivityLog:
    """Log surrogate info edit with redacted values."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.INFO_EDITED,
        actor_user_id=actor_user_id,
        details={"changes": _redact_changes(changes)},
    )


# NOTE: log_status_changed removed - status transitions are tracked in SurrogateStatusHistory (canonical source)


def log_assigned(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    to_user_id: UUID,
    from_user_id: UUID | None = None,
) -> SurrogateActivityLog:
    """Log surrogate assignment (includes previous assignee if reassignment)."""
    details = {"to_user_id": str(to_user_id)}
    if from_user_id:
        details["from_user_id"] = str(from_user_id)
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.ASSIGNED,
        actor_user_id=actor_user_id,
        details=details,
    )


def log_unassigned(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    from_user_id: UUID,
) -> SurrogateActivityLog:
    """Log surrogate unassignment."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.UNASSIGNED,
        actor_user_id=actor_user_id,
        details={"from_user_id": str(from_user_id)},
    )


def log_priority_changed(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    is_priority: bool,
) -> SurrogateActivityLog:
    """Log priority toggle."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.PRIORITY_CHANGED,
        actor_user_id=actor_user_id,
        details={"is_priority": is_priority},
    )


def log_archived(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
) -> SurrogateActivityLog:
    """Log surrogate archive."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.ARCHIVED,
        actor_user_id=actor_user_id,
    )


def log_restored(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
) -> SurrogateActivityLog:
    """Log surrogate restore."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.RESTORED,
        actor_user_id=actor_user_id,
    )


def log_note_added(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    note_id: UUID,
    content: str,
) -> SurrogateActivityLog:
    """Log note creation with sanitized preview snapshot."""
    preview = _sanitize_preview(content)
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.NOTE_ADDED,
        actor_user_id=actor_user_id,
        details={
            "note_id": str(note_id),
            "preview": preview,
        },
    )


def log_note_deleted(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    note_id: UUID,
    content_preview: str,
) -> SurrogateActivityLog:
    """Log note deletion with sanitized preview snapshot."""
    preview = _sanitize_preview(content_preview)
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.NOTE_DELETED,
        actor_user_id=actor_user_id,
        details={
            "note_id": str(note_id),
            "preview": preview,
        },
    )


def log_email_sent(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    email_log_id: UUID,
    subject: str,
    provider: str,
) -> SurrogateActivityLog:
    """Log email sent without storing subject/body."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.EMAIL_SENT,
        actor_user_id=actor_user_id,
        details={
            "email_log_id": str(email_log_id),
            "provider": provider,
        },
    )


def log_attachment_added(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    attachment_id: UUID,
    filename: str,
) -> SurrogateActivityLog:
    """Log attachment upload with filename."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.ATTACHMENT_ADDED,
        actor_user_id=actor_user_id,
        details={
            "attachment_id": str(attachment_id),
            "filename": filename,
        },
    )


def log_attachment_deleted(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    attachment_id: UUID,
    filename: str,
) -> SurrogateActivityLog:
    """Log attachment deletion with filename (call AFTER successful deletion)."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.ATTACHMENT_DELETED,
        actor_user_id=actor_user_id,
        details={
            "attachment_id": str(attachment_id),
            "filename": filename,
        },
    )


def log_task_deleted(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    task_id: UUID,
    title: str,
) -> SurrogateActivityLog:
    """Log task deletion with title (call BEFORE deletion)."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.TASK_DELETED,
        actor_user_id=actor_user_id,
        details={
            "task_id": str(task_id),
            "title": title,
        },
    )


def log_medical_info_updated(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
) -> SurrogateActivityLog:
    """Log that medical info was updated (no PHI in details)."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.MEDICAL_INFO_UPDATED,
        actor_user_id=actor_user_id,
        details={},
    )


def log_insurance_info_updated(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
) -> SurrogateActivityLog:
    """Log that insurance info was updated (no PHI in details)."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.INSURANCE_INFO_UPDATED,
        actor_user_id=actor_user_id,
        details={},
    )


def log_pregnancy_dates_updated(
    db: Session,
    surrogate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
) -> SurrogateActivityLog:
    """Log that pregnancy dates were updated (no PHI in details)."""
    return log_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=organization_id,
        activity_type=SurrogateActivityType.PREGNANCY_DATES_UPDATED,
        actor_user_id=actor_user_id,
        details={},
    )
