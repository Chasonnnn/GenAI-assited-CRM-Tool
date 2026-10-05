"""Clone-only migration gate and integrated permission-policy rehearsal entrypoint.

Copy this file and rehearsal.py into <API root>/_rehearsal in the frozen image.
This script never starts the API or workers, and never loads production keys.
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import logging
import os
import re
import socket
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

SOURCE_COMMIT = "c9b0018a418b01362f71a21a27f20f582473b029"
# Reuse the original clone identity without changing its sentinel.
CLONE_SOURCE_COMMIT = "00dc316eba4bb7261a9498d0ab7803407d226efc"
EXPECTED_DATABASE = "crm"
GUARD_TABLE = "permission_rehearsal_guard"
BUSINESS_TABLES = (
    "organizations",
    "users",
    "memberships",
    "surrogates",
    "donors",
    "intended_parents",
    "matches",
    "match_events",
    "match_attempts",
    "tasks",
    "entity_notes",
    "attachments",
    "appointments",
    "appointment_types",
    "availability_rules",
    "availability_overrides",
    "booking_links",
    "forms",
    "form_submissions",
    "form_submission_drafts",
    "form_submission_files",
    "form_intake_links",
    "form_intake_drafts",
    "intake_leads",
    "consent_records",
    "lead_attribution",
    "surrogate_status_history",
    "donor_status_history",
    "intended_parent_status_history",
    "surrogate_activity_log",
    "surrogate_contact_attempts",
    "surrogate_interviews",
    "interview_notes",
    "interview_attachments",
    "record_collaborators",
    "medical_records",
)
REQUIRED_TABLES = {"organizations", "users", "memberships", "surrogates", "donors"}
# Migration-managed routing, task state, configuration, and medical legacy fields
# are excluded; record identity, tenancy, assignment, stage and archive stay fixed.
IDENTITY_COLUMNS = (
    "id",
    "organization_id",
    "user_id",
    "surrogate_id",
    "donor_id",
    "intended_parent_id",
    "match_id",
    "owner_type",
    "owner_id",
    "created_by_user_id",
    "stage_id",
    "paused_from_stage_id",
    "is_archived",
)
CONTROL_ENV = {
    "DATABASE_URL",
    "EXPECTED_CLONE_IP",
    "EXPECTED_DATABASE",
    "REHEARSAL_RUN_ID",
    "SOURCE_COMMIT",
    "REHEARSAL_MODE",
    "ORG_ID",
    "ACTOR_USER_ID",
    "REHEARSAL_DECISION_FILE",
    "REHEARSAL_TEMPLATE_FILE",
    "DECISION_FILE",
    "TEMPLATE_FILE",
    "REVIEWED_DIGEST",
}
RUNTIME_ENV = {
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "PYTHONUNBUFFERED",
    "PYTHONDONTWRITEBYTECODE",
}
PHASE = "configuration"


class GuardFailure(RuntimeError):
    """Only a fixed, non-sensitive code may leave this exception."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_environment(environ: dict[str, str]) -> dict[str, str]:
    required = {
        "DATABASE_URL",
        "EXPECTED_CLONE_IP",
        "EXPECTED_DATABASE",
        "REHEARSAL_RUN_ID",
        "SOURCE_COMMIT",
    }
    if not required.issubset(environ):
        raise GuardFailure("missing_configuration")
    if environ["SOURCE_COMMIT"] != SOURCE_COMMIT:
        raise GuardFailure("source_commit_mismatch")
    if environ["EXPECTED_DATABASE"] != EXPECTED_DATABASE:
        raise GuardFailure("database_name_mismatch")
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", environ["REHEARSAL_RUN_ID"]):
        raise GuardFailure("invalid_run_id")
    try:
        expected_ip = ipaddress.ip_address(environ["EXPECTED_CLONE_IP"])
        url = urlsplit(environ["DATABASE_URL"])
        actual_ip = ipaddress.ip_address(url.hostname or "")
        port = url.port
    except ValueError:
        raise GuardFailure("invalid_database_address") from None
    if (
        expected_ip.is_loopback
        or expected_ip.is_unspecified
        or expected_ip.is_multicast
    ):
        raise GuardFailure("invalid_clone_address")
    if actual_ip != expected_ip or port != 5432:
        raise GuardFailure("database_host_mismatch")
    if url.scheme != "postgresql+psycopg" or unquote(url.path) != "/crm":
        raise GuardFailure("database_url_mismatch")
    if not url.username or not url.password or url.query or url.fragment:
        raise GuardFailure("database_url_options_forbidden")
    return {
        key: value for key, value in environ.items() if key in CONTROL_ENV | RUNTIME_ENV
    }


def install_network_guard(expected_ip: str) -> None:
    """Block Python sockets and independently constrain libpq's C-level connect."""
    # Import the DB driver before denying subprocesses used by library discovery.
    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    expected = ipaddress.ip_address(expected_ip)
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def allowed(address: object) -> bool:
        if not isinstance(address, tuple) or len(address) < 2:
            return False
        try:
            return ipaddress.ip_address(address[0]) == expected and address[1] == 5432
        except (ValueError, TypeError):
            return False

    def guarded_connect(sock, address):
        if not allowed(address):
            raise GuardFailure("outbound_socket_blocked")
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if not allowed(address):
            raise GuardFailure("outbound_socket_blocked")
        return original_connect_ex(sock, address)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex

    def audit(event: str, args: tuple) -> None:
        if event == "socket.connect" and not allowed(args[1]):
            raise GuardFailure("outbound_socket_blocked")
        if event in {
            "socket.sendto",
            "socket.sendmsg",
            "subprocess.Popen",
            "os.system",
            "os.posix_spawn",
        }:
            raise GuardFailure("outbound_process_or_datagram_blocked")
        if event == "socket.getaddrinfo":
            try:
                valid = ipaddress.ip_address(args[0]) == expected and args[1] in {
                    5432,
                    "5432",
                }
            except (ValueError, TypeError):
                valid = False
            if not valid:
                raise GuardFailure("outbound_dns_blocked")

    sys.addaudithook(audit)
    original_psycopg_connect = psycopg.connect

    def guarded_psycopg_connect(conninfo="", **kwargs):
        params = conninfo_to_dict(conninfo)
        params.update(
            {
                key: value
                for key, value in kwargs.items()
                if key in {"host", "hostaddr", "port", "dbname", "service", "options"}
            }
        )
        try:
            host_valid = ipaddress.ip_address(params.get("host", "")) == expected
            addr_valid = (
                "hostaddr" not in params
                or ipaddress.ip_address(params["hostaddr"]) == expected
            )
        except ValueError:
            host_valid = addr_valid = False
        if not host_valid or not addr_valid or str(params.get("port", "")) != "5432":
            raise GuardFailure("libpq_host_mismatch")
        if (
            params.get("dbname") != EXPECTED_DATABASE
            or params.get("service")
            or params.get("options", "") not in {"", "-c timezone=utc"}
        ):
            raise GuardFailure("libpq_database_mismatch")
        for attempt in range(4):
            try:
                return original_psycopg_connect(conninfo, **kwargs)
            except psycopg.OperationalError:
                if attempt == 3:
                    raise GuardFailure("clone_connection_unavailable") from None
                time.sleep(3)

    psycopg.connect = guarded_psycopg_connect


def connect_clone(database_url: str):
    import psycopg

    url = urlsplit(database_url)
    return psycopg.connect(
        host=url.hostname,
        port=5432,
        dbname=EXPECTED_DATABASE,
        user=unquote(url.username or ""),
        password=unquote(url.password or ""),
        connect_timeout=10,
        options="",
        autocommit=False,
    )


def verify_sentinel(connection, run_id: str) -> None:
    if (
        connection.execute("SELECT current_database()").fetchone()[0]
        != EXPECTED_DATABASE
    ):
        raise GuardFailure("connected_database_mismatch")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS public.permission_rehearsal_guard "
        "(run_id text PRIMARY KEY, source_commit text NOT NULL)"
    )
    connection.execute("LOCK TABLE public.permission_rehearsal_guard IN EXCLUSIVE MODE")
    rows = connection.execute(
        "SELECT run_id, source_commit FROM public.permission_rehearsal_guard"
    ).fetchall()
    if not rows:
        connection.execute(
            "INSERT INTO public.permission_rehearsal_guard (run_id, source_commit) VALUES (%s, %s)",
            (run_id, CLONE_SOURCE_COMMIT),
        )
    elif rows != [(run_id, CLONE_SOURCE_COMMIT)]:
        raise GuardFailure("clone_sentinel_mismatch")
    connection.commit()


def baseline(
    connection, columns_by_table: dict[str, tuple[str, ...]] | None = None
) -> dict:
    """Only aggregate counts and digests leave PostgreSQL, never row values."""
    from psycopg import sql

    available = {}
    for table, column in connection.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public'"
    ).fetchall():
        available.setdefault(table, set()).add(column)
    if not REQUIRED_TABLES.issubset(available):
        raise GuardFailure("required_business_tables_missing")
    selected = columns_by_table or {
        table: tuple(
            column for column in IDENTITY_COLUMNS if column in available[table]
        )
        for table in BUSINESS_TABLES
        if table in available and "id" in available[table]
    }
    result = {}
    for table, columns in selected.items():
        if table not in available or not set(columns).issubset(available[table]):
            raise GuardFailure("protected_identity_columns_missing")
        names = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
        query = sql.SQL(
            "SELECT count(*), md5(COALESCE(string_agg(id::text, ',' ORDER BY id::text), '')), "
            "md5(COALESCE(string_agg(md5(jsonb_build_array({fields})::text), ',' ORDER BY id::text), '')) "
            "FROM public.{table}"
        ).format(fields=names, table=sql.Identifier(table))
        count, identifiers, identity = connection.execute(query).fetchone()
        result[table] = {
            "count": count,
            "id_digest": identifiers,
            "identity_digest": identity,
            "columns": columns,
        }
    connection.rollback()
    return result


def disable_crypto() -> None:
    from app.core import encryption

    def denied(*args, **kwargs):
        raise GuardFailure("crypto_operation_blocked")

    for name in (
        "get_fernet",
        "get_data_fernet",
        "encrypt_token",
        "decrypt_token",
        "encrypt_value",
        "decrypt_value",
        "hash_pii",
        "hash_email",
        "hash_phone",
        "hash_date_of_birth",
    ):
        setattr(encryption, name, denied)


def main() -> int:
    global PHASE
    original_stdout = sys.stdout
    try:
        safe_env = validate_environment(dict(os.environ))
        api_root = Path(__file__).resolve().parent.parent
        if not (api_root / "app" / "core" / "config.py").is_file():
            raise GuardFailure("invalid_artifact_layout")
        os.environ.clear()
        os.environ.update(safe_env)
        os.environ.update(
            ENV="test",
            TESTING="1",
            DB_POOL_SIZE="1",
            DB_MAX_OVERFLOW="0",
            DB_CONNECT_TIMEOUT="10",
            DB_AUTO_MIGRATE="false",
            SENTRY_DSN="",
            GOOGLE_CALENDAR_SYNC_FALLBACK_ENABLED="false",
            GMAIL_SYNC_FALLBACK_ENABLED="false",
        )
        # Settings reads .env relative to cwd; use an empty private directory.
        os.chdir(tempfile.mkdtemp(prefix="permission-rehearsal-"))
        sys.path.insert(0, str(api_root))
        install_network_guard(safe_env["EXPECTED_CLONE_IP"])
        logging.disable(logging.CRITICAL)
        with (
            open(os.devnull, "w") as sink,
            contextlib.redirect_stdout(sink),
            contextlib.redirect_stderr(sink),
        ):
            PHASE = "clone_sentinel"
            with connect_clone(safe_env["DATABASE_URL"]) as connection:
                verify_sentinel(connection, safe_env["REHEARSAL_RUN_ID"])
                versions = connection.execute(
                    "SELECT version_num FROM public.alembic_version"
                ).fetchall()
                connection.rollback()
                if len(versions) != 1:
                    raise GuardFailure("unreviewed_migration_baseline")
                before_revision = versions[0][0]
                before = baseline(connection)
            PHASE = "migration_preflight"
            disable_crypto()
            import rehearsal

            rehearsal.install_guards()
            from app.core.migrations import get_migration_status
            from app.db import release_migration
            from app.db.session import engine

            release_migration.run_migration(
                engine, check_only=True, allow_match_expansion=False
            )
            PHASE = "migration"
            release_migration.run_migration(
                engine, check_only=False, allow_match_expansion=False
            )
            status = get_migration_status(engine)
            if not status.is_up_to_date or len(status.current_heads) != 1:
                raise GuardFailure("migration_head_mismatch")
            PHASE = "preservation"
            with connect_clone(safe_env["DATABASE_URL"]) as connection:
                verify_sentinel(connection, safe_env["REHEARSAL_RUN_ID"])
                after = baseline(
                    connection, {table: row["columns"] for table, row in before.items()}
                )
            if after != before:
                raise GuardFailure("business_identity_preservation_failed")
        original_stdout.write(
            json.dumps(
                {
                    "phase": "bootstrap",
                    "status": "passed",
                    "source_commit": SOURCE_COMMIT,
                    "schema_before": before_revision,
                    "schema_after": status.current_heads[0],
                    "business_counts": {
                        table: row["count"] for table, row in before.items()
                    },
                    "business_identities_preserved": True,
                    "protected_table_count": len(before),
                },
                sort_keys=True,
            )
            + "\n"
        )
        original_stdout.flush()
        PHASE = "permission_rehearsal"
        result = rehearsal.main()
        return result if isinstance(result, int) else 0
    except BaseException as exc:  # noqa: BLE001 - process boundary must never emit raw failures
        code = exc.code if isinstance(exc, GuardFailure) else "phase_failed"
        original_stdout.write(
            json.dumps(
                {
                    "phase": PHASE,
                    "status": "blocked",
                    "code": code,
                    "error_type": type(exc).__name__,
                }
            )
            + "\n"
        )
        original_stdout.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
