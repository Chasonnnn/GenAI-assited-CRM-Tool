"""PostgreSQL regressions for the Google Tasks membership-lock incident."""

import asyncio
import threading
import time
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.services import google_tasks_sync_service as service


@pytest.fixture
def sync_sessions(db_engine):
    # Committed synthetic memberships are visible to independent transactions.
    schema = f"google_sync_{uuid4().hex}"
    user_id, org_id = uuid4(), uuid4()
    with db_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        for table in ("users", "memberships"):
            connection.execute(
                text(f'CREATE TABLE "{schema}".{table} AS TABLE public.{table} WITH NO DATA')
            )
        connection.execute(
            text(f'INSERT INTO "{schema}".users (id, is_active) VALUES (:id, true)'),
            {"id": user_id},
        )
        connection.execute(
            text(
                f'INSERT INTO "{schema}".memberships '
                "(id, user_id, organization_id, role, is_active) "
                "VALUES (:id, :user_id, :org_id, 'admin', true)"
            ),
            {"id": uuid4(), "user_id": user_id, "org_id": org_id},
        )

    @contextmanager
    def open_session():
        with db_engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema}", public'))
            # Independent server-side watchdog also bounds the pre-fix deadlock.
            connection.execute(text("SET statement_timeout = '1500ms'"))
            connection.commit()
            try:
                with Session(bind=connection) as session:
                    yield session
            finally:
                connection.rollback()
                connection.execute(text("RESET search_path"))
                connection.execute(text("RESET statement_timeout"))
                connection.commit()

    try:
        yield open_session, user_id, org_id
    finally:
        with db_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.mark.asyncio
@pytest.mark.parametrize("same_user", [True, False])
async def test_overlapping_sync_keeps_event_loop_responsive(
    sync_sessions, db_engine, monkeypatch, same_user
):
    open_session, user_id, org_id = sync_sessions
    second_user_id = user_id if same_user else uuid4()
    if not same_user:
        with open_session() as db:
            db.execute(
                text("INSERT INTO users (id, is_active) VALUES (:id, true)"),
                {"id": second_user_id},
            )
            db.execute(
                text(
                    "INSERT INTO memberships (id, user_id, organization_id, role, is_active) "
                    "VALUES (:id, :user_id, :org_id, 'admin', true)"
                ),
                {"id": uuid4(), "user_id": second_user_id, "org_id": org_id},
            )
            db.commit()
    entered = threading.Event()
    second_waiting = threading.Event()
    loop_ran_during_wait = threading.Event()
    calls = []
    main_thread = threading.get_ident()
    # Room for slow runners: the lock holder waits on events below, not on fixed sleeps.
    monkeypatch.setattr(service, "GOOGLE_TASKS_LOCK_TIMEOUT_MS", 10_000)
    monkeypatch.setattr(
        service.oauth_service,
        "get_user_integration",
        lambda *_args: SimpleNamespace(granted_scopes=None),
    )

    async def wait_for(event, timeout):
        deadline = time.monotonic() + timeout
        while not event.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        return event.is_set()

    # Both syncs use the test engine's two pooled connections; the probe needs its own.
    probe_engine = create_engine(db_engine.url, poolclass=NullPool)

    def second_sync_blocked_on_lock():
        with probe_engine.connect() as probe:
            return probe.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock' "
                    "AND cardinality(pg_blocking_pids(pid)) > 0 "
                    "AND query ILIKE '%memberships%')"
                )
            ).scalar_one()

    async def token(sync_db, *_args):
        calls.append(threading.get_ident())
        sync_db.commit()  # A token refresh must not release the authorization lock.
        entered.set()
        if not same_user:
            await asyncio.sleep(0.2)
            return None
        if len(calls) == 1:
            # Hold the membership lock until the second sync waits on it, then until the
            # shared loop has run during that wait. A blocked loop never acknowledges.
            deadline = time.monotonic() + 5
            while not second_sync_blocked_on_lock() and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            second_waiting.set()
            await wait_for(loop_ran_during_wait, 5)
        return None

    monkeypatch.setattr(service.oauth_service, "get_access_token_async", token)

    async def sync(target_user_id):
        with open_session() as db:
            result = await service.sync_google_tasks_for_user_async(
                db, user_id=target_user_id, org_id=org_id
            )
            db.commit()
            return result

    async def acknowledge_loop_during_wait():
        if await wait_for(second_waiting, 10):
            loop_ran_during_wait.set()

    first = asyncio.create_task(sync(user_id))
    acknowledge = asyncio.create_task(acknowledge_loop_during_wait()) if same_user else None
    try:
        while not entered.is_set() and not first.done():
            await asyncio.sleep(0.005)
        results = await asyncio.gather(first, sync(second_user_id))
        assert results == [0, 0]
        assert len(calls) == 2
        assert all(thread_id != main_thread for thread_id in calls)
        if same_user:
            assert second_waiting.is_set()
            assert loop_ran_during_wait.is_set()
    finally:
        pending = [task for task in (first, acknowledge) if task is not None]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        probe_engine.dispose()


@pytest.mark.asyncio
async def test_sync_lock_timeout_is_retryable_and_preserves_caller_transaction(
    sync_sessions, monkeypatch
):
    open_session, user_id, org_id = sync_sessions
    monkeypatch.setattr(service, "GOOGLE_TASKS_LOCK_TIMEOUT_MS", 100, raising=False)
    monkeypatch.setattr(
        service.oauth_service,
        "get_user_integration",
        lambda *_args: SimpleNamespace(granted_scopes=None),
    )
    provider_calls = []

    async def token(*_args):
        provider_calls.append(True)
        return None

    monkeypatch.setattr(service.oauth_service, "get_access_token_async", token)
    with open_session() as holder, open_session() as contender:
        service.require_active_google_tasks_membership(
            holder, user_id=user_id, org_id=org_id, lock=True
        )
        before = contender.execute(text("SHOW lock_timeout")).scalar_one()
        start = time.monotonic()
        with pytest.raises(RuntimeError, match="Google Tasks sync failed"):
            await service.sync_google_tasks_for_user_async(
                contender, user_id=user_id, org_id=org_id
            )
        assert time.monotonic() - start < 1
        assert provider_calls == []
        assert contender.execute(text("SELECT 1")).scalar_one() == 1
        assert contender.execute(text("SHOW lock_timeout")).scalar_one() == before
        holder.rollback()
        assert (
            await service.sync_google_tasks_for_user_async(
                contender, user_id=user_id, org_id=org_id
            )
            == 0
        )
        assert provider_calls == [True]


@pytest.mark.asyncio
async def test_sync_rolls_back_partial_work_even_after_provider_commit(db, test_org, monkeypatch):
    from app.db.models import Organization

    original_name = test_org.name
    org_id = test_org.id
    db.execute(text("SET LOCAL lock_timeout = '750ms'"))

    async def incomplete(sync_db, **_kwargs):
        org = sync_db.get(Organization, org_id)
        org.name = "Partial sync"
        sync_db.commit()  # OAuth refresh may commit internally.
        raise RuntimeError("provider failure with sensitive details")

    monkeypatch.setattr(service, "_sync_google_tasks_for_user_async", incomplete)
    monkeypatch.setattr(
        service.oauth_service, "get_user_integration", lambda *_args: SimpleNamespace()
    )
    with pytest.raises(RuntimeError, match="Google Tasks sync failed") as error:
        await service.sync_google_tasks_for_user_async(db, user_id=uuid4(), org_id=org_id)
    assert "sensitive" not in str(error.value)
    db.refresh(test_org)
    assert test_org.name == original_name
    assert db.execute(text("SHOW lock_timeout")).scalar_one() == "750ms"


@pytest.mark.asyncio
async def test_membership_revocation_while_sync_waits_blocks_provider_access(
    sync_sessions, monkeypatch
):
    open_session, user_id, org_id = sync_sessions
    provider_calls = []
    monkeypatch.setattr(
        service.oauth_service,
        "get_user_integration",
        lambda *_args: SimpleNamespace(granted_scopes=None),
    )

    async def token(*_args):
        provider_calls.append(True)
        return None

    monkeypatch.setattr(service.oauth_service, "get_access_token_async", token)
    with open_session() as revoker, open_session() as sync_db:
        revoker.execute(text("UPDATE memberships SET is_active = false"))

        async def commit_revocation():
            await asyncio.sleep(0.1)
            revoker.commit()

        commit = asyncio.create_task(commit_revocation())
        try:
            with pytest.raises(ValueError, match="no active membership"):
                await service.sync_google_tasks_for_user_async(
                    sync_db, user_id=user_id, org_id=org_id
                )
            assert provider_calls == []
        finally:
            await commit


@pytest.mark.asyncio
async def test_sync_success_keeps_commit_with_caller_and_restores_timeouts(
    sync_sessions, monkeypatch
):
    open_session, user_id, org_id = sync_sessions

    async def complete(sync_db, **_kwargs):
        assert sync_db.execute(text("SHOW lock_timeout")).scalar_one() == "2s"
        assert sync_db.execute(text("SHOW statement_timeout")).scalar_one() == "10s"
        sync_db.execute(text("UPDATE memberships SET role = 'case_manager'"))
        sync_db.commit()
        return 1

    monkeypatch.setattr(service, "_sync_google_tasks_for_user_async", complete)
    monkeypatch.setattr(
        service.oauth_service, "get_user_integration", lambda *_args: SimpleNamespace()
    )
    with open_session() as db:
        db.execute(text("SET LOCAL lock_timeout = '750ms'"))
        statement_timeout = db.execute(text("SHOW statement_timeout")).scalar_one()
        assert (
            await service.sync_google_tasks_for_user_async(db, user_id=user_id, org_id=org_id) == 1
        )
        assert db.execute(text("SELECT role FROM memberships")).scalar_one() == "case_manager"
        assert db.execute(text("SHOW lock_timeout")).scalar_one() == "750ms"
        assert db.execute(text("SHOW statement_timeout")).scalar_one() == statement_timeout
        db.rollback()
        assert db.execute(text("SELECT role FROM memberships")).scalar_one() == "admin"


@pytest.mark.asyncio
async def test_sync_provider_deadline_rolls_back_and_raises_for_retry(db, test_org, monkeypatch):
    from app.db.models import Organization

    org_id, original_name = test_org.id, test_org.name
    monkeypatch.setattr(service, "GOOGLE_TASKS_SYNC_TIMEOUT_SECONDS", 0.05)

    async def stalled(sync_db, **_kwargs):
        sync_db.get(Organization, org_id).name = "Partial sync"
        sync_db.flush()
        await asyncio.sleep(10)
        return 1

    monkeypatch.setattr(service, "_sync_google_tasks_for_user_async", stalled)
    start = time.monotonic()
    with pytest.raises(RuntimeError, match="Google Tasks sync failed \\(TimeoutError\\)"):
        await service.sync_google_tasks_for_user_async(db, user_id=uuid4(), org_id=org_id)
    assert time.monotonic() - start < 1
    db.refresh(test_org)
    assert test_org.name == original_name
