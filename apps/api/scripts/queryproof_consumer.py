"""CRM-owned lifecycle checks for the QueryProof query-only pilot."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import os
import re

import psycopg
from sqlalchemy.engine import make_url


BENCHMARK_ROLE = "crm_queryproof_app"
READ_ONLY_RELATIONS = (
    "automation_workflows",
    "org_intelligent_suggestion_rules",
    "pipeline_stages",
    "pipelines",
    "surrogates",
    "tasks",
    "workflow_executions",
)
_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _quoted_identifier(value: str) -> str:
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError("QueryProof role ACL contains an unsafe identifier")
    return f'"{value}"'


def role_acl_statements() -> tuple[str, ...]:
    """Return the exact read-only ACL applied in each ephemeral benchmark database."""
    role = _quoted_identifier(BENCHMARK_ROLE)
    relations = ", ".join(
        f"public.{_quoted_identifier(relation)}" for relation in READ_ONLY_RELATIONS
    )
    return (
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        f"REVOKE ALL PRIVILEGES ON SCHEMA public FROM {role}",
        f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {role}",
        f"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {role}",
        f"GRANT USAGE ON SCHEMA public TO {role}",
        f"GRANT SELECT ON TABLE {relations} TO {role}",
    )


def extension_statements() -> tuple[str, ...]:
    """Return the database-local extension bootstrap run before migrations."""
    return ("CREATE EXTENSION IF NOT EXISTS pg_stat_statements",)


def _psycopg_url(raw_url: str) -> str:
    parsed = make_url(raw_url)
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("DATABASE_URL must target PostgreSQL")
    return parsed.set(drivername="postgresql").render_as_string(hide_password=False)


def doctor(environ: Mapping[str, str]) -> None:
    """Fail closed unless QueryProof selected the reviewed deterministic query mode."""
    if environ.get("QUERYPROOF_MODE") != "deterministic":
        raise RuntimeError("QUERYPROOF_MODE must be deterministic")
    if environ.get("QUERYPROOF_EXPECTED_SEED_PROFILE") != "production":
        raise RuntimeError("the reviewed QueryProof seed profile must be production")
    raw_url = environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        raise RuntimeError("DATABASE_URL is required")
    _psycopg_url(raw_url)


def _role_attributes_are_safe(row: Sequence[object]) -> bool:
    # rolinherit is intentionally false; all remaining capabilities must also be false.
    return tuple(row) == (False, False, False, False, False, False, False, False)


def provision_role(database_url: str) -> None:
    """Create the shared NOLOGIN role and apply per-database query-only grants."""
    role = _quoted_identifier(BENCHMARK_ROLE)
    with psycopg.connect(_psycopg_url(database_url), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin,
                       rolreplication, rolbypassrls,
                       EXISTS (
                           SELECT 1
                           FROM pg_auth_members
                           WHERE member = pg_roles.oid
                       )
                FROM pg_roles
                WHERE rolname = %s
                """,
                (BENCHMARK_ROLE,),
            )
            attributes = cursor.fetchone()
            if attributes is None:
                cursor.execute(
                    f"CREATE ROLE {role} NOLOGIN NOINHERIT NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                )
            elif not _role_attributes_are_safe(attributes):
                raise RuntimeError(
                    "existing QueryProof application role violates the reviewed "
                    "NOLOGIN, NOINHERIT, no-membership posture"
                )

            for statement in extension_statements():
                cursor.execute(statement)


def apply_role_acl(database_url: str) -> None:
    """Apply read-only table ACLs after this revision created the corpus relations."""
    with psycopg.connect(_psycopg_url(database_url), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin,
                       rolreplication, rolbypassrls,
                       EXISTS (
                           SELECT 1 FROM pg_auth_members WHERE member = pg_roles.oid
                       )
                FROM pg_roles WHERE rolname = %s
                """,
                (BENCHMARK_ROLE,),
            )
            attributes = cursor.fetchone()
            if attributes is None or not _role_attributes_are_safe(attributes):
                raise RuntimeError("QueryProof application role posture is unsafe")
            for statement in role_acl_statements():
                cursor.execute(statement)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("doctor", "provision-role", "apply-role-acl"))
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "doctor":
        doctor(os.environ)
        return
    doctor(os.environ)
    if args.command == "provision-role":
        provision_role(os.environ["DATABASE_URL"])
    else:
        apply_role_acl(os.environ["DATABASE_URL"])


if __name__ == "__main__":
    main()
