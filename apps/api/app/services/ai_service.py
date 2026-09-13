"""AI router helper queries for conversations and approvals."""

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import AIActionApproval, AIConversation, AIMessage


def list_conversations_for_entity(
    db: Session,
    org_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> list[AIConversation]:
    """List conversations for an entity (org-scoped)."""
    return (
        db.query(AIConversation)
        .filter(
            AIConversation.organization_id == org_id,
            AIConversation.entity_type == entity_type,
            AIConversation.entity_id == entity_id,
        )
        .order_by(AIConversation.updated_at.desc())
        .all()
    )


def get_action_approval(db: Session, approval_id: UUID) -> AIActionApproval | None:
    """Get AI action approval by ID."""
    return db.query(AIActionApproval).filter(AIActionApproval.id == approval_id).first()


def get_message(db: Session, message_id: UUID) -> AIMessage | None:
    """Get AI message by ID."""
    return db.query(AIMessage).filter(AIMessage.id == message_id).first()


def get_conversation(db: Session, conversation_id: UUID) -> AIConversation | None:
    """Get AI conversation by ID."""
    return db.query(AIConversation).filter(AIConversation.id == conversation_id).first()


def get_approval_with_conversation(
    db: Session,
    approval_id: UUID,
) -> tuple[AIActionApproval | None, AIMessage | None, AIConversation | None]:
    """Load approval and related message/conversation."""
    approval = get_action_approval(db, approval_id)
    if not approval:
        return None, None, None

    message = get_message(db, approval.message_id)
    if not message:
        return approval, None, None

    conversation = get_conversation(db, message.conversation_id)
    return approval, message, conversation


def list_pending_actions(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
) -> list[AIActionApproval]:
    """List pending AI approvals for a user."""
    query = (
        db.query(AIActionApproval)
        .join(AIMessage, AIActionApproval.message_id == AIMessage.id)
        .join(AIConversation, AIMessage.conversation_id == AIConversation.id)
        .filter(
            AIConversation.user_id == user_id,
            AIConversation.organization_id == org_id,
            AIActionApproval.status == "pending",
        )
    )

    from app.db.enums import Role
    from app.db.models import Surrogate, Task
    from app.services import permission_policy_service, permission_service, record_scope_service
    from app.services.workflow_execution_authority import active_session

    if permission_policy_service.is_enabled(db, org_id):
        actor = active_session(db, org_id, user_id)
        if actor is None:
            return []
        permissions = permission_service.get_effective_permissions(
            db, org_id, user_id, actor.role.value
        )
        if "use_ai_assistant" not in permissions:
            return []
        visible = [
            and_(AIConversation.entity_type == "global", AIConversation.entity_id == user_id)
        ]
        if "view_surrogates" in permissions:
            visible.append(
                and_(
                    AIConversation.entity_type.in_(("surrogate", "case")),
                    AIConversation.entity_id.in_(
                        select(Surrogate.id).where(
                            record_scope_service.build_visibility_filter(db, actor, "surrogate")
                        )
                    ),
                )
            )
        if "view_tasks" in permissions:
            task_filter = record_scope_service.build_linked_visibility_filter(db, actor, Task)
            if actor.role not in {Role.ADMIN, Role.DEVELOPER, Role.CASE_MANAGER}:
                task_filter = and_(
                    task_filter,
                    or_(
                        Task.created_by_user_id == user_id,
                        and_(Task.owner_type == "user", Task.owner_id == user_id),
                    ),
                )
            visible.append(
                and_(
                    AIConversation.entity_type == "task",
                    AIConversation.entity_id.in_(
                        select(Task.id).where(Task.organization_id == org_id, task_filter)
                    ),
                )
            )
        query = query.filter(or_(*visible))

    if entity_type:
        query = query.filter(AIConversation.entity_type == entity_type)
    if entity_id:
        query = query.filter(AIConversation.entity_id == entity_id)

    return query.order_by(AIActionApproval.created_at.desc()).all()
