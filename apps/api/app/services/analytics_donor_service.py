"""Subtype-aware donor analytics for reports and dashboard charts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, case, exists, func, or_
from sqlalchemy.orm import Session

from app.db.enums import OwnerType
from app.db.models import Donor, DonorStatusHistory, Pipeline, PipelineStage
from app.schemas.pipeline_semantics import normalize_feature_config, normalize_stage_semantics
from app.services import donor_service
from app.services.analytics_shared import _get_or_compute_snapshot

DonorType = Literal["egg", "sperm"]


class DonorAnalyticsPipelineNotFoundError(ValueError):
    """The requested pipeline is unavailable in the organization and subtype."""


def resolve_donor_pipeline(
    db: Session,
    organization_id: uuid.UUID,
    donor_type: DonorType,
    pipeline_id: uuid.UUID | None,
) -> Pipeline:
    expected_entity_type = donor_service.donor_pipeline_entity_type(donor_type)
    query = db.query(Pipeline).filter(
        Pipeline.organization_id == organization_id,
        Pipeline.entity_type == expected_entity_type,
    )
    if pipeline_id is not None:
        pipeline = query.filter(Pipeline.id == pipeline_id).first()
        if pipeline is None:
            raise DonorAnalyticsPipelineNotFoundError("Pipeline not found")
        return pipeline

    pipeline = query.filter(Pipeline.is_default.is_(True)).first()
    if pipeline is not None:
        return pipeline

    from app.services import pipeline_service

    return pipeline_service.get_or_create_default_pipeline(
        db,
        organization_id,
        entity_type=expected_entity_type,
    )


def _normalized_state(state: str | None) -> str | None:
    normalized = (state or "").strip().upper()
    return normalized or None


def _donor_filters(
    organization_id: uuid.UUID,
    donor_type: DonorType,
    pipeline_id: uuid.UUID,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    owner_id: uuid.UUID | None = None,
    state: str | None = None,
    include_archived: bool = False,
) -> list[Any]:
    filters: list[Any] = [
        Donor.organization_id == organization_id,
        Donor.donor_type == donor_type,
        PipelineStage.pipeline_id == pipeline_id,
    ]
    if not include_archived:
        filters.append(Donor.is_archived.is_(False))
    if start is not None:
        filters.append(Donor.created_at >= start)
    if end is not None:
        filters.append(Donor.created_at < end)
    if owner_id is not None:
        filters.extend(
            [
                Donor.owner_type == OwnerType.USER.value,
                Donor.owner_id == owner_id,
            ]
        )
    normalized_state = _normalized_state(state)
    if normalized_state is not None:
        filters.append(func.upper(Donor.state) == normalized_state)
    return filters


def get_donor_summary(
    db: Session,
    organization_id: uuid.UUID,
    donor_type: DonorType,
    *,
    start: datetime,
    end: datetime,
    pipeline_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    state: str | None = None,
    include_archived: bool = False,
) -> dict[str, Any]:
    pipeline = resolve_donor_pipeline(db, organization_id, donor_type, pipeline_id)
    active_stages = sorted(
        [stage for stage in pipeline.stages if stage.is_active],
        key=lambda stage: stage.order,
    )
    feature_config = normalize_feature_config(pipeline.feature_config, pipeline.entity_type)
    qualification_stage_key = feature_config.analytics.qualification_stage_key
    qualification_stage = next(
        (stage for stage in active_stages if stage.stage_key == qualification_stage_key),
        None,
    )
    qualified_stage_ids: list[uuid.UUID] = []
    if qualification_stage is not None:
        for stage in active_stages:
            semantics = normalize_stage_semantics(
                stage.stage_key,
                stage.stage_type,
                stage.semantics,
                pipeline.entity_type,
            )
            has_qualification_semantics = (
                stage.id == qualification_stage.id
                or semantics.capabilities.eligible_for_matching
                or semantics.capabilities.locks_match_state
            )
            if (
                stage.order >= qualification_stage.order
                and stage.stage_type not in {"paused", "terminal"}
                and has_qualification_semantics
            ):
                qualified_stage_ids.append(stage.id)
    reached_qualification = exists().where(
        and_(
            DonorStatusHistory.organization_id == organization_id,
            DonorStatusHistory.donor_id == Donor.id,
            DonorStatusHistory.new_stage_id.in_(qualified_stage_ids),
            or_(
                DonorStatusHistory.old_stage_id.is_(None),
                DonorStatusHistory.old_stage_id != DonorStatusHistory.new_stage_id,
            ),
        )
    )

    base_filters = _donor_filters(
        organization_id,
        donor_type,
        pipeline.id,
        owner_id=owner_id,
        state=state,
        include_archived=include_archived,
    )
    metrics = (
        db.query(
            func.count(Donor.id).label("total_donors"),
            func.coalesce(
                func.sum(
                    case(
                        (and_(Donor.created_at >= start, Donor.created_at < end), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("new_this_period"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            or_(
                                Donor.stage_id.in_(qualified_stage_ids),
                                reached_qualification,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("qualified_count"),
        )
        .join(PipelineStage, Donor.stage_id == PipelineStage.id)
        .filter(*base_filters)
        .one()
    )
    total_donors = int(metrics.total_donors or 0)
    qualified_count = int(metrics.qualified_count or 0)

    avg_hours: float | None = None
    if qualification_stage is not None:
        avg_value = (
            db.query(
                func.avg(
                    func.extract(
                        "epoch",
                        DonorStatusHistory.effective_at - Donor.created_at,
                    )
                    / 3600
                )
            )
            .join(Donor, Donor.id == DonorStatusHistory.donor_id)
            .join(PipelineStage, Donor.stage_id == PipelineStage.id)
            .filter(
                DonorStatusHistory.organization_id == organization_id,
                DonorStatusHistory.new_stage_id == qualification_stage.id,
                or_(
                    DonorStatusHistory.old_stage_id.is_(None),
                    DonorStatusHistory.old_stage_id != DonorStatusHistory.new_stage_id,
                ),
                DonorStatusHistory.effective_at >= start,
                DonorStatusHistory.effective_at < end,
                *base_filters,
            )
            .scalar()
        )
        if avg_value is not None:
            avg_hours = round(float(avg_value), 1)

    return {
        "donor_type": donor_type,
        "total_donors": total_donors,
        "new_this_period": int(metrics.new_this_period or 0),
        "qualification_rate": round(
            qualified_count / total_donors * 100 if total_donors else 0.0,
            1,
        ),
        "qualification_stage_key": qualification_stage_key,
        "avg_time_to_qualification_hours": avg_hours,
    }


def get_cached_donor_summary(
    db: Session,
    organization_id: uuid.UUID,
    donor_type: DonorType,
    *,
    start: datetime,
    end: datetime,
    pipeline_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    state: str | None = None,
    include_archived: bool = False,
) -> dict[str, Any]:
    pipeline = resolve_donor_pipeline(db, organization_id, donor_type, pipeline_id)
    params = {
        "donor_type": donor_type,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "pipeline_id": str(pipeline.id),
        "owner_id": str(owner_id) if owner_id else None,
        "state": _normalized_state(state),
        "include_archived": include_archived,
    }
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "donor_summary",
        params,
        lambda: get_donor_summary(
            db,
            organization_id,
            donor_type,
            start=start,
            end=end,
            pipeline_id=pipeline.id,
            owner_id=owner_id,
            state=state,
            include_archived=include_archived,
        ),
        range_start=start,
        range_end=end,
    )


def get_donors_by_status(
    db: Session,
    organization_id: uuid.UUID,
    donor_type: DonorType,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    pipeline_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    state: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    pipeline = resolve_donor_pipeline(db, organization_id, donor_type, pipeline_id)
    donor_join_filters = _donor_filters(
        organization_id,
        donor_type,
        pipeline.id,
        start=start,
        end=end,
        owner_id=owner_id,
        state=state,
        include_archived=include_archived,
    )
    rows = (
        db.query(
            PipelineStage.label.label("status"),
            PipelineStage.id.label("stage_id"),
            PipelineStage.order.label("stage_order"),
            func.count(Donor.id).label("count"),
        )
        .outerjoin(
            Donor,
            and_(
                Donor.stage_id == PipelineStage.id,
                *donor_join_filters,
            ),
        )
        .filter(
            PipelineStage.pipeline_id == pipeline.id,
            PipelineStage.is_active.is_(True),
        )
        .group_by(PipelineStage.id, PipelineStage.label, PipelineStage.order)
        .order_by(PipelineStage.order)
        .all()
    )
    return [
        {
            "status": row.status,
            "stage_id": str(row.stage_id),
            "count": int(row.count or 0),
            "order": row.stage_order,
        }
        for row in rows
    ]


def get_cached_donors_by_status(
    db: Session,
    organization_id: uuid.UUID,
    donor_type: DonorType,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    pipeline_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    state: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    pipeline = resolve_donor_pipeline(db, organization_id, donor_type, pipeline_id)
    params = {
        "donor_type": donor_type,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "pipeline_id": str(pipeline.id),
        "owner_id": str(owner_id) if owner_id else None,
        "state": _normalized_state(state),
        "include_archived": include_archived,
    }
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "donors_by_status",
        params,
        lambda: get_donors_by_status(
            db,
            organization_id,
            donor_type,
            start=start,
            end=end,
            pipeline_id=pipeline.id,
            owner_id=owner_id,
            state=state,
            include_archived=include_archived,
        ),
        range_start=start,
        range_end=end,
    )


def _timezone_name(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return ZoneInfo(value).key
    except ZoneInfoNotFoundError:
        return None


def get_donors_trend(
    db: Session,
    organization_id: uuid.UUID,
    donor_type: DonorType,
    *,
    start: datetime,
    end: datetime,
    period: Literal["day", "week", "month"] = "day",
    timezone_name: str | None = None,
    pipeline_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    state: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    pipeline = resolve_donor_pipeline(db, organization_id, donor_type, pipeline_id)
    normalized_timezone = _timezone_name(timezone_name)
    timestamp_column = (
        func.timezone(normalized_timezone, Donor.created_at)
        if normalized_timezone
        else Donor.created_at
    )
    if period == "week":
        bucket = func.date_trunc("week", timestamp_column)
    elif period == "month":
        bucket = func.date_trunc("month", timestamp_column)
    else:
        bucket = func.date(timestamp_column)

    rows = (
        db.query(bucket.label("period"), func.count(Donor.id).label("count"))
        .join(PipelineStage, Donor.stage_id == PipelineStage.id)
        .filter(
            *_donor_filters(
                organization_id,
                donor_type,
                pipeline.id,
                start=start,
                end=end,
                owner_id=owner_id,
                state=state,
                include_archived=include_archived,
            )
        )
        .group_by(bucket)
        .order_by(bucket)
        .all()
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row.period, datetime):
            period_value = row.period.strftime("%Y-%m-%d")
        elif isinstance(row.period, date):
            period_value = row.period.isoformat()
        else:
            period_value = str(row.period)
        result.append({"date": period_value, "count": int(row.count or 0)})
    return result


def get_cached_donors_trend(
    db: Session,
    organization_id: uuid.UUID,
    donor_type: DonorType,
    *,
    start: datetime,
    end: datetime,
    period: Literal["day", "week", "month"] = "day",
    timezone_name: str | None = None,
    pipeline_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    state: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    pipeline = resolve_donor_pipeline(db, organization_id, donor_type, pipeline_id)
    normalized_timezone = _timezone_name(timezone_name)
    params = {
        "donor_type": donor_type,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "period": period,
        "timezone": normalized_timezone,
        "pipeline_id": str(pipeline.id),
        "owner_id": str(owner_id) if owner_id else None,
        "state": _normalized_state(state),
        "include_archived": include_archived,
    }
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "donors_trend",
        params,
        lambda: get_donors_trend(
            db,
            organization_id,
            donor_type,
            start=start,
            end=end,
            period=period,
            timezone_name=normalized_timezone,
            pipeline_id=pipeline.id,
            owner_id=owner_id,
            state=state,
            include_archived=include_archived,
        ),
        range_start=start,
        range_end=end,
    )
