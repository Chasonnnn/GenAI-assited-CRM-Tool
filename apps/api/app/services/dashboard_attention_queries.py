"""Unpaginated attention datasets shared by dashboard rows and totals."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query, Session

from app.db.enums import OwnerType, TaskType
from app.db.models import (
    Donor,
    DonorStatusHistory,
    Pipeline,
    PipelineStage,
    Surrogate,
    SurrogateActivityLog,
    SurrogateStatusHistory,
    Task,
)
from app.schemas.auth import UserSession
from app.services import record_scope_service

ATTENTION_STUCK_DAYS = 90
ATTENTION_STUCK_EXCLUDED_STAGE_TYPES = ("post_approval", "paused", "terminal")
ATTENTION_STUCK_EXCLUDED_STAGE_KEYS = ("on_hold", "lost", "disqualified")
ATTENTION_DONOR_STUCK_EXCLUDED_STAGE_TYPES = ("paused", "terminal")


def attention_stuck_stage_filters():
    """Exclude post-approval, paused, terminal, and legacy semantic stage keys."""
    return (
        PipelineStage.stage_type.notin_(ATTENTION_STUCK_EXCLUDED_STAGE_TYPES),
        PipelineStage.stage_key.notin_(ATTENTION_STUCK_EXCLUDED_STAGE_KEYS),
    )


def attention_stuck_donor_stage_filters(org_id: UUID):
    """Require a same-organization pipeline matching each donor subtype."""
    return (
        Pipeline.organization_id == org_id,
        or_(
            and_(
                Donor.donor_type == "egg",
                Pipeline.entity_type == "egg_donor",
            ),
            and_(
                Donor.donor_type == "sperm",
                Pipeline.entity_type == "sperm_donor",
            ),
        ),
        PipelineStage.stage_type.notin_(ATTENTION_DONOR_STUCK_EXCLUDED_STAGE_TYPES),
    )


def unreached_surrogates(
    db: Session,
    org_id: UUID,
    *,
    cutoff: datetime,
    visibility_filters: list,
    owner_filters: list,
    pipeline_id: UUID | None,
) -> Query:
    latest_activity_subquery = (
        db.query(
            SurrogateActivityLog.surrogate_id.label("surrogate_id"),
            func.max(SurrogateActivityLog.created_at).label("last_activity_at"),
        )
        .filter(SurrogateActivityLog.organization_id == org_id)
        .group_by(SurrogateActivityLog.surrogate_id)
        .subquery()
    )
    last_touch_at = func.coalesce(
        latest_activity_subquery.c.last_activity_at,
        Surrogate.updated_at,
        Surrogate.created_at,
    )

    unreached_query = (
        db.query(Surrogate, PipelineStage.label.label("stage_label"))
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            latest_activity_subquery,
            latest_activity_subquery.c.surrogate_id == Surrogate.id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            PipelineStage.stage_type == "intake",
            PipelineStage.order <= 2,  # Only first 2 intake stages
            Surrogate.created_at < cutoff,
            last_touch_at < cutoff,
            or_(
                Surrogate.last_contacted_at.is_(None),
                Surrogate.last_contacted_at < cutoff,
            ),
            *visibility_filters,
            *owner_filters,
        )
    )

    if pipeline_id:
        unreached_query = unreached_query.filter(PipelineStage.pipeline_id == pipeline_id)

    return unreached_query.order_by(Surrogate.created_at.asc())


def overdue_tasks(
    db: Session,
    org_id: UUID,
    *,
    today: date,
    visibility_filters: list,
    effective_owner_id: UUID | None,
    owner_only: bool,
    pipeline_id: UUID | None,
    non_admin_visibility: bool,
    can_view_donors: bool,
    scope_session: UserSession | None,
) -> Query:
    from app.services import task_service

    task_filters = [
        Task.organization_id == org_id,
        task_service.task_subjects_belong_to_org(org_id),
        Task.due_date < today,
        Task.is_completed.is_(False),
        Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
    ]
    if not can_view_donors:
        task_filters.append(Task.donor_id.is_(None))
    if effective_owner_id:
        task_filters.extend(
            [
                Task.owner_type == OwnerType.USER.value,
                Task.owner_id == effective_owner_id,
            ]
        )
    elif owner_only:
        task_filters.append(Task.id.is_(None))

    if scope_session is not None:
        task_filters.append(
            record_scope_service.build_linked_visibility_filter(db, scope_session, Task)
        )

    overdue_tasks_query = db.query(Task)
    if pipeline_id:
        overdue_tasks_query = overdue_tasks_query.join(
            Surrogate,
            and_(
                Task.surrogate_id == Surrogate.id,
                Surrogate.organization_id == org_id,
            ),
        )
        task_filters.extend(
            [
                Surrogate.is_archived.is_(False),
                *visibility_filters,
            ]
        )
        overdue_tasks_query = overdue_tasks_query.join(
            PipelineStage, Surrogate.stage_id == PipelineStage.id
        )
        task_filters.append(PipelineStage.pipeline_id == pipeline_id)
    elif non_admin_visibility:
        overdue_tasks_query = overdue_tasks_query.outerjoin(
            Surrogate,
            and_(
                Task.surrogate_id == Surrogate.id,
                Surrogate.organization_id == org_id,
            ),
        )
        task_filters.append(
            or_(
                Task.surrogate_id.is_(None),
                and_(
                    Surrogate.id.is_not(None),
                    Surrogate.is_archived.is_(False),
                    *visibility_filters,
                ),
            )
        )

    return overdue_tasks_query.filter(and_(*task_filters)).order_by(Task.due_date.asc())


def stuck_surrogates(
    db: Session,
    org_id: UUID,
    *,
    cutoff: datetime,
    visibility_filters: list,
    owner_filters: list,
    pipeline_id: UUID | None,
) -> Query:
    latest_stage_change_subquery = (
        db.query(
            SurrogateStatusHistory.surrogate_id.label("surrogate_id"),
            func.max(SurrogateStatusHistory.changed_at).label("last_change_at"),
        )
        .filter(
            SurrogateStatusHistory.organization_id == org_id,
            SurrogateStatusHistory.to_stage_id.is_not(None),
        )
        .group_by(SurrogateStatusHistory.surrogate_id)
        .subquery()
    )

    last_change_col = func.coalesce(
        latest_stage_change_subquery.c.last_change_at,
        Surrogate.created_at,
    )
    stuck_query = (
        db.query(
            Surrogate,
            PipelineStage.label.label("stage_label"),
            last_change_col.label("last_change"),
        )
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            latest_stage_change_subquery,
            latest_stage_change_subquery.c.surrogate_id == Surrogate.id,
        )
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            *attention_stuck_stage_filters(),
            last_change_col < cutoff,
            *visibility_filters,
            *owner_filters,
        )
    )

    if pipeline_id:
        stuck_query = stuck_query.filter(PipelineStage.pipeline_id == pipeline_id)

    return stuck_query.order_by(last_change_col.asc())


def stuck_donors(
    db: Session,
    org_id: UUID,
    *,
    cutoff: datetime,
    effective_owner_id: UUID | None,
    owner_only: bool,
    pipeline_id: UUID | None,
    scope_session: UserSession | None,
) -> Query:
    donor_owner_filters = []
    if effective_owner_id:
        donor_owner_filters = [
            Donor.owner_type == OwnerType.USER.value,
            Donor.owner_id == effective_owner_id,
        ]
    elif owner_only:
        donor_owner_filters = [Donor.id.is_(None)]

    latest_donor_stage_change = (
        db.query(
            DonorStatusHistory.donor_id.label("donor_id"),
            func.max(DonorStatusHistory.effective_at).label("last_change_at"),
        )
        .filter(
            DonorStatusHistory.organization_id == org_id,
            DonorStatusHistory.new_stage_id.is_not(None),
        )
        .group_by(DonorStatusHistory.donor_id)
        .subquery()
    )
    donor_last_change_col = func.coalesce(
        latest_donor_stage_change.c.last_change_at,
        Donor.created_at,
    )
    donor_stuck_filters = [
        Donor.organization_id == org_id,
        Donor.is_archived.is_(False),
        *attention_stuck_donor_stage_filters(org_id),
        donor_last_change_col < cutoff,
        *donor_owner_filters,
    ]
    if scope_session is not None:
        donor_stuck_filters.append(
            record_scope_service.build_visibility_filter(db, scope_session, "donor")
        )
    if pipeline_id:
        donor_stuck_filters.append(PipelineStage.pipeline_id == pipeline_id)

    donor_stuck_query = (
        db.query(
            Donor,
            PipelineStage.label.label("stage_label"),
            donor_last_change_col.label("last_change"),
        )
        .join(PipelineStage, Donor.stage_id == PipelineStage.id)
        .join(Pipeline, PipelineStage.pipeline_id == Pipeline.id)
        .outerjoin(
            latest_donor_stage_change,
            latest_donor_stage_change.c.donor_id == Donor.id,
        )
        .filter(*donor_stuck_filters)
    )
    return donor_stuck_query.order_by(donor_last_change_col.asc())
