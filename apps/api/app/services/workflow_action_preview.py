"""Workflow action preview service.

Builds human-readable, PII-sanitized previews of workflow actions
for display in approval tasks.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import WorkflowActionType
from app.db.models import Case, User, Queue, PipelineStage


def build_action_preview(
    db: Session,
    action: dict,
    entity: Any,
) -> str:
    """
    Build a human-readable preview of a workflow action.

    This preview is shown in the approval task and should:
    - Be clear about what will happen
    - NOT contain PII (emails, phone numbers, etc.)
    - Be concise (under 200 characters ideally)

    Args:
        db: Database session
        action: The action configuration dict
        entity: The entity the action will operate on

    Returns:
        A sanitized, human-readable preview string
    """
    action_type = action.get("action_type")

    if action_type == WorkflowActionType.SEND_EMAIL.value:
        return _preview_send_email(db, action, entity)

    if action_type == WorkflowActionType.CREATE_TASK.value:
        return _preview_create_task(db, action, entity)

    if action_type == WorkflowActionType.ASSIGN_CASE.value:
        return _preview_assign_case(db, action, entity)

    if action_type == WorkflowActionType.SEND_NOTIFICATION.value:
        return _preview_send_notification(db, action, entity)

    if action_type == WorkflowActionType.UPDATE_FIELD.value:
        return _preview_update_field(db, action, entity)

    if action_type == WorkflowActionType.ADD_NOTE.value:
        return _preview_add_note(db, action, entity)

    return f"Execute action: {action_type}"


def render_action_payload(action: dict, entity: Any) -> dict:
    """
    Render the action payload snapshot for execution.

    This captures all values needed to execute the action later,
    including resolved IDs and computed values. This is stored
    internally and NEVER exposed via API.

    Args:
        action: The action configuration dict
        entity: The entity the action will operate on

    Returns:
        A dict containing all data needed to execute the action
    """
    action_type = action.get("action_type")
    payload = {
        "action_type": action_type,
        **action,  # Include all original config
    }

    # Add entity context for execution
    if hasattr(entity, "id"):
        payload["entity_id"] = str(entity.id)
    if hasattr(entity, "organization_id"):
        payload["organization_id"] = str(entity.organization_id)

    return payload


# =============================================================================
# Preview Builders (one per action type)
# =============================================================================


def _preview_send_email(db: Session, action: dict, entity: Any) -> str:
    """Preview for send_email action."""
    template_id = action.get("template_id")

    # Get template name if possible
    template_name = "email template"
    if template_id:
        from app.db.models import EmailTemplate

        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == UUID(str(template_id))
        ).first()
        if template:
            template_name = template.name

    case_ref = _get_case_ref(entity)
    return f"Send '{template_name}' to {case_ref}"


def _preview_create_task(db: Session, action: dict, entity: Any) -> str:
    """Preview for create_task action."""
    title = action.get("title", "Follow up")
    due_days = action.get("due_days", 1)
    assignee = action.get("assignee", "owner")

    assignee_desc = _describe_assignee(db, assignee, entity)
    return f"Create task '{title}' due in {due_days} day(s), assigned to {assignee_desc}"


def _preview_assign_case(db: Session, action: dict, entity: Any) -> str:
    """Preview for assign_case action."""
    owner_type = action.get("owner_type")
    owner_id = action.get("owner_id")

    assignee_name = _resolve_owner_name(db, owner_type, owner_id)
    case_ref = _get_case_ref(entity)
    return f"Assign {case_ref} to {assignee_name}"


def _preview_send_notification(db: Session, action: dict, entity: Any) -> str:
    """Preview for send_notification action."""
    title = action.get("title", "Notification")
    recipients = action.get("recipients", "owner")

    recipients_desc = _describe_recipients(recipients)
    return f"Send notification '{title}' to {recipients_desc}"


def _preview_update_field(db: Session, action: dict, entity: Any) -> str:
    """Preview for update_field action."""
    field = action.get("field")
    value = action.get("value")

    # Special handling for stage_id to show stage name
    if field == "stage_id" and value:
        stage = db.query(PipelineStage).filter(
            PipelineStage.id == UUID(str(value))
        ).first()
        if stage:
            value = stage.label

    case_ref = _get_case_ref(entity)
    return f"Update {field} to '{value}' on {case_ref}"


def _preview_add_note(db: Session, action: dict, entity: Any) -> str:
    """Preview for add_note action."""
    case_ref = _get_case_ref(entity)
    return f"Add note to {case_ref}"


# =============================================================================
# Helper Functions
# =============================================================================


def _get_case_ref(entity: Any) -> str:
    """Get a reference to the case without PII."""
    if hasattr(entity, "case_number") and entity.case_number:
        return f"Case #{entity.case_number}"
    if hasattr(entity, "id"):
        return f"Case {str(entity.id)[:8]}..."
    return "Case"


def _resolve_owner_name(db: Session, owner_type: str, owner_id: str | UUID) -> str:
    """Resolve owner type/id to a display name."""
    if not owner_id:
        return "Unknown"

    owner_uuid = UUID(str(owner_id)) if isinstance(owner_id, str) else owner_id

    if owner_type == "user":
        user = db.query(User).filter(User.id == owner_uuid).first()
        if user:
            return user.display_name or user.email.split("@")[0]
        return "User"

    if owner_type == "queue":
        queue = db.query(Queue).filter(Queue.id == owner_uuid).first()
        if queue:
            return f"Queue: {queue.name}"
        return "Queue"

    return f"{owner_type}:{str(owner_id)[:8]}..."


def _describe_assignee(db: Session, assignee: str, entity: Any) -> str:
    """Describe the assignee for task creation."""
    if assignee == "owner":
        if hasattr(entity, "owner_type") and hasattr(entity, "owner_id"):
            return _resolve_owner_name(db, entity.owner_type, entity.owner_id)
        return "case owner"

    if assignee == "creator":
        return "case creator"

    # Specific user ID
    if assignee:
        return _resolve_owner_name(db, "user", assignee)

    return "unknown"


def _describe_recipients(recipients: str | list) -> str:
    """Describe notification recipients."""
    if recipients == "owner":
        return "case owner"
    if recipients == "creator":
        return "case creator"
    if recipients == "all_admins":
        return "all admins"
    if isinstance(recipients, list):
        return f"{len(recipients)} user(s)"
    return str(recipients)
