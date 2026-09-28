"""Intended parent stage metadata carries each stage's semantics from the org's pipeline."""

import uuid

import pytest

from app.db.models import Organization
from app.main import app
from app.services import pipeline_service


def _ip_stages(db, org_id):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, org_id, entity_type="intended_parent"
    )
    return {
        stage.stage_key: stage
        for stage in pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    }


@pytest.mark.asyncio
async def test_intended_parent_statuses_include_stage_semantics(db, test_org, authed_client):
    stages = _ip_stages(db, test_org.id)
    stages["ready_to_match"].semantics = {
        **(stages["ready_to_match"].semantics or {}),
        "requires_reason_on_enter": True,
    }
    db.commit()

    response = await authed_client.get("/metadata/intended-parent-statuses")

    assert response.status_code == 200, response.text
    by_key = {status["stage_key"]: status for status in response.json()["statuses"]}
    assert by_key["ready_to_match"]["id"] == str(stages["ready_to_match"].id)
    assert by_key["ready_to_match"]["semantics"]["requires_reason_on_enter"] is True
    assert by_key["ready_to_match"]["semantics"]["capabilities"]["eligible_for_matching"] is True
    assert by_key["new"]["semantics"]["requires_reason_on_enter"] is False
    assert by_key["delivered"]["semantics"]["capabilities"]["requires_delivery_details"] is True
    assert {status["semantics"]["pause_behavior"] for status in by_key.values()} == {"none"}


@pytest.mark.asyncio
async def test_intended_parent_statuses_list_only_the_session_org_active_stages(
    db, test_org, authed_client
):
    other_org = Organization(
        id=uuid.uuid4(), name="Other Metadata Org", slug=f"other-meta-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    other_stage_ids = {str(stage.id) for stage in _ip_stages(db, other_org.id).values()}
    own_stages = _ip_stages(db, test_org.id)
    own_stages["ready_to_match"].is_active = False
    db.commit()

    response = await authed_client.get("/metadata/intended-parent-statuses")

    assert response.status_code == 200, response.text
    returned_ids = {status["id"] for status in response.json()["statuses"]}
    assert returned_ids.isdisjoint(other_stage_ids)
    assert returned_ids == {
        str(stage.id) for key, stage in own_stages.items() if key != "ready_to_match"
    }


def test_intended_parent_statuses_declare_a_response_schema() -> None:
    operation = app.openapi()["paths"]["/metadata/intended-parent-statuses"]["get"]
    schema_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    schemas = app.openapi()["components"]["schemas"]
    response_schema = schemas[schema_ref.rsplit("/", 1)[-1]]
    item_ref = response_schema["properties"]["statuses"]["items"]["$ref"]
    item = schemas[item_ref.rsplit("/", 1)[-1]]
    assert set(item["required"]) == {
        "id",
        "value",
        "label",
        "stage_key",
        "stage_slug",
        "stage_type",
        "color",
        "order",
        "semantics",
    }
    assert item["properties"]["semantics"]["$ref"].endswith("/StageSemantics")
