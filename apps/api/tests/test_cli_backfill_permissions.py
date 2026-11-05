"""The backfill command scans every organization, so this file runs in the serial group."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import event as sqlalchemy_event

from app.db.models import Organization


class _SessionProxy:
    """Keep shared pytest DB session open when CLI closes SessionLocal."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self) -> None:
        return None


@pytest.fixture
def _cli_db(monkeypatch, db):
    from app import cli as cli_module

    monkeypatch.setattr(cli_module, "SessionLocal", lambda: _SessionProxy(db))
    return cli_module


@pytest.fixture
def _echo_log(monkeypatch, _cli_db):
    messages: list[str] = []
    monkeypatch.setattr(_cli_db.click, "echo", lambda msg="": messages.append(str(msg)))
    return messages


def _create_org(db, slug: str) -> Organization:
    org = Organization(id=uuid4(), slug=slug, name=slug.title())
    db.add(org)
    db.flush()
    return org


@pytest.mark.parametrize("dry_run", [True, False])
def test_cli_backfill_permissions_bulk_loads_and_preserves_existing_permissions(
    db, _cli_db, _echo_log, dry_run
):
    from app.core.permissions import ROLE_DEFAULTS
    from app.db.models import RolePermission

    acme = _create_org(db, slug="acme")
    beta = _create_org(db, slug="beta")
    acme_id, beta_id = acme.id, beta.id
    existing_permission = next(iter(ROLE_DEFAULTS["admin"]))
    db.add(
        RolePermission(
            organization_id=acme.id,
            role="admin",
            permission=existing_permission,
            is_granted=False,
        )
    )
    db.commit()

    permission_selects: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("select") and "from role_permissions" in normalized:
            permission_selects.append(normalized)

    engine = db.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        _cli_db.backfill_permissions.callback(dry_run=dry_run)
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_sql)

    expected_per_org = sum(
        len(permissions) for role, permissions in ROLE_DEFAULTS.items() if role != "developer"
    )
    assert len(permission_selects) == 1
    verb = "would create" if dry_run else "created"
    assert f"  acme: {verb} {expected_per_org - 1} permissions" in _echo_log
    assert f"  beta: {verb} {expected_per_org} permissions" in _echo_log
    assert f"[OK] {verb.capitalize()} {2 * expected_per_org - 1} total permission(s)" in _echo_log
    denied = (
        db.query(RolePermission)
        .filter_by(organization_id=acme_id, role="admin", permission=existing_permission)
        .one()
    )
    assert denied.is_granted is False
    assert db.query(RolePermission).filter_by(organization_id=acme_id).count() == (
        1 if dry_run else expected_per_org
    )
    assert db.query(RolePermission).filter_by(organization_id=beta_id).count() == (
        0 if dry_run else expected_per_org
    )
    assert db.query(RolePermission).filter_by(role="developer").count() == 0
    if not dry_run:
        _echo_log.clear()
        _cli_db.backfill_permissions.callback(dry_run=False)
        assert "[OK] All permissions already up to date" in _echo_log
