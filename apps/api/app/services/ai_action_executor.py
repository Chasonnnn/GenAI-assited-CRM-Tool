"""AI Action executor framework.

Handles execution of AI-proposed actions after user approval.
Each action type has its own executor that performs the actual work.
"""
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    Case, EntityNote, Task, AIActionApproval
)
from app.db.enums import TaskType

logger = logging.getLogger(__name__)


# ============================================================================
# Base Executor
# ============================================================================

class ActionExecutor(ABC):
    """Base class for action executors."""
    
    action_type: str = ""
    
    @abstractmethod
    def validate(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> tuple[bool, str | None]:
        """Validate the action payload.
        
        Returns:
            (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def execute(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID, entity_id: uuid.UUID) -> dict[str, Any]:
        """Execute the action.
        
        Returns:
            Result dict with created/updated entity info
        """
        pass


# ============================================================================
# Action Executors
# ============================================================================

class AddNoteExecutor(ActionExecutor):
    """Add a note to a case."""
    
    action_type = "add_note"
    
    def validate(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> tuple[bool, str | None]:
        content = payload.get("content") or payload.get("body") or payload.get("text")
        if not content or not content.strip():
            return False, "Note content is required"
        return True, None
    
    def execute(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID, entity_id: uuid.UUID) -> dict[str, Any]:
        content = payload.get("content") or payload.get("body") or payload.get("text")
        
        # Create note (EntityNote uses entity_type, entity_id, content)
        note = EntityNote(
            entity_type="case",
            entity_id=entity_id,
            organization_id=org_id,
            author_id=user_id,
            content=content,
        )
        db.add(note)
        
        # Update case last_contacted
        case = db.query(Case).filter(Case.id == entity_id).first()
        if case:
            case.last_contacted_at = datetime.utcnow()
            case.last_contact_method = "note"
        
        db.flush()
        
        return {
            "action": "add_note",
            "note_id": str(note.id),
            "success": True,
        }


class CreateTaskExecutor(ActionExecutor):
    """Create a follow-up task."""
    
    action_type = "create_task"
    
    def validate(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> tuple[bool, str | None]:
        title = payload.get("title")
        if not title or not title.strip():
            return False, "Task title is required"
        return True, None
    
    def execute(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID, entity_id: uuid.UUID) -> dict[str, Any]:
        title = payload.get("title")
        description = payload.get("description", "")
        due_date_str = payload.get("due_date")
        
        # Parse due date if provided
        due_date_val = None
        if due_date_str:
            try:
                due_date_val = date.fromisoformat(due_date_str)
            except ValueError:
                logger.warning(f"Invalid due_date format: {due_date_str}")
        
        # Create task (uses case_id, not entity_type/entity_id)
        task = Task(
            organization_id=org_id,
            case_id=entity_id,
            title=title,
            description=description,
            due_date=due_date_val,
            is_completed=False,
            task_type=TaskType.FOLLOW_UP.value,
            created_by_user_id=user_id,
        )
        db.add(task)
        db.flush()
        
        return {
            "action": "create_task",
            "task_id": str(task.id),
            "title": title,
            "success": True,
        }


class UpdateStatusExecutor(ActionExecutor):
    """Update case status."""
    
    action_type = "update_status"
    
    def validate(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> tuple[bool, str | None]:
        stage_id = payload.get("stage_id")
        if not stage_id:
            return False, "stage_id is required"
        
        from app.services import pipeline_service
        stage = pipeline_service.get_stage_by_id(db, stage_id)
        if not stage or not stage.is_active:
            return False, "Invalid or inactive stage"
        
        return True, None
    
    def execute(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID, entity_id: uuid.UUID) -> dict[str, Any]:
        stage_id = payload.get("stage_id")
        
        case = db.query(Case).filter(Case.id == entity_id, Case.organization_id == org_id).first()
        if not case:
            return {"action": "update_status", "success": False, "error": "Case not found"}
        
        from app.services import pipeline_service
        stage = pipeline_service.get_stage_by_id(db, stage_id)
        current_stage = pipeline_service.get_stage_by_id(db, case.stage_id)
        case_pipeline_id = current_stage.pipeline_id if current_stage else None
        if not case_pipeline_id:
            case_pipeline_id = pipeline_service.get_or_create_default_pipeline(db, org_id).id
        if not stage or not stage.is_active or stage.pipeline_id != case_pipeline_id:
            return {"action": "update_status", "success": False, "error": "Invalid stage for case pipeline"}
        
        old_stage_id = case.stage_id
        old_label = case.status_label
        case.stage_id = stage.id
        case.status_label = stage.label
        
        # Add status history entry
        from app.db.models import CaseStatusHistory
        history = CaseStatusHistory(
            case_id=entity_id,
            organization_id=org_id,
            from_stage_id=old_stage_id,
            to_stage_id=stage.id,
            from_label_snapshot=old_label,
            to_label_snapshot=stage.label,
            changed_by_user_id=user_id,
        )
        db.add(history)
        
        return {
            "action": "update_status",
            "old_stage_id": str(old_stage_id) if old_stage_id else None,
            "new_stage_id": str(stage.id),
            "success": True,
        }


class SendEmailExecutor(ActionExecutor):
    """Draft/send email (requires Gmail integration)."""
    
    action_type = "send_email"
    
    def validate(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> tuple[bool, str | None]:
        to = payload.get("to")
        subject = payload.get("subject")
        body = payload.get("body")
        
        if not to:
            return False, "Recipient email is required"
        if not subject:
            return False, "Email subject is required"
        if not body:
            return False, "Email body is required"
        
        # Check if user has Gmail integration
        from app.db.models import UserIntegration
        integration = db.query(UserIntegration).filter(
            UserIntegration.user_id == user_id,
            UserIntegration.integration_type == "gmail"
        ).first()
        
        if not integration:
            return False, "Gmail not connected. Please connect your Gmail account in settings."
        
        return True, None
    
    def execute(self, payload: dict[str, Any], db: Session, user_id: uuid.UUID, org_id: uuid.UUID, entity_id: uuid.UUID) -> dict[str, Any]:
        """Execute email send via Gmail API."""
        import asyncio
        from app.services import gmail_service
        
        to = payload.get("to")
        subject = payload.get("subject")
        body = payload.get("body")
        
        # Try to send via Gmail API
        result = asyncio.run(gmail_service.send_email(
            db=db,
            user_id=str(user_id),
            to=to,
            subject=subject,
            body=body,
        ))
        
        # Always log email as note (whether sent or not)
        status_text = "✓ Sent" if result.get("success") else f"⚠ Failed: {result.get('error', 'Unknown error')}"
        email_content = f"""📧 **Email {status_text}** (via AI Assistant)

**To:** {to}
**Subject:** {subject}

---

{body}
"""
        
        note = EntityNote(
            entity_type="case",
            entity_id=entity_id,
            organization_id=org_id,
            author_id=user_id,
            content=email_content,
        )
        db.add(note)
        
        # Update case last_contacted
        case = db.query(Case).filter(Case.id == entity_id).first()
        if case:
            case.last_contacted_at = datetime.utcnow()
            case.last_contact_method = "email"
        
        db.flush()
        
        if result.get("success"):
            return {
                "action": "send_email",
                "to": to,
                "subject": subject,
                "note_id": str(note.id),
                "gmail_message_id": result.get("message_id"),
                "success": True,
            }
        else:
            return {
                "action": "send_email",
                "to": to,
                "subject": subject,
                "note_id": str(note.id),
                "success": False,
                "error": result.get("error", "Gmail send failed"),
            }


# ============================================================================
# Permission Mapping for Actions
# ============================================================================

# Maps action types to the permission required to execute them
ACTION_PERMISSIONS: dict[str, str] = {
    "add_note": "edit_case_notes",
    "create_task": "create_tasks",
    "update_status": "change_case_status",
    "send_email": "edit_cases",  # Sending email updates case contact info
}


# ============================================================================
# Executor Registry
# ============================================================================

EXECUTORS: dict[str, ActionExecutor] = {
    "add_note": AddNoteExecutor(),
    "create_task": CreateTaskExecutor(),
    "update_status": UpdateStatusExecutor(),
    "send_email": SendEmailExecutor(),
}


def get_executor(action_type: str) -> ActionExecutor | None:
    """Get executor for an action type."""
    return EXECUTORS.get(action_type)


def execute_action(
    db: Session,
    approval: AIActionApproval,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_permissions: set[str] | None = None,
) -> dict[str, Any]:
    """Execute an approved action with permission checks and activity logging.
    
    Args:
        db: Database session
        approval: The AIActionApproval record
        user_id: User executing the action
        org_id: Organization ID
        entity_id: The entity (case) ID
        user_permissions: Set of permissions the user has (for authorization)
    
    Returns:
        Result dict from executor
    """
    from app.db.models import CaseActivity
    
    # 1. Check approve_ai_actions permission
    if user_permissions is not None and "approve_ai_actions" not in user_permissions:
        error_msg = "You don't have permission to execute AI actions"
        approval.status = "failed"
        approval.error_message = error_msg
        approval.executed_at = datetime.utcnow()
        
        # Log denied action
        activity = CaseActivity(
            case_id=entity_id,
            organization_id=org_id,
            user_id=user_id,
            activity_type="ai_action_denied",
            details={
                "action_type": approval.action_type,
                "reason": "Missing approve_ai_actions permission",
                "approval_id": str(approval.id),
            },
        )
        db.add(activity)
        
        logger.warning(f"AI action denied: user {user_id} lacks approve_ai_actions permission")
        return {"success": False, "error": error_msg}
    
    # 2. Check action-specific permission
    required_permission = ACTION_PERMISSIONS.get(approval.action_type)
    if required_permission and user_permissions is not None:
        if required_permission not in user_permissions:
            error_msg = f"You don't have permission to {approval.action_type.replace('_', ' ')}"
            approval.status = "failed"
            approval.error_message = error_msg
            approval.executed_at = datetime.utcnow()
            
            # Log denied action
            activity = CaseActivity(
                case_id=entity_id,
                organization_id=org_id,
                user_id=user_id,
                activity_type="ai_action_denied",
                details={
                    "action_type": approval.action_type,
                    "reason": f"Missing {required_permission} permission",
                    "approval_id": str(approval.id),
                },
            )
            db.add(activity)
            
            logger.warning(f"AI action denied: user {user_id} lacks {required_permission} permission for {approval.action_type}")
            return {"success": False, "error": error_msg}
    
    # 3. Get executor
    executor = get_executor(approval.action_type)
    if not executor:
        approval.status = "failed"
        approval.error_message = f"Unknown action type: {approval.action_type}"
        approval.executed_at = datetime.utcnow()
        return {"success": False, "error": approval.error_message}
    
    # 4. Validate
    is_valid, error = executor.validate(approval.action_payload, db, user_id, org_id)
    if not is_valid:
        approval.status = "failed"
        approval.error_message = error
        approval.executed_at = datetime.utcnow()
        return {"success": False, "error": error}
    
    # 5. Execute
    try:
        result = executor.execute(approval.action_payload, db, user_id, org_id, entity_id)
        approval.status = "executed" if result.get("success") else "failed"
        approval.executed_at = datetime.utcnow()
        if not result.get("success"):
            approval.error_message = result.get("error")
        
        # 6. Log successful or failed execution to case activity
        activity = CaseActivity(
            case_id=entity_id,
            organization_id=org_id,
            user_id=user_id,
            activity_type="ai_action_executed" if result.get("success") else "ai_action_failed",
            details={
                "action_type": approval.action_type,
                "action_data": approval.action_payload,
                "approval_id": str(approval.id),
                "approved_by": str(user_id),
                "execution_result": "success" if result.get("success") else "failed",
                "error_message": result.get("error") if not result.get("success") else None,
                "result": {k: v for k, v in result.items() if k not in ("success", "error")},
            },
        )
        db.add(activity)
        
        return result
    except Exception as e:
        logger.exception(f"Action execution failed: {e}")
        approval.status = "failed"
        approval.error_message = str(e)
        approval.executed_at = datetime.utcnow()
        
        # Log failed execution
        activity = CaseActivity(
            case_id=entity_id,
            organization_id=org_id,
            user_id=user_id,
            activity_type="ai_action_failed",
            details={
                "action_type": approval.action_type,
                "action_data": approval.action_payload,
                "approval_id": str(approval.id),
                "error_message": str(e),
            },
        )
        db.add(activity)
        
        return {"success": False, "error": str(e)}

