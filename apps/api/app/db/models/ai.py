"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization, User


class AISettings(Base):
    """
    Org-level AI configuration.

    Stores BYOK API keys (encrypted) and model preferences.
    Only one settings record per organization.
    """

    __tablename__ = "ai_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    provider: Mapped[str] = mapped_column(
        String(20), default="openai", server_default=text("'openai'")
    )
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(
        String(50), default="gpt-4o-mini", server_default=text("'gpt-4o-mini'")
    )
    # Vertex AI (WIF) configuration
    vertex_project_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vertex_location: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vertex_audience: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vertex_service_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    context_notes_limit: Mapped[int | None] = mapped_column(
        Integer, default=5, server_default=text("5")
    )
    conversation_history_limit: Mapped[int | None] = mapped_column(
        Integer, default=10, server_default=text("10")
    )
    # Privacy settings
    consent_accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    consent_accepted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    anonymize_pii: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    # Version control
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()


class AIConversation(Base):
    """
    AI conversation thread.

    Each user has their own conversation per entity (case).
    Developers can view all conversations for audit purposes.
    """

    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'case'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()
    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation", order_by="AIMessage.created_at"
    )

    __table_args__ = (
        Index("ix_ai_conversations_entity", "organization_id", "entity_type", "entity_id"),
        Index("ix_ai_conversations_user", "user_id", "entity_type", "entity_id"),
        UniqueConstraint(
            "organization_id",
            "user_id",
            "entity_type",
            "entity_id",
            name="uq_ai_conversations_user_entity",
        ),
    )


class AIMessage(Base):
    """
    Individual message in an AI conversation.

    Role can be 'user', 'assistant', or 'system'.
    proposed_actions is a JSONB array of action specs when AI proposes actions.
    """

    __tablename__ = "ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_actions: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    conversation: Mapped["AIConversation"] = relationship(back_populates="messages")
    action_approvals: Mapped[list["AIActionApproval"]] = relationship(back_populates="message")

    __table_args__ = (Index("ix_ai_messages_conversation", "conversation_id", "created_at"),)


class AIActionApproval(Base):
    """
    Track approval status for each proposed action.

    Separates approval state from message content for cleaner queries.
    One record per action in the proposed_actions array.
    """

    __tablename__ = "ai_action_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default=text("'pending'")
    )
    executed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    message: Mapped["AIMessage"] = relationship(back_populates="action_approvals")

    __table_args__ = (
        Index("ix_ai_action_approvals_message", "message_id"),
        Index("ix_ai_action_approvals_status", "status"),
    )


class AIBulkTaskRequest(Base):
    """
    Idempotency store for AI bulk task creation.

    Ensures repeated request_id submissions return the same response.
    """

    __tablename__ = "ai_bulk_task_requests"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "request_id",
            name="uq_ai_bulk_task_requests",
        ),
        Index("ix_ai_bulk_task_requests_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class AIEntitySummary(Base):
    """
    Cached entity context for AI.

    Updated when case notes, status, or tasks change.
    Avoids regenerating context on every chat request.
    """

    __tablename__ = "ai_entity_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    notes_plain_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (UniqueConstraint("organization_id", "entity_type", "entity_id"),)


class AIUsageLog(Base):
    """
    Token usage tracking for cost monitoring.

    Records each AI API call with token counts and estimated cost.
    """

    __tablename__ = "ai_usage_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (Index("ix_ai_usage_log_org_date", "organization_id", "created_at"),)
