"""Helpers for resolving a surrogate's effective workflow stage."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import PipelineStage, Surrogate
from app.services import pipeline_service


@dataclass(frozen=True)
class SurrogateStageContext:
    current_stage: PipelineStage | None
    effective_stage: PipelineStage | None
    paused_from_stage: PipelineStage | None

    @property
    def is_on_hold(self) -> bool:
        return pipeline_service.stage_matches_key(self.current_stage, "on_hold")


def get_stage_context(
    db: Session,
    surrogate: Surrogate,
    *,
    current_stage: PipelineStage | None = None,
) -> SurrogateStageContext:
    """Resolve current and effective stages for a surrogate."""
    resolved_current_stage = current_stage
    if resolved_current_stage is None and surrogate.stage_id:
        resolved_current_stage = pipeline_service.get_stage_by_id(db, surrogate.stage_id)

    paused_from_stage = None
    if (
        resolved_current_stage
        and pipeline_service.stage_matches_key(resolved_current_stage, "on_hold")
        and surrogate.paused_from_stage_id
    ):
        paused_from_stage = pipeline_service.get_stage_by_id(db, surrogate.paused_from_stage_id)

    return SurrogateStageContext(
        current_stage=resolved_current_stage,
        effective_stage=paused_from_stage or resolved_current_stage,
        paused_from_stage=paused_from_stage,
    )
