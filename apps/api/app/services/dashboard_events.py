"""Dashboard events facade.

Centralizes dashboard stats push logic so callers don't depend directly on
dashboard_service implementation details.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session


def push_dashboard_stats(db: Session, org_id: UUID) -> None:
    """Compute and push dashboard stats to connected org clients."""
    from app.services import dashboard_service

    dashboard_service.push_dashboard_stats(db, org_id)
