"""Baseline consolidated migration.

Revision ID: 20260111_2137
Revises:
Create Date: 2026-01-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db import types

# System user constants (used for workflow-created tasks)
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"
SYSTEM_USER_EMAIL = "system@internal"
SYSTEM_USER_DISPLAY_NAME = "System"


# revision identifiers, used by Alembic.
revision: str = "20260111_2137"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table('ai_entity_summaries',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('summary_text', sa.Text(), nullable=False),
    sa.Column('notes_plain_text', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'entity_type', 'entity_id')
    )
    op.create_table('organizations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('timezone', sa.String(length=50), server_default=sa.text("'America/Los_Angeles'"), nullable=False),
    sa.Column('ai_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('current_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('signature_template', sa.String(length=50), nullable=True),
    sa.Column('signature_logo_url', sa.String(length=500), nullable=True),
    sa.Column('signature_primary_color', sa.String(length=7), nullable=True),
    sa.Column('signature_company_name', sa.String(length=255), nullable=True),
    sa.Column('signature_address', sa.String(length=500), nullable=True),
    sa.Column('signature_phone', sa.String(length=50), nullable=True),
    sa.Column('signature_website', sa.String(length=255), nullable=True),
    sa.Column('signature_social_links', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True, comment='Array of {platform, url} objects for org social links'),
    sa.Column('signature_disclaimer', sa.Text(), nullable=True, comment='Optional compliance footer for email signatures'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('request_metrics_rollup',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('period_type', sa.String(length=10), server_default=sa.text("'minute'"), nullable=False),
    sa.Column('route', sa.String(length=100), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('status_2xx', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('status_4xx', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('status_5xx', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('total_duration_ms', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('request_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'period_start', 'route', 'method', name='uq_request_metrics_rollup')
    )
    op.create_table('users',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('avatar_url', sa.String(length=500), nullable=True),
    sa.Column('token_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('signature_linkedin', sa.String(length=255), nullable=True),
    sa.Column('signature_twitter', sa.String(length=255), nullable=True),
    sa.Column('signature_instagram', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('title', sa.String(length=100), nullable=True),
    sa.Column('signature_name', sa.String(length=255), nullable=True, comment='Override display_name in signature (NULL = use profile)'),
    sa.Column('signature_title', sa.String(length=100), nullable=True, comment='Override title in signature (NULL = use profile)'),
    sa.Column('signature_phone', sa.String(length=50), nullable=True, comment='Override phone in signature (NULL = use profile)'),
    sa.Column('signature_photo_url', sa.String(length=500), nullable=True, comment='Override avatar in signature (NULL = use profile)'),
    sa.Column('mfa_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('totp_secret', sa.String(length=255), nullable=True),
    sa.Column('totp_enabled_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('duo_user_id', sa.String(length=255), nullable=True),
    sa.Column('duo_enrolled_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('mfa_recovery_codes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('mfa_required_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.execute(
        f"""
        INSERT INTO users (id, email, display_name, is_active, created_at, updated_at)
        VALUES (
            '{SYSTEM_USER_ID}'::uuid,
            '{SYSTEM_USER_EMAIL}',
            '{SYSTEM_USER_DISPLAY_NAME}',
            false,
            now(),
            now()
        )
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.create_table('ai_conversations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'user_id', 'entity_type', 'entity_id', name='uq_ai_conversations_user_entity')
    )
    op.create_table('ai_settings',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('provider', sa.String(length=20), server_default=sa.text("'openai'"), nullable=False),
    sa.Column('api_key_encrypted', sa.Text(), nullable=True),
    sa.Column('model', sa.String(length=50), server_default=sa.text("'gpt-4o-mini'"), nullable=True),
    sa.Column('context_notes_limit', sa.Integer(), server_default=sa.text('5'), nullable=True),
    sa.Column('conversation_history_limit', sa.Integer(), server_default=sa.text('10'), nullable=True),
    sa.Column('consent_accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('consent_accepted_by', sa.UUID(), nullable=True),
    sa.Column('anonymize_pii', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('current_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id')
    )
    op.create_table('analytics_snapshots',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('snapshot_type', sa.String(length=50), nullable=False),
    sa.Column('snapshot_key', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('range_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('range_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'snapshot_key', name='uq_analytics_snapshot_key')
    )
    op.create_table('appointment_types',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('buffer_before_minutes', sa.Integer(), nullable=False),
    sa.Column('buffer_after_minutes', sa.Integer(), nullable=False),
    sa.Column('meeting_mode', sa.String(length=20), server_default=sa.text("'zoom'"), nullable=False),
    sa.Column('reminder_hours_before', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'slug', name='uq_appointment_type_slug')
    )
    op.create_table('auth_identities',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('provider_subject', sa.String(length=255), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'provider_subject', name='uq_auth_identity')
    )
    op.create_table('automation_workflows',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=50), nullable=False),
    sa.Column('schema_version', sa.Integer(), nullable=False),
    sa.Column('trigger_type', sa.String(length=50), nullable=False),
    sa.Column('trigger_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('condition_logic', sa.String(length=10), nullable=False),
    sa.Column('actions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('is_enabled', sa.Boolean(), nullable=False),
    sa.Column('run_count', sa.Integer(), nullable=False),
    sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('recurrence_mode', sa.String(length=20), server_default=sa.text("'one_time'"), nullable=False),
    sa.Column('recurrence_interval_hours', sa.Integer(), nullable=True),
    sa.Column('recurrence_stop_on_status', sa.String(length=50), nullable=True),
    sa.Column('rate_limit_per_hour', sa.Integer(), nullable=True),
    sa.Column('rate_limit_per_entity_per_day', sa.Integer(), nullable=True),
    sa.Column('is_system_workflow', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('system_key', sa.String(length=100), nullable=True),
    sa.Column('requires_review', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reviewed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'name', name='uq_workflow_name')
    )
    op.create_table('workflow_executions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('workflow_id', sa.UUID(), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('depth', sa.Integer(), nullable=False),
    sa.Column('event_source', sa.String(length=20), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('trigger_event', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('dedupe_key', sa.String(length=200), nullable=True),
    sa.Column('matched_conditions', sa.Boolean(), nullable=False),
    sa.Column('actions_executed', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('paused_at_action_index', sa.Integer(), nullable=True),
    sa.Column('paused_task_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workflow_id'], ['automation_workflows.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('availability_overrides',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('override_date', sa.Date(), nullable=False),
    sa.Column('is_unavailable', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=True),
    sa.Column('end_time', sa.Time(), nullable=True),
    sa.Column('reason', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'override_date', name='uq_availability_override_date')
    )
    op.create_table('availability_rules',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('day_of_week', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('timezone', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('day_of_week >= 0 AND day_of_week <= 6', name='ck_valid_day_of_week'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('booking_links',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('public_slug', sa.String(length=32), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('public_slug', name='uq_booking_link_slug'),
    sa.UniqueConstraint('user_id', name='uq_booking_link_user')
    )
    op.create_table('case_imports',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('total_rows', sa.Integer(), nullable=False),
    sa.Column('imported_count', sa.Integer(), nullable=False),
    sa.Column('skipped_count', sa.Integer(), nullable=False),
    sa.Column('error_count', sa.Integer(), nullable=False),
    sa.Column('errors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('data_retention_policies',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('retention_days', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'entity_type', name='uq_retention_policy_org_entity')
    )
    op.create_table('email_suppressions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('reason', sa.String(length=30), nullable=False),
    sa.Column('source_type', sa.String(length=50), nullable=True),
    sa.Column('source_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'email', name='uq_email_suppression')
    )
    op.create_table('email_templates',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('is_system_template', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('system_key', sa.String(length=100), nullable=True),
    sa.Column('category', sa.String(length=50), nullable=True),
    sa.Column('current_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'name', name='uq_email_template_name')
    )
    op.create_table('entity_notes',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('author_id', sa.UUID(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('entity_versions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('schema_version', sa.Integer(), nullable=False),
    sa.Column('payload_encrypted', sa.LargeBinary(), nullable=False),
    sa.Column('checksum', sa.String(length=64), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('comment', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'entity_type', 'entity_id', 'version')
    )
    op.create_table('export_jobs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('export_type', sa.String(length=30), nullable=False),
    sa.Column('format', sa.String(length=10), nullable=False),
    sa.Column('redact_mode', sa.String(length=10), nullable=False),
    sa.Column('date_range_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('date_range_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('record_count', sa.Integer(), nullable=True),
    sa.Column('file_path', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('acknowledgment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('form_logos',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('file_size', sa.Integer(), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('forms',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'draft'"), nullable=False),
    sa.Column('schema_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('published_schema_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('max_file_size_bytes', sa.Integer(), server_default=sa.text('10485760'), nullable=False),
    sa.Column('max_file_count', sa.Integer(), server_default=sa.text('10'), nullable=False),
    sa.Column('allowed_mime_types', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('integration_error_rollup',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('integration_type', sa.String(length=50), nullable=False),
    sa.Column('integration_key', sa.String(length=255), nullable=True),
    sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('error_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'integration_type', 'integration_key', 'period_start', name='uq_integration_error_rollup')
    )
    op.create_table('integration_health',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('integration_type', sa.String(length=50), nullable=False),
    sa.Column('integration_key', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'healthy'"), nullable=False),
    sa.Column('config_status', sa.String(length=30), server_default=sa.text("'configured'"), nullable=False),
    sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'integration_type', 'integration_key', name='uq_integration_health_org_type_key')
    )
    op.create_table('intended_parents',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('email', types.EncryptedString(), nullable=False),
    sa.Column('email_hash', sa.String(length=64), nullable=False),
    sa.Column('phone', types.EncryptedString(), nullable=True),
    sa.Column('phone_hash', sa.String(length=64), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('budget', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('notes_internal', types.EncryptedText(), nullable=True),
    sa.Column('status', sa.String(length=50), server_default=sa.text("'new'"), nullable=False),
    sa.Column('owner_type', sa.String(length=10), nullable=True),
    sa.Column('owner_id', sa.UUID(), nullable=True),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_activity', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('jobs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('job_type', sa.String(length=50), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('run_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('max_attempts', sa.Integer(), server_default=sa.text('3'), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('idempotency_key', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('legal_holds',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=True),
    sa.Column('entity_id', sa.UUID(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('released_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['released_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('memberships',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('meta_leads',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('meta_lead_id', sa.String(length=100), nullable=False),
    sa.Column('meta_form_id', sa.String(length=100), nullable=True),
    sa.Column('meta_page_id', sa.String(length=100), nullable=True),
    sa.Column('field_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('is_converted', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('converted_case_id', sa.UUID(), nullable=True),
    sa.Column('conversion_error', sa.Text(), nullable=True),
    sa.Column('meta_created_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('converted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'received'"), nullable=False),
    sa.Column('fetch_error', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['converted_case_id'], ['cases.id'], ondelete='SET NULL', use_alter=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'meta_lead_id', name='uq_meta_lead')
    )
    op.create_table('meta_page_mappings',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('page_id', sa.String(length=100), nullable=False),
    sa.Column('page_name', sa.String(length=255), nullable=True),
    sa.Column('access_token_encrypted', sa.Text(), nullable=True),
    sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('page_id', name='uq_meta_page_id')
    )
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('entity_type', sa.String(length=50), nullable=True),
    sa.Column('entity_id', sa.UUID(), nullable=True),
    sa.Column('dedupe_key', sa.String(length=255), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('org_counters',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('counter_type', sa.String(length=50), nullable=False),
    sa.Column('current_value', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('organization_id', 'counter_type')
    )
    op.create_table('org_invites',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('invited_by_user_id', sa.UUID(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resend_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('last_resent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_by_user_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['revoked_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pipelines',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('current_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('queues',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'name', name='uq_queue_name')
    )
    op.create_table('role_permissions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('permission', sa.String(length=100), nullable=False),
    sa.Column('is_granted', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'role', 'permission', name='uq_role_permissions_org_role_perm')
    )
    op.create_table('system_alerts',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('dedupe_key', sa.String(length=64), nullable=False),
    sa.Column('integration_key', sa.String(length=255), nullable=True),
    sa.Column('alert_type', sa.String(length=50), nullable=False),
    sa.Column('severity', sa.String(length=20), server_default=sa.text("'error'"), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'open'"), nullable=False),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('occurrence_count', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolved_by_user_id', sa.UUID(), nullable=True),
    sa.Column('snoozed_until', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resolved_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'dedupe_key', name='uq_system_alerts_dedupe')
    )
    op.create_table('user_integrations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('integration_type', sa.String(length=30), nullable=False),
    sa.Column('access_token_encrypted', sa.Text(), nullable=False),
    sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
    sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('account_email', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('current_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'integration_type')
    )
    op.create_table('user_notification_settings',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('case_assigned', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('case_status_changed', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('case_handoff', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('task_assigned', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('workflow_approvals', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('task_reminders', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('appointments', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('contact_reminder', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('user_permission_overrides',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('permission', sa.String(length=100), nullable=False),
    sa.Column('override_type', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("override_type IN ('grant', 'revoke')", name='ck_override_type_valid'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'user_id', 'permission', name='uq_user_overrides_org_user_perm')
    )
    op.create_table('user_sessions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('session_token_hash', sa.String(length=64), nullable=False, comment='SHA256 hash of JWT token for revocation lookup'),
    sa.Column('device_info', sa.String(length=500), nullable=True, comment='Parsed device name from user agent'),
    sa.Column('ip_address', sa.String(length=45), nullable=True, comment='IPv4 or IPv6 address'),
    sa.Column('user_agent', sa.String(length=500), nullable=True, comment='Raw user agent string'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_token_hash')
    )
    op.create_table('workflow_templates',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=50), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('trigger_type', sa.String(length=50), nullable=False),
    sa.Column('trigger_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('condition_logic', sa.String(length=10), nullable=False),
    sa.Column('actions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('is_global', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('usage_count', sa.Integer(), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'name', name='uq_template_name')
    )
    op.create_table('ai_messages',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('proposed_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ai_usage_log',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=True),
    sa.Column('model', sa.String(length=50), nullable=False),
    sa.Column('prompt_tokens', sa.Integer(), nullable=False),
    sa.Column('completion_tokens', sa.Integer(), nullable=False),
    sa.Column('total_tokens', sa.Integer(), nullable=False),
    sa.Column('estimated_cost_usd', sa.Numeric(precision=10, scale=6), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('audit_logs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('actor_user_id', sa.UUID(), nullable=True),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=True),
    sa.Column('target_id', sa.UUID(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=500), nullable=True),
    sa.Column('request_id', sa.UUID(), nullable=True),
    sa.Column('prev_hash', sa.String(length=64), nullable=True),
    sa.Column('entry_hash', sa.String(length=64), nullable=True),
    sa.Column('before_version_id', sa.UUID(), nullable=True),
    sa.Column('after_version_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['after_version_id'], ['entity_versions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['before_version_id'], ['entity_versions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaigns',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('email_template_id', sa.UUID(), nullable=False),
    sa.Column('recipient_type', sa.String(length=30), nullable=False),
    sa.Column('filter_criteria', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('scheduled_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'draft'"), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['email_template_id'], ['email_templates.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'name', name='uq_campaign_name')
    )
    op.create_table('form_field_mappings',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('form_id', sa.UUID(), nullable=False),
    sa.Column('field_key', sa.String(length=100), nullable=False),
    sa.Column('case_field', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('form_id', 'case_field', name='uq_form_case_field'),
    sa.UniqueConstraint('form_id', 'field_key', name='uq_form_field_key')
    )
    op.create_table('intended_parent_status_history',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('intended_parent_id', sa.UUID(), nullable=False),
    sa.Column('changed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('old_status', sa.String(length=50), nullable=True),
    sa.Column('new_status', sa.String(length=50), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['intended_parent_id'], ['intended_parents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pipeline_stages',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('pipeline_id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=50), nullable=False),
    sa.Column('stage_type', sa.String(length=20), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('color', sa.String(length=7), nullable=False),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
    sa.Column('is_intake_stage', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('allowed_next_slugs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pipeline_id', 'slug', name='uq_stage_slug')
    )
    op.create_table('queue_members',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('queue_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['queue_id'], ['queues.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('queue_id', 'user_id', name='uq_queue_member')
    )
    op.create_table('user_workflow_preferences',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('workflow_id', sa.UUID(), nullable=False),
    sa.Column('is_opted_out', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workflow_id'], ['automation_workflows.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'workflow_id', name='uq_user_workflow')
    )
    op.create_table('ai_action_approvals',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('message_id', sa.UUID(), nullable=False),
    sa.Column('action_index', sa.Integer(), nullable=False),
    sa.Column('action_type', sa.String(length=50), nullable=False),
    sa.Column('action_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['ai_messages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaign_runs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('campaign_id', sa.UUID(), nullable=False),
    sa.Column('started_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'running'"), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('total_count', sa.Integer(), nullable=False),
    sa.Column('sent_count', sa.Integer(), nullable=False),
    sa.Column('failed_count', sa.Integer(), nullable=False),
    sa.Column('skipped_count', sa.Integer(), nullable=False),
    sa.Column('opened_count', sa.Integer(), nullable=False),
    sa.Column('clicked_count', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('cases',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_number', sa.String(length=10), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('stage_id', sa.UUID(), nullable=False),
    sa.Column('status_label', sa.String(length=100), nullable=False),
    sa.Column('source', sa.String(length=20), server_default=sa.text("'manual'"), nullable=False),
    sa.Column('is_priority', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('owner_type', sa.String(length=10), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('meta_lead_id', sa.UUID(), nullable=True),
    sa.Column('meta_ad_id', sa.String(length=100), nullable=True),
    sa.Column('meta_form_id', sa.String(length=100), nullable=True),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('email', types.EncryptedString(), nullable=False),
    sa.Column('email_hash', sa.String(length=64), nullable=False),
    sa.Column('phone', types.EncryptedString(), nullable=True),
    sa.Column('phone_hash', sa.String(length=64), nullable=True),
    sa.Column('state', sa.String(length=2), nullable=True),
    sa.Column('date_of_birth', types.EncryptedDate(), nullable=True),
    sa.Column('race', sa.String(length=100), nullable=True),
    sa.Column('height_ft', sa.Numeric(precision=3, scale=1), nullable=True),
    sa.Column('weight_lb', sa.Integer(), nullable=True),
    sa.Column('is_age_eligible', sa.Boolean(), nullable=True),
    sa.Column('is_citizen_or_pr', sa.Boolean(), nullable=True),
    sa.Column('has_child', sa.Boolean(), nullable=True),
    sa.Column('is_non_smoker', sa.Boolean(), nullable=True),
    sa.Column('has_surrogate_experience', sa.Boolean(), nullable=True),
    sa.Column('num_deliveries', sa.Integer(), nullable=True),
    sa.Column('num_csections', sa.Integer(), nullable=True),
    sa.Column('is_archived', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('archived_by_user_id', sa.UUID(), nullable=True),
    sa.Column('last_contacted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_contact_method', sa.String(length=20), nullable=True),
    sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('contact_status', sa.String(length=20), server_default=sa.text("'unreached'"), nullable=False),
    sa.Column('contacted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.ForeignKeyConstraint(['archived_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['meta_lead_id'], ['meta_leads.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['stage_id'], ['pipeline_stages.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'case_number', name='uq_case_number')
    )
    op.create_table('tasks',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=True),
    sa.Column('intended_parent_id', sa.UUID(), nullable=True),
    sa.Column('created_by_user_id', sa.UUID(), nullable=False),
    sa.Column('owner_type', sa.String(length=10), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('task_type', sa.String(length=50), server_default=sa.text("'other'"), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('due_time', sa.Time(), nullable=True),
    sa.Column('duration_minutes', sa.Integer(), nullable=True),
    sa.Column('is_completed', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('workflow_execution_id', sa.UUID(), nullable=True),
    sa.Column('workflow_action_index', sa.Integer(), nullable=True),
    sa.Column('workflow_action_type', sa.String(length=50), nullable=True),
    sa.Column('workflow_action_preview', sa.Text(), nullable=True),
    sa.Column('workflow_action_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Internal only - never exposed via API'),
    sa.Column('workflow_triggered_by_user_id', sa.UUID(), nullable=True),
    sa.Column('workflow_denial_reason', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True, comment='For workflow approvals: pending, completed, denied, expired'),
    sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['completed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['intended_parent_id'], ['intended_parents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workflow_triggered_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('workflow_resume_jobs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('idempotency_key', sa.String(length=255), nullable=False),
    sa.Column('execution_id', sa.UUID(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key')
    )
    op.create_table('appointments',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('appointment_type_id', sa.UUID(), nullable=True),
    sa.Column('case_id', sa.UUID(), nullable=True),
    sa.Column('intended_parent_id', sa.UUID(), nullable=True),
    sa.Column('client_name', sa.String(length=255), nullable=False),
    sa.Column('client_email', postgresql.CITEXT(), nullable=False),
    sa.Column('client_phone', sa.String(length=20), nullable=False),
    sa.Column('client_notes', sa.Text(), nullable=True),
    sa.Column('client_timezone', sa.String(length=50), nullable=False),
    sa.Column('scheduled_start', sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('scheduled_end', sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('buffer_before_minutes', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('buffer_after_minutes', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('meeting_mode', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('pending_expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('approved_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('approved_by_user_id', sa.UUID(), nullable=True),
    sa.Column('cancelled_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('cancelled_by_client', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
    sa.Column('cancellation_reason', sa.Text(), nullable=True),
    sa.Column('google_event_id', sa.String(length=255), nullable=True),
    sa.Column('zoom_meeting_id', sa.String(length=100), nullable=True),
    sa.Column('zoom_join_url', sa.String(length=500), nullable=True),
    sa.Column('reschedule_token', sa.String(length=64), nullable=True),
    sa.Column('cancel_token', sa.String(length=64), nullable=True),
    sa.Column('reschedule_token_expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('cancel_token_expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('idempotency_key', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['appointment_type_id'], ['appointment_types.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['intended_parent_id'], ['intended_parents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('cancel_token', name='uq_appointment_cancel_token'),
    sa.UniqueConstraint('idempotency_key', name='uq_appointment_idempotency'),
    sa.UniqueConstraint('reschedule_token', name='uq_appointment_reschedule_token')
    )
    op.create_table('attachments',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=True),
    sa.Column('intended_parent_id', sa.UUID(), nullable=True),
    sa.Column('uploaded_by_user_id', sa.UUID(), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('file_size', sa.Integer(), nullable=False),
    sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
    sa.Column('scan_status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('scanned_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('quarantined', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['deleted_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['intended_parent_id'], ['intended_parents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaign_recipients',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=30), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('recipient_email', postgresql.CITEXT(), nullable=False),
    sa.Column('recipient_name', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('skip_reason', sa.String(length=100), nullable=True),
    sa.Column('sent_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('external_message_id', sa.String(length=255), nullable=True),
    sa.Column('tracking_token', sa.String(length=64), nullable=True),
    sa.Column('opened_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('open_count', sa.Integer(), nullable=False),
    sa.Column('clicked_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('click_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['campaign_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id', 'entity_type', 'entity_id', name='uq_campaign_recipient')
    )
    op.create_table('case_activity_log',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('activity_type', sa.String(length=50), nullable=False),
    sa.Column('actor_user_id', sa.UUID(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('case_contact_attempts',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('attempted_by_user_id', sa.UUID(), nullable=True),
    sa.Column('contact_methods', postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('outcome', sa.String(length=30), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('case_owner_id_at_attempt', sa.UUID(), nullable=False),
    sa.CheckConstraint("attempted_at <= (now() + interval '5 minutes')", name='ck_attempted_at_not_future'),
    sa.CheckConstraint("contact_methods <@ ARRAY['phone', 'email', 'sms']::VARCHAR[]", name='ck_contact_methods_valid'),
    sa.CheckConstraint('array_length(contact_methods, 1) > 0', name='ck_contact_methods_not_empty'),
    sa.ForeignKeyConstraint(['attempted_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('case_interviews',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('interview_type', sa.String(length=20), nullable=False),
    sa.Column('conducted_at', sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('conducted_by_user_id', sa.UUID(), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=True),
    sa.Column('transcript_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('transcript_text', sa.Text(), nullable=True),
    sa.Column('transcript_storage_key', sa.String(length=500), nullable=True),
    sa.Column('transcript_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('transcript_hash', sa.String(length=64), nullable=True),
    sa.Column('transcript_size_bytes', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'completed'"), nullable=False),
    sa.Column('retention_policy_id', sa.UUID(), nullable=True),
    sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['conducted_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['retention_policy_id'], ['data_retention_policies.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('case_profile_hidden_fields',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('field_key', sa.String(length=255), nullable=False),
    sa.Column('hidden_by_user_id', sa.UUID(), nullable=True),
    sa.Column('hidden_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['hidden_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'field_key', name='uq_case_profile_hidden_field')
    )
    op.create_table('case_profile_overrides',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('field_key', sa.String(length=255), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'field_key', name='uq_case_profile_override_field')
    )
    op.create_table('case_status_history',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('from_stage_id', sa.UUID(), nullable=True),
    sa.Column('to_stage_id', sa.UUID(), nullable=True),
    sa.Column('from_label_snapshot', sa.String(length=100), nullable=True),
    sa.Column('to_label_snapshot', sa.String(length=100), nullable=True),
    sa.Column('changed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['from_stage_id'], ['pipeline_stages.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['to_stage_id'], ['pipeline_stages.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('email_logs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('job_id', sa.UUID(), nullable=True),
    sa.Column('template_id', sa.UUID(), nullable=True),
    sa.Column('case_id', sa.UUID(), nullable=True),
    sa.Column('recipient_email', sa.String(length=255), nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['template_id'], ['email_templates.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('form_submission_tokens',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('form_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('token', sa.String(length=255), nullable=False),
    sa.Column('expires_at', sa.TIMESTAMP(), nullable=False),
    sa.Column('max_submissions', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('used_submissions', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('revoked_at', sa.TIMESTAMP(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token', name='uq_form_submission_token')
    )
    op.create_table('matches',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('intended_parent_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('compatibility_score', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('proposed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('proposed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('reviewed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('rejection_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['intended_parent_id'], ['intended_parents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['proposed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'case_id', 'intended_parent_id', name='uq_match_org_case_ip')
    )
    op.create_table('zoom_meetings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('case_id', sa.UUID(), nullable=True),
    sa.Column('intended_parent_id', sa.UUID(), nullable=True),
    sa.Column('zoom_meeting_id', sa.String(length=50), nullable=False),
    sa.Column('topic', sa.String(length=255), nullable=False),
    sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('duration', sa.Integer(), nullable=False),
    sa.Column('timezone', sa.String(length=100), nullable=False),
    sa.Column('join_url', sa.String(length=500), nullable=False),
    sa.Column('start_url', sa.Text(), nullable=False),
    sa.Column('password', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['intended_parent_id'], ['intended_parents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('appointment_email_logs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('appointment_id', sa.UUID(), nullable=False),
    sa.Column('email_type', sa.String(length=30), nullable=False),
    sa.Column('recipient_email', postgresql.CITEXT(), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('sent_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('external_message_id', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaign_tracking_events',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('recipient_id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(length=10), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['recipient_id'], ['campaign_recipients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('form_submissions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('form_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('token_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending_review'"), nullable=False),
    sa.Column('answers_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('schema_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('submitted_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.Column('reviewed_at', sa.TIMESTAMP(), nullable=True),
    sa.Column('reviewed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('review_notes', sa.Text(), nullable=True),
    sa.Column('applied_at', sa.TIMESTAMP(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['token_id'], ['form_submission_tokens.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('form_id', 'case_id', name='uq_form_submission_case')
    )
    op.create_table('interview_attachments',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('interview_id', sa.UUID(), nullable=False),
    sa.Column('attachment_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('transcription_status', sa.String(length=20), nullable=True),
    sa.Column('transcription_job_id', sa.String(length=100), nullable=True),
    sa.Column('transcription_error', sa.Text(), nullable=True),
    sa.Column('transcription_completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['interview_id'], ['case_interviews.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('interview_id', 'attachment_id', name='uq_interview_attachment')
    )
    op.create_table('interview_notes',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('interview_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('transcript_version', sa.Integer(), nullable=False),
    sa.Column('comment_id', sa.String(length=36), nullable=True),
    sa.Column('anchor_text', sa.String(length=500), nullable=True),
    sa.Column('author_user_id', sa.UUID(), nullable=False),
    sa.Column('parent_id', sa.UUID(), nullable=True),
    sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('resolved_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['interview_id'], ['case_interviews.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['interview_notes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resolved_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('interview_transcript_versions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('interview_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('content_html', sa.Text(), nullable=True),
    sa.Column('content_text', sa.Text(), nullable=True),
    sa.Column('content_storage_key', sa.String(length=500), nullable=True),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('content_size_bytes', sa.Integer(), nullable=False),
    sa.Column('author_user_id', sa.UUID(), nullable=False),
    sa.Column('source', sa.String(length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['interview_id'], ['case_interviews.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('interview_id', 'version', name='uq_interview_version')
    )
    op.create_table('match_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('match_id', sa.UUID(), nullable=False),
    sa.Column('person_type', sa.String(length=20), nullable=False),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('timezone', sa.String(length=50), nullable=False),
    sa.Column('all_day', sa.Boolean(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('case_profile_states',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('base_submission_id', sa.UUID(), nullable=True),
    sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['base_submission_id'], ['form_submissions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', name='uq_case_profile_state_case')
    )
    op.create_table('form_submission_files',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('file_size', sa.Integer(), nullable=False),
    sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
    sa.Column('scan_status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('quarantined', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
    sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['submission_id'], ['form_submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_request_metrics_period', 'request_metrics_rollup', ['period_start', 'period_type'], unique=False)
    op.create_index('uq_request_metrics_rollup_null_org', 'request_metrics_rollup', ['period_start', 'route', 'method'], unique=True, postgresql_where=sa.text('organization_id IS NULL'))
    op.create_index('idx_task_wf_approval_unique', 'tasks', ['workflow_execution_id', 'workflow_action_index'], unique=True, postgresql_where=sa.text("task_type = 'workflow_approval'"))
    op.create_index('idx_tasks_due', 'tasks', ['organization_id', 'due_date'], unique=False, postgresql_where=sa.text('is_completed = FALSE'))
    op.create_index('idx_tasks_intended_parent', 'tasks', ['intended_parent_id'], unique=False)
    op.create_index('idx_tasks_org_created', 'tasks', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_tasks_org_owner', 'tasks', ['organization_id', 'owner_type', 'owner_id', 'is_completed'], unique=False)
    op.create_index('idx_tasks_org_status', 'tasks', ['organization_id', 'is_completed'], unique=False)
    op.create_index('idx_tasks_org_updated', 'tasks', ['organization_id', 'updated_at'], unique=False)
    op.create_index('idx_tasks_pending_approvals', 'tasks', ['organization_id', 'status', 'due_at'], unique=False, postgresql_where=sa.text("task_type = 'workflow_approval' AND status IN ('pending', 'in_progress')"))
    op.create_index('idx_exec_entity', 'workflow_executions', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_exec_event', 'workflow_executions', ['event_id'], unique=False)
    op.create_index('idx_exec_paused', 'workflow_executions', ['organization_id', 'status'], unique=False, postgresql_where=sa.text("status = 'paused'"))
    op.create_index('idx_exec_workflow', 'workflow_executions', ['workflow_id', 'executed_at'], unique=False)
    op.create_index('ix_ai_conversations_entity', 'ai_conversations', ['organization_id', 'entity_type', 'entity_id'], unique=False)
    op.create_index('ix_ai_conversations_user', 'ai_conversations', ['user_id', 'entity_type', 'entity_id'], unique=False)
    op.create_index('idx_analytics_snapshot_expires', 'analytics_snapshots', ['expires_at'], unique=False)
    op.create_index('idx_analytics_snapshot_org_type', 'analytics_snapshots', ['organization_id', 'snapshot_type'], unique=False)
    op.create_index('idx_appointment_types_org', 'appointment_types', ['organization_id'], unique=False)
    op.create_index('idx_appointment_types_user', 'appointment_types', ['user_id', 'is_active'], unique=False)
    op.create_index('idx_auth_identities_user_id', 'auth_identities', ['user_id'], unique=False)
    op.create_index('idx_wf_org_enabled', 'automation_workflows', ['organization_id', 'is_enabled'], unique=False)
    op.create_index('idx_availability_overrides_org', 'availability_overrides', ['organization_id'], unique=False)
    op.create_index('idx_availability_overrides_user', 'availability_overrides', ['user_id'], unique=False)
    op.create_index('idx_availability_rules_org', 'availability_rules', ['organization_id'], unique=False)
    op.create_index('idx_availability_rules_user', 'availability_rules', ['user_id'], unique=False)
    op.create_index('idx_booking_links_org', 'booking_links', ['organization_id'], unique=False)
    op.create_index('idx_case_imports_org_created', 'case_imports', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_retention_policy_org_active', 'data_retention_policies', ['organization_id', 'is_active'], unique=False)
    op.create_index('idx_email_suppressions_email', 'email_suppressions', ['email'], unique=False)
    op.create_index('idx_email_suppressions_org', 'email_suppressions', ['organization_id'], unique=False)
    op.create_index('idx_email_templates_org', 'email_templates', ['organization_id', 'is_active'], unique=False)
    op.create_index('idx_entity_notes_lookup', 'entity_notes', ['entity_type', 'entity_id', 'created_at'], unique=False)
    op.create_index('idx_entity_notes_org', 'entity_notes', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_entity_notes_search_vector', 'entity_notes', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('idx_entity_versions_lookup', 'entity_versions', ['organization_id', 'entity_type', 'entity_id', 'created_at'], unique=False)
    op.create_index('idx_export_jobs_org_created', 'export_jobs', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_export_jobs_org_status', 'export_jobs', ['organization_id', 'status'], unique=False)
    op.create_index('idx_form_logos_org', 'form_logos', ['organization_id'], unique=False)
    op.create_index('idx_forms_org', 'forms', ['organization_id'], unique=False)
    op.create_index('idx_forms_org_status', 'forms', ['organization_id', 'status'], unique=False)
    op.create_index('ix_integration_error_rollup_lookup', 'integration_error_rollup', ['organization_id', 'integration_type', 'period_start'], unique=False)
    op.create_index('uq_integration_error_rollup_null_key', 'integration_error_rollup', ['organization_id', 'integration_type', 'period_start'], unique=True, postgresql_where=sa.text('integration_key IS NULL'))
    op.create_index('ix_integration_health_org_type', 'integration_health', ['organization_id', 'integration_type'], unique=False)
    op.create_index('uq_integration_health_org_type_null_key', 'integration_health', ['organization_id', 'integration_type'], unique=True, postgresql_where=sa.text('integration_key IS NULL'))
    op.create_index('idx_ip_org_created', 'intended_parents', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_ip_org_owner', 'intended_parents', ['organization_id', 'owner_type', 'owner_id'], unique=False)
    op.create_index('idx_ip_org_phone_hash', 'intended_parents', ['organization_id', 'phone_hash'], unique=False)
    op.create_index('idx_ip_org_status', 'intended_parents', ['organization_id', 'status'], unique=False)
    op.create_index('idx_ip_org_updated', 'intended_parents', ['organization_id', 'updated_at'], unique=False)
    op.create_index('ix_intended_parents_search_vector', 'intended_parents', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('uq_ip_email_hash_active', 'intended_parents', ['organization_id', 'email_hash'], unique=True, postgresql_where=sa.text('is_archived = false'))
    op.create_index('idx_jobs_org', 'jobs', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_jobs_pending', 'jobs', ['status', 'run_at'], unique=False, postgresql_where=sa.text("status = 'pending'"))
    op.create_index('uq_job_idempotency', 'jobs', ['idempotency_key'], unique=True, postgresql_where=sa.text('idempotency_key IS NOT NULL'))
    op.create_index('idx_legal_holds_entity_active', 'legal_holds', ['organization_id', 'entity_type', 'entity_id', 'released_at'], unique=False)
    op.create_index('idx_legal_holds_org_active', 'legal_holds', ['organization_id', 'released_at'], unique=False)
    op.create_index('idx_memberships_org_id', 'memberships', ['organization_id'], unique=False)
    op.create_index('idx_meta_leads_status', 'meta_leads', ['organization_id', 'status'], unique=False)
    op.create_index('idx_meta_unconverted', 'meta_leads', ['organization_id'], unique=False, postgresql_where=sa.text('is_converted = FALSE'))
    op.create_index('idx_meta_page_org', 'meta_page_mappings', ['organization_id'], unique=False)
    op.create_index('idx_notif_dedupe', 'notifications', ['dedupe_key', 'created_at'], unique=False)
    op.create_index('idx_notif_org_user', 'notifications', ['organization_id', 'user_id', 'created_at'], unique=False)
    op.create_index('idx_notif_user_unread', 'notifications', ['user_id', 'read_at', 'created_at'], unique=False)
    op.create_index('idx_org_invites_org_id', 'org_invites', ['organization_id'], unique=False)
    op.create_index('uq_pending_invite_email', 'org_invites', ['email'], unique=True, postgresql_where=sa.text('accepted_at IS NULL AND revoked_at IS NULL'))
    op.create_index('idx_pipelines_org', 'pipelines', ['organization_id'], unique=False)
    op.create_index('idx_queues_org_active', 'queues', ['organization_id', 'is_active'], unique=False)
    op.create_index('idx_role_permissions_org_role', 'role_permissions', ['organization_id', 'role'], unique=False)
    op.create_index('ix_system_alerts_org_status', 'system_alerts', ['organization_id', 'status', 'severity'], unique=False)
    op.create_index('idx_user_overrides_org_user', 'user_permission_overrides', ['organization_id', 'user_id'], unique=False)
    op.create_index('idx_user_sessions_expires', 'user_sessions', ['expires_at'], unique=False)
    op.create_index('idx_user_sessions_org_id', 'user_sessions', ['organization_id'], unique=False)
    op.create_index('idx_user_sessions_token_hash', 'user_sessions', ['session_token_hash'], unique=False)
    op.create_index('idx_user_sessions_user_id', 'user_sessions', ['user_id'], unique=False)
    op.create_index('idx_resume_jobs_pending', 'workflow_resume_jobs', ['status', 'created_at'], unique=False, postgresql_where=sa.text("status = 'pending'"))
    op.create_index('idx_template_category', 'workflow_templates', ['category'], unique=False)
    op.create_index('idx_template_org', 'workflow_templates', ['organization_id'], unique=False)
    op.create_index('ix_ai_messages_conversation', 'ai_messages', ['conversation_id', 'created_at'], unique=False)
    op.create_index('ix_ai_usage_log_org_date', 'ai_usage_log', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_audit_org_actor_created', 'audit_logs', ['organization_id', 'actor_user_id', 'created_at'], unique=False)
    op.create_index('idx_audit_org_created', 'audit_logs', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_audit_org_event_created', 'audit_logs', ['organization_id', 'event_type', 'created_at'], unique=False)
    op.create_index('idx_campaigns_org_created', 'campaigns', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_campaigns_org_status', 'campaigns', ['organization_id', 'status'], unique=False)
    op.create_index('idx_form_mappings_form', 'form_field_mappings', ['form_id'], unique=False)
    op.create_index('idx_ip_history_ip', 'intended_parent_status_history', ['intended_parent_id', 'changed_at'], unique=False)
    op.create_index('idx_stage_pipeline_active', 'pipeline_stages', ['pipeline_id', 'is_active'], unique=False)
    op.create_index('idx_stage_pipeline_order', 'pipeline_stages', ['pipeline_id', 'order'], unique=False)
    op.create_index('idx_queue_members_user', 'queue_members', ['user_id'], unique=False)
    op.create_index('ix_ai_action_approvals_message', 'ai_action_approvals', ['message_id'], unique=False)
    op.create_index('ix_ai_action_approvals_status', 'ai_action_approvals', ['status'], unique=False)
    op.create_index('idx_campaign_runs_campaign', 'campaign_runs', ['campaign_id', 'started_at'], unique=False)
    op.create_index('idx_campaign_runs_org', 'campaign_runs', ['organization_id', 'started_at'], unique=False)
    op.create_index('idx_cases_meta_ad', 'cases', ['organization_id', 'meta_ad_id'], unique=False, postgresql_where=sa.text('meta_ad_id IS NOT NULL'))
    op.create_index('idx_cases_meta_form', 'cases', ['organization_id', 'meta_form_id'], unique=False, postgresql_where=sa.text('meta_form_id IS NOT NULL'))
    op.create_index('idx_cases_org_active', 'cases', ['organization_id'], unique=False, postgresql_where=sa.text('is_archived = FALSE'))
    op.create_index('idx_cases_org_created', 'cases', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_cases_org_owner', 'cases', ['organization_id', 'owner_type', 'owner_id'], unique=False)
    op.create_index('idx_cases_org_phone_hash', 'cases', ['organization_id', 'phone_hash'], unique=False)
    op.create_index('idx_cases_org_stage', 'cases', ['organization_id', 'stage_id'], unique=False)
    op.create_index('idx_cases_org_status_label', 'cases', ['organization_id', 'status_label'], unique=False)
    op.create_index('idx_cases_org_updated', 'cases', ['organization_id', 'updated_at'], unique=False)
    op.create_index('idx_cases_reminder_check', 'cases', ['organization_id', 'owner_type', 'contact_status', 'stage_id'], unique=False)
    op.create_index('idx_cases_stage', 'cases', ['stage_id'], unique=False)
    op.create_index('ix_cases_search_vector', 'cases', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('uq_case_email_hash_active', 'cases', ['organization_id', 'email_hash'], unique=True, postgresql_where=sa.text('is_archived = FALSE'))
    op.create_index('idx_appointments_case', 'appointments', ['case_id'], unique=False)
    op.create_index('idx_appointments_ip', 'appointments', ['intended_parent_id'], unique=False)
    op.create_index('idx_appointments_org_created', 'appointments', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_appointments_org_status', 'appointments', ['organization_id', 'status'], unique=False)
    op.create_index('idx_appointments_org_updated', 'appointments', ['organization_id', 'updated_at'], unique=False)
    op.create_index('idx_appointments_org_user', 'appointments', ['organization_id', 'user_id'], unique=False)
    op.create_index('idx_appointments_pending_expiry', 'appointments', ['pending_expires_at'], unique=False, postgresql_where=sa.text("status = 'pending'"))
    op.create_index('idx_appointments_type', 'appointments', ['appointment_type_id'], unique=False)
    op.create_index('idx_appointments_user_date', 'appointments', ['user_id', 'scheduled_start'], unique=False)
    op.create_index('idx_attachments_active', 'attachments', ['case_id'], unique=False, postgresql_where=sa.text('deleted_at IS NULL AND quarantined = FALSE'))
    op.create_index('idx_attachments_case', 'attachments', ['case_id'], unique=False)
    op.create_index('idx_attachments_intended_parent', 'attachments', ['intended_parent_id'], unique=False)
    op.create_index('idx_attachments_org_scan', 'attachments', ['organization_id', 'scan_status'], unique=False)
    op.create_index('ix_attachments_search_vector', 'attachments', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('idx_campaign_recipients_entity', 'campaign_recipients', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_campaign_recipients_run', 'campaign_recipients', ['run_id'], unique=False)
    op.create_index('idx_campaign_recipients_tracking_token', 'campaign_recipients', ['tracking_token'], unique=True)
    op.create_index('idx_case_activity_case_time', 'case_activity_log', ['case_id', 'created_at'], unique=False)
    op.create_index('idx_contact_attempts_case', 'case_contact_attempts', ['case_id', 'attempted_at'], unique=False)
    op.create_index('idx_contact_attempts_case_owner', 'case_contact_attempts', ['case_id', 'case_owner_id_at_attempt', 'attempted_at'], unique=False)
    op.create_index('idx_contact_attempts_org_pending', 'case_contact_attempts', ['organization_id', 'outcome', 'attempted_at'], unique=False, postgresql_where=sa.text("outcome != 'reached'"))
    op.create_index('ix_case_interviews_case_id', 'case_interviews', ['case_id'], unique=False)
    op.create_index('ix_case_interviews_org_conducted', 'case_interviews', ['organization_id', 'conducted_at'], unique=False)
    op.create_index('ix_case_interviews_search_vector', 'case_interviews', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('idx_profile_hidden_case', 'case_profile_hidden_fields', ['case_id'], unique=False)
    op.create_index('idx_profile_overrides_case', 'case_profile_overrides', ['case_id'], unique=False)
    op.create_index('idx_case_history_case', 'case_status_history', ['case_id', 'changed_at'], unique=False)
    op.create_index('idx_email_logs_case', 'email_logs', ['case_id', 'created_at'], unique=False)
    op.create_index('idx_email_logs_org', 'email_logs', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_form_tokens_case', 'form_submission_tokens', ['case_id'], unique=False)
    op.create_index('idx_form_tokens_form', 'form_submission_tokens', ['form_id'], unique=False)
    op.create_index('idx_form_tokens_org', 'form_submission_tokens', ['organization_id'], unique=False)
    op.create_index('idx_matches_org_created', 'matches', ['organization_id', 'created_at'], unique=False)
    op.create_index('idx_matches_org_status', 'matches', ['organization_id', 'status'], unique=False)
    op.create_index('idx_matches_org_updated', 'matches', ['organization_id', 'updated_at'], unique=False)
    op.create_index('ix_matches_case_id', 'matches', ['case_id'], unique=False)
    op.create_index('ix_matches_ip_id', 'matches', ['intended_parent_id'], unique=False)
    op.create_index('ix_matches_status', 'matches', ['status'], unique=False)
    op.create_index('uq_one_accepted_match_per_case', 'matches', ['organization_id', 'case_id'], unique=True, postgresql_where=sa.text("status = 'accepted'"))
    op.create_index('ix_zoom_meetings_case_id', 'zoom_meetings', ['case_id'], unique=False)
    op.create_index('ix_zoom_meetings_org_created', 'zoom_meetings', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_zoom_meetings_user_id', 'zoom_meetings', ['user_id'], unique=False)
    op.create_index('idx_appointment_email_logs_appt', 'appointment_email_logs', ['appointment_id'], unique=False)
    op.create_index('idx_appointment_email_logs_org', 'appointment_email_logs', ['organization_id'], unique=False)
    op.create_index('idx_tracking_events_recipient', 'campaign_tracking_events', ['recipient_id'], unique=False)
    op.create_index('idx_tracking_events_type', 'campaign_tracking_events', ['event_type'], unique=False)
    op.create_index('idx_form_submissions_case', 'form_submissions', ['case_id'], unique=False)
    op.create_index('idx_form_submissions_form', 'form_submissions', ['form_id'], unique=False)
    op.create_index('idx_form_submissions_org', 'form_submissions', ['organization_id'], unique=False)
    op.create_index('idx_form_submissions_status', 'form_submissions', ['status'], unique=False)
    op.create_index('ix_interview_attachments_interview', 'interview_attachments', ['interview_id'], unique=False)
    op.create_index(op.f('ix_interview_notes_comment_id'), 'interview_notes', ['comment_id'], unique=False)
    op.create_index('ix_interview_notes_interview', 'interview_notes', ['interview_id'], unique=False)
    op.create_index('ix_interview_notes_org', 'interview_notes', ['organization_id'], unique=False)
    op.create_index('ix_interview_notes_parent', 'interview_notes', ['parent_id'], unique=False)
    op.create_index('ix_interview_versions_interview', 'interview_transcript_versions', ['interview_id', 'version'], unique=False)
    op.create_index('ix_interview_versions_org', 'interview_transcript_versions', ['organization_id'], unique=False)
    op.create_index('ix_match_events_match_starts', 'match_events', ['match_id', 'starts_at'], unique=False)
    op.create_index('ix_match_events_org_starts', 'match_events', ['organization_id', 'starts_at'], unique=False)
    op.create_index('idx_profile_state_case', 'case_profile_states', ['case_id'], unique=False)
    op.create_index('idx_form_files_org', 'form_submission_files', ['organization_id'], unique=False)
    op.create_index('idx_form_files_submission', 'form_submission_files', ['submission_id'], unique=False)
    op.create_foreign_key(
        'fk_meta_leads_converted_case_id_cases',
        'meta_leads',
        'cases',
        ['converted_case_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(None, 'tasks', 'workflow_executions', ['workflow_execution_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'workflow_executions', 'tasks', ['paused_task_id'], ['id'], ondelete='SET NULL')
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER update_organizations_updated_at
            BEFORE UPDATE ON organizations
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE TRIGGER update_cases_updated_at
            BEFORE UPDATE ON cases
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE TRIGGER update_tasks_updated_at
            BEFORE UPDATE ON tasks
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION cases_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '') || ' ' ||
                coalesce(NEW.case_number, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER cases_search_vector_trigger
        BEFORE INSERT OR UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION cases_search_vector_update();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION entity_notes_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                regexp_replace(coalesce(NEW.content, ''), '<[^>]+>', ' ', 'g')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER entity_notes_search_vector_trigger
        BEFORE INSERT OR UPDATE ON entity_notes
        FOR EACH ROW EXECUTE FUNCTION entity_notes_search_vector_update();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION attachments_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.filename, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER attachments_search_vector_trigger
        BEFORE INSERT OR UPDATE ON attachments
        FOR EACH ROW EXECUTE FUNCTION attachments_search_vector_update();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION intended_parents_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER intended_parents_search_vector_trigger
        BEFORE INSERT OR UPDATE ON intended_parents
        FOR EACH ROW EXECUTE FUNCTION intended_parents_search_vector_update();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_case_interviews_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.transcript_text, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_case_interviews_search_vector
        BEFORE INSERT OR UPDATE OF transcript_text
        ON case_interviews
        FOR EACH ROW
        EXECUTE FUNCTION update_case_interviews_search_vector();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_case_interviews_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_case_interviews_updated_at
        BEFORE UPDATE ON case_interviews
        FOR EACH ROW
        EXECUTE FUNCTION update_case_interviews_updated_at();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION audit_logs_immutable_guard() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs are append-only';
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER audit_logs_no_update
        BEFORE UPDATE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable_guard();
    """)

    op.execute("""
        CREATE TRIGGER audit_logs_no_delete
        BEFORE DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable_guard();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_immutable_guard()")

    op.execute("DROP TRIGGER IF EXISTS trg_case_interviews_updated_at ON case_interviews")
    op.execute("DROP FUNCTION IF EXISTS update_case_interviews_updated_at()")
    op.execute("DROP TRIGGER IF EXISTS trg_case_interviews_search_vector ON case_interviews")
    op.execute("DROP FUNCTION IF EXISTS update_case_interviews_search_vector()")

    op.execute("DROP TRIGGER IF EXISTS intended_parents_search_vector_trigger ON intended_parents")
    op.execute("DROP FUNCTION IF EXISTS intended_parents_search_vector_update()")
    op.execute("DROP TRIGGER IF EXISTS attachments_search_vector_trigger ON attachments")
    op.execute("DROP FUNCTION IF EXISTS attachments_search_vector_update()")
    op.execute("DROP TRIGGER IF EXISTS entity_notes_search_vector_trigger ON entity_notes")
    op.execute("DROP FUNCTION IF EXISTS entity_notes_search_vector_update()")
    op.execute("DROP TRIGGER IF EXISTS cases_search_vector_trigger ON cases")
    op.execute("DROP FUNCTION IF EXISTS cases_search_vector_update()")

    op.execute("DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks")
    op.execute("DROP TRIGGER IF EXISTS update_cases_updated_at ON cases")
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users")
    op.execute("DROP TRIGGER IF EXISTS update_organizations_updated_at ON organizations")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.drop_table('form_submission_files')
    op.drop_table('case_profile_states')
    op.drop_table('match_events')
    op.drop_table('interview_transcript_versions')
    op.drop_table('interview_notes')
    op.drop_table('interview_attachments')
    op.drop_table('form_submissions')
    op.drop_table('campaign_tracking_events')
    op.drop_table('appointment_email_logs')
    op.drop_table('zoom_meetings')
    op.drop_table('matches')
    op.drop_table('form_submission_tokens')
    op.drop_table('email_logs')
    op.drop_table('case_status_history')
    op.drop_table('case_profile_overrides')
    op.drop_table('case_profile_hidden_fields')
    op.drop_table('case_interviews')
    op.drop_table('case_contact_attempts')
    op.drop_table('case_activity_log')
    op.drop_table('campaign_recipients')
    op.drop_table('attachments')
    op.drop_table('appointments')
    op.drop_constraint(
        'fk_meta_leads_converted_case_id_cases',
        'meta_leads',
        type_='foreignkey',
    )
    op.drop_table('cases')
    op.drop_table('campaign_runs')
    op.drop_table('ai_action_approvals')
    op.drop_table('user_workflow_preferences')
    op.drop_table('queue_members')
    op.drop_table('pipeline_stages')
    op.drop_table('intended_parent_status_history')
    op.drop_table('form_field_mappings')
    op.drop_table('campaigns')
    op.drop_table('audit_logs')
    op.drop_table('ai_usage_log')
    op.drop_table('ai_messages')
    op.drop_table('workflow_templates')
    op.drop_table('workflow_resume_jobs')
    op.drop_table('user_sessions')
    op.drop_table('user_permission_overrides')
    op.drop_table('user_notification_settings')
    op.drop_table('user_integrations')
    op.drop_table('system_alerts')
    op.drop_table('role_permissions')
    op.drop_table('queues')
    op.drop_table('pipelines')
    op.drop_table('org_invites')
    op.drop_table('org_counters')
    op.drop_table('notifications')
    op.drop_table('meta_page_mappings')
    op.drop_table('meta_leads')
    op.drop_table('memberships')
    op.drop_table('legal_holds')
    op.drop_table('jobs')
    op.drop_table('intended_parents')
    op.drop_table('integration_health')
    op.drop_table('integration_error_rollup')
    op.drop_table('forms')
    op.drop_table('form_logos')
    op.drop_table('export_jobs')
    op.drop_table('entity_versions')
    op.drop_table('entity_notes')
    op.drop_table('email_templates')
    op.drop_table('email_suppressions')
    op.drop_table('data_retention_policies')
    op.drop_table('case_imports')
    op.drop_table('booking_links')
    op.drop_table('availability_rules')
    op.drop_table('availability_overrides')
    op.drop_table('automation_workflows')
    op.drop_table('auth_identities')
    op.drop_table('appointment_types')
    op.drop_table('analytics_snapshots')
    op.drop_table('ai_settings')
    op.drop_table('ai_conversations')
    op.drop_table('workflow_executions')
    op.drop_table('users')
    op.drop_table('tasks')
    op.drop_table('request_metrics_rollup')
    op.drop_table('organizations')
    op.drop_table('ai_entity_summaries')
    op.execute("DROP EXTENSION IF EXISTS citext")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
