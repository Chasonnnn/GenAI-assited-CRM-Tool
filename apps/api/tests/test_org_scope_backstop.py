"""Tests for the defense-in-depth multi-tenant org-scoping backstop.

The backstop is a SQLAlchemy ``do_orm_execute`` listener (app/db/org_scope.py)
that, when a session is stamped with the active organization (via
``set_org_scope``), restricts every org-scoped entity (any mapped class with an
``organization_id`` column) to that organization. It sits BEHIND the explicit
``.organization_id == org_id`` filters services already apply, catching the case
where a query forgets the filter.

Lifecycle: ``get_current_session`` stamps the request's session at auth time and
``clear_org_scope_middleware`` clears it at request end, so the scope is strictly
request-bounded. Worker/CLI sessions never stamp and are unaffected.

These tests use ``Queue`` as a minimal org-scoped model (only organization_id +
name are required).
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError

import pytest
from sqlalchemy import select

from app.db.models import Organization, Queue
from app.db.org_scope import (
    ORG_SCOPE_KEY,
    clear_org_scope,
    current_org_scope,
    set_org_scope,
)


def _make_org(db, name: str) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        name=name,
        slug=f"{name.lower()}-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(org)
    db.flush()
    return org


def _make_queue(db, org: Organization, name: str) -> Queue:
    q = Queue(organization_id=org.id, name=name)
    db.add(q)
    db.flush()
    return q


@pytest.fixture(autouse=True)
def _reset_scope(db):
    """Ensure no org scope leaks into/out of a test via the shared session."""
    clear_org_scope(db)
    yield
    clear_org_scope(db)


def test_unscoped_session_sees_all_orgs(db, test_org):
    """Baseline: without a scope stamp, a forgotten-filter query leaks every org.

    This documents the vulnerability the backstop defends against — and proves
    the backstop is opt-in (worker/CLI/public sessions are unaffected).
    """
    org_b = _make_org(db, "OrgB")
    q_a = _make_queue(db, test_org, "A-queue")
    q_b = _make_queue(db, org_b, "B-queue")

    ids = {q.id for q in db.scalars(select(Queue)).all()}
    assert {q_a.id, q_b.id} <= ids


def test_backstop_blocks_forgotten_org_filter(db, test_org):
    """With org A scope set, a query that omits the org filter must not see org B."""
    org_b = _make_org(db, "OrgB")
    q_a = _make_queue(db, test_org, "A-queue")
    q_b = _make_queue(db, org_b, "B-queue")

    set_org_scope(db, test_org.id)

    ids = {q.id for q in db.scalars(select(Queue)).all()}
    assert q_a.id in ids
    assert q_b.id not in ids

    # A by-id lookup that crosses tenants returns nothing (fresh SELECT, not identity map).
    assert db.scalars(select(Queue).where(Queue.id == q_b.id)).first() is None
    assert db.scalars(select(Queue).where(Queue.id == q_a.id)).first() is not None


def test_backstop_blocks_legacy_query_api(db, test_org):
    """The backstop also covers the legacy ``db.query(...)`` API, not just 2.0 select()."""
    org_b = _make_org(db, "OrgB")
    q_a = _make_queue(db, test_org, "A-queue")
    q_b = _make_queue(db, org_b, "B-queue")

    set_org_scope(db, test_org.id)

    ids = {q.id for q in db.query(Queue).all()}
    assert q_a.id in ids
    assert q_b.id not in ids


def test_backstop_is_cache_safe_across_orgs(db, test_org):
    """Switching the scoped org must change results — guards the statement-cache
    cross-tenant bug where org_id is baked into the cached query instead of being
    a re-evaluated bound parameter."""
    org_b = _make_org(db, "OrgB")
    q_a = _make_queue(db, test_org, "A-queue")
    q_b = _make_queue(db, org_b, "B-queue")
    db.expire_all()

    set_org_scope(db, test_org.id)
    a_ids = {q.id for q in db.scalars(select(Queue)).all()}
    assert q_a.id in a_ids
    assert q_b.id not in a_ids

    set_org_scope(db, org_b.id)
    b_ids = {q.id for q in db.scalars(select(Queue)).all()}
    assert q_b.id in b_ids
    assert q_a.id not in b_ids

    # Back to A to confirm the value is truly re-bound each execution.
    set_org_scope(db, test_org.id)
    a_ids2 = {q.id for q in db.scalars(select(Queue)).all()}
    assert q_a.id in a_ids2
    assert q_b.id not in a_ids2


def test_backstop_coexists_with_yield_per(db, test_org):
    """Regression: a scoped session must still run ``yield_per`` streams.

    A naive backstop that injected criteria into relationship post-loads breaks
    SQLAlchemy's chunked loader ("Can't use yield_per in conjunction with
    unique()"). Our listener only constrains the top-level SELECT and keeps the
    criteria off post-loads (propagate_to_loaders=False), so streaming services
    (task notifications, campaign sends, admin export) keep working — and stay
    correctly scoped.
    """
    org_b = _make_org(db, "OrgB")
    for i in range(5):
        _make_queue(db, test_org, f"a{i}")
        _make_queue(db, org_b, f"b{i}")

    set_org_scope(db, test_org.id)

    # Legacy Query API (matches task_service / admin_export_service).
    legacy = list(db.query(Queue).yield_per(2))
    assert legacy
    assert all(q.organization_id == test_org.id for q in legacy)

    # 2.0 select() with the yield_per execution option.
    modern = list(db.scalars(select(Queue).execution_options(yield_per=2)))
    assert modern
    assert all(q.organization_id == test_org.id for q in modern)


def test_skip_org_scope_execution_option_opts_out(db, test_org):
    """Legitimate cross-org queries can opt out via execution_options(skip_org_scope=True)."""
    org_b = _make_org(db, "OrgB")
    q_b = _make_queue(db, org_b, "B-queue")

    set_org_scope(db, test_org.id)

    # Default: blocked.
    assert q_b.id not in {q.id for q in db.scalars(select(Queue)).all()}

    # Opt-out: visible.
    rows = db.scalars(select(Queue).execution_options(skip_org_scope=True)).all()
    assert q_b.id in {q.id for q in rows}


def test_global_models_are_not_filtered(db, test_org):
    """Models without an organization_id column (e.g. Organization) must not be
    filtered by the backstop even when a scope is set."""
    org_b = _make_org(db, "OrgB")

    set_org_scope(db, test_org.id)

    org_ids = {o.id for o in db.scalars(select(Organization)).all()}
    assert test_org.id in org_ids
    assert org_b.id in org_ids


def test_nullable_org_treats_null_as_global(db, test_org):
    """Models with a NULLABLE organization_id treat NULL as platform-global.

    Such rows (e.g. a system/platform WorkflowTemplate) belong to every scope, so
    they stay visible under an active org scope — while another org's rows do not.
    This is what lets ``/templates`` surface platform-published templates to a
    tenant even though the backstop is active.
    """
    from app.db.models import WorkflowTemplate

    org_b = _make_org(db, "OrgB")
    global_tpl = WorkflowTemplate(
        name=f"global-{uuid.uuid4().hex[:8]}",
        trigger_type="surrogate_created",
        is_global=True,
        organization_id=None,
    )
    org_b_tpl = WorkflowTemplate(
        name=f"orgb-{uuid.uuid4().hex[:8]}",
        trigger_type="surrogate_created",
        organization_id=org_b.id,
    )
    db.add_all([global_tpl, org_b_tpl])
    db.flush()

    set_org_scope(db, test_org.id)

    ids = {t.id for t in db.scalars(select(WorkflowTemplate)).all()}
    assert global_tpl.id in ids  # NULL-org global row stays visible
    assert org_b_tpl.id not in ids  # another org's row is hidden


def test_set_org_scope_none_clears(db, test_org):
    org_b = _make_org(db, "OrgB")
    q_b = _make_queue(db, org_b, "B-queue")

    set_org_scope(db, test_org.id)
    assert ORG_SCOPE_KEY in db.info
    assert q_b.id not in {q.id for q in db.scalars(select(Queue)).all()}

    set_org_scope(db, None)
    assert ORG_SCOPE_KEY not in db.info
    assert q_b.id in {q.id for q in db.scalars(select(Queue)).all()}


def test_request_db_provider_leaves_scope_teardown_to_middleware(monkeypatch):
    """A request session has one org-scope teardown owner.

    The request middleware clears the listener after ``call_next``. The database
    dependency must only close the session; clearing in both lifecycle hooks can
    race and make SQLAlchemy remove the same listener twice.
    """
    from sqlalchemy.orm import Session

    from app.core import deps

    session = Session()
    monkeypatch.setattr(deps, "SessionLocal", lambda: session)
    provider = deps.get_db()
    yielded = next(provider)
    org_id = uuid.uuid4()
    set_org_scope(yielded, org_id)

    provider.close()

    assert current_org_scope(session) == org_id
    clear_org_scope(session)


def test_concurrent_request_lifecycle_has_one_scope_teardown_owner(monkeypatch):
    """Dependency close may overlap middleware teardown without double removal.

    Synchronizing listener removal makes the former two-owner implementation
    deterministic: both cleanup paths observe the listener and attempt to remove
    it together. With middleware as the sole owner, only its thread reaches the
    removal barrier while the dependency independently closes the session.
    """
    from sqlalchemy.orm import Session

    from app.core import deps
    from app.db import org_scope

    session = Session()
    monkeypatch.setattr(deps, "SessionLocal", lambda: session)
    provider = deps.get_db()
    yielded = next(provider)
    set_org_scope(yielded, uuid.uuid4())

    remove_barrier = Barrier(2)
    real_remove = org_scope.event.remove

    def _synchronized_remove(target, identifier, fn):
        try:
            remove_barrier.wait(timeout=0.2)
        except BrokenBarrierError:
            pass
        return real_remove(target, identifier, fn)

    monkeypatch.setattr(org_scope.event, "remove", _synchronized_remove)

    with ThreadPoolExecutor(max_workers=2) as pool:
        dependency_cleanup = pool.submit(provider.close)
        middleware_cleanup = pool.submit(clear_org_scope, session)

    assert dependency_cleanup.exception() is None
    assert middleware_cleanup.exception() is None
    assert current_org_scope(session) is None


@pytest.mark.asyncio
async def test_authenticated_request_stamps_active_org(authed_client, test_auth, monkeypatch):
    """Wiring: get_current_session stamps the active org onto the request session."""
    import app.core.deps as deps

    seen: list = []
    real = deps.set_org_scope

    def _spy(session, org_id):
        seen.append(org_id)
        return real(session, org_id)

    monkeypatch.setattr(deps, "set_org_scope", _spy)

    resp = await authed_client.get("/auth/me")
    assert resp.status_code == 200
    assert test_auth.org.id in seen


def test_backstop_covers_count_select_from(db, test_org):
    """A column-less ``select(func.count()).select_from(Model)`` has an empty
    ``all_mappers``; the backstop must still scope it by recovering the entity
    from the FROM clause, or a forgotten org filter on a count leaks tenants.
    """
    from sqlalchemy import func

    org_b = _make_org(db, "OrgB")
    _make_queue(db, test_org, "A1")
    _make_queue(db, test_org, "A2")
    _make_queue(db, org_b, "B1")

    # Baseline: unscoped sees all three.
    assert db.scalar(select(func.count()).select_from(Queue)) >= 3

    set_org_scope(db, test_org.id)
    assert db.scalar(select(func.count()).select_from(Queue)) == 2


def test_backstop_covers_top_level_alias(db, test_org):
    """A top-level aliased query ``select(aliased(Model))`` must be scoped too
    (covered via include_aliases=True)."""
    from sqlalchemy.orm import aliased

    org_b = _make_org(db, "OrgB")
    q_a = _make_queue(db, test_org, "A-queue")
    q_b = _make_queue(db, org_b, "B-queue")

    set_org_scope(db, test_org.id)

    QAlias = aliased(Queue)
    ids = {q.id for q in db.scalars(select(QAlias)).all()}
    assert q_a.id in ids
    assert q_b.id not in ids


@pytest.mark.asyncio
async def test_request_scope_is_cleared_after_request(authed_client, db, test_auth):
    """The stamp is request-bounded: clear_org_scope_middleware removes it at
    request end so it can never leak onto subsequent (cross-org) work on a
    reused session."""
    resp = await authed_client.get("/auth/me")
    assert resp.status_code == 200
    assert ORG_SCOPE_KEY not in db.info
