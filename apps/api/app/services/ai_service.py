"""AI router helper queries for conversations and approvals."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import AIActionApproval, AIConversation, AIMessage


def list_conversations_for_entity(
    db: Session,
    org_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> list[AIConversation]:
    """List conversations for an entity (org-scoped)."""
    return db.query(AIConversation).filter(
        AIConversation.organization_id == org_id,
        AIConversation.entity_type == entity_type,
        AIConversation.entity_id == entity_id,
    ).order_by(AIConversation.updated_at.desc()).all()


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
    query = db.query(AIActionApproval).join(
        AIMessage, AIActionApproval.message_id == AIMessage.id
    ).join(
        AIConversation, AIMessage.conversation_id == AIConversation.id
    ).filter(
        AIConversation.user_id == user_id,
        AIConversation.organization_id == org_id,
        AIActionApproval.status == "pending",
    )

    if entity_type:
        query = query.filter(AIConversation.entity_type == entity_type)
    if entity_id:
        query = query.filter(AIConversation.entity_id == entity_id)

    return query.order_by(AIActionApproval.created_at.desc()).all()
