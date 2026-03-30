"""Tests for Pipelines API with versioning."""

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.stage_definitions import get_default_stage_defs
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import (
    EmailTemplate,
    Membership,
    OrgIntelligentSuggestionRule,
    Pipeline,
    PipelineStage,
    StatusChangeRequest,
    Surrogate,
    User,
)
from app.main import app
from app.schemas.campaign import CampaignCreate
from app.schemas.workflow import WorkflowCreate
from app.services import (
    campaign_service,
    pipeline_service,
    session_service,
    workflow_service,
    zapier_settings_service,
)
from app.db.enums import WorkflowTriggerType
from app.utils.normalization import normalize_email


def _create_surrogate_for_stage(
    db, *, org_id: UUID, user_id: UUID, stage: PipelineStage
) -> Surrogate:
    email = f"pipeline-stage-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Pipeline Stage Surrogate",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _create_email_template(db, *, org_id: UUID) -> EmailTemplate:
    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=f"Pipeline template {uuid.uuid4().hex[:8]}",
        subject="Pipeline update",
        body="<p>Pipeline update</p>",
        is_active=True,
    )
    db.add(template)
    db.flush()
    return template


def _remove_stage_key_refs(feature_config: dict, stage_key: str) -> dict:
    next_config = deepcopy(feature_config)
    for milestone in next_config["journey"]["milestones"]:
        milestone["mapped_stage_keys"] = [
            key for key in milestone["mapped_stage_keys"] if key != stage_key
        ]
    next_config["analytics"]["funnel_stage_keys"] = [
        key for key in next_config["analytics"]["funnel_stage_keys"] if key != stage_key
    ]
    for rules_key in ("role_visibility", "role_mutation"):
        for rule in next_config[rules_key].values():
            rule["stage_keys"] = [key for key in rule["stage_keys"] if key != stage_key]
    return next_config


@pytest.mark.asyncio
async def test_list_pipelines_authed(authed_client: AsyncClient):
    """Authenticated request to /settings/pipelines should return 200."""
    response = await authed_client.get("/settings/pipelines")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_or_create_default_pipeline_prunes_legacy_feature_config_refs(db, test_org):
    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        entity_type="surrogate",
        name="Legacy Pipeline",
        is_default=True,
        current_version=1,
        feature_config={},
    )
    db.add(pipeline)
    db.flush()

    db.add(
        PipelineStage(
            id=uuid.uuid4(),
            pipeline_id=pipeline.id,
            stage_key="new_unread",
            slug="new_unread",
            label="New Unread",
            color="#3B82F6",
            stage_type="intake",
            order=1,
            is_active=True,
        )
    )
    db.flush()

    hydrated = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    active_stage_keys = {
        stage.stage_key for stage in hydrated.stages if stage.is_active and not stage.deleted_at
    }

    for milestone in hydrated.feature_config["journey"]["milestones"]:
        assert set(milestone["mapped_stage_keys"]).issubset(active_stage_keys)
    assert set(hydrated.feature_config["analytics"]["funnel_stage_keys"]).issubset(
        active_stage_keys
    )
    assert set(hydrated.feature_config["analytics"]["performance_stage_keys"]).issubset(
        active_stage_keys
    )


def test_create_stage_clamps_custom_stage_order_between_protected_anchors(db, test_org, test_user):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)

    stage = pipeline_service.create_stage(
        db=db,
        pipeline_id=pipeline.id,
        slug=f"custom_{uuid.uuid4().hex[:6]}",
        label="Custom Stage",
        color="#6B7280",
        stage_type="intake",
        order=0,
        user_id=test_user.id,
    )

    active_stage_keys = [
        current_stage.stage_key
        for current_stage in sorted(
            (current_stage for current_stage in pipeline.stages if current_stage.is_active),
            key=lambda current_stage: current_stage.order,
        )
    ]
    assert active_stage_keys[0] == "new_unread"
    assert active_stage_keys[-1] == "disqualified"
    assert active_stage_keys[1] == stage.stage_key


@pytest.mark.asyncio
async def test_recommended_pipeline_draft_matches_platform_default_stage_order(
    authed_client: AsyncClient,
):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200
    pipeline_id = default_response.json()["id"]

    response = await authed_client.get(f"/settings/pipelines/{pipeline_id}/recommended-draft")
    assert response.status_code == 200

    data = response.json()
    expected_defs = get_default_stage_defs()

    assert [(stage["stage_key"], stage["label"], stage["order"]) for stage in data["stages"]] == [
        (stage["stage_key"], stage["label"], stage["order"]) for stage in expected_defs
    ]


@pytest.mark.asyncio
async def test_create_pipeline(authed_client: AsyncClient):
    """Create a pipeline should return 201 with version=1."""
    payload = {
        "name": "Test Pipeline",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
            {
                "slug": "contacted",
                "label": "Contacted",
                "color": "#F59E0B",
                "stage_type": "intake",
                "order": 2,
            },
            {
                "slug": "delivered",
                "label": "Delivered",
                "color": "#10B981",
                "stage_type": "terminal",
                "order": 3,
            },
        ],
    }
    response = await authed_client.post("/settings/pipelines", json=payload)
    if response.status_code != 201:
        print(f"Create response: {response.status_code} - {response.text}")
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Pipeline"
    assert data["current_version"] == 1
    assert data["feature_config"]["schema_version"] == 1
    protected_stage_keys = {
        "new_unread",
        "approved",
        "ready_to_match",
        "matched",
        "on_hold",
        "delivered",
        "lost",
        "disqualified",
    }
    assert protected_stage_keys.issubset({stage["stage_key"] for stage in data["stages"]})
    assert all("semantics" in stage for stage in data["stages"])


@pytest.mark.asyncio
async def test_update_pipeline_increments_version(authed_client: AsyncClient):
    """Updating a pipeline should increment current_version."""
    # Create first
    create_payload = {
        "name": "Version Test Pipeline",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
        ],
    }
    create_resp = await authed_client.post("/settings/pipelines", json=create_payload)
    if create_resp.status_code != 201:
        print(f"Create response: {create_resp.status_code} - {create_resp.text}")
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]
    initial_version = create_resp.json()["current_version"]

    # Update name only (stages unchanged)
    update_payload = {
        "name": "Version Test Pipeline Updated",
        "expected_version": initial_version,
    }
    update_resp = await authed_client.patch(
        f"/settings/pipelines/{pipeline_id}", json=update_payload
    )
    if update_resp.status_code != 200:
        print(f"Update response: {update_resp.status_code} - {update_resp.text}")
    assert update_resp.status_code == 200
    assert update_resp.json()["current_version"] == initial_version + 1


@pytest.mark.asyncio
async def test_update_pipeline_version_conflict(authed_client: AsyncClient):
    """Updating with wrong expected_version should return 409."""
    # Create first
    create_payload = {
        "name": "Conflict Test Pipeline",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
        ],
    }
    create_resp = await authed_client.post("/settings/pipelines", json=create_payload)
    if create_resp.status_code != 201:
        print(f"Create response: {create_resp.status_code} - {create_resp.text}")
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]

    # Update with wrong version
    update_payload = {
        "name": "Should Fail",
        "expected_version": 999,  # Wrong version
    }
    update_resp = await authed_client.patch(
        f"/settings/pipelines/{pipeline_id}", json=update_payload
    )
    assert update_resp.status_code == 409


@pytest.mark.asyncio
async def test_create_pipeline_sets_is_intake_stage(authed_client, db):
    payload = {
        "name": "Intake Stage Flags",
        "stages": [
            {
                "slug": "new_unread",
                "label": "New",
                "color": "#3B82F6",
                "stage_type": "intake",
                "order": 1,
            },
            {
                "slug": "ready_to_match",
                "label": "Ready to Match",
                "color": "#F59E0B",
                "stage_type": "post_approval",
                "order": 2,
            },
            {
                "slug": "delivered",
                "label": "Delivered",
                "color": "#10B981",
                "stage_type": "post_approval",
                "order": 3,
            },
        ],
    }
    response = await authed_client.post("/settings/pipelines", json=payload)
    assert response.status_code == 201, response.text
    pipeline_id = UUID(response.json()["id"])

    stages = db.query(PipelineStage).filter(PipelineStage.pipeline_id == pipeline_id).all()
    stage_by_slug = {stage.slug: stage for stage in stages}

    assert stage_by_slug["new_unread"].is_intake_stage is True
    assert stage_by_slug["ready_to_match"].is_intake_stage is False
    assert stage_by_slug["delivered"].is_intake_stage is False


@pytest.mark.asyncio
async def test_intake_can_get_default_pipeline(db, test_org):
    intake_user = User(
        id=uuid.uuid4(),
        email=f"intake-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Intake Pipeline Reader",
        token_version=1,
        is_active=True,
    )
    db.add(intake_user)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=intake_user.id,
            organization_id=test_org.id,
            role=Role.INTAKE_SPECIALIST,
            is_active=True,
        )
    )
    db.flush()

    token = create_session_token(
        user_id=intake_user.id,
        org_id=test_org.id,
        role=Role.INTAKE_SPECIALIST.value,
        token_version=intake_user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db, user_id=intake_user.id, org_id=test_org.id, token=token, request=None
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        response = await client.get("/settings/pipelines/default")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["is_default"] is True
        assert len(payload["stages"]) > 0

    app.dependency_overrides.clear()


def test_sync_missing_stages_inserts_on_hold_before_terminal_stages(db, test_org, test_user):
    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Missing On Hold",
        is_default=False,
        current_version=1,
    )
    db.add(pipeline)
    db.flush()

    stage_defs = [stage for stage in get_default_stage_defs() if stage["slug"] != "on_hold"]
    for stage_def in stage_defs:
        db.add(
            PipelineStage(
                id=uuid.uuid4(),
                pipeline_id=pipeline.id,
                stage_key=stage_def["stage_key"],
                slug=stage_def["slug"],
                label=stage_def["label"],
                color=stage_def["color"],
                stage_type=stage_def["stage_type"],
                order=stage_def["order"],
                is_active=True,
                is_intake_stage=stage_def["stage_type"] == "intake",
            )
        )
    db.commit()
    db.refresh(pipeline)

    added = pipeline_service.sync_missing_stages(db, pipeline, test_user.id)
    slugs = [stage.slug for stage in pipeline_service.get_stages(db, pipeline.id)]

    assert added == 1
    assert slugs.index("on_hold") < slugs.index("lost")
    assert slugs.index("on_hold") < slugs.index("disqualified")


def test_get_or_create_default_pipeline_normalizes_legacy_stage_categories(db, test_org, test_user):
    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Legacy Categories",
        is_default=True,
        current_version=1,
    )
    db.add(pipeline)
    db.flush()

    for stage_def in get_default_stage_defs():
        stage_type = stage_def["stage_type"]
        if stage_def["stage_key"] in {"on_hold", "lost", "disqualified"}:
            stage_type = "intake"
        db.add(
            PipelineStage(
                id=uuid.uuid4(),
                pipeline_id=pipeline.id,
                stage_key=stage_def["stage_key"],
                slug=stage_def["slug"],
                label=stage_def["label"],
                color=stage_def["color"],
                stage_type=stage_type,
                order=stage_def["order"],
                is_active=True,
                is_intake_stage=stage_type == "intake",
            )
        )
    db.commit()

    normalized = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)
    stage_by_key = {stage.stage_key: stage for stage in normalized.stages}

    assert stage_by_key["on_hold"].stage_type == "paused"
    assert stage_by_key["on_hold"].is_intake_stage is False
    assert stage_by_key["lost"].stage_type == "terminal"
    assert stage_by_key["disqualified"].stage_type == "terminal"


@pytest.mark.asyncio
async def test_required_pause_stage_cannot_be_deleted(authed_client):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    on_hold_stage = next(stage for stage in pipeline["stages"] if stage["slug"] == "on_hold")
    lost_stage = next(stage for stage in pipeline["stages"] if stage["slug"] == "lost")

    response = await authed_client.request(
        "DELETE",
        f"/settings/pipelines/{pipeline['id']}/stages/{on_hold_stage['id']}",
        json={"migrate_to_stage_id": lost_stage["id"]},
    )
    assert response.status_code == 400
    assert "protected system stage" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stage_reads_include_protection_metadata(authed_client: AsyncClient):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    new_unread = next(stage for stage in pipeline["stages"] if stage["stage_key"] == "new_unread")
    contacted = next(stage for stage in pipeline["stages"] if stage["stage_key"] == "contacted")

    assert new_unread["is_locked"] is True
    assert new_unread["system_role"] == "intake_entry"
    assert "label" in new_unread["locked_fields"]
    assert "duplicate" in new_unread["locked_fields"]
    assert new_unread["lock_reason"]

    assert contacted["is_locked"] is False
    assert contacted["system_role"] is None
    assert contacted["lock_reason"] is None
    assert contacted["locked_fields"] == []


@pytest.mark.asyncio
async def test_protected_stage_cannot_be_updated_deleted_or_reordered(
    authed_client: AsyncClient,
):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    ready_to_match_stage = next(
        stage for stage in pipeline["stages"] if stage["stage_key"] == "ready_to_match"
    )
    approved_stage = next(stage for stage in pipeline["stages"] if stage["stage_key"] == "approved")

    update_response = await authed_client.put(
        f"/settings/pipelines/{pipeline['id']}/stages/{ready_to_match_stage['id']}",
        json={
            "label": "Matching Queue",
            "expected_version": pipeline["current_version"],
        },
    )
    assert update_response.status_code == 400
    assert "protected system stage" in update_response.json()["detail"].lower()

    delete_response = await authed_client.request(
        "DELETE",
        f"/settings/pipelines/{pipeline['id']}/stages/{ready_to_match_stage['id']}",
        json={
            "migrate_to_stage_id": approved_stage["id"],
            "expected_version": pipeline["current_version"],
        },
    )
    assert delete_response.status_code == 400
    assert "protected system stage" in delete_response.json()["detail"].lower()

    reordered_ids = [stage["id"] for stage in reversed(pipeline["stages"])]
    reorder_response = await authed_client.put(
        f"/settings/pipelines/{pipeline['id']}/stages/reorder",
        json={
            "ordered_stage_ids": reordered_ids,
            "expected_version": pipeline["current_version"],
        },
    )
    assert reorder_response.status_code == 400
    assert "protected system stages" in reorder_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_stage_accepts_category_alias(authed_client: AsyncClient):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    contacted_stage = next(
        stage for stage in pipeline["stages"] if stage["stage_key"] == "contacted"
    )

    response = await authed_client.put(
        f"/settings/pipelines/{pipeline['id']}/stages/{contacted_stage['id']}",
        json={
            "category": "post_approval",
            "expected_version": pipeline["current_version"],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["category"] == "post_approval"
    assert payload["stage_type"] == "post_approval"


@pytest.mark.asyncio
async def test_custom_stage_cannot_claim_reserved_lifecycle_semantics(
    authed_client: AsyncClient,
):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    response = await authed_client.post(
        f"/settings/pipelines/{pipeline['id']}/stages",
        json={
            "slug": "matching_review",
            "label": "Matching Review",
            "color": "#8b5cf6",
            "category": "post_approval",
            "expected_version": pipeline["current_version"],
            "semantics": {
                "capabilities": {
                    "counts_as_contacted": False,
                    "eligible_for_matching": True,
                    "locks_match_state": False,
                    "shows_pregnancy_tracking": False,
                    "requires_delivery_details": False,
                    "tracks_interview_outcome": False,
                },
                "pause_behavior": "none",
                "terminal_outcome": "none",
                "integration_bucket": "qualified",
                "analytics_bucket": "matching_review",
                "suggestion_profile_key": "ready_to_match_followup",
                "requires_reason_on_enter": False,
            },
        },
    )

    assert response.status_code == 400
    assert "reserved lifecycle semantics" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_pipeline_change_preview_requires_remap_for_removed_stage_dependencies(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    ready_to_match_stage = next(
        stage for stage in pipeline["stages"] if stage["stage_key"] == "ready_to_match"
    )
    ready_to_match_db = pipeline_service.get_stage_by_id(db, UUID(ready_to_match_stage["id"]))
    assert ready_to_match_db is not None
    _create_surrogate_for_stage(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=ready_to_match_db,
    )

    db.add(
        OrgIntelligentSuggestionRule(
            id=uuid.uuid4(),
            organization_id=test_org.id,
            template_key="ready_to_match_stale",
            name="Ready to Match stale",
            rule_kind="stage_inactivity",
            stage_slug="ready_to_match",
            business_days=3,
            enabled=True,
            sort_order=1,
        )
    )
    zapier_settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    zapier_settings.outbound_event_mapping = [
        {
            "stage_key": "ready_to_match",
            "event_name": "Converted",
            "enabled": True,
            "bucket": "converted",
        }
    ]
    template = _create_email_template(db, org_id=test_org.id)
    campaign_service.create_campaign(
        db,
        test_org.id,
        test_user.id,
        CampaignCreate(
            name="Ready to Match Campaign",
            email_template_id=template.id,
            recipient_type="case",
            filter_criteria={"stage_ids": [str(ready_to_match_db.id)]},
        ),
    )
    workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name="Ready to Match Workflow",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED,
            trigger_config={"to_stage_key": "ready_to_match"},
            conditions=[
                {
                    "field": "stage_id",
                    "operator": "equals",
                    "value": "ready_to_match",
                }
            ],
            actions=[
                {
                    "action_type": "update_field",
                    "field": "stage_id",
                    "value": "ready_to_match",
                }
            ],
        ),
    )
    db.commit()

    preview_payload = {
        "name": pipeline["name"],
        "stages": [
            {
                "id": stage["id"],
                "stage_key": stage["stage_key"],
                "slug": stage["slug"],
                "label": stage["label"],
                "color": stage["color"],
                "order": index + 1,
                "category": stage["stage_type"],
                "is_active": stage["is_active"],
                "semantics": stage["semantics"],
            }
            for index, stage in enumerate(pipeline["stages"])
            if stage["stage_key"] != "ready_to_match"
        ],
        "feature_config": _remove_stage_key_refs(
            pipeline["feature_config"],
            "ready_to_match",
        ),
        "expected_version": pipeline["current_version"],
        "remaps": [],
    }

    response = await authed_client.post(
        f"/settings/pipelines/{pipeline['id']}/change-preview",
        json=preview_payload,
    )

    assert response.status_code == 200, response.text
    preview = response.json()
    required_remap = next(
        item for item in preview["required_remaps"] if item["stage_key"] == "ready_to_match"
    )
    assert required_remap["surrogate_count"] == 1
    assert "active_surrogates" in required_remap["reasons"]
    assert "campaigns" in required_remap["reasons"]
    assert "intelligent_suggestions" in required_remap["reasons"]
    assert "integrations" in required_remap["reasons"]
    assert "workflows" in required_remap["reasons"]


@pytest.mark.asyncio
async def test_apply_pipeline_draft_rejects_protected_stage_changes(
    authed_client: AsyncClient,
):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    draft_stages = []
    for stage in pipeline["stages"]:
        next_stage = {
            "id": stage["id"],
            "stage_key": stage["stage_key"],
            "slug": stage["slug"],
            "label": "Matching Queue" if stage["stage_key"] == "ready_to_match" else stage["label"],
            "color": stage["color"],
            "order": stage["order"],
            "category": stage["stage_type"],
            "is_active": stage["is_active"],
            "semantics": stage["semantics"],
        }
        draft_stages.append(next_stage)

    response = await authed_client.put(
        f"/settings/pipelines/{pipeline['id']}/apply-draft",
        json={
            "name": pipeline["name"],
            "stages": draft_stages,
            "feature_config": pipeline["feature_config"],
            "expected_version": pipeline["current_version"],
            "remaps": [],
        },
    )

    assert response.status_code == 400
    assert "protected system stage" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_apply_pipeline_draft_adds_custom_stage_and_remaps_deleted_stage_dependencies(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    contacted_stage = next(
        stage for stage in pipeline["stages"] if stage["stage_key"] == "contacted"
    )
    contacted_stage_db = pipeline_service.get_stage_by_id(db, UUID(contacted_stage["id"]))
    assert contacted_stage_db is not None
    surrogate = _create_surrogate_for_stage(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=contacted_stage_db,
    )
    template = _create_email_template(db, org_id=test_org.id)
    campaign = campaign_service.create_campaign(
        db,
        test_org.id,
        test_user.id,
        CampaignCreate(
            name="Pipeline remap campaign",
            email_template_id=template.id,
            recipient_type="case",
            filter_criteria={
                "stage_ids": [str(contacted_stage_db.id)],
                "stage_keys": ["contacted"],
                "stage_slugs": ["contacted"],
            },
        ),
    )
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name="Pipeline remap workflow",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED,
            trigger_config={"to_stage_key": "contacted"},
            conditions=[
                {
                    "field": "stage_id",
                    "operator": "equals",
                    "value": "contacted",
                }
            ],
            actions=[
                {
                    "action_type": "update_field",
                    "field": "stage_id",
                    "value": "contacted",
                }
            ],
        ),
    )
    db.commit()

    feature_config = deepcopy(pipeline["feature_config"])
    for milestone in feature_config["journey"]["milestones"]:
        if "contacted" in milestone["mapped_stage_keys"]:
            milestone["mapped_stage_keys"] = [
                "matching_review" if key == "contacted" else key
                for key in milestone["mapped_stage_keys"]
            ]
    feature_config["analytics"]["funnel_stage_keys"] = [
        "matching_review" if key == "contacted" else key
        for key in feature_config["analytics"]["funnel_stage_keys"]
    ]
    feature_config["analytics"]["performance_stage_keys"] = [
        "matching_review" if key == "contacted" else key
        for key in feature_config["analytics"]["performance_stage_keys"]
    ]
    if feature_config["analytics"]["qualification_stage_key"] == "contacted":
        feature_config["analytics"]["qualification_stage_key"] = "matching_review"
    for rules_key in ("role_visibility", "role_mutation"):
        for rule in feature_config[rules_key].values():
            rule["stage_keys"] = [
                "matching_review" if key == "contacted" else key for key in rule["stage_keys"]
            ]

    draft_stages = []
    for stage in pipeline["stages"]:
        if stage["stage_key"] == "contacted":
            continue
        if stage["stage_key"] == "approved":
            draft_stages.append(
                {
                    "id": stage["id"],
                    "stage_key": stage["stage_key"],
                    "slug": stage["slug"],
                    "label": stage["label"],
                    "color": stage["color"],
                    "order": stage["order"],
                    "category": stage["stage_type"],
                    "is_active": stage["is_active"],
                    "semantics": stage["semantics"],
                }
            )
            draft_stages.append(
                {
                    "stage_key": "matching_review",
                    "slug": "matching_review",
                    "label": "Matching Review",
                    "color": "#8b5cf6",
                    "order": stage["order"] + 1,
                    "category": "post_approval",
                    "is_active": True,
                    "semantics": {
                        "capabilities": {
                            "counts_as_contacted": True,
                            "eligible_for_matching": False,
                            "locks_match_state": False,
                            "shows_pregnancy_tracking": False,
                            "requires_delivery_details": False,
                            "tracks_interview_outcome": False,
                        },
                        "pause_behavior": "none",
                        "terminal_outcome": "none",
                        "integration_bucket": "qualified",
                        "analytics_bucket": "matching_review",
                        "suggestion_profile_key": "contacted_followup",
                        "requires_reason_on_enter": False,
                    },
                }
            )
            continue

        draft_stages.append(
            {
                "id": stage["id"],
                "stage_key": stage["stage_key"],
                "slug": stage["slug"],
                "label": stage["label"],
                "color": stage["color"],
                "order": stage["order"],
                "category": stage["stage_type"],
                "is_active": stage["is_active"],
                "semantics": stage["semantics"],
            }
        )

    response = await authed_client.put(
        f"/settings/pipelines/{pipeline['id']}/apply-draft",
        json={
            "name": pipeline["name"],
            "stages": draft_stages,
            "feature_config": feature_config,
            "expected_version": pipeline["current_version"],
            "comment": "Applied per-org pipeline draft",
            "remaps": [
                {
                    "removed_stage_key": "contacted",
                    "target_stage_key": "matching_review",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert any(stage["stage_key"] == "matching_review" for stage in payload["stages"])
    assert all(
        stage["stage_key"] != "contacted" or not stage["is_active"] for stage in payload["stages"]
    )

    db.refresh(surrogate)
    db.refresh(campaign)
    db.refresh(workflow)
    matching_review_stage = pipeline_service.get_stage_by_key(
        db, UUID(payload["id"]), "matching_review"
    )
    assert matching_review_stage is not None
    assert surrogate.stage_id == matching_review_stage.id
    assert surrogate.status_label == matching_review_stage.label
    assert campaign.filter_criteria["stage_keys"] == ["matching_review"]
    assert str(matching_review_stage.id) in {
        str(stage_id) for stage_id in campaign.filter_criteria["stage_ids"]
    }
    assert workflow.trigger_config["to_stage_key"] == "matching_review"
    assert str(workflow.trigger_config["to_stage_id"]) == str(matching_review_stage.id)
    assert workflow.conditions[0]["stage_key"] == "matching_review"
    assert str(workflow.conditions[0]["value"]) == str(matching_review_stage.id)
    assert workflow.actions[0]["value_stage_key"] == "matching_review"
    assert str(workflow.actions[0]["value"]) == str(matching_review_stage.id)


@pytest.mark.asyncio
async def test_apply_pipeline_draft_remaps_paused_from_stage_and_pending_status_change_request(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    add_stage_draft = []
    for stage in pipeline["stages"]:
        add_stage_draft.append(
            {
                "id": stage["id"],
                "stage_key": stage["stage_key"],
                "slug": stage["slug"],
                "label": stage["label"],
                "color": stage["color"],
                "order": stage["order"],
                "category": stage["stage_type"],
                "is_active": stage["is_active"],
                "semantics": stage["semantics"],
            }
        )
        if stage["stage_key"] == "approved":
            add_stage_draft.append(
                {
                    "stage_key": "matching_review",
                    "slug": "matching_review",
                    "label": "Matching Review",
                    "color": "#8b5cf6",
                    "order": stage["order"] + 1,
                    "category": "post_approval",
                    "is_active": True,
                    "semantics": {
                        "capabilities": {
                            "counts_as_contacted": False,
                            "eligible_for_matching": False,
                            "locks_match_state": False,
                            "shows_pregnancy_tracking": False,
                            "requires_delivery_details": False,
                            "tracks_interview_outcome": False,
                        },
                        "pause_behavior": "none",
                        "terminal_outcome": "none",
                        "integration_bucket": "qualified",
                        "analytics_bucket": "matching_review",
                        "suggestion_profile_key": "ready_to_match_followup",
                        "requires_reason_on_enter": False,
                    },
                }
            )

    add_stage_response = await authed_client.put(
        f"/settings/pipelines/{pipeline['id']}/apply-draft",
        json={
            "name": pipeline["name"],
            "stages": add_stage_draft,
            "feature_config": pipeline["feature_config"],
            "expected_version": pipeline["current_version"],
            "remaps": [],
        },
    )

    assert add_stage_response.status_code == 200, add_stage_response.text
    updated_pipeline = add_stage_response.json()
    custom_stage = next(
        stage for stage in updated_pipeline["stages"] if stage["stage_key"] == "matching_review"
    )
    on_hold_stage = pipeline_service.get_stage_by_key(db, UUID(updated_pipeline["id"]), "on_hold")
    approved_stage = pipeline_service.get_stage_by_key(db, UUID(updated_pipeline["id"]), "approved")
    assert on_hold_stage is not None
    assert approved_stage is not None

    surrogate = _create_surrogate_for_stage(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=on_hold_stage,
    )
    surrogate.paused_from_stage_id = UUID(custom_stage["id"])

    request = StatusChangeRequest(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        entity_type="surrogate",
        entity_id=surrogate.id,
        target_stage_id=UUID(custom_stage["id"]),
        effective_at=datetime.now(timezone.utc),
        reason="Need approval",
        requested_by_user_id=test_user.id,
        status="pending",
    )
    db.add(request)
    db.commit()

    removal_draft = [
        {
            "id": stage["id"],
            "stage_key": stage["stage_key"],
            "slug": stage["slug"],
            "label": stage["label"],
            "color": stage["color"],
            "order": index + 1,
            "category": stage["stage_type"],
            "is_active": stage["is_active"],
            "semantics": stage["semantics"],
        }
        for index, stage in enumerate(updated_pipeline["stages"])
        if stage["stage_key"] != "matching_review"
    ]

    remove_stage_response = await authed_client.put(
        f"/settings/pipelines/{updated_pipeline['id']}/apply-draft",
        json={
            "name": updated_pipeline["name"],
            "stages": removal_draft,
            "feature_config": updated_pipeline["feature_config"],
            "expected_version": updated_pipeline["current_version"],
            "remaps": [
                {
                    "removed_stage_key": "matching_review",
                    "target_stage_key": "approved",
                }
            ],
        },
    )

    assert remove_stage_response.status_code == 200, remove_stage_response.text

    db.refresh(surrogate)
    db.refresh(request)
    assert surrogate.paused_from_stage_id == approved_stage.id
    assert request.target_stage_id == approved_stage.id
