"""Run k6 against a disposable, migrated PostgreSQL container and two API workers."""

import argparse
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
from cryptography.fernet import Fernet
from psycopg.rows import dict_row

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
POSTGRES_IMAGE = "postgres:18.1"


def seed(output: Path, audit_rows: int) -> None:
    """Create synthetic repeated matches; the caller owns the disposable database."""
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    from app.core.config import settings
    from app.core.encryption import hash_email
    from app.db.models import AuditLog, IntendedParent, Match, MatchAttempt, Surrogate
    from app.db.session import SessionLocal
    from app.services import dev_service, pipeline_service

    # This command cannot seed an arbitrary development or production database.
    url = make_url(settings.DATABASE_URL.get_secret_value())
    if settings.ENV != "test" or url.host != "127.0.0.1" or url.database != "crm_benchmark":
        raise ValueError("Seeding requires the runner's disposable local crm_benchmark database")
    with SessionLocal() as db:
        if db.query(Match).first() is not None:
            raise ValueError("Benchmark database must be empty")
        context = dev_service.seed_test_data(db)
        org_id = UUID(context["org_id"])
        user_id = UUID(next(row["user_id"] for row in context["users"] if row["role"] == "admin"))
        stages = {}
        for entity in ("surrogate", "intended_parent"):
            pipeline = pipeline_service.get_or_create_default_pipeline(
                db, org_id, user_id, entity_type=entity
            )
            stages[entity] = pipeline_service.get_stage_by_slug(db, pipeline.id, "matched")
        fixtures = []
        for number in range(1, 5):
            surrogate = Surrogate(
                organization_id=org_id,
                surrogate_number=f"S{number:05d}",
                full_name=f"Synthetic Surrogate {number}",
                email=f"surrogate-{number}@example.test",
                email_hash=hash_email(f"surrogate-{number}@example.test"),
                stage_id=stages["surrogate"].id,
                status_label=stages["surrogate"].label,
                owner_type="user",
                owner_id=user_id,
                created_by_user_id=user_id,
            )
            parent = IntendedParent(
                organization_id=org_id,
                intended_parent_number=f"I{number:05d}",
                full_name=f"Synthetic Parent {number}",
                email=f"parent-{number}@example.test",
                email_hash=hash_email(f"parent-{number}@example.test"),
                stage_id=stages["intended_parent"].id,
                status="matched",
                owner_type="user",
                owner_id=user_id,
            )
            db.add_all([surrogate, parent])
            db.flush()
            matches = [
                Match(
                    organization_id=org_id,
                    match_number=f"M{number * 2 + offset:05d}",
                    surrogate_id=surrogate.id,
                    intended_parent_id=parent.id,
                    proposed_by_user_id=user_id,
                    status=status,
                )
                for offset, status in enumerate(("completed", "accepted"))
            ]
            db.add_all(matches)
            db.flush()
            previous, current = matches
            attempt = MatchAttempt(
                organization_id=org_id,
                match_id=current.id,
                sequence=1,
                attempt_type="embryo_transfer",
                status="planned",
            )
            db.add(attempt)
            db.flush()
            db.add(
                AuditLog(
                    organization_id=org_id,
                    event_type="note_created",
                    target_type="match",
                    target_id=current.id,
                    details={"attempt_id": str(attempt.id)},
                )
            )
            db.execute(
                text("""
                INSERT INTO audit_logs (organization_id, event_type, target_type, target_id, details)
                SELECT :org, 'phi_viewed',
                       CASE WHEN n % 2 = 0 THEN 'match' ELSE 'surrogate' END,
                       CASE WHEN n % 2 = 0 THEN CAST(:match AS uuid) ELSE CAST(:surrogate AS uuid) END,
                       '{}'::jsonb FROM generate_series(1, :rows) AS n
            """),
                {
                    "org": org_id,
                    "match": previous.id,
                    "surrogate": surrogate.id,
                    "rows": audit_rows // 4 + (number <= audit_rows % 4),
                },
            )
            db.execute(
                text("""
                INSERT INTO audit_logs (organization_id, event_type, target_type, target_id, details)
                SELECT :org, 'task_created', 'match', :match,
                       jsonb_build_object('task_id', gen_random_uuid()::text)
                FROM generate_series(1, 800)
            """),
                {"org": org_id, "match": previous.id},
            )
            db.execute(
                text("""
                INSERT INTO surrogate_activity_log (organization_id, surrogate_id, activity_type, details)
                SELECT :org, :surrogate, 'created', '{}'::jsonb FROM generate_series(1, 128)
            """),
                {"org": org_id, "surrogate": surrogate.id},
            )
            fixtures.append(
                {
                    "match_id": str(current.id),
                    "previous_match_id": str(previous.id),
                    "attempt_id": str(attempt.id),
                }
            )
        token, _, _, _ = dev_service.create_verified_session(db, user_id)
        db.commit()
        db.execute(text("ANALYZE"))
        db.commit()
    output.write_text(json.dumps({"cookie": f"crm_session={token}", "fixtures": fixtures}))
    output.chmod(0o600)


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run(args) -> int:
    for executable in ("docker", "k6"):
        if not shutil.which(executable):
            raise SystemExit(f"{executable} is required")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    output = (ROOT / "load-tests/results" / stamp).resolve()
    output.mkdir(parents=True)
    container = f"crm-benchmark-{uuid4().hex[:12]}"
    server = None
    password = secrets.token_urlsafe(24)
    with tempfile.TemporaryDirectory(prefix="crm-benchmark-") as scratch:
        scratch = Path(scratch)
        # A clean cwd and explicit environment prevent .env/provider credentials from leaking in.
        env = {
            key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR") if key in os.environ
        }
        env.update(
            PYTHONPATH=str(API),
            ENV="test",
            TESTING="1",
            MATCH_CASE_EXPANSION_ENABLED="true",
            JWT_SECRET=secrets.token_urlsafe(48),
            DATA_ENCRYPTION_KEY=Fernet.generate_key().decode(),
            VERSION_ENCRYPTION_KEY=Fernet.generate_key().decode(),
            PII_HASH_KEY=secrets.token_urlsafe(48),
            DB_POOL_SIZE=str(args.pool_size),
            DB_MAX_OVERFLOW="0",
            DB_POOL_TIMEOUT="5",
            OTEL_ENABLED="false",
            STORAGE_BACKEND="local",
            LOCAL_STORAGE_PATH=str(scratch / "storage"),
        )
        try:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "--name",
                    container,
                    "-p",
                    "127.0.0.1::5432",
                    "--tmpfs",
                    "/var/lib/postgresql",
                    "-e",
                    "POSTGRES_PASSWORD",
                    "-e",
                    "POSTGRES_DB=crm_benchmark",
                    POSTGRES_IMAGE,
                    "-c",
                    "shared_preload_libraries=pg_stat_statements",
                    "-c",
                    "track_io_timing=on",
                ],
                env={**env, "POSTGRES_PASSWORD": password},
                check=True,
                stdout=subprocess.DEVNULL,
            )
            port = (
                subprocess.check_output(["docker", "port", container, "5432"], text=True)
                .strip()
                .rsplit(":", 1)[1]
            )
            dsn = f"postgresql://postgres:{password}@127.0.0.1:{port}/crm_benchmark"
            env["DATABASE_URL"] = dsn.replace("postgresql://", "postgresql+psycopg://", 1)
            deadline = time.monotonic() + 45
            while True:
                try:
                    with psycopg.connect(dsn, connect_timeout=1, autocommit=True) as db:
                        db.execute("CREATE EXTENSION pg_stat_statements")
                    break
                except psycopg.OperationalError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Disposable PostgreSQL did not become ready") from None
                    time.sleep(0.3)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "alembic",
                    "-c",
                    str(API / "alembic.ini"),
                    "upgrade",
                    "head",
                ],
                cwd=scratch,
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            seed_file = scratch / "seed.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.benchmark_match_dashboard",
                    "--seed",
                    str(seed_file),
                    "--audit-rows",
                    str(args.audit_rows),
                ],
                cwd=scratch,
                env=env,
                check=True,
            )
            seeded = json.loads(seed_file.read_text())
            fixture_file = scratch / "fixtures.json"
            fixture_file.write_text(json.dumps(seeded["fixtures"]))
            api_port = unused_port()
            base = f"http://127.0.0.1:{api_port}"
            with (scratch / "api.log").open("w+") as log:
                server = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                        "--workers",
                        str(args.workers),
                        "--no-access-log",
                    ],
                    cwd=scratch,
                    env=env,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
                print(
                    f"Benchmark API PID {server.pid}; disposable container {container}", flush=True
                )
                deadline = time.monotonic() + 60
                with httpx.Client(timeout=1, trust_env=False) as client:
                    while True:
                        try:
                            if client.get(f"{base}/health").status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        if server.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError("Benchmark API did not become ready")
                        time.sleep(0.3)
                with psycopg.connect(dsn, autocommit=True) as db:
                    db.execute("SELECT pg_stat_statements_reset()")
                result = subprocess.run(
                    [
                        "k6",
                        "run",
                        "--summary-export",
                        str(output / "k6-summary.json"),
                        str(ROOT / "load-tests/k6-match-dashboard.js"),
                    ],
                    cwd=scratch,
                    env={
                        **env,
                        "BASE_URL": base,
                        "AUTH_COOKIE": seeded["cookie"],
                        "FIXTURE_FILE": str(fixture_file),
                        "DURATION": args.duration,
                        "VUS_MATCH": str(args.match_vus),
                        "VUS_DASHBOARD": str(args.dashboard_vus),
                        "ALLOW_FORBIDDEN": "0",
                        "P95_MS": str(args.p95_ms),
                    },
                )
                with psycopg.connect(dsn, row_factory=dict_row) as db:
                    stats = db.execute("""
                        SELECT queryid::text, query, calls, total_exec_time, mean_exec_time, rows,
                               shared_blks_hit, shared_blks_read, temp_blks_written
                        FROM pg_stat_statements
                        WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                        ORDER BY total_exec_time DESC LIMIT 30
                    """).fetchall()
                (output / "database.json").write_text(json.dumps(stats, indent=2))
                log.flush()
                log.seek(0)
                logs = log.read()
                metadata = {key: value for key, value in vars(args).items() if key != "seed"}
                metadata.update(
                    k6_exit_code=result.returncode,
                    postgres_image=POSTGRES_IMAGE,
                    pool_timeout_errors=logs.count("QueuePool limit"),
                    k6_version=subprocess.check_output(["k6", "version"], text=True).strip(),
                    git_sha=subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                    ).strip(),
                    git_dirty=bool(
                        subprocess.check_output(
                            ["git", "status", "--porcelain"], cwd=ROOT, text=True
                        ).strip()
                    ),
                )
                (output / "run.json").write_text(json.dumps(metadata, indent=2))
                print(f"Results: {output}", flush=True)
                return result.returncode
        finally:
            try:
                if server is not None:
                    with suppress(ProcessLookupError):
                        os.killpg(server.pid, signal.SIGTERM)
                    try:
                        server.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        with suppress(ProcessLookupError):
                            os.killpg(server.pid, signal.SIGKILL)
                        server.wait(timeout=5)
            finally:
                subprocess.run(
                    ["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, check=False
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", default="2m")
    parser.add_argument("--audit-rows", type=int, default=400_000)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--pool-size", type=int, default=2)
    parser.add_argument("--match-vus", type=int, default=3)
    parser.add_argument("--dashboard-vus", type=int, default=2)
    parser.add_argument("--p95-ms", type=int, default=800)
    parser.add_argument("--seed", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (
        min(
            args.audit_rows,
            args.workers,
            args.pool_size,
            args.match_vus,
            args.dashboard_vus,
            args.p95_ms,
        )
        < 1
    ):
        parser.error("Row counts, workers, pools, VUs, and latency budgets must be positive")
    if args.seed:
        seed(args.seed, args.audit_rows)
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
