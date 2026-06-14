"""Defense-in-depth multi-tenant org-scoping backstop.

Every service query is *supposed* to filter by ``organization_id``. That
convention is the project's #1 non-negotiable, but it has no enforcement: a
single forgotten ``.where(Model.organization_id == org_id)`` silently leaks one
tenant's data into another's request.

This module adds a safety net behind those manual filters. A SQLAlchemy
``do_orm_execute`` listener inspects every ORM ``SELECT`` and injects a
``with_loader_criteria`` ``WHERE organization_id = :org`` for every org-scoped
entity in the statement — i.e. any mapped class that has an ``organization_id``
column. Globals (Organization, association tables without ``organization_id``)
are left untouched, and the relevant entities are discovered from
``ORMExecuteState.all_mappers`` so new models are covered automatically with no
registry to maintain.

Why per-session (not a global ``Session``-class listener)
--------------------------------------------------------
The listener is attached to an *individual session instance* by
:func:`set_org_scope` and removed by :func:`clear_org_scope` — it is **not**
registered globally on the ``Session`` class. This is deliberate and load-bearing:

* **Request-scoped, not process-wide.** Only request sessions (stamped by
  ``get_current_session``) carry the backstop; worker/CLI/job sessions never do.
  The scope is bound to the request lifecycle (stamped at auth, cleared by
  ``clear_org_scope_middleware`` at request end).
* **``yield_per`` safety.** Merely *registering* a ``do_orm_execute`` listener on
  the ``Session`` class — even an inert one — makes SQLAlchemy require uniquing on
  ``selectin``/eager post-loads driven by a ``yield_per`` stream, which then
  raises "Can't use the ORM yield_per feature in conjunction with unique()".
  The platform's streaming queries (task notifications, campaign sends, admin
  export) all run on **worker** ``SessionLocal()`` sessions; by attaching the
  listener only to stamped request sessions, those streams never see it and keep
  working. (A request handler must therefore not run a ``yield_per`` stream on
  its own scoped session — use a worker session, as the codebase already does.)

Other design properties:

* **Opt-out per statement.** ``select(...).execution_options(skip_org_scope=True)``
  bypasses the backstop for legitimate cross-org queries (platform/ops tooling).
* **Cache-safe.** The criteria uses the lambda form so ``org_id`` is tracked as a
  re-evaluated bound parameter rather than baked into the compiled-statement
  cache — otherwise one org's id could be reused for another org's query.

It is a backstop, not a replacement: services must keep their explicit
``organization_id`` filters (they also scope writes, which this does not touch).

Coverage
--------
This backstop constrains **top-level** ORM ``SELECT`` statements — the dominant
leak vector, i.e. a service query that forgets its ``organization_id`` filter.
It deliberately does NOT rewrite relationship post-loads (lazy/selectin/joined)
or deferred column loads. In practice cross-tenant relationship traversal is
already prevented by the foreign-key data model (org-scoped rows never reference
another org's rows). Extending the backstop to relationship loads (via a shared
``OrgScoped`` mixin + ``propagate_to_loaders=True``) is a documented follow-up.
"""

from __future__ import annotations

import uuid

from sqlalchemy import event, or_
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

# Key under which the active organization id is stored in ``Session.info``.
ORG_SCOPE_KEY = "org_scope_id"
# Per-statement execution option to bypass the backstop.
SKIP_ORG_SCOPE = "skip_org_scope"
# Column that marks an entity as organization-scoped.
_ORG_COLUMN = "organization_id"
# SQLAlchemy event identifier the listener attaches to.
_EVENT = "do_orm_execute"


def set_org_scope(session: Session, org_id: uuid.UUID | str | None) -> None:
    """Stamp the active org on a session and arm the backstop for it.

    Stores ``org_id`` in ``session.info`` and attaches the ``do_orm_execute``
    listener to *this session instance* (idempotently). Subsequent SELECTs on the
    session are restricted to ``org_id`` for every org-scoped entity. Passing
    ``None`` clears the scope (see :func:`clear_org_scope`).
    """
    if org_id is None:
        clear_org_scope(session)
        return

    session.info[ORG_SCOPE_KEY] = org_id
    if not event.contains(session, _EVENT, _apply_org_scope):
        event.listen(session, _EVENT, _apply_org_scope)


def clear_org_scope(session: Session) -> None:
    """Remove the active org scope from a session and disarm the backstop.

    Pops the stamp from ``session.info`` and detaches the per-session listener so
    the session behaves like an unscoped worker session again (critical for the
    test harness, where one session is reused across a request and direct calls).
    """
    session.info.pop(ORG_SCOPE_KEY, None)
    if event.contains(session, _EVENT, _apply_org_scope):
        event.remove(session, _EVENT, _apply_org_scope)


def current_org_scope(session: Session) -> uuid.UUID | str | None:
    """Return the org id currently scoping this session, if any."""
    return session.info.get(ORG_SCOPE_KEY)


def _apply_org_scope(state: ORMExecuteState) -> None:
    # Only constrain TOP-LEVEL ORM SELECTs:
    #   * ``is_relationship_load`` — lazy/selectin/joined post-loads. Leave these
    #     to the FK data model; rewriting them would also re-introduce the
    #     yield_per/uniquing incompatibility on streamed post-loads.
    #   * ``is_column_load`` — a deferred/expired column reload for a row already
    #     identified; there is no entity criteria to add.
    if not state.is_select or state.is_relationship_load or state.is_column_load:
        return

    org_id = state.session.info.get(ORG_SCOPE_KEY)
    if org_id is None:
        return

    if state.execution_options.get(SKIP_ORG_SCOPE):
        return

    options = []
    for mapper in state.all_mappers:
        if _ORG_COLUMN not in mapper.columns:
            continue
        entity = mapper.class_
        # A NULLABLE organization_id means NULL == "platform-global / unowned"
        # (e.g. WorkflowTemplate published platform-wide, request_metrics_rollup
        # for unauthenticated traffic). Such rows belong to every scope, so admit
        # them alongside the active org. The 118 tenant models have a NOT NULL
        # column, so they keep the strict ``== org_id`` form (no IS NULL noise).
        nullable_org = mapper.columns[_ORG_COLUMN].nullable

        # Lambda form is REQUIRED: it registers ``org_id`` as a bound parameter
        # re-read on every execution. A plain ``entity.organization_id == org_id``
        # expression would be baked into the cached statement and could apply one
        # org's id to another org's query (a cross-tenant leak via the cache).
        if nullable_org:
            criteria = lambda cls: or_(  # noqa: E731
                cls.organization_id == org_id, cls.organization_id.is_(None)
            )
        else:
            criteria = lambda cls: cls.organization_id == org_id  # noqa: E731

        options.append(
            with_loader_criteria(
                entity,
                criteria,
                # include_aliases is left at its default of False on purpose:
                # applying the criteria to *aliases* of an org-scoped entity turns
                # LEFT OUTER JOINs against those aliases (e.g. an owner/creator
                # User alias in the surrogate export) into inner joins, dropping
                # rows whose alias is NULL or cross-org. The backstop only needs to
                # constrain the primary/queried entities; FK integrity keeps
                # aliased look-ups in-org.
                propagate_to_loaders=False,
            )
        )

    if options:
        state.statement = state.statement.options(*options)
