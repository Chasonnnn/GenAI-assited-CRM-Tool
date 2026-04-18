import uuid
from collections.abc import Iterable

from app.core.stage_definitions import SURROGATE_PIPELINE_ENTITY, get_default_stage_defs
from app.db.models import Pipeline, PipelineStage
from app.schemas.pipeline_semantics import default_pipeline_feature_config, default_stage_semantics
from app.services import pipeline_service
from app.services.pipeline_default_rollout_service import rollout_surrogate_default_pipelines

NEW_PLATFORM_STAGE_KEYS = {
    "pending_docusign",
    "life_insurance_application_started",
    "pbo_process_started",
    "cold_leads",
}


def _legacy_surrogate_stage_keys() -> list[str]:
    return [
        stage["stage_key"]
        for stage in get_default_stage_defs()
        if stage["stage_key"] not in NEW_PLATFORM_STAGE_KEYS
    ]


def _active_stage_keys(pipeline: Pipeline) -> list[str]:
    return [
        stage.stage_key
        for stage in sorted(
            (stage for stage in pipeline.stages if stage.is_active and not stage.deleted_at),
            key=lambda stage: stage.order,
        )
    ]


def _create_default_pipeline(
    db,
    *,
    org_id,
    stage_keys: Iterable[str],
    custom_stage_defs: list[dict[str, str | int]] | None = None,
) -> Pipeline:
    default_defs_by_key = {
        stage["stage_key"]: stage for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
    }
    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=org_id,
        entity_type=SURROGATE_PIPELINE_ENTITY,
        name="Default",
        is_default=True,
        current_version=1,
        feature_config=default_pipeline_feature_config(SURROGATE_PIPELINE_ENTITY),
    )
    db.add(pipeline)
    db.flush()

    items: list[dict[str, object]] = []
    for stage_key in stage_keys:
        stage_def = default_defs_by_key[stage_key]
        items.append(
            {
                "stage_key": stage_key,
                "slug": stage_def["slug"],
                "label": stage_def["label"],
                "color": stage_def["color"],
                "stage_type": stage_def["stage_type"],
            }
        )
    for custom_stage_def in custom_stage_defs or []:
        items.append(custom_stage_def)

    for order, stage_def in enumerate(items, start=1):
        stage_key = str(stage_def["stage_key"])
        stage_type = str(stage_def["stage_type"])
        db.add(
            PipelineStage(
                id=uuid.uuid4(),
                pipeline_id=pipeline.id,
                stage_key=stage_key,
                slug=str(stage_def["slug"]),
                label=str(stage_def["label"]),
                color=str(stage_def["color"]),
                order=order,
                stage_type=stage_type,
                semantics=default_stage_semantics(
                    stage_key,
                    stage_type,
                    SURROGATE_PIPELINE_ENTITY,
                ),
                is_intake_stage=stage_type == "intake",
                is_active=True,
            )
        )

    db.flush()
    pipeline_service._bump_pipeline_version(db, pipeline, None, "Initial version")
    db.refresh(pipeline)
    return pipeline


def test_new_org_bootstrap_uses_full_platform_default_surrogate_pipeline(db, test_org, test_user):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)

    assert _active_stage_keys(pipeline) == [
        stage["stage_key"] for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
    ]


def test_rollout_dry_run_reports_missing_platform_stages_for_legacy_default_pipeline(
    db,
    test_org,
):
    pipeline = _create_default_pipeline(
        db,
        org_id=test_org.id,
        stage_keys=_legacy_surrogate_stage_keys(),
    )

    report = rollout_surrogate_default_pipelines(
        db,
        organization_ids=[test_org.id],
        apply=False,
    )

    assert len(report) == 1
    item = report[0]
    assert item["organization_id"] == str(test_org.id)
    assert item["pipeline_id"] == str(pipeline.id)
    assert item["missing_stage_keys"] == [
        "pending_docusign",
        "life_insurance_application_started",
        "pbo_process_started",
        "cold_leads",
    ]
    assert item["existing_matching_stage_keys"] == []
    assert item["blockers"] == []
    assert item["applied"] is False
    assert _active_stage_keys(pipeline) == _legacy_surrogate_stage_keys()
    assert [(entry["stage_key"], entry["after_stage_key"], entry["before_stage_key"]) for entry in item["target_insertions"]] == [
        ("pending_docusign", "interview_scheduled", "under_review"),
        ("life_insurance_application_started", "heartbeat_confirmed", "ob_care_established"),
        ("pbo_process_started", "ob_care_established", "anatomy_scanned"),
        ("cold_leads", "on_hold", "lost"),
    ]


def test_rollout_apply_inserts_missing_platform_stages_and_preserves_custom_stage_positions(
    db,
    test_org,
):
    legacy_stage_keys = _legacy_surrogate_stage_keys()
    insert_at = legacy_stage_keys.index("ob_care_established")
    pipeline = _create_default_pipeline(
        db,
        org_id=test_org.id,
        stage_keys=legacy_stage_keys[:insert_at],
        custom_stage_defs=[
            {
                "stage_key": "insurance_review",
                "slug": "insurance_review",
                "label": "Insurance Review",
                "color": "#6B7280",
                "stage_type": "post_approval",
            }
        ]
        + [
            {
                "stage_key": stage_key,
                "slug": next(
                    stage["slug"]
                    for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
                    if stage["stage_key"] == stage_key
                ),
                "label": next(
                    stage["label"]
                    for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
                    if stage["stage_key"] == stage_key
                ),
                "color": next(
                    stage["color"]
                    for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
                    if stage["stage_key"] == stage_key
                ),
                "stage_type": next(
                    stage["stage_type"]
                    for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
                    if stage["stage_key"] == stage_key
                ),
            }
            for stage_key in legacy_stage_keys[insert_at:]
        ],
    )

    report = rollout_surrogate_default_pipelines(
        db,
        organization_ids=[test_org.id],
        apply=True,
    )

    assert len(report) == 1
    assert report[0]["applied"] is True
    db.refresh(pipeline)
    assert _active_stage_keys(pipeline) == [
        "new_unread",
        "contacted",
        "pre_qualified",
        "application_submitted",
        "interview_scheduled",
        "pending_docusign",
        "under_review",
        "approved",
        "ready_to_match",
        "matched",
        "medical_clearance_passed",
        "legal_clearance_passed",
        "transfer_cycle",
        "second_hcg_confirmed",
        "heartbeat_confirmed",
        "life_insurance_application_started",
        "insurance_review",
        "ob_care_established",
        "pbo_process_started",
        "anatomy_scanned",
        "delivered",
        "on_hold",
        "cold_leads",
        "lost",
        "disqualified",
    ]
    assert pipeline.current_version == 2


def test_rollout_reorders_existing_screenshot_stage_without_creating_duplicates(db, test_org):
    legacy_stage_keys = _legacy_surrogate_stage_keys()
    pipeline = _create_default_pipeline(
        db,
        org_id=test_org.id,
        stage_keys=legacy_stage_keys[:-3]
        + [
            "on_hold",
            "lost",
            "cold_leads",
            "disqualified",
        ],
    )
    cold_leads_stage = next(stage for stage in pipeline.stages if stage.stage_key == "cold_leads")

    report = rollout_surrogate_default_pipelines(
        db,
        organization_ids=[test_org.id],
        apply=True,
    )

    assert len(report) == 1
    assert report[0]["existing_matching_stage_keys"] == ["cold_leads"]
    db.refresh(pipeline)
    active_stages = [
        stage
        for stage in sorted(
            (stage for stage in pipeline.stages if stage.is_active and not stage.deleted_at),
            key=lambda stage: stage.order,
        )
    ]
    assert [stage.stage_key for stage in active_stages][-4:] == [
        "on_hold",
        "cold_leads",
        "lost",
        "disqualified",
    ]
    assert [stage.stage_key for stage in active_stages].count("cold_leads") == 1
    assert next(stage for stage in active_stages if stage.stage_key == "cold_leads").id == cold_leads_stage.id


def test_rollout_flags_slug_collisions_for_manual_review_without_mutating_pipeline(db, test_org):
    pipeline = _create_default_pipeline(
        db,
        org_id=test_org.id,
        stage_keys=_legacy_surrogate_stage_keys()[:-2],
        custom_stage_defs=[
            {
                "stage_key": "cooling_off",
                "slug": "cold_leads",
                "label": "Cooling Off",
                "color": "#64748B",
                "stage_type": "terminal",
            },
            *[
                {
                    "stage_key": stage_key,
                    "slug": next(
                        stage["slug"]
                        for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
                        if stage["stage_key"] == stage_key
                    ),
                    "label": next(
                        stage["label"]
                        for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
                        if stage["stage_key"] == stage_key
                    ),
                    "color": next(
                        stage["color"]
                        for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
                        if stage["stage_key"] == stage_key
                    ),
                    "stage_type": next(
                        stage["stage_type"]
                        for stage in get_default_stage_defs(SURROGATE_PIPELINE_ENTITY)
                        if stage["stage_key"] == stage_key
                    ),
                }
                for stage_key in _legacy_surrogate_stage_keys()[-2:]
            ],
        ],
    )

    report = rollout_surrogate_default_pipelines(
        db,
        organization_ids=[test_org.id],
        apply=True,
    )

    assert len(report) == 1
    item = report[0]
    assert item["applied"] is False
    assert item["blockers"] == [
        "Stage slug collision for 'cold_leads' on pipeline 'Default'; manual review required."
    ]
    assert "cold_leads" not in _active_stage_keys(pipeline)
