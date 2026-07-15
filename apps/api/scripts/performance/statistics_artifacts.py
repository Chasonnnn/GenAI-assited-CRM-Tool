from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

from cryptography.fernet import Fernet, InvalidToken

from scripts.performance.statistics import StatisticsAllowlist, sanitize_statistics_dump


class StatisticsArtifactError(RuntimeError):
    pass


def _fernet_from_environment(key_environment_variable: str) -> Fernet:
    raw_key = os.environ.get(key_environment_variable, "")
    if not raw_key:
        raise StatisticsArtifactError(
            f"{key_environment_variable} must contain a Fernet key; the key is never written to disk"
        )
    try:
        return Fernet(raw_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise StatisticsArtifactError(
            f"{key_environment_variable} does not contain a valid Fernet key"
        ) from exc


def _require_postgres_18_4(executable: str) -> None:
    result = subprocess.run(
        [executable, "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"PostgreSQL\)\s+(\d+)\.(\d+)", result.stdout)
    supported = bool(match and int(match.group(1)) == 18 and int(match.group(2)) >= 4)
    if not supported:
        raise StatisticsArtifactError(
            f"{executable} 18.4 or newer within PostgreSQL 18 is required"
        )


def export_encrypted_statistics(
    *,
    database_url: str,
    allowlist_path: Path,
    output_path: Path,
    key_environment_variable: str = "PERFORMANCE_STATS_FERNET_KEY",
    pg_dump_executable: str = "pg_dump",
) -> None:
    """Dump, sanitize, and encrypt statistics without writing plaintext to disk."""
    _require_postgres_18_4(pg_dump_executable)
    allowlist = StatisticsAllowlist.from_json_file(allowlist_path)
    result = subprocess.run(
        [
            pg_dump_executable,
            "--statistics-only",
            "--format=plain",
            "--no-owner",
            "--no-privileges",
            database_url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    sanitized = sanitize_statistics_dump(result.stdout, allowlist)
    encrypted = _fernet_from_environment(key_environment_variable).encrypt(
        sanitized.encode("utf-8")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encrypted)
    output_path.chmod(0o600)


def restore_encrypted_statistics(
    *,
    database_url: str,
    allowlist_path: Path,
    artifact_path: Path,
    key_environment_variable: str = "PERFORMANCE_STATS_FERNET_KEY",
    psql_executable: str = "psql",
) -> None:
    """Decrypt in memory and stream sanitized statistics directly to PostgreSQL."""
    _require_postgres_18_4(psql_executable)
    fernet = _fernet_from_environment(key_environment_variable)
    try:
        plaintext = fernet.decrypt(artifact_path.read_bytes()).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise StatisticsArtifactError("Statistics artifact could not be decrypted") from exc

    allowlist = StatisticsAllowlist.from_json_file(allowlist_path)
    sanitized = sanitize_statistics_dump(plaintext, allowlist)
    subprocess.run(
        [psql_executable, "--no-psqlrc", "--set=ON_ERROR_STOP=1", database_url],
        input=sanitized,
        text=True,
        check=True,
    )
