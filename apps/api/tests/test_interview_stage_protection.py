"""Interview workflow stages are required, protected surrogate pipeline stages."""

from copy import deepcopy

import pytest

from app.core.stage_definitions import get_stage_protection_metadata
from app.db.models import PipelineStage
from app.services import pipeline_service


@pytest.mark.parametrize("stage_key", ["interview_scheduled", "reschedule_needed"])
def test_interview_stage_protection_metadata(stage_key):
    metadata = get_stage_protection_metadata(stage_key, "surrogate")

    assert metadata["is_locked"] is True
    assert {"delete", "is_active", "duplicate"}.issubset(metadata["locked_fields"])
    assert metadata["lock_reason"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage_key", ["interview_scheduled", "reschedule_needed"])
@pytest.mark.parametrize("action", ["delete", "remove_from_draft", "deactivate"])
async def test_interview_stages_cannot_be_removed(authed_client, stage_key, action):
    response = await authed_client.get("/settings/pipelines/default")
    assert response.status_code == 200, response.text
    pipeline = response.json()
    stage = next(item for item in pipeline["stages"] if item["stage_key"] == stage_key)

    if action == "delete":
        target = next(item for item in pipeline["stages"] if item["stage_key"] == "contacted")
        response = await authed_client.request(
            "DELETE",
            f"/settings/pipelines/{pipeline['id']}/stages/{stage['id']}",
            json={
                "migrate_to_stage_id": target["id"],
                "expected_version": pipeline["current_version"],
            },
        )
    else:
        draft = deepcopy(pipeline["stages"])
        if action == "remove_from_draft":
            draft = [item for item in draft if item["stage_key"] != stage_key]
        else:
            next(item for item in draft if item["stage_key"] == stage_key)["is_active"] = False
        response = await authed_client.put(
            f"/settings/pipelines/{pipeline['id']}/apply-draft",
            json={
                "name": pipeline["name"],
                "stages": draft,
                "feature_config": pipeline["feature_config"],
                "expected_version": pipeline["current_version"],
                "remaps": [{"removed_stage_key": stage_key, "target_stage_key": "contacted"}],
            },
        )

    assert response.status_code == 400, response.text
    assert "protected system stage" in response.json()["detail"].lower()
    reloaded = (await authed_client.get("/settings/pipelines/default")).json()
    assert reloaded["current_version"] == pipeline["current_version"]
    saved_stage = next(item for item in reloaded["stages"] if item["stage_key"] == stage_key)
    assert saved_stage["id"] == stage["id"]
    assert saved_stage["is_active"] is True
    assert saved_stage["is_locked"] is True


@pytest.mark.parametrize(
    "missing_keys",
    [{"reschedule_needed"}, {"interview_scheduled", "reschedule_needed"}],
)
def test_existing_pipeline_restores_required_interview_stages(
    db, test_org, test_user, missing_keys
):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)
    existing_ids = {
        stage.stage_key: stage.id
        for stage in pipeline.stages
        if stage.stage_key not in missing_keys
    }
    for stage in list(pipeline.stages):
        if stage.stage_key in missing_keys:
            db.delete(stage)
    db.commit()
    db.expire_all()

    restored = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)
    stages = pipeline_service.get_stages(db, restored.id)
    keys = [stage.stage_key for stage in stages]
    interview_index = keys.index("interview_scheduled")
    assert keys[interview_index + 1 : interview_index + 3] == [
        "reschedule_needed",
        "pending_docusign",
    ]
    assert {
        stage.stage_key: stage.id for stage in stages if stage.stage_key in existing_ids
    } == existing_ids
    version = restored.current_version
    repeated = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)
    assert repeated.current_version == version
    assert (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline.id, PipelineStage.stage_key.in_(missing_keys))
        .count()
    ) == len(missing_keys)
