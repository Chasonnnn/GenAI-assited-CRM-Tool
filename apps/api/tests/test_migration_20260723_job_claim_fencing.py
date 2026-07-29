"""Deployment-safety rehearsal for introducing fenced background-job claims."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
PRE_FENCING_REVISION = "20260723_0220"
FENCING_REVISION = "20260723_0230"
CHAIN_ROOT_MIGRATION_PATH = (
    API_ROOT / "alembic" / "versions" / "20260723_0048_add_resend_webhook_events.py"
)
FENCING_MIGRATION_PATH = (
    API_ROOT / "alembic" / "versions" / "20260723_0230_fence_reconciliation_jobs.py"
)

ORG_ID = uuid.UUID("71000000-0000-4000-8000-000000000001")
RUNNING_JOB_ID = uuid.UUID("72000000-0000-4000-8000-000000000001")
ORIGINAL_RUN_AT = datetime(2026, 7, 23, 17, 30, tzinfo=UTC)
ORIGINAL_ERROR = "old worker still owns this non-Resend job"


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def test_resend_chain_inherits_expansion_without_reowning_claim_columns() -> None:
    chain_root_source = CHAIN_ROOT_MIGRATION_PATH.read_text()
    fencing_source = FENCING_MIGRATION_PATH.read_text()

    assert 'down_revision = "20260725_1800"' in chain_root_source
    assert 'down_revision = "20260723_0220"' in fencing_source
    assert 'op.add_column(\n        "jobs"' not in fencing_source
    assert 'op.drop_column("jobs", "claimed_at")' not in fencing_source
    assert 'op.drop_column("jobs", "claim_token")' not in fencing_source
    assert "ck_jobs_claim_pair" not in fencing_source
    assert "ck_jobs_running_claimed" not in fencing_source
    assert "idx_jobs_stale_resend_reconciliation" in fencing_source


@pytest.mark.parametrize("job_type", ["notification", "resend_event_reconcile"])
def test_upgrade_preserves_tokenless_running_jobs_from_the_expansion(
    db_engine,
    job_type: str,
) -> None:
    """The schema cutover must wait until the old worker is fully drained."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            command.downgrade(config, PRE_FENCING_REVISION)

            connection.execute(
                text(
                    """
                    INSERT INTO organizations (id, name, slug)
                    VALUES (:id, :name, :slug)
                    """
                ),
                {
                    "id": ORG_ID,
                    "name": "Worker Fencing Migration Org",
                    "slug": "worker-fencing-migration-org",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO jobs (
                        id,
                        organization_id,
                        job_type,
                        payload,
                        run_at,
                        status,
                        attempts,
                        last_error
                    )
                    VALUES (
                        :id,
                        :organization_id,
                        :job_type,
                        CAST(:payload AS jsonb),
                        :run_at,
                        'running',
                        1,
                        :last_error
                    )
                    """
                ),
                {
                    "id": RUNNING_JOB_ID,
                    "organization_id": ORG_ID,
                    "job_type": job_type,
                    "payload": '{"source":"pre-upgrade-worker"}',
                    "run_at": ORIGINAL_RUN_AT,
                    "last_error": ORIGINAL_ERROR,
                },
            )

            command.upgrade(config, FENCING_REVISION)

            row = (
                connection.execute(
                    text(
                        """
                        SELECT status, run_at, attempts, last_error, claim_token, claimed_at
                        FROM jobs
                        WHERE id = :id
                        """
                    ),
                    {"id": RUNNING_JOB_ID},
                )
                .mappings()
                .one()
            )
            assert dict(row) == {
                "status": "running",
                "run_at": ORIGINAL_RUN_AT,
                "attempts": 1,
                "last_error": ORIGINAL_ERROR,
                "claim_token": None,
                "claimed_at": None,
            }
        finally:
            transaction.rollback()


def test_upgrade_keeps_rolling_legacy_claims_schema_compatible(db_engine) -> None:
    """The Resend index revision must not reject a still-rolling legacy worker."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            command.downgrade(config, PRE_FENCING_REVISION)

            connection.execute(
                text(
                    """
                    INSERT INTO organizations (id, name, slug)
                    VALUES (:id, :name, :slug)
                    """
                ),
                {
                    "id": ORG_ID,
                    "name": "Worker Fencing Migration Org",
                    "slug": "worker-fencing-migration-org",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO jobs (
                        id,
                        organization_id,
                        job_type,
                        payload,
                        run_at,
                        status,
                        attempts
                    )
                    VALUES (
                        :id,
                        :organization_id,
                        :job_type,
                        CAST(:payload AS jsonb),
                        :run_at,
                        'pending',
                        0
                    )
                    """
                ),
                {
                    "id": RUNNING_JOB_ID,
                    "organization_id": ORG_ID,
                    "job_type": "notification",
                    "payload": '{"source":"pre-upgrade-worker"}',
                    "run_at": ORIGINAL_RUN_AT,
                },
            )

            command.upgrade(config, FENCING_REVISION)

            connection.execute(
                text("UPDATE jobs SET status = 'running' WHERE id = :id"),
                {"id": RUNNING_JOB_ID},
            )
            row = (
                connection.execute(
                    text("SELECT status, claim_token, claimed_at FROM jobs WHERE id = :id"),
                    {"id": RUNNING_JOB_ID},
                )
                .mappings()
                .one()
            )
            assert dict(row) == {
                "status": "running",
                "claim_token": None,
                "claimed_at": None,
            }
        finally:
            transaction.rollback()
