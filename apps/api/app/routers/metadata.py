"""Metadata router - API endpoints for picklist values (enums)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db
from app.db.enums import SurrogateSource, TaskType, IntendedParentStatus, Role
from app.services import pipeline_service
from app.schemas.auth import UserSession

router = APIRouter()


@router.get("/statuses")
def list_surrogate_statuses(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Get all surrogate statuses with metadata.

    Returns list of {value, label, stage} for populating dropdowns.
    """
    statuses = []
    pipeline = pipeline_service.get_or_create_default_pipeline(db, session.org_id, session.user_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=False)
    for stage in stages:
        statuses.append(
            {
                "id": str(stage.id),
                "value": stage.slug,
                "label": stage.label,
                "stage_type": stage.stage_type,
            }
        )

    return {"statuses": statuses}


@router.get("/sources")
def list_surrogate_sources(
    session: UserSession = Depends(get_current_session),
):
    """
    Get all surrogate sources.

    Returns list of {value, label} for populating dropdowns.
    """
    allowed_sources = {
        "manual",
        "meta",
        "tiktok",
        "google",
        "website",
        "referral",
        "other",
    }
    sources = [
        {
            "value": source.value,
            "label": "Others"
            if source.value == "other"
            else source.value.replace("_", " ").title(),
        }
        for source in SurrogateSource
        if source.value in allowed_sources
    ]
    return {"sources": sources}


@router.get("/task-types")
def list_task_types(
    session: UserSession = Depends(get_current_session),
):
    """
    Get all task types.

    Returns list of {value, label} for populating dropdowns.
    """
    task_types = [
        {"value": tt.value, "label": tt.value.replace("_", " ").title()} for tt in TaskType
    ]
    return {"task_types": task_types}


@router.get("/intended-parent-statuses")
def list_intended_parent_statuses(
    session: UserSession = Depends(get_current_session),
):
    """
    Get all intended parent statuses.

    Returns list of {value, label} for populating dropdowns.
    """
    statuses = []
    for status in IntendedParentStatus:
        # Skip pseudo-statuses used for history only
        if status.value in ("archived", "restored"):
            continue

        statuses.append(
            {
                "value": status.value,
                "label": status.value.replace("_", " ").title(),
            }
        )

    return {"statuses": statuses}


@router.get("/roles")
def list_roles(
    session: UserSession = Depends(get_current_session),
):
    """
    Get all user roles.

    Returns list of {value, label} for populating dropdowns.
    """
    roles = [{"value": role.value, "label": role.value.replace("_", " ").title()} for role in Role]
    return {"roles": roles}
