"""Roll out platform surrogate default pipeline changes via draft preview/apply."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.core.stage_definitions import SURROGATE_PIPELINE_ENTITY, get_default_stage_defs
from app.db.models import Organization, Pipeline, PipelineStage
from app.services import pipeline_semantics_service, pipeline_service

ROLLOUT_COMMENT = "Rolled out platform default surrogate pipeline"

TARGET_INSERTIONS: dict[str, dict[str, str]] = {
    "pending_docusign": {
        "after_stage_key": "interview_scheduled",
        "before_stage_key": "under_review",
    },
    "life_insurance_application_started": {
        "after_stage_key": "heartbeat_confirmed",
        "before_stage_key": "ob_care_established",
    },
    "pbo_process_started": {
        "after_stage_key": "ob_care_established",
        "before_stage_key": "anatomy_scanned",
    },
    "cold_leads": {
        "after_stage_key": "on_hold",
        "before_stage_key": "lost",
    },
}


def _default_stage_defs_by_key() -> dict[str, dict[str, object]]:
    return {
        str(stage["stage_key"]): stage
        for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
    }


def _default_stage_keys() -> list[str]:
    return list(_default_stage_defs_by_key().keys())


def _active_stages(pipeline: Pipeline) -> list[PipelineStage]:
    return sorted(
        (stage for stage in pipeline.stages if stage.is_active and not stage.deleted_at),
        key=lambda stage: stage.order,
    )


def _stage_to_draft_payload(stage: PipelineStage) -> dict[str, object]:
    return {
        "id": stage.id,
        "stage_key": stage.stage_key,
        "slug": stage.slug,
        "label": stage.label,
        "color": stage.color,
        "order": stage.order,
        "category": stage.stage_type,
        "stage_type": stage.stage_type,
        "is_active": True,
        "semantics": pipeline_semantics_service.get_stage_semantics(stage).model_dump(mode="json"),
    }


def _default_stage_payload(stage_def: dict[str, object]) -> dict[str, object]:
    stage_key = str(stage_def["stage_key"])
    stage_type = str(stage_def["stage_type"])
    return {
        "stage_key": stage_key,
        "slug": stage_def["slug"],
        "label": stage_def["label"],
        "color": stage_def["color"],
        "order": int(stage_def["order"]),
        "category": stage_type,
        "stage_type": stage_type,
        "is_active": True,
        "semantics": pipeline_semantics_service.get_stage_semantics(
            {
                "entity_type": SURROGATE_PIPELINE_ENTITY,
                "stage_key": stage_key,
                "slug": stage_def["slug"],
                "stage_type": stage_type,
            }
        ).model_dump(mode="json"),
    }


def _build_custom_stage_gap_map(
    active_stages: list[PipelineStage],
    platform_stage_keys: set[str],
) -> tuple[dict[tuple[str | None, str | None], list[PipelineStage]], list[str]]:
    next_platform_key_by_index: dict[int, str | None] = {}
    next_platform_key: str | None = None
    for index in range(len(active_stages) - 1, -1, -1):
        stage = active_stages[index]
        if stage.stage_key in platform_stage_keys:
            next_platform_key = stage.stage_key
        next_platform_key_by_index[index] = next_platform_key

    gap_map: dict[tuple[str | None, str | None], list[PipelineStage]] = defaultdict(list)
    blockers: list[str] = []
    previous_platform_key: str | None = None

    for index, stage in enumerate(active_stages):
        if stage.stage_key in platform_stage_keys:
            previous_platform_key = stage.stage_key
            continue
        gap = (previous_platform_key, next_platform_key_by_index[index])
        gap_map[gap].append(stage)

    for (_, next_key), stages in gap_map.items():
        if next_key is None:
            blockers.extend(
                [
                    f"Custom stage '{stage.label}' appears after the platform terminal tail; manual review required."
                    for stage in stages
                ]
            )
    for (prev_key, _), stages in gap_map.items():
        if prev_key is None:
            blockers.extend(
                [
                    f"Custom stage '{stage.label}' appears before the platform entry stage; manual review required."
                    for stage in stages
                ]
            )

    return gap_map, blockers


def _build_rollout_feature_config(pipeline: Pipeline) -> dict[str, object]:
    feature_config = pipeline_semantics_service.get_pipeline_feature_config(pipeline).model_dump(
        mode="json"
    )
    milestones_by_slug = {
        milestone["slug"]: milestone
        for milestone in feature_config.get("journey", {}).get("milestones", [])
        if isinstance(milestone, dict) and milestone.get("slug")
    }

    for milestone_slug, stage_keys in (
        ("screening_interviews", ["pending_docusign"]),
        (
            "ongoing_care",
            ["life_insurance_application_started", "pbo_process_started"],
        ),
    ):
        milestone = milestones_by_slug.get(milestone_slug)
        if milestone is None:
            continue
        mapped_stage_keys = list(milestone.get("mapped_stage_keys") or [])
        for stage_key in stage_keys:
            if stage_key not in mapped_stage_keys:
                mapped_stage_keys.append(stage_key)
        milestone["mapped_stage_keys"] = mapped_stage_keys

    return feature_config


def _build_rollout_draft(
    pipeline: Pipeline,
) -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    stage_defs_by_key = _default_stage_defs_by_key()
    desired_platform_keys = list(stage_defs_by_key.keys())
    platform_stage_keys = set(desired_platform_keys)
    active_stages = _active_stages(pipeline)
    existing_stage_by_key = {
        stage.stage_key: stage for stage in pipeline.stages if stage.stage_key is not None
    }
    gap_map, blockers = _build_custom_stage_gap_map(active_stages, platform_stage_keys)

    desired_items: list[PipelineStage | dict[str, object]] = []
    emitted_gaps: set[tuple[str | None, str | None]] = set()
    seen_platform_keys: set[str] = set()

    for stage_key in desired_platform_keys:
        for gap, custom_stages in gap_map.items():
            prev_key, next_key = gap
            if gap in emitted_gaps or next_key != stage_key:
                continue
            if prev_key is not None and prev_key not in seen_platform_keys:
                continue
            desired_items.extend(custom_stages)
            emitted_gaps.add(gap)

        desired_items.append(existing_stage_by_key.get(stage_key) or stage_defs_by_key[stage_key])
        seen_platform_keys.add(stage_key)

    for gap, custom_stages in gap_map.items():
        if gap not in emitted_gaps and gap[1] is None:
            desired_items.extend(custom_stages)
            emitted_gaps.add(gap)

    draft_stages: list[dict[str, object]] = []
    for order, item in enumerate(desired_items, start=1):
        payload = (
            _stage_to_draft_payload(item)
            if isinstance(item, PipelineStage)
            else _default_stage_payload(item)
        )
        payload["order"] = order
        draft_stages.append(payload)

    return draft_stages, _build_rollout_feature_config(pipeline), blockers


def _local_blockers(pipeline: Pipeline) -> list[str]:
    blockers: list[str] = []
    existing_stage_by_key = {stage.stage_key: stage for stage in pipeline.stages if stage.stage_key}

    for stage_key in TARGET_INSERTIONS:
        if stage_key in existing_stage_by_key:
            continue
        collision = next(
            (
                stage
                for stage in pipeline.stages
                if stage.slug == stage_key and stage.stage_key != stage_key
            ),
            None,
        )
        if collision is not None:
            blockers.append(
                f"Stage slug collision for '{stage_key}' on pipeline '{pipeline.name}'; manual review required."
            )

    return blockers


def _stage_order(stage_keys: list[str]) -> dict[str, int]:
    return {stage_key: index for index, stage_key in enumerate(stage_keys)}


def _build_target_insertion_report(
    *,
    missing_stage_keys: list[str],
    reordered_stage_keys: list[str],
) -> list[dict[str, object]]:
    return [
        {
            "stage_key": stage_key,
            **TARGET_INSERTIONS[stage_key],
            "action": (
                "insert"
                if stage_key in missing_stage_keys
                else "reorder"
                if stage_key in reordered_stage_keys
                else "none"
            ),
        }
        for stage_key in TARGET_INSERTIONS
        if stage_key in missing_stage_keys or stage_key in reordered_stage_keys
    ]


def _build_report_item(
    db: Session,
    pipeline: Pipeline,
    *,
    organization_slug: str,
    draft_stages: list[dict[str, object]],
    feature_config: dict[str, object],
    blockers: list[str],
    apply: bool,
    user_id: UUID | None,
) -> dict[str, object]:
    active_stage_keys = [stage.stage_key for stage in _active_stages(pipeline)]
    existing_stage_keys = {stage.stage_key for stage in pipeline.stages if stage.stage_key}
    current_stage_order = _stage_order(active_stage_keys)
    final_stage_keys = [str(stage["stage_key"]) for stage in draft_stages]
    final_stage_order = _stage_order(final_stage_keys)

    target_stage_keys = list(TARGET_INSERTIONS.keys())
    missing_stage_keys = [stage_key for stage_key in target_stage_keys if stage_key not in existing_stage_keys]
    existing_matching_stage_keys = [
        stage_key for stage_key in target_stage_keys if stage_key in existing_stage_keys
    ]
    reordered_stage_keys = [
        stage_key
        for stage_key in existing_matching_stage_keys
        if current_stage_order.get(stage_key) != final_stage_order.get(stage_key)
    ]

    current_feature_config = pipeline_semantics_service.get_pipeline_feature_config(pipeline).model_dump(
        mode="json"
    )
    next_feature_config = pipeline_semantics_service.get_pipeline_feature_config(
        {"entity_type": pipeline.entity_type, "feature_config": feature_config}
    ).model_dump(mode="json")
    would_change = active_stage_keys != final_stage_keys or current_feature_config != next_feature_config

    preview = None
    preview_blockers: list[str] = []
    if not blockers:
        preview = pipeline_service.build_pipeline_draft_preview(
            db=db,
            pipeline=pipeline,
            name=pipeline.name,
            stages=draft_stages,
            feature_config=feature_config,
            remaps=[],
        )
        preview_blockers = list(preview["validation_errors"]) + list(preview["blocking_issues"])

    all_blockers = list(dict.fromkeys([*blockers, *preview_blockers]))
    applied = False
    if apply and would_change and not all_blockers:
        pipeline_service.apply_pipeline_draft(
            db=db,
            pipeline=pipeline,
            name=pipeline.name,
            stages=draft_stages,
            feature_config=feature_config,
            remaps=[],
            user_id=user_id,
            comment=ROLLOUT_COMMENT,
        )
        applied = True

    return {
        "organization_id": str(pipeline.organization_id),
        "organization_slug": organization_slug,
        "pipeline_id": str(pipeline.id),
        "pipeline_name": pipeline.name,
        "missing_stage_keys": missing_stage_keys,
        "existing_matching_stage_keys": existing_matching_stage_keys,
        "reordered_stage_keys": reordered_stage_keys,
        "target_insertions": _build_target_insertion_report(
            missing_stage_keys=missing_stage_keys,
            reordered_stage_keys=reordered_stage_keys,
        ),
        "blockers": all_blockers,
        "would_change": would_change,
        "applied": applied,
    }


def rollout_surrogate_default_pipelines(
    db: Session,
    *,
    organization_ids: list[UUID] | None = None,
    org_slugs: list[str] | None = None,
    apply: bool = False,
    user_id: UUID | None = None,
) -> list[dict[str, object]]:
    query = db.query(Organization).order_by(Organization.slug)
    if organization_ids:
        query = query.filter(Organization.id.in_(organization_ids))
    if org_slugs:
        query = query.filter(Organization.slug.in_(org_slugs))

    organizations = query.all()
    reports: list[dict[str, object]] = []
    for organization in organizations:
        pipeline = (
            db.query(Pipeline)
            .options(selectinload(Pipeline.stages))
            .filter(
                Pipeline.organization_id == organization.id,
                Pipeline.entity_type == SURROGATE_PIPELINE_ENTITY,
                Pipeline.is_default.is_(True),
            )
            .first()
        )

        if pipeline is None:
            reports.append(
                {
                    "organization_id": str(organization.id),
                    "organization_slug": organization.slug,
                    "pipeline_id": None,
                    "pipeline_name": None,
                    "missing_stage_keys": list(TARGET_INSERTIONS.keys()),
                    "existing_matching_stage_keys": [],
                    "reordered_stage_keys": [],
                    "target_insertions": [
                        {"stage_key": stage_key, **config, "action": "insert"}
                        for stage_key, config in TARGET_INSERTIONS.items()
                    ],
                    "blockers": ["Default surrogate pipeline not found; manual review required."],
                    "would_change": False,
                    "applied": False,
                }
            )
            continue

        draft_stages, feature_config, blockers = _build_rollout_draft(pipeline)
        blockers.extend(_local_blockers(pipeline))
        reports.append(
            _build_report_item(
                db,
                pipeline,
                organization_slug=organization.slug,
                draft_stages=draft_stages,
                feature_config=feature_config,
                blockers=list(dict.fromkeys(blockers)),
                apply=apply,
                user_id=user_id,
            )
        )

    return reports
