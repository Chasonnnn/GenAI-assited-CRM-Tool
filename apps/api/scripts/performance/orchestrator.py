from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class DeterministicComparisonResult:
    base_report: Path
    candidate_report: Path


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _database_url(database_url: str, database_name: str, *, sqlalchemy: bool) -> str:
    url = make_url(database_url).set(database=database_name)
    rendered = url.render_as_string(hide_password=False)
    return rendered if sqlalchemy else _psycopg_url(rendered)


def _create_database(admin_database_url: str, database_name: str) -> None:
    with psycopg.connect(_psycopg_url(admin_database_url), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))


def _drop_database(admin_database_url: str, database_name: str) -> None:
    with psycopg.connect(_psycopg_url(admin_database_url), autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (database_name,),
        )
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name))
        )


def _worktree(repository_root: Path, destination: Path, git_ref: str) -> None:
    _run(
        ["git", "worktree", "add", "--detach", str(destination), git_ref],
        cwd=repository_root,
    )


def _remove_worktree(repository_root: Path, destination: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(destination)],
        cwd=repository_root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _prepare_database(checkout: Path, database_url: str) -> None:
    api_root = checkout / "apps" / "api"
    _run(["uv", "sync", "--frozen", "--extra", "test"], cwd=api_root)
    environment = os.environ.copy()
    environment.update({"DATABASE_URL": database_url, "ENV": "test"})
    _run(["uv", "run", "-m", "alembic", "upgrade", "head"], cwd=api_root, env=environment)


def _seed_database(
    harness_checkout: Path,
    database_url: str,
    seed_profile: str,
) -> None:
    api_root = harness_checkout / "apps" / "api"
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": database_url,
            "ENV": "test",
            "SEED_PROFILE": seed_profile,
            "SEED_REDACT_SUMMARY": "1",
        }
    )
    _run(
        ["uv", "run", "python", "-m", "scripts.seed_mock_data"],
        cwd=api_root,
        env=environment,
    )


def _capture_database(
    harness_checkout: Path,
    database_url: str,
    output_path: Path,
) -> None:
    api_root = harness_checkout / "apps" / "api"
    manifest_path = api_root / "performance" / "capture-manifest.json"
    environment = os.environ.copy()
    environment.update({"DATABASE_URL": database_url, "ENV": "test"})
    _run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "scripts.performance",
            "capture",
            "--manifest",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
        cwd=api_root,
        env=environment,
    )


def run_deterministic_comparison(
    *,
    repository_root: Path,
    base_ref: str,
    candidate_ref: str,
    admin_database_url: str,
    results_dir: Path,
    seed_profile: str = "production",
) -> DeterministicComparisonResult:
    """Build isolated refs/databases and capture the same deterministic corpus on both."""
    if candidate_ref == "HEAD":
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
        if status.stdout.strip():
            raise RuntimeError(
                "Candidate HEAD has uncommitted changes; commit them so the detached worktree "
                "matches the requested candidate"
            )

    token = secrets.token_hex(4)
    base_database = f"perf_{os.getpid()}_{token}_base"
    candidate_database = f"perf_{os.getpid()}_{token}_candidate"
    database_names = (base_database, candidate_database)
    results_dir.mkdir(parents=True, exist_ok=True)
    base_report = results_dir / "base-plan-report.json"
    candidate_report = results_dir / "candidate-plan-report.json"

    with tempfile.TemporaryDirectory(prefix="crm-deterministic-performance-") as temporary:
        temporary_root = Path(temporary)
        base_checkout = temporary_root / "base"
        candidate_checkout = temporary_root / "candidate"
        worktrees: list[Path] = []
        try:
            _worktree(repository_root, base_checkout, base_ref)
            worktrees.append(base_checkout)
            _worktree(repository_root, candidate_checkout, candidate_ref)
            worktrees.append(candidate_checkout)
            for database_name in database_names:
                _create_database(admin_database_url, database_name)

            base_sqlalchemy_url = _database_url(admin_database_url, base_database, sqlalchemy=True)
            candidate_sqlalchemy_url = _database_url(
                admin_database_url, candidate_database, sqlalchemy=True
            )
            _prepare_database(base_checkout, base_sqlalchemy_url)
            _prepare_database(candidate_checkout, candidate_sqlalchemy_url)

            # The candidate harness intentionally seeds both databases. This pins the
            # distribution even when seed code changes between refs. A schema-incompatible
            # seed fails the comparison explicitly rather than silently changing data.
            _seed_database(candidate_checkout, base_sqlalchemy_url, seed_profile)
            _seed_database(candidate_checkout, candidate_sqlalchemy_url, seed_profile)

            _capture_database(candidate_checkout, base_sqlalchemy_url, base_report)
            _capture_database(candidate_checkout, candidate_sqlalchemy_url, candidate_report)
        finally:
            for database_name in reversed(database_names):
                try:
                    _drop_database(admin_database_url, database_name)
                except Exception:
                    pass
            for worktree in reversed(worktrees):
                _remove_worktree(repository_root, worktree)

    # Parsing here makes interrupted/truncated artifacts fail before gate evaluation.
    json.loads(base_report.read_text())
    json.loads(candidate_report.read_text())
    return DeterministicComparisonResult(
        base_report=base_report,
        candidate_report=candidate_report,
    )
