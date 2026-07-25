"""Production-shaped preservation rehearsal for the Email Template Studio migration."""

import json
import logging
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import text


API_ROOT = Path(__file__).resolve().parents[1]
PRE_STUDIO_REVISION = "20260723_0270"
STUDIO_REVISION = "20260723_0280"
PINNED_SEND_REVISION = "20260725_0290"

ORG_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
ORG_TEMPLATE_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
PERSONAL_TEMPLATE_ID = uuid.UUID("30000000-0000-0000-0000-000000000002")
PLATFORM_TEMPLATE_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")
SYSTEM_TEMPLATE_KEY = "studio_migration_preservation_rehearsal"
CAMPAIGN_ID = uuid.UUID("50000000-0000-0000-0000-000000000001")
CAMPAIGN_RUN_ID = uuid.UUID("50000000-0000-0000-0000-000000000002")
WORKFLOW_JOB_ID = uuid.UUID("60000000-0000-0000-0000-000000000001")
PERSONAL_WORKFLOW_JOB_ID = uuid.UUID("60000000-0000-0000-0000-000000000002")

ORG_BODY = (
    "<section>\r\n"
    "  <h1>Existing organization template — 保留</h1>\r\n"
    "  <p>Hello {{surrogate.first_name}} 👋</p>  \r\n"
    "</section>"
)
PERSONAL_BODY = (
    '<div data-owner="existing-user">\n'
    "\t<p>Personal draft-free template &amp; signature: {{user.signature}}</p>\n"
    "</div> "
)
PLATFORM_BODY = "<main>\n  <p>Ops working copy: {{organization.name}}</p>\n</main>\n"
PLATFORM_PUBLISHED_BODY = (
    "<main>\r\n  <p>Published ops snapshot v6 — immutable until publish.</p>\r\n</main>"
)
SYSTEM_BODY = (
    "<html><body>\n<p>System notification: {{recipient.display_name}}</p>\n</body></html>\n"
)


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def _seed_pre_studio_templates(connection) -> None:
    connection.execute(
        text(
            """
            INSERT INTO organizations (id, name, slug)
            VALUES (:id, :name, :slug)
            """
        ),
        {
            "id": ORG_ID,
            "name": "Studio Migration Preservation Org",
            "slug": "studio-migration-preservation-org",
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO users (id, email, display_name)
            VALUES (:id, :email, :display_name)
            """
        ),
        {
            "id": USER_ID,
            "email": "studio-migration-preservation@example.test",
            "display_name": "Existing Template Owner",
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO email_templates (
                id,
                organization_id,
                created_by_user_id,
                name,
                subject,
                from_email,
                body,
                is_active,
                scope,
                owner_user_id,
                source_template_id,
                is_system_template,
                system_key,
                category,
                current_version
            )
            VALUES (
                :id,
                :organization_id,
                :created_by_user_id,
                :name,
                :subject,
                :from_email,
                :body,
                :is_active,
                :scope,
                :owner_user_id,
                :source_template_id,
                :is_system_template,
                :system_key,
                :category,
                :current_version
            )
            """
        ),
        [
            {
                "id": ORG_TEMPLATE_ID,
                "organization_id": ORG_ID,
                "created_by_user_id": USER_ID,
                "name": "Existing Org Welcome",
                "subject": "Welcome, {{surrogate.first_name}} — next steps",
                "from_email": "Surrogacy Force <care+legacy@example.test>",
                "body": ORG_BODY,
                "is_active": True,
                "scope": "org",
                "owner_user_id": None,
                "source_template_id": None,
                "is_system_template": False,
                "system_key": None,
                "category": "welcome",
                "current_version": 9,
            },
            {
                "id": PERSONAL_TEMPLATE_ID,
                "organization_id": ORG_ID,
                "created_by_user_id": USER_ID,
                "name": "Existing Personal Follow-up",
                "subject": "A personal follow-up for {{surrogate.first_name}}",
                "from_email": "Existing Owner <owner+legacy@example.test>",
                "body": PERSONAL_BODY,
                "is_active": False,
                "scope": "personal",
                "owner_user_id": USER_ID,
                "source_template_id": ORG_TEMPLATE_ID,
                "is_system_template": False,
                "system_key": None,
                "category": "follow_up",
                "current_version": 4,
            },
        ],
    )
    connection.execute(
        text(
            """
            INSERT INTO user_integrations (
                user_id,
                integration_type,
                access_token_encrypted,
                account_email
            )
            VALUES (
                :user_id,
                'gmail',
                :access_token_encrypted,
                :account_email
            )
            """
        ),
        {
            "user_id": USER_ID,
            "access_token_encrypted": "migration-rehearsal-token",
            "account_email": "existing-owner@gmail.example.test",
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO resend_settings (
                organization_id,
                email_provider,
                api_key_encrypted,
                from_email,
                from_name,
                verified_domain
            )
            VALUES (
                :organization_id,
                'resend',
                :api_key_encrypted,
                :from_email,
                :from_name,
                :verified_domain
            )
            """
        ),
        {
            "organization_id": ORG_ID,
            "api_key_encrypted": "migration-rehearsal-write-only",
            "from_email": "fallback@example.test",
            "from_name": "Fallback Team",
            "verified_domain": "example.test",
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO jobs (
                id,
                job_scope,
                organization_id,
                job_type,
                payload,
                status,
                run_at
            )
            VALUES (
                :id,
                'organization',
                :organization_id,
                'workflow_email',
                CAST(:payload AS jsonb),
                'pending',
                now() + interval '1 hour'
            )
            """
        ),
        {
            "id": PERSONAL_WORKFLOW_JOB_ID,
            "organization_id": ORG_ID,
            "payload": json.dumps(
                {
                    "template_id": str(ORG_TEMPLATE_ID),
                    "recipient_email": "personal-org-template@example.test",
                    "variables": {"surrogate.first_name": "Personal"},
                    "workflow_scope": "personal",
                    "workflow_owner_id": str(USER_ID),
                }
            ),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO campaigns (
                id,
                organization_id,
                name,
                email_template_id,
                recipient_type,
                filter_criteria,
                scheduled_at,
                status,
                created_by_user_id
            )
            VALUES (
                :id,
                :organization_id,
                :name,
                :email_template_id,
                'case',
                '{}'::jsonb,
                now() + interval '2 hours',
                'scheduled',
                :created_by_user_id
            )
            """
        ),
        {
            "id": CAMPAIGN_ID,
            "organization_id": ORG_ID,
            "name": "Existing Scheduled Campaign",
            "email_template_id": ORG_TEMPLATE_ID,
            "created_by_user_id": USER_ID,
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO campaign_runs (
                id,
                organization_id,
                campaign_id,
                status,
                email_provider,
                total_count,
                sent_count,
                delivered_count,
                failed_count,
                skipped_count,
                opened_count,
                clicked_count
            )
            VALUES (
                :id,
                :organization_id,
                :campaign_id,
                'running',
                'resend',
                0,
                0,
                0,
                0,
                0,
                0,
                0
            )
            """
        ),
        {
            "id": CAMPAIGN_RUN_ID,
            "organization_id": ORG_ID,
            "campaign_id": CAMPAIGN_ID,
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO jobs (
                id,
                job_scope,
                organization_id,
                job_type,
                payload,
                status,
                run_at
            )
            VALUES (
                :id,
                'organization',
                :organization_id,
                'workflow_email',
                CAST(:payload AS jsonb),
                'pending',
                now() + interval '1 hour'
            )
            """
        ),
        {
            "id": WORKFLOW_JOB_ID,
            "organization_id": ORG_ID,
            "payload": json.dumps(
                {
                    "template_id": str(ORG_TEMPLATE_ID),
                    "recipient_email": "existing-queued@example.test",
                    "variables": {"surrogate.first_name": "Existing"},
                    "workflow_scope": "org",
                    "workflow_owner_id": None,
                }
            ),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO platform_email_templates (
                id,
                name,
                subject,
                body,
                from_email,
                category,
                published_name,
                published_subject,
                published_body,
                published_from_email,
                published_category,
                status,
                current_version,
                published_version,
                is_published_globally
            )
            VALUES (
                :id,
                :name,
                :subject,
                :body,
                :from_email,
                :category,
                :published_name,
                :published_subject,
                :published_body,
                :published_from_email,
                :published_category,
                :status,
                :current_version,
                :published_version,
                :is_published_globally
            )
            """
        ),
        {
            "id": PLATFORM_TEMPLATE_ID,
            "name": "Existing Ops Invite Draft",
            "subject": "Ops draft subject — v7",
            "body": PLATFORM_BODY,
            "from_email": "Ops Draft <ops-draft@example.test>",
            "category": "organization_invite",
            "published_name": "Existing Ops Invite Published",
            "published_subject": "Ops published subject — v6",
            "published_body": PLATFORM_PUBLISHED_BODY,
            "published_from_email": "Ops Published <ops@example.test>",
            "published_category": "organization_invite",
            "status": "published",
            "current_version": 7,
            "published_version": 6,
            "is_published_globally": True,
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO platform_system_email_templates (
                system_key,
                name,
                subject,
                body,
                from_email,
                is_active,
                current_version
            )
            VALUES (
                :system_key,
                :name,
                :subject,
                :body,
                :from_email,
                :is_active,
                :current_version
            )
            """
        ),
        {
            "system_key": SYSTEM_TEMPLATE_KEY,
            "name": "Existing System Notification",
            "subject": "System notice — action required",
            "body": SYSTEM_BODY,
            "from_email": "Surrogacy Force System <system@example.test>",
            "is_active": True,
            "current_version": 12,
        },
    )


def _template_fingerprints(connection) -> dict[str, list[tuple]]:
    """Return byte-oriented fingerprints for the production template stores."""
    return {
        "email_templates": [
            tuple(row)
            for row in connection.execute(
                text(
                    """
                    SELECT
                        id,
                        organization_id,
                        created_by_user_id,
                        convert_to(name, 'UTF8'),
                        convert_to(subject, 'UTF8'),
                        convert_to(from_email, 'UTF8'),
                        convert_to(body, 'UTF8'),
                        is_active,
                        convert_to(scope, 'UTF8'),
                        owner_user_id,
                        source_template_id,
                        is_system_template,
                        system_key,
                        convert_to(category, 'UTF8'),
                        current_version
                    FROM email_templates
                    WHERE id IN (:org_id, :personal_id)
                    ORDER BY id
                    """
                ),
                {
                    "org_id": ORG_TEMPLATE_ID,
                    "personal_id": PERSONAL_TEMPLATE_ID,
                },
            )
        ],
        "platform_email_templates": [
            tuple(row)
            for row in connection.execute(
                text(
                    """
                    SELECT
                        id,
                        convert_to(name, 'UTF8'),
                        convert_to(subject, 'UTF8'),
                        convert_to(body, 'UTF8'),
                        convert_to(from_email, 'UTF8'),
                        convert_to(category, 'UTF8'),
                        convert_to(published_name, 'UTF8'),
                        convert_to(published_subject, 'UTF8'),
                        convert_to(published_body, 'UTF8'),
                        convert_to(published_from_email, 'UTF8'),
                        convert_to(published_category, 'UTF8'),
                        convert_to(status, 'UTF8'),
                        current_version,
                        published_version,
                        is_published_globally
                    FROM platform_email_templates
                    WHERE id = :id
                    """
                ),
                {"id": PLATFORM_TEMPLATE_ID},
            )
        ],
        "platform_system_email_templates": [
            tuple(row)
            for row in connection.execute(
                text(
                    """
                    SELECT
                        convert_to(system_key, 'UTF8'),
                        convert_to(name, 'UTF8'),
                        convert_to(subject, 'UTF8'),
                        convert_to(body, 'UTF8'),
                        convert_to(from_email, 'UTF8'),
                        is_active,
                        current_version
                    FROM platform_system_email_templates
                    WHERE system_key = :system_key
                    """
                ),
                {"system_key": SYSTEM_TEMPLATE_KEY},
            )
        ],
    }


def test_template_studio_upgrade_preserves_existing_template_stores(db_engine) -> None:
    """Studio and queued-send snapshots preserve every published template byte."""
    ops_logger = logging.getLogger("app.ops")
    ops_logger.disabled = False

    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, STUDIO_REVISION)
            command.downgrade(config, PRE_STUDIO_REVISION)

            assert connection.scalar(text("SELECT to_regclass('email_template_drafts')")) is None

            _seed_pre_studio_templates(connection)
            before_upgrade = _template_fingerprints(connection)

            assert [row[0] for row in before_upgrade["email_templates"]] == [
                ORG_TEMPLATE_ID,
                PERSONAL_TEMPLATE_ID,
            ]
            assert before_upgrade["email_templates"][0][6] == ORG_BODY.encode()
            assert before_upgrade["email_templates"][1][6] == PERSONAL_BODY.encode()
            assert before_upgrade["email_templates"][1][10] == ORG_TEMPLATE_ID
            assert before_upgrade["platform_email_templates"][0][0] == PLATFORM_TEMPLATE_ID
            assert before_upgrade["platform_email_templates"][0][3] == PLATFORM_BODY.encode()
            assert (
                before_upgrade["platform_email_templates"][0][8] == PLATFORM_PUBLISHED_BODY.encode()
            )
            assert before_upgrade["platform_system_email_templates"][0][0] == (
                SYSTEM_TEMPLATE_KEY.encode()
            )
            assert before_upgrade["platform_system_email_templates"][0][3] == (SYSTEM_BODY.encode())

            command.upgrade(config, "head")

            assert _template_fingerprints(connection) == before_upgrade
            assert connection.scalar(text("SELECT count(*) FROM email_template_drafts")) == 0
            campaign_snapshot = connection.scalar(
                text(
                    """
                    SELECT email_template_snapshot
                    FROM campaign_runs
                    WHERE id = :id
                    """
                ),
                {"id": CAMPAIGN_RUN_ID},
            )
            assert campaign_snapshot == {
                "schema_version": 1,
                "organization_id": str(ORG_ID),
                "template_id": str(ORG_TEMPLATE_ID),
                "template_version": 9,
                "subject": "Welcome, {{surrogate.first_name}} — next steps",
                "body": ORG_BODY,
                "from_email": "Surrogacy Force <care+legacy@example.test>",
            }
            workflow_snapshot = connection.scalar(
                text(
                    """
                    SELECT payload->'email_template_snapshot'
                    FROM jobs
                    WHERE id = :id
                    """
                ),
                {"id": WORKFLOW_JOB_ID},
            )
            assert workflow_snapshot == {
                "schema_version": 1,
                "organization_id": str(ORG_ID),
                "template_id": str(ORG_TEMPLATE_ID),
                "template_version": 9,
                "subject": "Welcome, {{surrogate.first_name}} — next steps",
                "body": ORG_BODY,
                "from_email": "Surrogacy Force <care+legacy@example.test>",
                "scope": "org",
                "owner_user_id": None,
                "system_key": None,
            }
            personal_workflow_snapshot = connection.scalar(
                text(
                    """
                    SELECT payload->'email_template_snapshot'
                    FROM jobs
                    WHERE id = :id
                    """
                ),
                {"id": PERSONAL_WORKFLOW_JOB_ID},
            )
            assert personal_workflow_snapshot == {
                "schema_version": 1,
                "organization_id": str(ORG_ID),
                "template_id": str(ORG_TEMPLATE_ID),
                "template_version": 9,
                "subject": "Welcome, {{surrogate.first_name}} — next steps",
                "body": ORG_BODY,
                "from_email": "existing-owner@gmail.example.test",
                "scope": "org",
                "owner_user_id": None,
                "system_key": None,
            }
            assert (
                connection.scalar(
                    text(
                        """
                        SELECT count(*)
                        FROM information_schema.columns
                        WHERE table_name = 'email_logs'
                          AND column_name = 'email_template_snapshot'
                        """
                    )
                )
                == 1
            )
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == PINNED_SEND_REVISION
            )
        finally:
            transaction.rollback()

    assert ops_logger.disabled is False
