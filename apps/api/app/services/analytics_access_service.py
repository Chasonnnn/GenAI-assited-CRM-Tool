"""Apply one authorized record dataset to an analytics request."""

from contextlib import contextmanager

from sqlalchemy import and_, event, false, or_, select
from sqlalchemy.orm import with_loader_criteria

from app.db.enums import Role
from app.db.models import (
    Donor,
    DonorStatusHistory,
    IntendedParent,
    MetaLead,
    Surrogate,
    SurrogateActivityLog,
    SurrogateStatusHistory,
    Task,
)
from app.services import permission_policy_service, permission_service, record_scope_service

REQUEST_CACHE_KEY = "authorized_analytics_cache"


def has_organization_record_scope(db, session) -> bool:
    effective = permission_service.get_effective_permissions(
        db, session.org_id, session.user_id, session.role.value
    )
    if not {"view_reports", "view_surrogates", "view_donors"}.issubset(effective):
        return False
    additions = record_scope_service.list_scope_additions(db, session.org_id, session.user_id)
    for module in ("surrogates", "donors"):
        rules = [record_scope_service.get_role_scope(db, session.org_id, session.role, module)]
        rules.extend(row for row in additions if row.module == module)
        if not any(
            rule.assignment == "all" and rule.phase == "all" and not rule.stage_ids
            for rule in rules
        ):
            return False
    return True


@contextmanager
def authorized_dataset(db, session):
    if not permission_policy_service.is_enabled(db, session.org_id):
        yield
        return
    permissions = permission_service.get_effective_permissions(
        db, session.org_id, session.user_id, session.role.value
    )
    visible = {}
    for kind, model, key in (
        ("surrogate", Surrogate, "view_surrogates"),
        ("donor", Donor, "view_donors"),
        ("intended_parent", IntendedParent, "view_intended_parents"),
    ):
        table = model.__table__.alias(f"analytics_visible_{kind}")
        predicate = (
            record_scope_service.build_visibility_filter(
                db, session, kind, model=table, allow_archived=True
            )
            if key in permissions
            else false()
        )
        visible[kind] = select(table.c.id).where(predicate)
    surrogate_ids, donor_ids, parent_ids = (
        visible["surrogate"],
        visible["donor"],
        visible["intended_parent"],
    )
    organization_id = session.org_id
    include_unlinked = session.role in {Role.INTAKE_SPECIALIST, Role.ADMIN, Role.DEVELOPER}
    view_surrogates = "view_surrogates" in permissions
    view_donors = "view_donors" in permissions
    options = (
        with_loader_criteria(
            Surrogate,
            lambda cls: cls.id.in_(surrogate_ids),
            include_aliases=True,
            propagate_to_loaders=False,
        ),
        with_loader_criteria(
            Donor,
            lambda cls: cls.id.in_(donor_ids),
            include_aliases=True,
            propagate_to_loaders=False,
        ),
        with_loader_criteria(
            IntendedParent,
            lambda cls: cls.id.in_(parent_ids),
            include_aliases=True,
            propagate_to_loaders=False,
        ),
        with_loader_criteria(
            SurrogateStatusHistory,
            lambda cls: cls.surrogate_id.in_(surrogate_ids),
            include_aliases=True,
            propagate_to_loaders=False,
        ),
        with_loader_criteria(
            SurrogateActivityLog,
            lambda cls: cls.surrogate_id.in_(surrogate_ids),
            include_aliases=True,
            propagate_to_loaders=False,
        ),
        with_loader_criteria(
            DonorStatusHistory,
            lambda cls: cls.donor_id.in_(donor_ids),
            include_aliases=True,
            propagate_to_loaders=False,
        ),
        with_loader_criteria(
            MetaLead,
            lambda cls: and_(
                cls.organization_id == organization_id,
                or_(
                    cls.converted_surrogate_id.in_(surrogate_ids),
                    cls.converted_donor_id.in_(donor_ids),
                    and_(
                        include_unlinked,
                        cls.converted_surrogate_id.is_(None),
                        cls.converted_donor_id.is_(None),
                        or_(
                            and_(view_surrogates, cls.lead_kind == "surrogate"),
                            and_(view_donors, cls.lead_kind.in_(("egg_donor", "sperm_donor"))),
                            and_(view_surrogates, view_donors, cls.lead_kind.is_(None)),
                        ),
                    ),
                ),
            ),
            include_aliases=True,
            propagate_to_loaders=False,
        ),
        with_loader_criteria(
            Task,
            record_scope_service.build_linked_visibility_filter(
                db, session, Task, permissions=permissions
            ),
            include_aliases=True,
            propagate_to_loaders=False,
        ),
    )

    def scope_query(state):
        if state.is_select and state.is_orm_statement:
            state.statement = state.statement.options(*options)

    # Record ownership and collaborator removals must affect the next request.
    # A request-local cache shares repeated report sections without stale grants.
    previous_cache = db.info.get(REQUEST_CACHE_KEY)
    db.info[REQUEST_CACHE_KEY] = {}
    event.listen(db, "do_orm_execute", scope_query)
    try:
        yield
    finally:
        event.remove(db, "do_orm_execute", scope_query)
        if previous_cache is None:
            db.info.pop(REQUEST_CACHE_KEY, None)
        else:
            db.info[REQUEST_CACHE_KEY] = previous_cache
