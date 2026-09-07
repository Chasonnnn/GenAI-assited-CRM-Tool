"""Clone-only ASGI availability probe; no lifespan or provider execution.

Run separate processes with PROBE_CODE_ROOT=/old and /app. The former disables
migration-head checking; the latter enables it. Only aggregate results are emitted.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from threading import Event

OUTPUT = sys.stdout
CLONE_HOST = "10.9.0.14"
CLONE_DATABASE = "crm"
TARGET = "crm-match-rehearsal-0906"
LOCK_SECONDS = 1.25


def emit(event: str, **fields) -> None:
    OUTPUT.write(json.dumps({"availability_probe": event, **fields}) + "\n")
    OUTPUT.flush()


def deny_external_network(event: str, args: tuple) -> None:
    if event == "socket.connect":
        address = args[1]
        if not (
            isinstance(address, tuple)
            and len(address) >= 2
            and address[0] == CLONE_HOST
            and address[1] == 5432
        ):
            raise RuntimeError("Probe external network access denied")
    elif event == "socket.getaddrinfo":
        if args[0] != CLONE_HOST or args[1] not in (5432, "5432", None):
            raise RuntimeError("Probe external name resolution denied")


def configure_probe() -> tuple[str, bool]:
    from sqlalchemy.engine import make_url

    database_url = os.environ["DATABASE_URL"]
    url = make_url(database_url)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != CLONE_HOST
        or url.database != CLONE_DATABASE
        or url.port not in (None, 5432)
        or dict(url.query) != {"sslmode": "require"}
        or os.environ.get("REHEARSAL_TARGET") != TARGET
    ):
        raise RuntimeError("Probe requires the pinned clone database")
    code_root = os.environ.get("PROBE_CODE_ROOT")
    if code_root not in ("/old", "/app"):
        raise RuntimeError("PROBE_CODE_ROOT must select /old or /app")
    if not (Path(code_root) / "app" / "main.py").is_file():
        raise RuntimeError("Selected application source is missing")
    check_migrations = code_root == "/app"

    # Keep process essentials and the clone DSN only. No inherited provider,
    # encryption, Redis, telemetry, ADC-file or application signing credentials.
    preserved = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LD_LIBRARY_PATH", "SSL_CERT_FILE"}
    }
    os.environ.clear()
    os.environ.update(preserved)
    os.environ.update(
        DATABASE_URL=database_url,
        ENV="test",
        TESTING="1",
        GCP_MONITORING_ENABLED="false",
        OTEL_ENABLED="false",
        SENTRY_DSN="",
        REDIS_URL="memory://",
        REDIS_REQUIRED="false",
        DB_AUTO_MIGRATE="false",
        DB_MIGRATION_CHECK=str(check_migrations).lower(),
        MATCH_CASE_EXPANSION_ENABLED="false",
        PYTHONDONTWRITEBYTECODE="1",
    )
    sys.dont_write_bytecode = True
    sys.path.insert(0, code_root)
    os.chdir(code_root)
    sys.addaudithook(deny_external_network)
    return code_root, check_migrations


async def run_probe() -> None:
    code_root, check_migrations = configure_probe()
    import httpx
    from sqlalchemy import create_engine, event, select, text
    from sqlalchemy.orm import Session

    # Import the actual selected image source. ASGITransport does not dispatch
    # lifespan; no server, listener, worker loop or application startup is run.
    from app import main as application
    from app.db.models import IntendedParent, Match, Surrogate

    if Path(application.__file__).resolve() != Path(code_root) / "app" / "main.py":
        raise RuntimeError("Incorrect application source imported")
    engine = create_engine(
        os.environ["DATABASE_URL"],
        hide_parameters=True,
        connect_args={
            "connect_timeout": 10,
            "options": "-c statement_timeout=10000 -c lock_timeout=5000",
        },
    )
    # Readiness uses this pinned, bounded engine. Metrics use a separate outer
    # transaction below, so record_request's internal commit releases only its
    # savepoint. Every probe write is rolled back before the next request.
    original_engine = application.engine
    original_session_factory = application.SessionLocal
    application.engine = engine
    sql_errors: list[str] = []

    def record_sql_error(context) -> None:
        sql_errors.append(type(context.original_exception).__name__)

    event.listen(engine, "handle_error", record_sql_error)
    metrics_table = application.metrics_service.RequestMetricsRollup.__tablename__
    quote = engine.dialect.identifier_preparer.quote
    transport = httpx.ASGITransport(app=application.app, raise_app_exceptions=False)

    async def request(client, path: str, phase: str) -> None:
        with engine.connect() as connection:
            transaction = connection.begin()
            application.SessionLocal = lambda: Session(
                bind=connection, join_transaction_mode="create_savepoint"
            )
            start = time.monotonic()
            try:
                response = await client.get(path)
                elapsed = round((time.monotonic() - start) * 1000, 2)
                status = response.status_code
                await response.aclose()
            finally:
                transaction.rollback()
                application.SessionLocal = original_session_factory
        emit("http", source=code_root, phase=phase, path=path, status=status, milliseconds=elapsed)
        if status != 200:
            raise RuntimeError("Probe health endpoint did not return success")

    def hold_metrics_lock(locked: Event) -> None:
        with engine.connect() as blocker:
            transaction = blocker.begin()
            try:
                blocker.execute(text(f"LOCK TABLE {quote(metrics_table)} IN ACCESS EXCLUSIVE MODE"))
                locked.set()
                time.sleep(LOCK_SECONDS)
            finally:
                transaction.rollback()

    try:
        with engine.connect() as connection:
            if connection.scalar(text("SELECT current_database()")) != CLONE_DATABASE:
                raise RuntimeError("Unexpected connected database")
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != "20260905_1600_record_integrations":
                raise RuntimeError("Probe requires the expanded clone schema")
            for model in (Surrogate, IntendedParent, Match):
                # Compile actual old/new ORM column selections, but execute as
                # raw driver SQL: no ORM hydration or encryption result processors.
                compiled = (
                    select(model)
                    .limit(1)
                    .compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
                )
                result = connection.exec_driver_sql(str(compiled))
                row_present = result.fetchone() is not None
                result.close()
                emit(
                    "model_select",
                    source=code_root,
                    model=model.__name__,
                    succeeded=True,
                    row_present=row_present,
                )

        emit(
            "configuration",
            source=code_root,
            migration_check=check_migrations,
            lifespan_started=False,
            provider_egress=False,
        )
        async with httpx.AsyncClient(
            transport=transport, base_url="http://probe.invalid", follow_redirects=False
        ) as client:
            for path in ("/healthz", "/health/live", "/readyz"):
                await request(client, path, "baseline")
            for path in ("/healthz", "/health/live"):
                locked = Event()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(hold_metrics_lock, locked)
                    if not locked.wait(timeout=10):
                        future.result(timeout=2)
                        raise RuntimeError("Probe contention lock was not acquired")
                    await request(client, path, "synthetic_metrics_contention")
                    future.result(timeout=10)
        if sql_errors:
            raise RuntimeError("Unexpected database error during availability probe")
        emit(
            "success",
            source=code_root,
            writes_rolled_back=True,
            database_errors=0,
            scope="isolated ASGI code and synthetic metrics contention; deployment availability not measured",
        )
    finally:
        application.SessionLocal = original_session_factory
        application.engine = original_engine
        engine.dispose()
        original_engine.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    warnings.filterwarnings("ignore")
    try:
        # Library prints and tracebacks must never expose records, SQL parameters
        # or configuration. emit() writes only the fixed aggregate fields above.
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            asyncio.run(run_probe())
    except Exception as exc:
        emit("failure", error_type=type(exc).__name__)
        raise SystemExit(1) from None
