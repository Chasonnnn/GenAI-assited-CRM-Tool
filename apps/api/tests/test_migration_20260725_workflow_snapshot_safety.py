"""Safety regressions for immutable workflow email snapshots."""

from __future__ import annotations

import json
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


API_ROOT = Path(__file__).resolve().parents[1]
PRE_SNAPSHOT_REVISION = "20260723_0280"
SNAPSHOT_MIGRATION = (
    API_ROOT / "alembic" / "versions" / "20260725_0290_pin_scheduled_email_templates.py"
)

ORG_ID = uuid.UUID("81000000-0000-4000-8000-000000000001")
OTHER_ORG_ID = uuid.UUID("81000000-0000-4000-8000-000000000002")
SYSTEM_TEMPLATE_ID = uuid.UUID("82000000-0000-4000-8000-000000000001")
NORMAL_TEMPLATE_ID = uuid.UUID("82000000-0000-4000-8000-000000000002")
SYSTEM_JOB_ID = uuid.UUID("83000000-0000-4000-8000-000000000001")
LEGACY_WORKFLOW_JOB_ID = uuid.UUID("83000000-0000-4000-8000-000000000002")
SUPPLIED_WORKFLOW_JOB_ID = uuid.UUID("83000000-0000-4000-8000-000000000003")
POST_MIGRATION_SYSTEM_JOB_ID = uuid.UUID("83000000-0000-4000-8000-000000000004")
CROSS_ORG_WORKFLOW_JOB_ID = uuid.UUID("83000000-0000-4000-8000-000000000005")
FAILED_WORKFLOW_JOB_ID = uuid.UUID("83000000-0000-4000-8000-000000000006")
FAILED_SYSTEM_WORKFLOW_JOB_ID = uuid.UUID("83000000-0000-4000-8000-000000000007")
NULL_SNAPSHOT_WORKFLOW_JOB_ID = uuid.UUID("83000000-0000-4000-8000-000000000008")
USER_ID = uuid.UUID("84000000-0000-4000-8000-000000000001")
CAMPAIGN_ID = uuid.UUID("85000000-0000-4000-8000-000000000001")
LEGACY_CAMPAIGN_RUN_ID = uuid.UUID("86000000-0000-4000-8000-000000000001")
SUPPLIED_CAMPAIGN_RUN_ID = uuid.UUID("86000000-0000-4000-8000-000000000002")
CROSS_ORG_CAMPAIGN_RUN_ID = uuid.UUID("86000000-0000-4000-8000-000000000003")


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def test_migration_locks_campaign_writes_before_snapshot_backfill() -> None:
    """No old-API campaign write can land between backfill and trigger creation."""
    migration_source = SNAPSHOT_MIGRATION.read_text()

    lock_offset = migration_source.index(
        "LOCK TABLE campaigns, campaign_runs IN SHARE ROW EXCLUSIVE MODE"
    )
    campaign_backfill_offset = migration_source.index("UPDATE campaign_runs AS run")
    campaign_trigger_offset = migration_source.index(
        "CREATE TRIGGER preserve_scheduled_campaign_template_0290"
    )

    assert lock_offset < campaign_backfill_offset < campaign_trigger_offset


def _seed_prohibited_workflow_job(connection) -> dict:
    connection.execute(
        text(
            """
            INSERT INTO organizations (id, name, slug)
            VALUES (:id, 'Snapshot Safety Org', 'snapshot-safety-org')
            """
        ),
        {"id": ORG_ID},
    )
    connection.execute(
        text(
            """
            INSERT INTO email_templates (
                id,
                organization_id,
                name,
                subject,
                body,
                from_email,
                is_active,
                scope,
                is_system_template,
                system_key,
                current_version
            )
            VALUES (
                :id,
                :organization_id,
                'Legacy Organization Invite',
                'Invitation to join {{org_name}}',
                '<p>Accept at {{invite_url}}</p>',
                'Platform <platform@example.test>',
                true,
                'org',
                true,
                'org_invite',
                7
            )
            """
        ),
        {"id": SYSTEM_TEMPLATE_ID, "organization_id": ORG_ID},
    )
    payload = {
        "template_id": str(SYSTEM_TEMPLATE_ID),
        "recipient_email": "must-not-send@example.test",
        "variables": {
            "org_name": "Snapshot Safety Org",
            "invite_url": "https://example.test/invite",
        },
        "workflow_scope": "org",
        "workflow_owner_id": None,
    }
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
            "id": SYSTEM_JOB_ID,
            "organization_id": ORG_ID,
            "payload": json.dumps(payload),
        },
    )
    return payload


def _seed_legacy_producer_inputs(connection) -> None:
    connection.execute(
        text(
            """
            INSERT INTO organizations (id, name, slug)
            VALUES
                (:id, 'Legacy Producer Org', 'legacy-producer-org'),
                (:other_id, 'Other Legacy Producer Org', 'other-legacy-producer-org')
            """
        ),
        {"id": ORG_ID, "other_id": OTHER_ORG_ID},
    )
    connection.execute(
        text(
            """
            INSERT INTO users (id, email, display_name)
            VALUES (:id, 'legacy-producer@example.test', 'Legacy Producer')
            """
        ),
        {"id": USER_ID},
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
                body,
                from_email,
                is_active,
                scope,
                is_system_template,
                system_key,
                current_version
            )
            VALUES
                (
                    :normal_id,
                    :organization_id,
                    :created_by_user_id,
                    'Legacy Producer Template',
                    'Pinned subject',
                    '<p>Pinned body</p>',
                    NULL,
                    true,
                    'org',
                    false,
                    NULL,
                    5
                ),
                (
                    :system_id,
                    :organization_id,
                    :created_by_user_id,
                    'Legacy Organization Invite',
                    'Invitation to join {{org_name}}',
                    '<p>Accept at {{invite_url}}</p>',
                    'Platform <platform@example.test>',
                    true,
                    'org',
                    true,
                    'org_invite',
                    7
                )
            """
        ),
        {
            "normal_id": NORMAL_TEMPLATE_ID,
            "system_id": SYSTEM_TEMPLATE_ID,
            "organization_id": ORG_ID,
            "created_by_user_id": USER_ID,
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
                'legacy-producer-write-only',
                'care@example.test',
                'Care Team',
                'example.test'
            )
            """
        ),
        {"organization_id": ORG_ID},
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
                'Legacy Producer Campaign',
                :template_id,
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
            "template_id": NORMAL_TEMPLATE_ID,
            "created_by_user_id": USER_ID,
        },
    )


@pytest.mark.asyncio
async def test_upgrade_preserves_prohibited_system_template_job_as_non_sendable(
    db_engine,
) -> None:
    """0290 must not turn a legacy platform/system intent into sendable bytes."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            command.downgrade(config, PRE_SNAPSHOT_REVISION)
            original_payload = _seed_prohibited_workflow_job(connection)

            command.upgrade(config, "head")

            row = connection.execute(
                text(
                    """
                    SELECT status, payload
                    FROM jobs
                    WHERE id = :id
                    """
                ),
                {"id": SYSTEM_JOB_ID},
            ).one()
            assert row.status == "pending"
            assert row.payload == original_payload

            from app.db.models import EmailLog, Job
            from app.jobs.handlers.email import process_workflow_email

            session = Session(bind=connection, join_transaction_mode="create_savepoint")
            try:
                job = session.query(Job).filter(Job.id == SYSTEM_JOB_ID).one()
                with pytest.raises(Exception, match="Platform system template 'org_invite'"):
                    await process_workflow_email(session, job)
                assert (
                    session.query(EmailLog)
                    .filter(
                        EmailLog.organization_id == ORG_ID,
                        EmailLog.source_type == "workflow_job",
                        EmailLog.source_id == SYSTEM_JOB_ID,
                    )
                    .count()
                    == 0
                )
            finally:
                session.close()
        finally:
            transaction.rollback()


def test_upgrade_snapshots_legacy_api_inserts_without_overwriting_new_payloads(
    db_engine,
) -> None:
    """0290 bridges migration-to-API rollout without reopening mutable sends."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            command.downgrade(config, PRE_SNAPSHOT_REVISION)
            _seed_legacy_producer_inputs(connection)
            command.upgrade(config, "head")

            supplied_campaign_snapshot = {
                "schema_version": 1,
                "organization_id": str(ORG_ID),
                "template_id": str(NORMAL_TEMPLATE_ID),
                "template_version": 99,
                "subject": "API supplied campaign subject",
                "body": "<p>API supplied campaign body</p>",
                "from_email": "API <api@example.test>",
            }
            connection.execute(
                text(
                    """
                    INSERT INTO campaign_runs (
                        id,
                        organization_id,
                        campaign_id,
                        status,
                        email_provider,
                        email_template_snapshot,
                        total_count,
                        sent_count,
                        delivered_count,
                        failed_count,
                        skipped_count,
                        opened_count,
                        clicked_count
                    )
                    VALUES
                        (
                            :legacy_id,
                            :organization_id,
                            :campaign_id,
                            'running',
                            'resend',
                            NULL,
                            0, 0, 0, 0, 0, 0, 0
                        ),
                        (
                            :supplied_id,
                            :organization_id,
                            :campaign_id,
                            'running',
                            'resend',
                            CAST(:supplied_snapshot AS jsonb),
                            0, 0, 0, 0, 0, 0, 0
                        ),
                        (
                            :cross_org_id,
                            :other_organization_id,
                            :campaign_id,
                            'running',
                            'resend',
                            NULL,
                            0, 0, 0, 0, 0, 0, 0
                        )
                    """
                ),
                {
                    "legacy_id": LEGACY_CAMPAIGN_RUN_ID,
                    "supplied_id": SUPPLIED_CAMPAIGN_RUN_ID,
                    "cross_org_id": CROSS_ORG_CAMPAIGN_RUN_ID,
                    "organization_id": ORG_ID,
                    "other_organization_id": OTHER_ORG_ID,
                    "campaign_id": CAMPAIGN_ID,
                    "supplied_snapshot": json.dumps(supplied_campaign_snapshot),
                },
            )

            supplied_workflow_snapshot = {
                "schema_version": 1,
                "organization_id": str(ORG_ID),
                "template_id": str(NORMAL_TEMPLATE_ID),
                "template_version": 99,
                "subject": "API supplied workflow subject",
                "body": "<p>API supplied workflow body</p>",
                "from_email": "API <api@example.test>",
                "scope": "org",
                "owner_user_id": None,
                "system_key": None,
            }
            base_payload = {
                "recipient_email": "legacy-insert@example.test",
                "variables": {},
                "workflow_scope": "org",
                "workflow_owner_id": None,
            }
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
                    VALUES
                        (
                            :legacy_id,
                            'organization',
                            :organization_id,
                            'workflow_email',
                            CAST(:legacy_payload AS jsonb),
                            'pending',
                            now() + interval '1 hour'
                        ),
                        (
                            :supplied_id,
                            'organization',
                            :organization_id,
                            'workflow_email',
                            CAST(:supplied_payload AS jsonb),
                            'pending',
                            now() + interval '1 hour'
                        ),
                        (
                            :system_id,
                            'organization',
                            :organization_id,
                            'workflow_email',
                            CAST(:system_payload AS jsonb),
                            'pending',
                            now() + interval '1 hour'
                        ),
                        (
                            :cross_org_id,
                            'organization',
                            :other_organization_id,
                            'workflow_email',
                            CAST(:legacy_payload AS jsonb),
                            'pending',
                            now() + interval '1 hour'
                        )
                    """
                ),
                {
                    "legacy_id": LEGACY_WORKFLOW_JOB_ID,
                    "supplied_id": SUPPLIED_WORKFLOW_JOB_ID,
                    "system_id": POST_MIGRATION_SYSTEM_JOB_ID,
                    "cross_org_id": CROSS_ORG_WORKFLOW_JOB_ID,
                    "organization_id": ORG_ID,
                    "other_organization_id": OTHER_ORG_ID,
                    "legacy_payload": json.dumps(
                        {"template_id": str(NORMAL_TEMPLATE_ID), **base_payload}
                    ),
                    "supplied_payload": json.dumps(
                        {
                            "template_id": str(NORMAL_TEMPLATE_ID),
                            **base_payload,
                            "email_template_snapshot": supplied_workflow_snapshot,
                        }
                    ),
                    "system_payload": json.dumps(
                        {"template_id": str(SYSTEM_TEMPLATE_ID), **base_payload}
                    ),
                },
            )

            campaign_snapshots = {
                row.id: row.email_template_snapshot
                for row in connection.execute(
                    text(
                        """
                        SELECT id, email_template_snapshot
                        FROM campaign_runs
                            WHERE id IN (:legacy_id, :supplied_id, :cross_org_id)
                        """
                    ),
                    {
                        "legacy_id": LEGACY_CAMPAIGN_RUN_ID,
                        "supplied_id": SUPPLIED_CAMPAIGN_RUN_ID,
                        "cross_org_id": CROSS_ORG_CAMPAIGN_RUN_ID,
                    },
                )
            }
            assert campaign_snapshots[LEGACY_CAMPAIGN_RUN_ID] == {
                "schema_version": 1,
                "organization_id": str(ORG_ID),
                "template_id": str(NORMAL_TEMPLATE_ID),
                "template_version": 5,
                "subject": "Pinned subject",
                "body": "<p>Pinned body</p>",
                "from_email": "Care Team <care@example.test>",
            }
            assert campaign_snapshots[SUPPLIED_CAMPAIGN_RUN_ID] == supplied_campaign_snapshot
            assert campaign_snapshots[CROSS_ORG_CAMPAIGN_RUN_ID] is None

            job_payloads = {
                row.id: row.payload
                for row in connection.execute(
                    text(
                        """
                        SELECT id, payload
                        FROM jobs
                        WHERE id IN (:legacy_id, :supplied_id, :system_id, :cross_org_id)
                        """
                    ),
                    {
                        "legacy_id": LEGACY_WORKFLOW_JOB_ID,
                        "supplied_id": SUPPLIED_WORKFLOW_JOB_ID,
                        "system_id": POST_MIGRATION_SYSTEM_JOB_ID,
                        "cross_org_id": CROSS_ORG_WORKFLOW_JOB_ID,
                    },
                )
            }
            assert job_payloads[LEGACY_WORKFLOW_JOB_ID]["email_template_snapshot"] == {
                "schema_version": 1,
                "organization_id": str(ORG_ID),
                "template_id": str(NORMAL_TEMPLATE_ID),
                "template_version": 5,
                "subject": "Pinned subject",
                "body": "<p>Pinned body</p>",
                "from_email": "Care Team <care@example.test>",
                "scope": "org",
                "owner_user_id": None,
                "system_key": None,
            }
            assert (
                job_payloads[SUPPLIED_WORKFLOW_JOB_ID]["email_template_snapshot"]
                == supplied_workflow_snapshot
            )
            assert "email_template_snapshot" not in job_payloads[POST_MIGRATION_SYSTEM_JOB_ID]
            assert "email_template_snapshot" not in job_payloads[CROSS_ORG_WORKFLOW_JOB_ID]
        finally:
            transaction.rollback()


def test_upgrade_pins_failed_workflow_jobs_before_dlq_replay(db_engine) -> None:
    """Failed legacy intents keep their migration-time bytes or fail closed."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            command.downgrade(config, PRE_SNAPSHOT_REVISION)
            _seed_legacy_producer_inputs(connection)

            base_payload = {
                "recipient_email": "legacy-replay@example.test",
                "variables": {},
                "workflow_scope": "org",
                "workflow_owner_id": None,
            }
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
                        run_at,
                        attempts,
                        max_attempts,
                        last_error
                    )
                    VALUES
                        (
                            :normal_id,
                            'organization',
                            :organization_id,
                            'workflow_email',
                            CAST(:normal_payload AS jsonb),
                            'failed',
                            now() - interval '1 hour',
                            3,
                            3,
                            'provider timeout'
                        ),
                        (
                            :system_id,
                            'organization',
                            :organization_id,
                            'workflow_email',
                            CAST(:system_payload AS jsonb),
                            'failed',
                            now() - interval '1 hour',
                            3,
                            3,
                            'unsafe legacy intent'
                        ),
                        (
                            :null_snapshot_id,
                            'organization',
                            :organization_id,
                            'workflow_email',
                            CAST(:null_snapshot_payload AS jsonb),
                            'failed',
                            now() - interval '1 hour',
                            3,
                            3,
                            'legacy null snapshot'
                        )
                    """
                ),
                {
                    "normal_id": FAILED_WORKFLOW_JOB_ID,
                    "system_id": FAILED_SYSTEM_WORKFLOW_JOB_ID,
                    "null_snapshot_id": NULL_SNAPSHOT_WORKFLOW_JOB_ID,
                    "organization_id": ORG_ID,
                    "normal_payload": json.dumps(
                        {"template_id": str(NORMAL_TEMPLATE_ID), **base_payload}
                    ),
                    "system_payload": json.dumps(
                        {"template_id": str(SYSTEM_TEMPLATE_ID), **base_payload}
                    ),
                    "null_snapshot_payload": json.dumps(
                        {
                            "template_id": str(NORMAL_TEMPLATE_ID),
                            **base_payload,
                            "email_template_snapshot": None,
                        }
                    ),
                },
            )

            command.upgrade(config, "head")
            connection.execute(
                text(
                    """
                    UPDATE email_templates
                    SET subject = 'Edited after deployment',
                        body = '<p>Edited after deployment</p>',
                        current_version = current_version + 1
                    WHERE id = :id
                    """
                ),
                {"id": NORMAL_TEMPLATE_ID},
            )

            from app.db.models import Job
            from app.services import job_service

            session = Session(bind=connection, join_transaction_mode="create_savepoint")
            try:
                replayed = job_service.replay_failed_job(
                    session,
                    org_id=ORG_ID,
                    job_id=FAILED_WORKFLOW_JOB_ID,
                )
                assert replayed.status == "pending"
                assert replayed.payload["email_template_snapshot"]["subject"] == "Pinned subject"
                assert replayed.payload["email_template_snapshot"]["body"] == "<p>Pinned body</p>"
                assert replayed.payload["email_template_snapshot"]["template_version"] == 5

                replayed_null_snapshot = job_service.replay_failed_job(
                    session,
                    org_id=ORG_ID,
                    job_id=NULL_SNAPSHOT_WORKFLOW_JOB_ID,
                )
                assert replayed_null_snapshot.status == "pending"
                assert (
                    replayed_null_snapshot.payload["email_template_snapshot"]["subject"]
                    == "Pinned subject"
                )
                assert (
                    replayed_null_snapshot.payload["email_template_snapshot"]["template_version"]
                    == 5
                )

                unsafe_job = (
                    session.query(Job).filter(Job.id == FAILED_SYSTEM_WORKFLOW_JOB_ID).one()
                )
                assert "email_template_snapshot" not in unsafe_job.payload
                with pytest.raises(
                    ValueError,
                    match="queued template snapshot is unavailable",
                ):
                    job_service.replay_failed_job(
                        session,
                        org_id=ORG_ID,
                        job_id=FAILED_SYSTEM_WORKFLOW_JOB_ID,
                    )
                assert unsafe_job.status == "failed"

                with pytest.raises(
                    DBAPIError,
                    match="queued template snapshot is unavailable",
                ):
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                """
                                UPDATE jobs
                                SET status = 'pending'
                                WHERE id = :id
                                """
                            ),
                            {"id": FAILED_SYSTEM_WORKFLOW_JOB_ID},
                        )
            finally:
                session.close()
        finally:
            transaction.rollback()


def test_upgrade_blocks_legacy_api_template_changes_for_scheduled_campaigns(
    db_engine,
) -> None:
    """The database closes the migration-to-new-API campaign mutation window."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            command.downgrade(config, PRE_SNAPSHOT_REVISION)
            _seed_legacy_producer_inputs(connection)
            command.upgrade(config, "head")

            with pytest.raises(
                DBAPIError,
                match="Cannot change email template after campaign is scheduled",
            ):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            """
                            UPDATE campaigns
                            SET email_template_id = :replacement_template_id
                            WHERE id = :campaign_id
                              AND organization_id = :organization_id
                            """
                        ),
                        {
                            "replacement_template_id": SYSTEM_TEMPLATE_ID,
                            "campaign_id": CAMPAIGN_ID,
                            "organization_id": ORG_ID,
                        },
                    )

            assert (
                connection.scalar(
                    text("SELECT email_template_id FROM campaigns WHERE id = :id"),
                    {"id": CAMPAIGN_ID},
                )
                == NORMAL_TEMPLATE_ID
            )
        finally:
            transaction.rollback()
