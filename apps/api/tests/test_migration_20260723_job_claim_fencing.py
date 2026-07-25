"""Deployment-safety rehearsal for introducing fenced background-job claims."""

from datetime import datetime, timezone
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError


API_ROOT = Path(__file__).resolve().parents[1]
PRE_FENCING_REVISION = "20260723_0220"
FENCING_REVISION = "20260723_0230"

ORG_ID = uuid.UUID("71000000-0000-4000-8000-000000000001")
RUNNING_JOB_ID = uuid.UUID("72000000-0000-4000-8000-000000000001")
ORIGINAL_RUN_AT = datetime(2026, 7, 23, 17, 30, tzinfo=timezone.utc)
ORIGINAL_ERROR = "old worker still owns this non-Resend job"


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


@pytest.mark.parametrize("job_type", ["notification", "resend_event_reconcile"])
def test_upgrade_refuses_to_cut_over_while_an_old_worker_owns_a_job(
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

            with pytest.raises(DBAPIError, match="drain the old worker"):
                command.upgrade(config, FENCING_REVISION)
        finally:
            transaction.rollback()


def test_upgrade_blocks_pre_fencing_workers_from_claiming_new_jobs(db_engine) -> None:
    """An old worker cannot claim work during the migration-to-worker cutover gap."""
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

            with pytest.raises(IntegrityError, match="ck_jobs_running_claimed"):
                connection.execute(
                    text("UPDATE jobs SET status = 'running' WHERE id = :id"),
                    {"id": RUNNING_JOB_ID},
                )
        finally:
            transaction.rollback()
