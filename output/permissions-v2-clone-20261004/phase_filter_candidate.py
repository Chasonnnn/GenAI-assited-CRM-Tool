"""Unlanded phase-query candidate for local and clone validation only."""

from sqlalchemy import and_, case, func, literal, or_, select, true

from app.core.stage_definitions import PROTECTED_SYSTEM_STAGES_BY_ENTITY
from app.db.models import Pipeline, PipelineStage
from app.db.models.record_access import RecordScopeMigrationReview
from app.services.record_scope_service import RECORDS


def _stage_filter(session, kind, model, rule):
    if rule.phase == "all" and not rule.stage_ids:
        return true()
    current = PipelineStage.__table__.alias("scope_current")
    effective = PipelineStage.__table__.alias("scope_effective")
    pipeline = Pipeline.__table__.alias("scope_pipeline")
    if rule.phase == "all":
        return (
            select(literal(1))
            .select_from(current.join(pipeline, pipeline.c.id == current.c.pipeline_id))
            .where(
                current.c.id == model.stage_id,
                current.c.id.in_(rule.stage_ids),
                current.c.is_active.is_(True),
                pipeline.c.organization_id == session.org_id,
            )
            .exists()
        )
    effective_id = model.stage_id
    if kind in {"surrogate", "donor"}:
        from app.db.models import DonorStatusHistory, SurrogateStatusHistory

        history_model = SurrogateStatusHistory if kind == "surrogate" else DonorStatusHistory
        history = history_model.__table__.alias("scope_history")
        prior = PipelineStage.__table__.alias("scope_history_prior")
        following = PipelineStage.__table__.alias("scope_history_following")
        before_id = history.c.from_stage_id if kind == "surrogate" else history.c.old_stage_id
        after_id = history.c.to_stage_id if kind == "surrogate" else history.c.new_stage_id
        known_stage = case(
            (
                and_(
                    following.c.stage_type.notin_(["paused", "terminal"]),
                    following.c.pipeline_id == current.c.pipeline_id,
                ),
                following.c.id,
            ),
            (
                and_(
                    prior.c.stage_type.notin_(["paused", "terminal"]),
                    prior.c.pipeline_id == current.c.pipeline_id,
                ),
                prior.c.id,
            ),
        )
        historical_stage = (
            select(known_stage)
            .select_from(
                history.outerjoin(prior, prior.c.id == before_id).outerjoin(
                    following, following.c.id == after_id
                )
            )
            .where(
                history.c.organization_id == session.org_id,
                getattr(history.c, f"{kind}_id") == model.id,
                known_stage.isnot(None),
            )
            .order_by(history.c.recorded_at.desc(), history.c.id.desc())
            .limit(1)
            .correlate_except(history, prior, following)
            .scalar_subquery()
        )
        paused_origin = PipelineStage.__table__.alias("scope_paused_origin")
        origin_needs_history = (
            select(literal(1))
            .select_from(paused_origin)
            .where(
                paused_origin.c.id == model.paused_from_stage_id,
                paused_origin.c.pipeline_id == current.c.pipeline_id,
                paused_origin.c.is_active.is_(True),
                paused_origin.c.stage_type.in_(["paused", "terminal"]),
            )
            .correlate_except(paused_origin)
            .exists()
        )
        # A paused/terminal origin needs the same historical phase evidence as a terminal record.
        paused_effective_id = case(
            (origin_needs_history, historical_stage),
            else_=func.coalesce(model.paused_from_stage_id, historical_stage),
        )
        effective_id = case(
            (
                current.c.stage_type == "paused",
                paused_effective_id,
            ),
            (current.c.stage_type == "terminal", historical_stage),
            else_=model.stage_id,
        )
    source = current.join(pipeline, pipeline.c.id == current.c.pipeline_id)
    conditions = [
        current.c.id == model.stage_id,
        current.c.is_active.is_(True),
        pipeline.c.organization_id == session.org_id,
    ]
    if rule.stage_ids:
        conditions.append(current.c.id.in_(rule.stage_ids))
    gate = PipelineStage.__table__.alias("scope_approval_gate")
    gate_keys = {
        key
        for entity in RECORDS[kind][2]
        for key, definition in PROTECTED_SYSTEM_STAGES_BY_ENTITY.get(entity, {}).items()
        if definition.system_role == "approval_gate"
    }
    # Older donor pipelines have phase categories before an approval gate is installed.
    if gate_keys:
        gate_order = (
            select(gate.c.order)
            .where(
                gate.c.pipeline_id == effective.c.pipeline_id,
                gate.c.stage_key.in_(gate_keys),
                gate.c.is_active.is_(True),
            )
            .limit(1)
            .correlate_except(gate)
            .scalar_subquery()
        )
        post = effective.c.order >= gate_order
        pre = effective.c.order < gate_order
    else:
        post = effective.c.stage_type == "post_approval"
        pre = effective.c.stage_type == "intake"
    phase = post if rule.phase == "post_approval" else pre
    effective_phase = (
        select(literal(1))
        .select_from(effective)
        .where(
            effective.c.id == effective_id,
            effective.c.pipeline_id == current.c.pipeline_id,
            effective.c.is_active.is_(True),
            effective.c.stage_type.notin_(["paused", "terminal"]),
            phase,
        )
        .correlate_except(effective)
        .exists()
    )
    if kind in {"surrogate", "donor"}:
        reviewed_phase = (
            select(literal(1))
            .select_from(RecordScopeMigrationReview)
            .where(
                RecordScopeMigrationReview.organization_id == session.org_id,
                getattr(RecordScopeMigrationReview, f"{kind}_id") == model.id,
                RecordScopeMigrationReview.reviewed_stage_id == model.stage_id,
                RecordScopeMigrationReview.resolved_phase == rule.phase,
                RecordScopeMigrationReview.evidence_reference.isnot(None),
            )
            .correlate_except(RecordScopeMigrationReview)
            .exists()
        )
        effective_exists = (
            select(literal(1))
            .select_from(effective)
            .where(effective.c.id == effective_id)
            .correlate_except(effective)
            .exists()
        )
        effective_phase = or_(effective_phase, and_(~effective_exists, reviewed_phase))
    conditions.append(effective_phase)
    return select(literal(1)).select_from(source).where(*conditions).exists()
