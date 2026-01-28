"""Meta analytics service (lead ads, spend, campaign filters)."""

from __future__ import annotations

import uuid
from datetime import datetime, date, timezone
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db.models import (
    MetaAdAccount,
    MetaCampaign,
    MetaDailySpend,
    MetaForm,
    MetaLead,
    Surrogate,
)
from app.services.analytics_shared import (
    FUNNEL_SLUGS,
    _apply_date_range_filters,
    _get_default_pipeline_stages,
    _get_or_compute_snapshot,
    _get_or_compute_snapshot_async,
)


def get_meta_performance(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Get Meta Lead Ads performance metrics."""
    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")
    converted_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "application_submitted")

    qualified_or_later_ids = []
    converted_or_later_ids = []
    if qualified_stage:
        qualified_or_later_ids = [
            s.id for s in stages if s.order >= qualified_stage.order and s.is_active
        ]
    if converted_stage:
        converted_or_later_ids = [
            s.id for s in stages if s.order >= converted_stage.order and s.is_active
        ]

    lead_time = func.coalesce(MetaLead.meta_created_time, MetaLead.received_at)
    leads_received = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == organization_id,
            lead_time >= start,
            lead_time < end,
        )
        .count()
    )

    leads_qualified = 0
    if qualified_or_later_ids:
        leads_qualified = (
            db.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM meta_leads ml
                JOIN surrogates c ON ml.converted_surrogate_id = c.id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
                  AND c.stage_id = ANY(:stage_ids)
            """
                ),
                {
                    "org_id": organization_id,
                    "start": start,
                    "end": end,
                    "stage_ids": qualified_or_later_ids,
                },
            ).scalar()
            or 0
        )

    leads_converted = 0
    if converted_or_later_ids:
        leads_converted = (
            db.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM meta_leads ml
                JOIN surrogates c ON ml.converted_surrogate_id = c.id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
                  AND c.stage_id = ANY(:stage_ids)
            """
                ),
                {
                    "org_id": organization_id,
                    "start": start,
                    "end": end,
                    "stage_ids": converted_or_later_ids,
                },
            ).scalar()
            or 0
        )

    qualification_rate = (leads_qualified / leads_received * 100) if leads_received > 0 else 0.0
    conversion_rate = (leads_converted / leads_received * 100) if leads_received > 0 else 0.0

    avg_hours = None
    if converted_stage:
        result = db.execute(
            text(
                """
                SELECT AVG(EXTRACT(EPOCH FROM (csh.changed_at - COALESCE(ml.meta_created_time, ml.received_at))) / 3600) as avg_hours
                FROM meta_leads ml
                JOIN surrogates c ON ml.converted_surrogate_id = c.id
                JOIN surrogate_status_history csh ON c.id = csh.surrogate_id AND csh.to_stage_id = :converted_stage_id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
            """
            ),
            {
                "org_id": organization_id,
                "start": start,
                "end": end,
                "converted_stage_id": converted_stage.id,
            },
        )
        row = result.fetchone()
        avg_hours = float(round(row[0], 1)) if row and row[0] else None

    return {
        "leads_received": leads_received,
        "leads_qualified": leads_qualified,
        "leads_converted": leads_converted,
        "qualification_rate": round(qualification_rate, 1),
        "conversion_rate": round(conversion_rate, 1),
        "avg_time_to_convert_hours": avg_hours,
    }


def get_cached_meta_performance(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "meta_performance",
        params,
        lambda: get_meta_performance(db, organization_id, start, end),
        range_start=start,
        range_end=end,
    )


def get_campaigns(
    db: Session,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Get unique meta_ad_external_id values for campaign filter dropdown."""
    results = (
        db.query(
            Surrogate.meta_ad_external_id,
            func.count(Surrogate.id).label("surrogate_count"),
        )
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.meta_ad_external_id.isnot(None),
            Surrogate.is_archived.is_(False),
        )
        .group_by(Surrogate.meta_ad_external_id)
        .order_by(func.count(Surrogate.id).desc())
        .all()
    )

    return [
        {
            "ad_id": r.meta_ad_external_id,
            "ad_name": f"Campaign {r.meta_ad_external_id[:8]}..."
            if len(r.meta_ad_external_id) > 8
            else r.meta_ad_external_id,
            "lead_count": r.surrogate_count,
        }
        for r in results
    ]


def get_cached_campaigns(
    db: Session,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "campaigns",
        {"scope": "all"},
        lambda: get_campaigns(db, organization_id),
    )


def get_funnel_with_filter(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    ad_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get conversion funnel data with optional campaign filter."""
    stages = _get_default_pipeline_stages(db, organization_id)
    stage_by_slug = {s.slug: s for s in stages if s.is_active}
    funnel_stages = [stage_by_slug[slug] for slug in FUNNEL_SLUGS if slug in stage_by_slug]
    if not funnel_stages:
        funnel_stages = sorted([s for s in stages if s.is_active], key=lambda s: s.order)[:5]

    query = db.query(Surrogate).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)
    if ad_id:
        query = query.filter(Surrogate.meta_ad_external_id == ad_id)

    active_stages = [s for s in stages if s.is_active]
    counts_by_stage = dict(
        query.with_entities(Surrogate.stage_id, func.count(Surrogate.id))
        .group_by(Surrogate.stage_id)
        .all()
    )
    total = sum(counts_by_stage.values())

    funnel_data = []
    for stage in funnel_stages:
        eligible_stage_ids = [s.id for s in active_stages if s.order >= stage.order]
        count = sum(counts_by_stage.get(stage_id, 0) for stage_id in eligible_stage_ids)
        funnel_data.append(
            {
                "stage": stage.slug,
                "label": stage.label,
                "count": count,
                "percentage": round((count / total * 100) if total > 0 else 0, 1),
            }
        )

    return funnel_data


def get_cached_funnel_with_filter(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    ad_id: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "ad_id": ad_id,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "funnel_compare",
        params,
        lambda: get_funnel_with_filter(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
            ad_id=ad_id,
        ),
        range_start=range_start,
        range_end=range_end,
    )


def get_surrogates_by_state_with_filter(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    ad_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get case count by US state with optional campaign filter."""
    query = db.query(
        Surrogate.state,
        func.count(Surrogate.id).label("count"),
    ).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
        Surrogate.state.isnot(None),
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)
    if ad_id:
        query = query.filter(Surrogate.meta_ad_external_id == ad_id)

    results = query.group_by(Surrogate.state).order_by(func.count(Surrogate.id).desc()).all()

    return [{"state": r.state, "count": r.count} for r in results]


def get_cached_surrogates_by_state_with_filter(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    ad_id: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "ad_id": ad_id,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "surrogates_by_state_compare",
        params,
        lambda: get_surrogates_by_state_with_filter(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
            ad_id=ad_id,
        ),
        range_start=range_start,
        range_end=range_end,
    )


async def get_meta_spend_summary(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
    time_increment: int | None = None,
    breakdowns: list[str] | None = None,
    ad_account_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    start_date = start.date() if start else None
    end_date = end.date() if end else None

    if not start_date or not end_date:
        return {
            "total_spend": 0.0,
            "total_impressions": 0,
            "total_leads": 0,
            "cost_per_lead": None,
            "campaigns": [],
            "time_series": [],
            "breakdowns": [],
        }

    totals = get_spend_totals(
        db=db,
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
        ad_account_id=ad_account_id,
    )

    campaigns_data = get_spend_by_campaign(
        db=db,
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
        ad_account_id=ad_account_id,
    )

    campaigns = [
        {
            "campaign_id": item["campaign_external_id"],
            "campaign_name": item["campaign_name"],
            "spend": item["spend"],
            "impressions": item["impressions"],
            "reach": 0,
            "clicks": item["clicks"],
            "leads": item["leads"],
            "cost_per_lead": item["cost_per_lead"],
        }
        for item in campaigns_data
    ]

    time_series_points = []
    if time_increment is not None:
        trend_data = get_spend_trend(
            db=db,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            ad_account_id=ad_account_id,
        )
        time_series_points = [
            {
                "date_start": point["date"],
                "date_stop": point["date"],
                "spend": point["spend"],
                "impressions": point["impressions"],
                "reach": 0,
                "clicks": point["clicks"],
                "leads": point["leads"],
                "cost_per_lead": point["cost_per_lead"],
            }
            for point in trend_data
        ]

    breakdown_points = []
    if breakdowns:
        for breakdown in breakdowns:
            breakdown_data = get_spend_by_breakdown(
                db=db,
                organization_id=organization_id,
                start_date=start_date,
                end_date=end_date,
                breakdown_type=breakdown,
                ad_account_id=ad_account_id,
            )
            for item in breakdown_data:
                breakdown_points.append(
                    {
                        "breakdown_values": {breakdown: item["breakdown_value"]},
                        "spend": item["spend"],
                        "impressions": item["impressions"],
                        "reach": 0,
                        "clicks": item["clicks"],
                        "leads": item["leads"],
                        "cost_per_lead": item["cost_per_lead"],
                    }
                )

    breakdown_points.sort(key=lambda item: item["spend"], reverse=True)

    return {
        "total_spend": totals.get("total_spend", 0.0),
        "total_impressions": totals.get("total_impressions", 0),
        "total_leads": totals.get("total_leads", 0),
        "cost_per_lead": totals.get("cost_per_lead"),
        "campaigns": campaigns,
        "time_series": time_series_points,
        "breakdowns": breakdown_points,
    }


async def get_cached_meta_spend_summary(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
    time_increment: int | None = None,
    breakdowns: list[str] | None = None,
) -> dict[str, Any]:
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "time_increment": time_increment,
        "breakdowns": breakdowns or [],
    }
    return await _get_or_compute_snapshot_async(
        db,
        organization_id,
        "meta_spend",
        params,
        lambda: get_meta_spend_summary(
            db=db,
            organization_id=organization_id,
            start=start,
            end=end,
            time_increment=time_increment,
            breakdowns=breakdowns,
        ),
        range_start=start,
        range_end=end,
    )


def get_meta_ad_accounts(
    db: Session,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Get list of ad accounts for the organization."""
    accounts = (
        db.query(MetaAdAccount)
        .filter(
            MetaAdAccount.organization_id == organization_id,
            MetaAdAccount.is_active.is_(True),
        )
        .order_by(MetaAdAccount.ad_account_name)
        .all()
    )

    return [
        {
            "id": str(a.id),
            "ad_account_external_id": a.ad_account_external_id,
            "ad_account_name": a.ad_account_name or a.ad_account_external_id,
            "hierarchy_synced_at": a.hierarchy_synced_at.isoformat()
            if a.hierarchy_synced_at
            else None,
            "spend_synced_at": a.spend_synced_at.isoformat() if a.spend_synced_at else None,
        }
        for a in accounts
    ]


def get_spend_sync_status(
    db: Session,
    organization_id: uuid.UUID,
    ad_account_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Get sync status for spend data."""
    query = db.query(MetaAdAccount).filter(
        MetaAdAccount.organization_id == organization_id,
        MetaAdAccount.is_active.is_(True),
    )

    if ad_account_id:
        query = query.filter(MetaAdAccount.id == ad_account_id)

    accounts = query.all()

    if not accounts:
        return {
            "sync_status": "never",
            "last_synced_at": None,
            "ad_accounts_configured": 0,
        }

    last_synced = None
    for a in accounts:
        if a.spend_synced_at:
            if not last_synced or a.spend_synced_at > last_synced:
                last_synced = a.spend_synced_at

    if not last_synced:
        return {
            "sync_status": "pending",
            "last_synced_at": None,
            "ad_accounts_configured": len(accounts),
        }

    return {
        "sync_status": "synced",
        "last_synced_at": last_synced.isoformat(),
        "ad_accounts_configured": len(accounts),
    }


def get_spend_by_campaign(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Aggregate spend by campaign from stored data."""
    query = (
        db.query(
            MetaDailySpend.campaign_external_id,
            MetaDailySpend.campaign_name,
            func.sum(MetaDailySpend.spend).label("spend"),
            func.sum(MetaDailySpend.impressions).label("impressions"),
            func.sum(MetaDailySpend.clicks).label("clicks"),
            func.sum(MetaDailySpend.leads).label("leads"),
        )
        .filter(
            MetaDailySpend.organization_id == organization_id,
            MetaDailySpend.spend_date >= start_date,
            MetaDailySpend.spend_date <= end_date,
            MetaDailySpend.breakdown_type == "_total",
        )
        .group_by(
            MetaDailySpend.campaign_external_id,
            MetaDailySpend.campaign_name,
        )
        .order_by(func.sum(MetaDailySpend.spend).desc())
    )

    if ad_account_id:
        query = query.filter(MetaDailySpend.ad_account_id == ad_account_id)

    results = query.all()

    campaigns = []
    for r in results:
        spend = float(r.spend) if r.spend else 0.0
        leads = int(r.leads or 0)
        cpl = round(spend / leads, 2) if leads > 0 else None

        campaigns.append(
            {
                "campaign_external_id": r.campaign_external_id,
                "campaign_name": r.campaign_name,
                "spend": round(spend, 2),
                "impressions": r.impressions or 0,
                "clicks": r.clicks or 0,
                "leads": leads,
                "cost_per_lead": cpl,
            }
        )

    return campaigns


def get_spend_by_breakdown(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    breakdown_type: str,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Aggregate spend by breakdown dimension."""
    if breakdown_type not in (
        "publisher_platform",
        "platform_position",
        "age",
        "region",
    ):
        return []

    query = (
        db.query(
            MetaDailySpend.breakdown_value,
            func.sum(MetaDailySpend.spend).label("spend"),
            func.sum(MetaDailySpend.impressions).label("impressions"),
            func.sum(MetaDailySpend.clicks).label("clicks"),
            func.sum(MetaDailySpend.leads).label("leads"),
        )
        .filter(
            MetaDailySpend.organization_id == organization_id,
            MetaDailySpend.spend_date >= start_date,
            MetaDailySpend.spend_date <= end_date,
            MetaDailySpend.breakdown_type == breakdown_type,
        )
        .group_by(MetaDailySpend.breakdown_value)
        .order_by(func.sum(MetaDailySpend.spend).desc())
    )

    if ad_account_id:
        query = query.filter(MetaDailySpend.ad_account_id == ad_account_id)

    results = query.all()

    breakdowns = []
    for r in results:
        spend = float(r.spend) if r.spend else 0.0
        leads = int(r.leads or 0)
        cpl = round(spend / leads, 2) if leads > 0 else None

        breakdowns.append(
            {
                "breakdown_value": r.breakdown_value,
                "spend": round(spend, 2),
                "impressions": r.impressions or 0,
                "clicks": r.clicks or 0,
                "leads": leads,
                "cost_per_lead": cpl,
            }
        )

    return breakdowns


def get_spend_trend(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
    campaign_external_id: str | None = None,
) -> list[dict[str, Any]]:
    """Daily spend time series from stored data."""
    query = (
        db.query(
            MetaDailySpend.spend_date,
            func.sum(MetaDailySpend.spend).label("spend"),
            func.sum(MetaDailySpend.impressions).label("impressions"),
            func.sum(MetaDailySpend.clicks).label("clicks"),
            func.sum(MetaDailySpend.leads).label("leads"),
        )
        .filter(
            MetaDailySpend.organization_id == organization_id,
            MetaDailySpend.spend_date >= start_date,
            MetaDailySpend.spend_date <= end_date,
            MetaDailySpend.breakdown_type == "_total",
        )
        .group_by(MetaDailySpend.spend_date)
        .order_by(MetaDailySpend.spend_date)
    )

    if ad_account_id:
        query = query.filter(MetaDailySpend.ad_account_id == ad_account_id)
    if campaign_external_id:
        query = query.filter(MetaDailySpend.campaign_external_id == campaign_external_id)

    results = query.all()

    trend = []
    for r in results:
        spend = float(r.spend) if r.spend else 0.0
        leads = int(r.leads or 0)
        cpl = round(spend / leads, 2) if leads > 0 else None

        trend.append(
            {
                "date": r.spend_date.isoformat(),
                "spend": round(spend, 2),
                "impressions": r.impressions or 0,
                "clicks": r.clicks or 0,
                "leads": leads,
                "cost_per_lead": cpl,
            }
        )

    return trend


def get_spend_totals(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Get aggregate spend totals for the date range."""
    query = db.query(
        func.sum(MetaDailySpend.spend).label("spend"),
        func.sum(MetaDailySpend.impressions).label("impressions"),
        func.sum(MetaDailySpend.clicks).label("clicks"),
        func.sum(MetaDailySpend.leads).label("leads"),
    ).filter(
        MetaDailySpend.organization_id == organization_id,
        MetaDailySpend.spend_date >= start_date,
        MetaDailySpend.spend_date <= end_date,
        MetaDailySpend.breakdown_type == "_total",
    )

    if ad_account_id:
        query = query.filter(MetaDailySpend.ad_account_id == ad_account_id)

    result = query.first()

    spend = float(result.spend) if result and result.spend else 0.0
    impressions = result.impressions if result else 0
    clicks = result.clicks if result else 0
    leads = int(result.leads) if result and result.leads else 0
    cpl = round(spend / leads, 2) if leads > 0 else None

    sync_status = get_spend_sync_status(db, organization_id, ad_account_id)

    return {
        "total_spend": round(spend, 2),
        "total_impressions": impressions or 0,
        "total_clicks": clicks or 0,
        "total_leads": leads or 0,
        "cost_per_lead": cpl,
        **sync_status,
    }


def get_cached_spend_by_campaign(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "ad_account_id": str(ad_account_id) if ad_account_id else None,
    }
    range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    range_end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "spend_by_campaign",
        params,
        lambda: get_spend_by_campaign(db, organization_id, start_date, end_date, ad_account_id),
        range_start=range_start,
        range_end=range_end,
    )


def get_cached_spend_by_breakdown(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    breakdown_type: str,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "breakdown_type": breakdown_type,
        "ad_account_id": str(ad_account_id) if ad_account_id else None,
    }
    range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    range_end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "spend_by_breakdown",
        params,
        lambda: get_spend_by_breakdown(
            db, organization_id, start_date, end_date, breakdown_type, ad_account_id
        ),
        range_start=range_start,
        range_end=range_end,
    )


def get_cached_spend_trend(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
    campaign_external_id: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "ad_account_id": str(ad_account_id) if ad_account_id else None,
        "campaign_external_id": campaign_external_id,
    }
    range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    range_end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "spend_trend",
        params,
        lambda: get_spend_trend(
            db,
            organization_id,
            start_date,
            end_date,
            ad_account_id,
            campaign_external_id,
        ),
        range_start=range_start,
        range_end=range_end,
    )


def get_leads_by_form(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Lead counts from meta_leads, conversion rates from joined Cases."""
    from app.services import pipeline_service

    lead_time = func.coalesce(MetaLead.meta_created_time, MetaLead.received_at)

    lead_counts_query = (
        db.query(
            MetaLead.meta_form_id.label("form_external_id"),
            func.count(MetaLead.id).label("lead_count"),
            func.count(MetaLead.converted_surrogate_id).label("surrogate_count"),
        )
        .filter(MetaLead.organization_id == organization_id)
        .filter(MetaLead.meta_form_id.isnot(None))
        .group_by(MetaLead.meta_form_id)
    )
    lead_counts_query = _apply_date_range_filters(
        lead_counts_query, lead_time, start_date, end_date
    )

    lead_counts = {r.form_external_id: r for r in lead_counts_query.all()}

    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")

    qualified_stage_ids = []
    if qualified_stage:
        qualified_stage_ids = [
            s.id for s in stages if s.order >= qualified_stage.order and s.is_active
        ]

    qualified_counts: dict[str, int] = {}
    if qualified_stage_ids:
        qualified_query = (
            db.query(
                MetaLead.meta_form_id.label("form_external_id"),
                func.count(Surrogate.id).label("qualified_count"),
            )
            .join(Surrogate, MetaLead.converted_surrogate_id == Surrogate.id)
            .filter(
                MetaLead.organization_id == organization_id,
                MetaLead.meta_form_id.isnot(None),
                MetaLead.is_converted.is_(True),
                Surrogate.stage_id.in_(qualified_stage_ids),
            )
        )
        qualified_query = _apply_date_range_filters(
            qualified_query, lead_time, start_date, end_date
        )

        qualified_query = qualified_query.group_by(MetaLead.meta_form_id)

        for r in qualified_query.all():
            qualified_counts[r.form_external_id] = r.qualified_count

    form_names: dict[str, str] = {}
    forms = (
        db.query(MetaForm.form_external_id, MetaForm.form_name)
        .filter(MetaForm.organization_id == organization_id)
        .all()
    )
    for f in forms:
        form_names[f.form_external_id] = f.form_name

    result = []
    for form_external_id, counts in lead_counts.items():
        lead_count = counts.lead_count or 0
        surrogate_count = counts.surrogate_count or 0
        qualified_count = qualified_counts.get(form_external_id, 0)

        conversion_rate = round(surrogate_count / lead_count * 100, 1) if lead_count > 0 else 0.0
        qualified_rate = (
            round(qualified_count / surrogate_count * 100, 1) if surrogate_count > 0 else 0.0
        )

        result.append(
            {
                "form_external_id": form_external_id,
                "form_name": form_names.get(form_external_id, f"Form {form_external_id[:8]}..."),
                "lead_count": lead_count,
                "surrogate_count": surrogate_count,
                "qualified_count": qualified_count,
                "conversion_rate": conversion_rate,
                "qualified_rate": qualified_rate,
            }
        )

    result.sort(key=lambda x: x["lead_count"], reverse=True)

    return result


def get_cached_leads_by_form(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "leads_by_form",
        params,
        lambda: get_leads_by_form(db, organization_id, start_date, end_date),
        range_start=range_start,
        range_end=range_end,
    )


def get_meta_campaign_list(
    db: Session,
    organization_id: uuid.UUID,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Get list of synced campaigns for filter dropdown."""
    query = db.query(MetaCampaign).filter(
        MetaCampaign.organization_id == organization_id,
    )

    if ad_account_id:
        query = query.filter(MetaCampaign.ad_account_id == ad_account_id)

    campaigns = query.order_by(MetaCampaign.campaign_name).all()

    return [
        {
            "campaign_external_id": c.campaign_external_id,
            "campaign_name": c.campaign_name,
            "status": c.status,
            "objective": c.objective,
        }
        for c in campaigns
    ]
