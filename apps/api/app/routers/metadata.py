"""Metadata router - API endpoints for picklist values (enums)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.pipeline_stage_colors import resolve_stage_color
from app.core.match_status_definitions import MATCH_STATUS_DEFINITIONS
from app.core.stage_definitions import INTENDED_PARENT_PIPELINE_ENTITY
from app.core.deps import get_current_session, get_db
from app.db.enums import SurrogateSource, TaskType, Role
from app.services import pipeline_service
from app.schemas.auth import UserSession

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get("/statuses")
def list_surrogate_statuses(
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> object:
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
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> object:
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
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> object:
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
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> object:
    """
    Get intended-parent stage metadata from the scoped default pipeline.

    Returns list of {id, value, label, stage_key, stage_slug, stage_type, color, order}.
    """
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        session.org_id,
        session.user_id,
        entity_type=INTENDED_PARENT_PIPELINE_ENTITY,
    )
    statuses = [
        {
            "id": str(stage.id),
            "value": stage.stage_key,
            "label": stage.label,
            "stage_key": stage.stage_key,
            "stage_slug": stage.slug,
            "stage_type": stage.stage_type,
            "color": resolve_stage_color(
                color=stage.color,
                label=stage.label,
                slug=stage.slug,
                stage_key=stage.stage_key,
                stage_type=stage.stage_type,
                order=stage.order,
                is_locked=stage.is_locked,
            ),
            "order": stage.order,
        }
        for stage in pipeline_service.get_stages(db, pipeline.id, include_inactive=False)
    ]
    return {"statuses": statuses}


@router.get("/match-statuses")
def list_match_statuses() -> object:
    """Get shared fixed match lifecycle metadata."""
    return {"statuses": MATCH_STATUS_DEFINITIONS}


@router.get("/roles")
def list_roles(
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> object:
    """
    Get all user roles.

    Returns list of {value, label} for populating dropdowns.
    """
    roles = [{"value": role.value, "label": role.value.replace("_", " ").title()} for role in Role]
    return {"roles": roles}
