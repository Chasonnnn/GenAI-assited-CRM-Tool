"""Compatibility rehearsal for expanding background-job claim metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


API_ROOT = Path(__file__).resolve().parents[1]
PRE_EXPANSION_REVISION = "20260701_1025"
EXPANSION_REVISION = "20260725_1800"
MIGRATION_PATH = API_ROOT / "alembic" / "versions" / "20260725_1800_expand_job_claim_metadata.py"

ORG_ID = uuid.UUID("71000000-0000-4000-8000-000000000001")
RUNNING_JOB_ID = uuid.UUID("72000000-0000-4000-8000-000000000001")
ORIGINAL_RUN_AT = datetime(2026, 5, 20, 5, 4, tzinfo=timezone.utc)


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def test_expansion_preserves_legacy_running_claim_and_remains_rolling_compatible(
    db_engine,
) -> None:
    database_name = f"test_job_claim_expansion_{uuid.uuid4().hex}"
    quoted_database = f'"{database_name}"'
    admin_engine = create_engine(db_engine.url.set(database="postgres"), poolclass=NullPool)
    isolated_engine = create_engine(
        db_engine.url.set(database=database_name),
        poolclass=NullPool,
    )

    with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text(f"CREATE DATABASE {quoted_database}"))

    try:
        with isolated_engine.connect() as connection:
            config = _alembic_config(connection)
            command.upgrade(config, PRE_EXPANSION_REVISION)

            connection.execute(
                text(
                    """
                    INSERT INTO organizations (id, name, slug)
                    VALUES (:id, :name, :slug)
                    """
                ),
                {
                    "id": ORG_ID,
                    "name": "Worker Claim Expansion Org",
                    "slug": "worker-claim-expansion-org",
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
                        max_attempts,
                        last_error,
                        idempotency_key
                    )
                    VALUES (
                        :id,
                        :organization_id,
                        'workflow_email',
                        CAST(:payload AS jsonb),
                        :run_at,
                        'running',
                        1,
                        3,
                        :last_error,
                        :idempotency_key
                    )
                    """
                ),
                {
                    "id": RUNNING_JOB_ID,
                    "organization_id": ORG_ID,
                    "payload": '{"source":"pre-expansion-worker"}',
                    "run_at": ORIGINAL_RUN_AT,
                    "last_error": "legacy claim still has an unknown outcome",
                    "idempotency_key": "legacy-workflow-email:test",
                },
            )
            connection.commit()

            command.upgrade(config, EXPANSION_REVISION)

            row = (
                connection.execute(
                    text(
                        """
                        SELECT
                            status,
                            payload,
                            run_at,
                            attempts,
                            max_attempts,
                            last_error,
                            idempotency_key,
                            claim_token,
                            claimed_at
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
                "payload": {"source": "pre-expansion-worker"},
                "run_at": ORIGINAL_RUN_AT,
                "attempts": 1,
                "max_attempts": 3,
                "last_error": "legacy claim still has an unknown outcome",
                "idempotency_key": "legacy-workflow-email:test",
                "claim_token": None,
                "claimed_at": None,
            }

            constraints = set(
                connection.execute(
                    text(
                        """
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid = 'jobs'::regclass
                        """
                    )
                ).scalars()
            )
            assert "ck_jobs_claim_pair" not in constraints
            assert "ck_jobs_running_claimed" not in constraints

            indexes = set(
                connection.execute(
                    text(
                        """
                        SELECT indexname
                        FROM pg_indexes
                        WHERE schemaname = current_schema()
                          AND tablename = 'jobs'
                        """
                    )
                ).scalars()
            )
            assert "idx_jobs_stale_claims" not in indexes

            command.downgrade(config, PRE_EXPANSION_REVISION)
            columns = set(
                connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = 'jobs'
                        """
                    )
                ).scalars()
            )
            assert "claim_token" not in columns
            assert "claimed_at" not in columns
    finally:
        isolated_engine.dispose()
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {quoted_database}"))
        admin_engine.dispose()


def test_expansion_sets_a_short_lock_timeout_before_schema_changes() -> None:
    source = MIGRATION_PATH.read_text()

    lock_timeout = "op.execute(\"SET LOCAL lock_timeout = '5s'\")"
    assert lock_timeout in source
    assert source.index(lock_timeout) < source.index("op.add_column")
