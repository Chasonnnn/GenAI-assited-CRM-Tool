"""Tests for Pipelines API with versioning."""

import uuid
from copy import deepcopy
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
    Membership,
    OrgIntelligentSuggestionRule,
    Pipeline,
    PipelineStage,
    Surrogate,
    User,
)
from app.main import app
from app.services import pipeline_service, session_service, zapier_settings_service
from app.utils.normalization import normalize_email


def _create_surrogate_for_stage(db, *, org_id: UUID, user_id: UUID, stage: PipelineStage) -> Surrogate:
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

    assert [
        (stage["stage_key"], stage["label"], stage["order"])
        for stage in data["stages"]
    ] == [
        (stage["stage_key"], stage["label"], stage["order"])
        for stage in expected_defs
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
    assert len(data["stages"]) == 4
    assert any(stage["slug"] == "on_hold" for stage in data["stages"])
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
    assert "resume_previous_stage" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_stage_accepts_category_alias(authed_client: AsyncClient):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    contacted_stage = next(stage for stage in pipeline["stages"] if stage["stage_key"] == "contacted")

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
    assert "intelligent_suggestions" in required_remap["reasons"]
    assert "integrations" in required_remap["reasons"]


@pytest.mark.asyncio
async def test_apply_pipeline_draft_adds_stage_reclassifies_stage_and_deletes_with_remap(
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
    surrogate = _create_surrogate_for_stage(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=ready_to_match_db,
    )
    db.commit()

    feature_config = deepcopy(pipeline["feature_config"])
    for milestone in feature_config["journey"]["milestones"]:
        if "ready_to_match" in milestone["mapped_stage_keys"]:
            milestone["mapped_stage_keys"] = [
                "matching_review" if key == "ready_to_match" else key
                for key in milestone["mapped_stage_keys"]
            ]
    feature_config["analytics"]["funnel_stage_keys"] = [
        "matching_review" if key == "ready_to_match" else key
        for key in feature_config["analytics"]["funnel_stage_keys"]
    ]
    for rules_key in ("role_visibility", "role_mutation"):
        for rule in feature_config[rules_key].values():
            rule["stage_keys"] = [
                "matching_review" if key == "ready_to_match" else key
                for key in rule["stage_keys"]
            ]

    draft_stages = []
    insert_order = ready_to_match_stage["order"]
    for stage in pipeline["stages"]:
        if stage["stage_key"] == "ready_to_match":
            draft_stages.append(
                {
                    "stage_key": "matching_review",
                    "slug": "matching_review",
                    "label": "Matching Review",
                    "color": "#8b5cf6",
                    "order": insert_order,
                    "category": "post_approval",
                    "is_active": True,
                    "semantics": {
                        **stage["semantics"],
                        "capabilities": {
                            **stage["semantics"]["capabilities"],
                            "eligible_for_matching": True,
                        },
                        "integration_bucket": "converted",
                        "analytics_bucket": "matching_review",
                        "suggestion_profile_key": "ready_to_match_followup",
                    },
                }
            )
            continue

        next_stage = {
            "id": stage["id"],
            "stage_key": stage["stage_key"],
            "slug": stage["slug"],
            "label": stage["label"],
            "color": stage["color"],
            "order": stage["order"] + (1 if stage["order"] > insert_order else 0),
            "category": "post_approval"
            if stage["stage_key"] == "contacted"
            else stage["stage_type"],
            "is_active": stage["is_active"],
            "semantics": stage["semantics"],
        }
        draft_stages.append(next_stage)

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
                    "removed_stage_key": "ready_to_match",
                    "target_stage_key": "matching_review",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert any(stage["stage_key"] == "matching_review" for stage in payload["stages"])
    contacted = next(stage for stage in payload["stages"] if stage["stage_key"] == "contacted")
    assert contacted["category"] == "post_approval"
    assert all(stage["stage_key"] != "ready_to_match" or not stage["is_active"] for stage in payload["stages"])

    db.refresh(surrogate)
    matching_review_stage = pipeline_service.get_stage_by_key(db, UUID(payload["id"]), "matching_review")
    assert matching_review_stage is not None
    assert surrogate.stage_id == matching_review_stage.id
    assert surrogate.status_label == matching_review_stage.label
