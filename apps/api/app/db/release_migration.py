"""Checked migration entry point for production release jobs."""

from __future__ import annotations

import argparse

from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from alembic import command
from app.core.migrations import MIGRATION_LOCK_ID, _current_heads, _get_alembic_config
from app.db.session import engine

EXPANDED_REVISION = "20260905_1600_record_integrations"
EXPANSION_STARTS = {
    "20260830_0100",
    "20260905_1400_match_cases",
    "20260905_1500_match_work",
}


def preflight(connection: Connection, *, allow_match_expansion: bool) -> bool:
    """Reject unreviewed expansion; return whether it still needs the cutover window."""
    heads = _current_heads(connection)
    if len(heads) != 1:
        raise RuntimeError("Release baseline must have one reviewed migration revision")
    revision = heads[0]
    if revision == EXPANDED_REVISION:
        return False
    if revision not in EXPANSION_STARTS:
        script = ScriptDirectory.from_config(_get_alembic_config())
        try:
            expanded = any(
                item.revision == EXPANDED_REVISION
                for item in script.walk_revisions(base="base", head=revision)
            )
        except Exception as exc:
            raise RuntimeError("Unknown release baseline; review the deployed revision") from exc
        if expanded:
            return False
        raise RuntimeError("Older release baseline requires a separate migration rehearsal")
    if not allow_match_expansion:
        raise RuntimeError("This schema requires an explicit match expansion rollout")
    if revision == "20260830_0100":
        conflicts = connection.execute(
            text(
                "SELECT count(*) FROM (SELECT organization_id, surrogate_id FROM matches "
                "WHERE status IN ('accepted', 'cancel_pending') "
                "GROUP BY organization_id, surrogate_id HAVING count(*) > 1) conflicts"
            )
        ).scalar_one()
        if conflicts:
            raise RuntimeError(
                f"{conflicts} conflicting surrogate commitments require reviewed reconciliation; "
                "no records were changed"
            )
    return True


def run_migration(db_engine: Engine, *, check_only: bool, allow_match_expansion: bool) -> None:
    with db_engine.connect() as connection:
        if check_only:
            preflight(connection, allow_match_expansion=allow_match_expansion)
            return
        locked = connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID}
        ).scalar_one()
        connection.commit()
        if not locked:
            raise RuntimeError("Another migration is running; retry after it completes")
        try:
            preflight(connection, allow_match_expansion=allow_match_expansion)
            config = _get_alembic_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
        finally:
            # Clear a failed DDL transaction before releasing the session lock.
            connection.rollback()
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID}
            )
            connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--allow-match-expansion", choices=("true", "false"), default="false")
    args = parser.parse_args()
    run_migration(
        engine,
        check_only=args.check_only,
        allow_match_expansion=args.allow_match_expansion == "true",
    )


if __name__ == "__main__":
    main()
