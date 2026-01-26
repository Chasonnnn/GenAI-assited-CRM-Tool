"""Database migration utilities for startup checks and health probes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings

ALEMBIC_VERSION_TABLE = "alembic_version"
MIGRATION_LOCK_ID = 9823417


@dataclass(frozen=True)
class MigrationStatus:
    current_heads: tuple[str, ...]
    head_revisions: tuple[str, ...]
    is_up_to_date: bool


class MigrationError(RuntimeError):
    """Raised when automatic migrations fail to reach head."""


def _get_alembic_config() -> Config:
    api_root = Path(__file__).resolve().parents[2]
    alembic_ini = api_root / "alembic.ini"
    if not alembic_ini.is_file():
        raise FileNotFoundError(f"Alembic config not found at {alembic_ini}")
    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return config


def _tuple_or_empty(values: Iterable[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(values)


def _current_heads(connection: Connection) -> tuple[str, ...]:
    inspector = inspect(connection)
    if ALEMBIC_VERSION_TABLE not in inspector.get_table_names():
        return ()

    context = MigrationContext.configure(connection)
    return _tuple_or_empty(context.get_current_heads())


def get_migration_status(engine: Engine) -> MigrationStatus:
    config = _get_alembic_config()
    script = ScriptDirectory.from_config(config)
    head_revisions = _tuple_or_empty(script.get_heads())

    with engine.connect() as connection:
        current_heads = _current_heads(connection)

    is_up_to_date = set(current_heads) == set(head_revisions)
    return MigrationStatus(
        current_heads=current_heads,
        head_revisions=head_revisions,
        is_up_to_date=is_up_to_date,
    )


def ensure_migrations(engine: Engine, auto_migrate: bool) -> MigrationStatus:
    status = get_migration_status(engine)
    if status.is_up_to_date or not auto_migrate:
        return status

    _upgrade_to_head(engine)
    status = get_migration_status(engine)
    if not status.is_up_to_date:
        raise MigrationError("Database migrations did not reach head after auto-upgrade.")
    return status


def _upgrade_to_head(engine: Engine) -> None:
    config = _get_alembic_config()

    if engine.dialect.name != "postgresql":
        command.upgrade(config, "head")
        return

    with engine.connect() as connection:
        _acquire_advisory_lock(connection)
        if connection.in_transaction():
            connection.commit()
        try:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            if connection.in_transaction():
                connection.commit()
        finally:
            try:
                _release_advisory_lock(connection)
                if connection.in_transaction():
                    connection.commit()
            except Exception:
                pass


def _acquire_advisory_lock(connection: Connection) -> None:
    connection.execute(
        text("SELECT pg_advisory_lock(:lock_id)"),
        {"lock_id": MIGRATION_LOCK_ID},
    )


def _release_advisory_lock(connection: Connection) -> None:
    connection.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": MIGRATION_LOCK_ID},
    )
