"""fix ai conversations and rollup constraints

Revision ID: a4f2c9b7e1d3
Revises: e64c5c89667e
Create Date: 2025-12-26 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4f2c9b7e1d3'
down_revision: Union[str, Sequence[str], None] = 'e64c5c89667e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'attachments',
        'uploaded_by_user_id',
        existing_type=sa.UUID(),
        nullable=True,
    )

    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY organization_id, integration_type
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC, id DESC
                ) AS rn
            FROM integration_health
            WHERE integration_key IS NULL
        )
        DELETE FROM integration_health
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
    """)

    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY organization_id, integration_type, period_start
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS rn,
                SUM(error_count) OVER (
                    PARTITION BY organization_id, integration_type, period_start
                ) AS total_error_count,
                FIRST_VALUE(last_error) OVER (
                    PARTITION BY organization_id, integration_type, period_start
                    ORDER BY created_at DESC NULLS LAST, id DESC
                ) AS latest_error
            FROM integration_error_rollup
            WHERE integration_key IS NULL
        ),
        updated AS (
            UPDATE integration_error_rollup ier
            SET
                error_count = r.total_error_count,
                last_error = r.latest_error
            FROM ranked r
            WHERE ier.id = r.id AND r.rn = 1
            RETURNING ier.id
        )
        DELETE FROM integration_error_rollup
        WHERE integration_key IS NULL
          AND id NOT IN (SELECT id FROM ranked WHERE rn = 1);
    """)

    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY period_start, route, method
                    ORDER BY id
                ) AS rn,
                SUM(status_2xx) OVER (
                    PARTITION BY period_start, route, method
                ) AS total_2xx,
                SUM(status_4xx) OVER (
                    PARTITION BY period_start, route, method
                ) AS total_4xx,
                SUM(status_5xx) OVER (
                    PARTITION BY period_start, route, method
                ) AS total_5xx,
                SUM(total_duration_ms) OVER (
                    PARTITION BY period_start, route, method
                ) AS total_duration,
                SUM(request_count) OVER (
                    PARTITION BY period_start, route, method
                ) AS total_requests,
                MAX(period_type) OVER (
                    PARTITION BY period_start, route, method
                ) AS max_period_type
            FROM request_metrics_rollup
            WHERE organization_id IS NULL
        ),
        updated AS (
            UPDATE request_metrics_rollup r
            SET
                status_2xx = ranked.total_2xx,
                status_4xx = ranked.total_4xx,
                status_5xx = ranked.total_5xx,
                total_duration_ms = ranked.total_duration,
                request_count = ranked.total_requests,
                period_type = ranked.max_period_type
            FROM ranked
            WHERE r.id = ranked.id AND ranked.rn = 1
            RETURNING r.id
        )
        DELETE FROM request_metrics_rollup
        WHERE organization_id IS NULL
          AND id NOT IN (SELECT id FROM ranked WHERE rn = 1);
    """)

    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                organization_id,
                user_id,
                entity_type,
                entity_id,
                FIRST_VALUE(id) OVER (
                    PARTITION BY organization_id, user_id, entity_type, entity_id
                    ORDER BY created_at ASC, id ASC
                ) AS keep_id,
                MAX(updated_at) OVER (
                    PARTITION BY organization_id, user_id, entity_type, entity_id
                ) AS max_updated_at
            FROM ai_conversations
        )
        UPDATE ai_conversations c
        SET updated_at = r.max_updated_at
        FROM ranked r
        WHERE c.id = r.keep_id;
    """)

    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                FIRST_VALUE(id) OVER (
                    PARTITION BY organization_id, user_id, entity_type, entity_id
                    ORDER BY created_at ASC, id ASC
                ) AS keep_id
            FROM ai_conversations
        )
        UPDATE ai_messages m
        SET conversation_id = r.keep_id
        FROM ranked r
        WHERE m.conversation_id = r.id
          AND r.id <> r.keep_id;
    """)

    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                FIRST_VALUE(id) OVER (
                    PARTITION BY organization_id, user_id, entity_type, entity_id
                    ORDER BY created_at ASC, id ASC
                ) AS keep_id
            FROM ai_conversations
        )
        UPDATE ai_usage_log u
        SET conversation_id = r.keep_id
        FROM ranked r
        WHERE u.conversation_id = r.id
          AND r.id <> r.keep_id;
    """)

    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                FIRST_VALUE(id) OVER (
                    PARTITION BY organization_id, user_id, entity_type, entity_id
                    ORDER BY created_at ASC, id ASC
                ) AS keep_id
            FROM ai_conversations
        )
        DELETE FROM ai_conversations
        WHERE id IN (SELECT id FROM ranked WHERE id <> keep_id);
    """)

    op.create_unique_constraint(
        'uq_ai_conversations_user_entity',
        'ai_conversations',
        ['organization_id', 'user_id', 'entity_type', 'entity_id'],
    )
    op.create_index(
        'uq_integration_health_org_type_null_key',
        'integration_health',
        ['organization_id', 'integration_type'],
        unique=True,
        postgresql_where=sa.text('integration_key IS NULL'),
    )
    op.create_index(
        'uq_integration_error_rollup_null_key',
        'integration_error_rollup',
        ['organization_id', 'integration_type', 'period_start'],
        unique=True,
        postgresql_where=sa.text('integration_key IS NULL'),
    )
    op.create_index(
        'uq_request_metrics_rollup_null_org',
        'request_metrics_rollup',
        ['period_start', 'route', 'method'],
        unique=True,
        postgresql_where=sa.text('organization_id IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_request_metrics_rollup_null_org', table_name='request_metrics_rollup')
    op.drop_index('uq_integration_error_rollup_null_key', table_name='integration_error_rollup')
    op.drop_index('uq_integration_health_org_type_null_key', table_name='integration_health')
    op.drop_constraint('uq_ai_conversations_user_entity', 'ai_conversations', type_='unique')

    op.alter_column(
        'attachments',
        'uploaded_by_user_id',
        existing_type=sa.UUID(),
        nullable=False,
    )
