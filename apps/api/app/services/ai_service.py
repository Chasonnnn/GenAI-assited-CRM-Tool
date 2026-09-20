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


def get_approval_with_conversation(
    db: Session,
    approval_id: UUID,
    org_id: UUID,
) -> tuple[AIActionApproval | None, AIMessage | None, AIConversation | None]:
    """Lock and refresh a tenant's approval before an approve/reject decision."""
    row = (
        db.query(AIActionApproval, AIMessage, AIConversation)
        .join(AIMessage, AIActionApproval.message_id == AIMessage.id)
        .join(AIConversation, AIMessage.conversation_id == AIConversation.id)
        .filter(
            AIActionApproval.id == approval_id,
            AIConversation.organization_id == org_id,
        )
        .populate_existing()
        .with_for_update(of=AIActionApproval)
        .first()
    )
    if row is None:
        return None, None, None
    return row[0], row[1], row[2]


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

    if entity_type:
        query = query.filter(AIConversation.entity_type == entity_type)
    if entity_id:
        query = query.filter(AIConversation.entity_id == entity_id)

    return query.order_by(AIActionApproval.created_at.desc()).all()
