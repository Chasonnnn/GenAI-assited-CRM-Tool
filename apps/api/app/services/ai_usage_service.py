"""AI Usage tracking service.

Logs token usage and provides analytics for cost monitoring.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AIUsageLog
from app.types import JsonObject


def log_usage(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost_usd: Decimal | None = None,
    conversation_id: uuid.UUID | None = None,
) -> AIUsageLog:
    """Log a single AI API call usage."""
    usage = AIUsageLog(
        organization_id=organization_id,
        user_id=user_id,
        conversation_id=conversation_id,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )
    db.add(usage)
    db.flush()
    return usage


def get_org_usage_summary(
    db: Session,
    organization_id: uuid.UUID,
    days: int = 30,
) -> JsonObject:
    """Get usage summary for an organization."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = (
        db.query(
            func.count(AIUsageLog.id).label("total_requests"),
            func.sum(AIUsageLog.prompt_tokens).label("total_prompt_tokens"),
            func.sum(AIUsageLog.completion_tokens).label("total_completion_tokens"),
            func.sum(AIUsageLog.total_tokens).label("total_tokens"),
            func.sum(AIUsageLog.estimated_cost_usd).label("total_cost_usd"),
        )
        .filter(
            AIUsageLog.organization_id == organization_id,
            AIUsageLog.created_at >= since,
        )
        .first()
    )

    return {
        "period_days": days,
        "total_requests": result.total_requests or 0,
        "total_prompt_tokens": result.total_prompt_tokens or 0,
        "total_completion_tokens": result.total_completion_tokens or 0,
        "total_tokens": result.total_tokens or 0,
        "total_cost_usd": float(result.total_cost_usd or 0),
    }


def get_user_usage_summary(
    db: Session,
    user_id: uuid.UUID,
    days: int = 30,
) -> JsonObject:
    """Get usage summary for a specific user."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = (
        db.query(
            func.count(AIUsageLog.id).label("total_requests"),
            func.sum(AIUsageLog.total_tokens).label("total_tokens"),
            func.sum(AIUsageLog.estimated_cost_usd).label("total_cost_usd"),
        )
        .filter(
            AIUsageLog.user_id == user_id,
            AIUsageLog.created_at >= since,
        )
        .first()
    )

    return {
        "period_days": days,
        "total_requests": result.total_requests or 0,
        "total_tokens": result.total_tokens or 0,
        "total_cost_usd": float(result.total_cost_usd or 0),
    }


def get_usage_by_model(
    db: Session,
    organization_id: uuid.UUID,
    days: int = 30,
) -> list[JsonObject]:
    """Get usage breakdown by model."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    results = (
        db.query(
            AIUsageLog.model,
            func.count(AIUsageLog.id).label("requests"),
            func.sum(AIUsageLog.total_tokens).label("tokens"),
            func.sum(AIUsageLog.estimated_cost_usd).label("cost"),
        )
        .filter(
            AIUsageLog.organization_id == organization_id,
            AIUsageLog.created_at >= since,
        )
        .group_by(AIUsageLog.model)
        .all()
    )

    return [
        {
            "model": r.model,
            "requests": r.requests,
            "tokens": r.tokens or 0,
            "cost_usd": float(r.cost or 0),
        }
        for r in results
    ]


def get_daily_usage(
    db: Session,
    organization_id: uuid.UUID,
    days: int = 30,
) -> list[JsonObject]:
    """Get daily usage for the past N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    results = (
        db.query(
            func.date(AIUsageLog.created_at).label("date"),
            func.count(AIUsageLog.id).label("requests"),
            func.sum(AIUsageLog.total_tokens).label("tokens"),
            func.sum(AIUsageLog.estimated_cost_usd).label("cost"),
        )
        .filter(
            AIUsageLog.organization_id == organization_id,
            AIUsageLog.created_at >= since,
        )
        .group_by(func.date(AIUsageLog.created_at))
        .order_by(func.date(AIUsageLog.created_at))
        .all()
    )

    return [
        {
            "date": r.date.isoformat() if r.date else None,
            "requests": r.requests,
            "tokens": r.tokens or 0,
            "cost_usd": float(r.cost or 0),
        }
        for r in results
    ]


def get_top_users(
    db: Session,
    organization_id: uuid.UUID,
    days: int = 30,
    limit: int = 10,
) -> list[JsonObject]:
    """Get top users by token usage."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    results = (
        db.query(
            AIUsageLog.user_id,
            func.count(AIUsageLog.id).label("requests"),
            func.sum(AIUsageLog.total_tokens).label("tokens"),
            func.sum(AIUsageLog.estimated_cost_usd).label("cost"),
        )
        .filter(
            AIUsageLog.organization_id == organization_id,
            AIUsageLog.created_at >= since,
        )
        .group_by(AIUsageLog.user_id)
        .order_by(func.sum(AIUsageLog.total_tokens).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "user_id": str(r.user_id),
            "requests": r.requests,
            "tokens": r.tokens or 0,
            "cost_usd": float(r.cost or 0),
        }
        for r in results
    ]
