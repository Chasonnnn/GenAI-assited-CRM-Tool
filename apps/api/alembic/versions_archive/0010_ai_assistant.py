"""AI Assistant tables - Week 11

Revision ID: 0010_ai_assistant
Revises: 0009_backfill_integration_key
Create Date: 2025-12-16

Tables:
- ai_settings: Org-level AI configuration (BYOK keys, provider)
- ai_conversations: Per-user conversation threads per entity
- ai_messages: Individual messages with proposed actions
- ai_action_approvals: Track approval status per action
- ai_entity_summaries: Cached context to avoid token waste
- ai_usage_log: Token tracking for cost monitoring
- user_integrations: Per-user OAuth tokens (Gmail, Zoom)

Also adds last_contacted_at and last_contact_method to cases table.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = "0010_ai_assistant"
down_revision = "0009_backfill_integration_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Org-level AI configuration
    op.create_table(
        "ai_settings",
        sa.Column(
            "id", UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("organization_id", UUID(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("provider", sa.String(20), nullable=False, server_default="openai"),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("model", sa.String(50), nullable=True, server_default="gpt-4o-mini"),
        sa.Column(
            "context_notes_limit", sa.Integer(), nullable=True, server_default="5"
        ),
        sa.Column(
            "conversation_history_limit",
            sa.Integer(),
            nullable=True,
            server_default="10",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("organization_id"),
    )

    # AI conversation threads
    op.create_table(
        "ai_conversations",
        sa.Column(
            "id", UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("organization_id", UUID(), nullable=False),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_ai_conversations_entity",
        "ai_conversations",
        ["organization_id", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_ai_conversations_user",
        "ai_conversations",
        ["user_id", "entity_type", "entity_id"],
    )

    # Individual messages
    op.create_table(
        "ai_messages",
        sa.Column(
            "id", UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("conversation_id", UUID(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # user, assistant, system
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("proposed_actions", JSONB(), nullable=True),  # Array of action specs
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_ai_messages_conversation", "ai_messages", ["conversation_id", "created_at"]
    )

    # Action approval tracking
    op.create_table(
        "ai_action_approvals",
        sa.Column(
            "id", UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("message_id", UUID(), nullable=False),
        sa.Column("action_index", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("action_payload", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["message_id"], ["ai_messages.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_ai_action_approvals_message", "ai_action_approvals", ["message_id"]
    )
    op.create_index("ix_ai_action_approvals_status", "ai_action_approvals", ["status"])

    # Cached entity summaries
    op.create_table(
        "ai_entity_summaries",
        sa.Column(
            "id", UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("organization_id", UUID(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("notes_plain_text", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "entity_type", "entity_id"),
    )

    # Token usage tracking
    op.create_table(
        "ai_usage_log",
        sa.Column(
            "id", UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("organization_id", UUID(), nullable=False),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("conversation_id", UUID(), nullable=True),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversations.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_ai_usage_log_org_date", "ai_usage_log", ["organization_id", "created_at"]
    )

    # Per-user integrations (Gmail, Zoom, etc.)
    op.create_table(
        "user_integrations",
        sa.Column(
            "id", UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column(
            "integration_type", sa.String(30), nullable=False
        ),  # gmail, zoom, google_calendar
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("account_email", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "integration_type"),
    )

    # Add last_contacted fields to cases
    op.add_column(
        "cases",
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cases", sa.Column("last_contact_method", sa.String(20), nullable=True)
    )


def downgrade() -> None:
    # Remove case columns
    op.drop_column("cases", "last_contact_method")
    op.drop_column("cases", "last_contacted_at")

    # Drop tables in reverse order
    op.drop_table("user_integrations")
    op.drop_table("ai_usage_log")
    op.drop_table("ai_entity_summaries")
    op.drop_table("ai_action_approvals")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    op.drop_table("ai_settings")
