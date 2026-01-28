"""Usage analytics service (activity feed)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Surrogate, SurrogateActivityLog, User


def get_activity_feed(
    db: Session,
    organization_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    activity_type: str | None = None,
    user_id: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Get org-wide activity feed entries."""
    from sqlalchemy import desc

    query = (
        db.query(
            SurrogateActivityLog,
            Surrogate.surrogate_number,
            Surrogate.full_name.label("surrogate_name"),
            User.display_name.label("actor_name"),
        )
        .join(Surrogate, SurrogateActivityLog.surrogate_id == Surrogate.id)
        .outerjoin(User, SurrogateActivityLog.actor_user_id == User.id)
        .filter(SurrogateActivityLog.organization_id == organization_id)
    )

    if activity_type:
        query = query.filter(SurrogateActivityLog.activity_type == activity_type)

    if user_id:
        try:
            parsed_id = uuid.UUID(user_id)
            query = query.filter(SurrogateActivityLog.actor_user_id == parsed_id)
        except ValueError:
            pass

    query = query.order_by(desc(SurrogateActivityLog.created_at))
    query = query.offset(offset).limit(limit + 1)

    results = query.all()
    has_more = len(results) > limit
    items = results[:limit]

    return (
        [
            {
                "id": str(row.SurrogateActivityLog.id),
                "activity_type": row.SurrogateActivityLog.activity_type,
                "surrogate_id": str(row.SurrogateActivityLog.surrogate_id),
                "surrogate_number": row.surrogate_number,
                "surrogate_name": row.surrogate_name,
                "actor_name": row.actor_name,
                "details": row.SurrogateActivityLog.details,
                "created_at": row.SurrogateActivityLog.created_at.isoformat(),
            }
            for row in items
        ],
        has_more,
    )
