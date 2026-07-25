"""Production-shaped preservation rehearsal for the Email Template Studio migration."""

import logging
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import text


API_ROOT = Path(__file__).resolve().parents[1]
PRE_STUDIO_REVISION = "20260723_0270"
STUDIO_REVISION = "20260723_0280"

ORG_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
ORG_TEMPLATE_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
PERSONAL_TEMPLATE_ID = uuid.UUID("30000000-0000-0000-0000-000000000002")
PLATFORM_TEMPLATE_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")
SYSTEM_TEMPLATE_KEY = "studio_migration_preservation_rehearsal"

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
    """Revision 0280 adds drafts without rewriting any published template store."""
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
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == STUDIO_REVISION
            )
        finally:
            transaction.rollback()

    assert ops_logger.disabled is False
