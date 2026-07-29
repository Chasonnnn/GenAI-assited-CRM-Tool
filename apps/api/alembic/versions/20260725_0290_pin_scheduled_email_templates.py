"""Pin published email content for queued campaign runs and workflow jobs.

Revision ID: 20260725_0290
Revises: 20260723_0280
Create Date: 2026-07-25 03:30:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260725_0290"
down_revision = "20260723_0280"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fence legacy campaign mutations before reading any queued intent. The
    # preservation trigger is created later in this transaction and is not
    # visible to the old API until commit, so locking first closes that gap.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("LOCK TABLE campaigns, campaign_runs IN SHARE ROW EXCLUSIVE MODE")
    op.add_column(
        "campaign_runs",
        sa.Column("email_template_snapshot", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "email_logs",
        sa.Column("email_template_snapshot", postgresql.JSONB(), nullable=True),
    )

    # Existing unfinished runs cannot recover the historical bytes that were
    # originally selected, so pin the current published bytes at deployment.
    # Completed history is left untouched to keep this backfill bounded.
    op.execute(
        sa.text(
            """
            UPDATE campaign_runs AS run
            SET email_template_snapshot = jsonb_build_object(
                'schema_version', 1,
                'organization_id', campaign.organization_id::text,
                'template_id', template.id::text,
                'template_version', template.current_version,
                'subject', template.subject,
                'body', template.body,
                'from_email', CASE
                    WHEN NULLIF(btrim(template.from_email), '') IS NOT NULL
                     AND NULLIF(btrim(settings.from_name), '') IS NOT NULL
                     AND position('<' in template.from_email) = 0
                        THEN settings.from_name || ' <' || template.from_email || '>'
                    WHEN NULLIF(btrim(template.from_email), '') IS NOT NULL
                        THEN template.from_email
                    WHEN NULLIF(btrim(settings.from_email), '') IS NULL
                        THEN NULL
                    WHEN NULLIF(btrim(settings.from_name), '') IS NOT NULL
                        THEN settings.from_name || ' <' || settings.from_email || '>'
                    ELSE settings.from_email
                END
            )
            FROM campaigns AS campaign
            JOIN email_templates AS template
              ON template.id = campaign.email_template_id
             AND template.organization_id = campaign.organization_id
            LEFT JOIN resend_settings AS settings
              ON settings.organization_id = campaign.organization_id
            WHERE run.campaign_id = campaign.id
              AND run.organization_id = campaign.organization_id
              AND run.status <> 'completed'
              AND run.email_template_snapshot IS NULL
            """
        )
    )

    # Keep legacy API revisions safe during the migration-to-API cutover. New
    # producers already supply immutable snapshots, so both triggers are
    # strict no-ops when a snapshot is present.
    op.execute(
        """
        CREATE FUNCTION pin_legacy_campaign_run_template_snapshot_0290()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            snapshot_payload jsonb;
        BEGIN
            IF NEW.email_template_snapshot IS NOT NULL OR NEW.status = 'completed' THEN
                RETURN NEW;
            END IF;

            SELECT jsonb_build_object(
                'schema_version', 1,
                'organization_id', campaign.organization_id::text,
                'template_id', template.id::text,
                'template_version', template.current_version,
                'subject', template.subject,
                'body', template.body,
                'from_email', CASE
                    WHEN NULLIF(btrim(template.from_email), '') IS NOT NULL
                     AND NULLIF(btrim(settings.from_name), '') IS NOT NULL
                     AND position('<' in template.from_email) = 0
                        THEN settings.from_name || ' <' || template.from_email || '>'
                    WHEN NULLIF(btrim(template.from_email), '') IS NOT NULL
                        THEN template.from_email
                    WHEN NULLIF(btrim(settings.from_email), '') IS NULL
                        THEN NULL
                    WHEN NULLIF(btrim(settings.from_name), '') IS NOT NULL
                        THEN settings.from_name || ' <' || settings.from_email || '>'
                    ELSE settings.from_email
                END
            )
            INTO snapshot_payload
            FROM campaigns AS campaign
            JOIN email_templates AS template
              ON template.id = campaign.email_template_id
             AND template.organization_id = campaign.organization_id
            LEFT JOIN resend_settings AS settings
              ON settings.organization_id = campaign.organization_id
            WHERE campaign.id = NEW.campaign_id
              AND campaign.organization_id = NEW.organization_id;

            NEW.email_template_snapshot := snapshot_payload;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER pin_legacy_campaign_run_template_snapshot_0290
        BEFORE INSERT ON campaign_runs
        FOR EACH ROW
        EXECUTE FUNCTION pin_legacy_campaign_run_template_snapshot_0290()
        """
    )
    op.execute(
        """
        CREATE FUNCTION preserve_scheduled_campaign_template_0290()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status = 'scheduled'
               AND NEW.email_template_id IS DISTINCT FROM OLD.email_template_id
            THEN
                RAISE EXCEPTION
                    'Cannot change email template after campaign is scheduled'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER preserve_scheduled_campaign_template_0290
        BEFORE UPDATE OF email_template_id ON campaigns
        FOR EACH ROW
        EXECUTE FUNCTION preserve_scheduled_campaign_template_0290()
        """
    )
    op.execute(
        """
        CREATE FUNCTION pin_legacy_workflow_job_template_snapshot_0290()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            snapshot_payload jsonb;
        BEGIN
            IF NEW.job_type <> 'workflow_email'
               OR NEW.status NOT IN ('pending', 'running', 'failed')
               OR jsonb_typeof(NEW.payload) <> 'object'
               OR (
                   NEW.payload ? 'email_template_snapshot'
                   AND NEW.payload->'email_template_snapshot' <> 'null'::jsonb
               )
            THEN
                RETURN NEW;
            END IF;

            SELECT jsonb_build_object(
                'schema_version', 1,
                'organization_id', NEW.organization_id::text,
                'template_id', template.id::text,
                'template_version', template.current_version,
                'subject', template.subject,
                'body', template.body,
                'from_email', CASE
                    WHEN NEW.payload->>'workflow_scope' = 'personal'
                        THEN (
                            SELECT integration.account_email
                            FROM user_integrations AS integration
                            WHERE integration.user_id::text =
                                  NEW.payload->>'workflow_owner_id'
                              AND integration.integration_type = 'gmail'
                            LIMIT 1
                        )
                    WHEN NULLIF(btrim(template.from_email), '') IS NOT NULL
                     AND NULLIF(btrim(settings.from_name), '') IS NOT NULL
                     AND position('<' in template.from_email) = 0
                        THEN settings.from_name || ' <' || template.from_email || '>'
                    WHEN NULLIF(btrim(template.from_email), '') IS NOT NULL
                        THEN template.from_email
                    WHEN NULLIF(btrim(settings.from_email), '') IS NULL
                        THEN NULL
                    WHEN NULLIF(btrim(settings.from_name), '') IS NOT NULL
                        THEN settings.from_name || ' <' || settings.from_email || '>'
                    ELSE settings.from_email
                END,
                'scope', template.scope,
                'owner_user_id', template.owner_user_id::text,
                'system_key', template.system_key
            )
            INTO snapshot_payload
            FROM email_templates AS template
            LEFT JOIN resend_settings AS settings
              ON settings.organization_id = template.organization_id
            WHERE NEW.organization_id = template.organization_id
              AND NEW.payload->>'template_id' = template.id::text
              AND (
                  template.system_key IS NULL
                  OR template.system_key NOT IN ('org_invite', 'platform_update')
              );

            IF snapshot_payload IS NOT NULL THEN
                NEW.payload := jsonb_set(
                    NEW.payload,
                    '{email_template_snapshot}',
                    snapshot_payload,
                    true
                );
            ELSIF TG_OP = 'UPDATE'
                  AND OLD.status = 'failed'
                  AND NEW.status = 'pending'
            THEN
                RAISE EXCEPTION
                    'Cannot replay workflow email: queued template snapshot is unavailable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER pin_legacy_workflow_job_template_snapshot_0290
        BEFORE INSERT OR UPDATE OF status, payload, job_type, organization_id ON jobs
        FOR EACH ROW
        EXECUTE FUNCTION pin_legacy_workflow_job_template_snapshot_0290()
        """
    )

    # Workflow intents already carry their delivery data in JSONB. Transparently
    # add a published-template snapshot to unfinished legacy jobs in place.
    op.execute(
        sa.text(
            """
            UPDATE jobs AS job
            SET payload = jsonb_set(
                job.payload,
                '{email_template_snapshot}',
                jsonb_build_object(
                    'schema_version', 1,
                    'organization_id', job.organization_id::text,
                    'template_id', template.id::text,
                    'template_version', template.current_version,
                    'subject', template.subject,
                    'body', template.body,
                    'from_email', CASE
                        WHEN job.payload->>'workflow_scope' = 'personal'
                            THEN (
                                SELECT integration.account_email
                                FROM user_integrations AS integration
                                WHERE integration.user_id::text =
                                      job.payload->>'workflow_owner_id'
                                  AND integration.integration_type = 'gmail'
                                LIMIT 1
                            )
                        WHEN NULLIF(btrim(template.from_email), '') IS NOT NULL
                         AND NULLIF(btrim(settings.from_name), '') IS NOT NULL
                         AND position('<' in template.from_email) = 0
                            THEN settings.from_name || ' <' || template.from_email || '>'
                        WHEN NULLIF(btrim(template.from_email), '') IS NOT NULL
                            THEN template.from_email
                        WHEN NULLIF(btrim(settings.from_email), '') IS NULL
                            THEN NULL
                        WHEN NULLIF(btrim(settings.from_name), '') IS NOT NULL
                            THEN settings.from_name || ' <' || settings.from_email || '>'
                        ELSE settings.from_email
                    END,
                    'scope', template.scope,
                    'owner_user_id', template.owner_user_id::text,
                    'system_key', template.system_key
                ),
                true
            )
            FROM email_templates AS template
            LEFT JOIN resend_settings AS settings
              ON settings.organization_id = template.organization_id
            WHERE job.job_type = 'workflow_email'
              AND job.status IN ('pending', 'running', 'failed')
              AND job.organization_id = template.organization_id
              AND job.payload->>'template_id' = template.id::text
              AND (
                  template.system_key IS NULL
                  OR template.system_key NOT IN ('org_invite', 'platform_update')
              )
              AND (
                  NOT (job.payload ? 'email_template_snapshot')
                  OR job.payload->'email_template_snapshot' = 'null'::jsonb
              )
            """
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS pin_legacy_workflow_job_template_snapshot_0290 ON jobs")
    op.execute("DROP FUNCTION IF EXISTS pin_legacy_workflow_job_template_snapshot_0290()")
    op.execute("DROP TRIGGER IF EXISTS preserve_scheduled_campaign_template_0290 ON campaigns")
    op.execute("DROP FUNCTION IF EXISTS preserve_scheduled_campaign_template_0290()")
    op.execute(
        "DROP TRIGGER IF EXISTS pin_legacy_campaign_run_template_snapshot_0290 ON campaign_runs"
    )
    op.execute("DROP FUNCTION IF EXISTS pin_legacy_campaign_run_template_snapshot_0290()")
    op.execute(
        sa.text(
            """
            UPDATE jobs
            SET payload = payload - 'email_template_snapshot'
            WHERE job_type = 'workflow_email'
              AND payload ? 'email_template_snapshot'
            """
        )
    )
    op.drop_column("email_logs", "email_template_snapshot")
    op.drop_column("campaign_runs", "email_template_snapshot")
