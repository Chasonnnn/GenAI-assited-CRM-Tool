"""Tests for Pipelines API with versioning."""

import uuid
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.permissions import PermissionKey as P
from app.core.pipeline_stage_colors import resolve_stage_color
from app.core.security import create_session_token
from app.core.stage_definitions import (
    EGG_DONOR_PIPELINE_ENTITY,
    INTENDED_PARENT_PIPELINE_ENTITY,
    SPERM_DONOR_PIPELINE_ENTITY,
    get_default_stage_defs,
)
from app.db.enums import Role, WorkflowTriggerType
from app.db.models import (
    AutomationWorkflow,
    Donor,
    EmailTemplate,
    IntendedParent,
    Membership,
    OrgIntelligentSuggestionRule,
    Pipeline,
    PipelineStage,
    StatusChangeRequest,
    Surrogate,
    User,
    UserPermissionOverride,
)
from app.main import app
from app.schemas.campaign import CampaignCreate
from app.schemas.workflow import WorkflowCreate
from app.services import (
    campaign_service,
    meta_crm_dataset_settings_service,
    pipeline_dependency_service,
    pipeline_service,
    session_service,
    workflow_service,
    zapier_settings_service,
)
from app.utils.normalization import normalize_email


def _admin_with_revoked_pipeline_permissions(
    db,
    *,
    org_id: UUID,
    permissions: list[P],
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"pipeline-rbac-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Pipeline RBAC Tester",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=org_id,
            role=Role.ADMIN.value,
            is_active=True,
        )
    )
    db.add_all(
        [
            UserPermissionOverride(
                id=uuid.uuid4(),
                organization_id=org_id,
                user_id=user.id,
                permission=permission.value,
                override_type="revoke",
            )
            for permission in permissions
        ]
    )
    db.flush()
    return user


@asynccontextmanager
async def _pipeline_client_for(db, *, org_id: UUID, user: User):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=Role.ADMIN.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
            headers={CSRF_HEADER: csrf_token},
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


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


def _create_donor_for_stage(
    db, *, org_id: UUID, donor_type: str, stage: PipelineStage
) -> Donor:
    email = f"pipeline-{donor_type}-donor-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    donor = Donor(
        id=uuid.uuid4(),
        organization_id=org_id,
        donor_number=f"D{uuid.uuid4().int % 90000 + 10000:05d}",
        donor_type=donor_type,
        stage_id=stage.id,
        full_name=f"Pipeline {donor_type.title()} Donor",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(donor)
    db.flush()
    return donor


def _create_intended_parent_for_stage(
    db, *, org_id: UUID, stage: PipelineStage
) -> IntendedParent:
    email = f"pipeline-ip-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    intended_parent = IntendedParent(
        id=uuid.uuid4(),
        organization_id=org_id,
        intended_parent_number=f"IP{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status=stage.slug,
        full_name="Pipeline Intended Parent",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(intended_parent)
    db.flush()
    return intended_parent


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


def _remap_stage_key_refs(
    feature_config: dict, removed_stage_key: str, target_stage_key: str
) -> dict:
    next_config = deepcopy(feature_config)

    def replace_keys(values: list[str]) -> list[str]:
        replaced = [target_stage_key if key == removed_stage_key else key for key in values]
        return list(dict.fromkeys(replaced))

    for milestone in next_config["journey"]["milestones"]:
        milestone["mapped_stage_keys"] = replace_keys(milestone["mapped_stage_keys"])
    next_config["analytics"]["funnel_stage_keys"] = replace_keys(
        next_config["analytics"]["funnel_stage_keys"]
    )
    next_config["analytics"]["performance_stage_keys"] = replace_keys(
        next_config["analytics"]["performance_stage_keys"]
    )
    if next_config["analytics"]["qualification_stage_key"] == removed_stage_key:
        next_config["analytics"]["qualification_stage_key"] = target_stage_key
    if next_config["analytics"]["conversion_stage_key"] == removed_stage_key:
        next_config["analytics"]["conversion_stage_key"] = target_stage_key
    for rules_key in ("role_visibility", "role_mutation"):
        for rule in next_config[rules_key].values():
            rule["stage_keys"] = replace_keys(rule["stage_keys"])
    return next_config


def _draft_stage_payload(stage: dict, order: int) -> dict:
    return {
        "id": stage["id"],
        "stage_key": stage["stage_key"],
        "slug": stage["slug"],
        "label": stage["label"],
        "color": stage["color"],
        "order": order,
        "category": stage["stage_type"],
        "is_active": stage["is_active"],
        "semantics": stage["semantics"],
    }


@pytest.mark.asyncio
async def test_list_pipelines_authed(authed_client: AsyncClient):
    """Authenticated request to /settings/pipelines should return 200."""
    response = await authed_client.get("/settings/pipelines")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_pipeline_api_rejects_unknown_non_empty_entity_type(authed_client: AsyncClient):
    response = await authed_client.get("/settings/pipelines", params={"entity_type": "egg-donor"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pipeline_api_returns_distinct_donor_defaults(authed_client: AsyncClient):
    egg_response = await authed_client.get(
        "/settings/pipelines/default", params={"entity_type": EGG_DONOR_PIPELINE_ENTITY}
    )
    sperm_response = await authed_client.get(
        "/settings/pipelines/default", params={"entity_type": SPERM_DONOR_PIPELINE_ENTITY}
    )

    assert egg_response.status_code == 200, egg_response.text
    assert sperm_response.status_code == 200, sperm_response.text
    assert egg_response.json()["entity_type"] == EGG_DONOR_PIPELINE_ENTITY
    assert sperm_response.json()["entity_type"] == SPERM_DONOR_PIPELINE_ENTITY
    assert [stage["stage_key"] for stage in egg_response.json()["stages"]] != [
        stage["stage_key"] for stage in sperm_response.json()["stages"]
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entity_type",
    [EGG_DONOR_PIPELINE_ENTITY, SPERM_DONOR_PIPELINE_ENTITY],
)
async def test_donor_pipeline_reads_require_donor_view_after_resolving_actual_type(
    db,
    test_org,
    test_user,
    entity_type,
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=entity_type,
    )
    user = _admin_with_revoked_pipeline_permissions(
        db,
        org_id=test_org.id,
        permissions=[P.DONORS_VIEW],
    )
    stages = pipeline_service.get_stages(db, pipeline.id)
    draft_payload = {
        "name": pipeline.name,
        "stages": [
            {
                "id": str(stage.id),
                "stage_key": stage.stage_key,
                "slug": stage.slug,
                "label": stage.label,
                "color": stage.color,
                "order": stage.order,
                "category": stage.stage_type,
                "is_active": stage.is_active,
                "semantics": stage.semantics,
            }
            for stage in stages
        ],
        "feature_config": pipeline.feature_config,
        "remaps": [],
    }

    async with _pipeline_client_for(db, org_id=test_org.id, user=user) as client:
        responses = [
            await client.get("/settings/pipelines", params={"entity_type": entity_type}),
            await client.get(
                "/settings/pipelines/default",
                params={"entity_type": entity_type},
            ),
            await client.get(f"/settings/pipelines/{pipeline.id}"),
            await client.get(f"/settings/pipelines/{pipeline.id}/dependency-graph"),
            await client.post(
                f"/settings/pipelines/{pipeline.id}/change-preview",
                json=draft_payload,
            ),
        ]
        surrogate_control = await client.get("/settings/pipelines/default")

    assert [response.status_code for response in responses] == [403, 403, 403, 403, 403]
    assert surrogate_control.status_code == 200, surrogate_control.text


@pytest.mark.asyncio
async def test_donor_pipeline_configuration_mutations_require_donor_edit(
    db,
    test_org,
    test_user,
):
    donor_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )
    surrogate_pipeline = pipeline_service.create_pipeline(
        db,
        test_org.id,
        test_user.id,
        "Surrogate mutation control",
    )
    user = _admin_with_revoked_pipeline_permissions(
        db,
        org_id=test_org.id,
        permissions=[P.DONORS_EDIT],
    )

    async with _pipeline_client_for(db, org_id=test_org.id, user=user) as client:
        detail = await client.get(f"/settings/pipelines/{donor_pipeline.id}")
        donor_update = await client.patch(
            f"/settings/pipelines/{donor_pipeline.id}",
            json={"name": "Forbidden donor pipeline update"},
        )
        donor_create = await client.post(
            "/settings/pipelines",
            json={
                "name": "Forbidden donor pipeline",
                "entity_type": SPERM_DONOR_PIPELINE_ENTITY,
            },
        )
        surrogate_update = await client.patch(
            f"/settings/pipelines/{surrogate_pipeline.id}",
            json={"name": "Allowed surrogate pipeline update"},
        )

    assert detail.status_code == 200, detail.text
    assert donor_update.status_code == 403
    assert donor_create.status_code == 403
    assert surrogate_update.status_code == 200, surrogate_update.text


@pytest.mark.asyncio
async def test_donor_pipeline_record_remaps_require_donor_change_status(
    db,
    test_org,
    test_user,
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )
    custom_stage = pipeline_service.create_stage(
        db,
        pipeline.id,
        slug="permission_review",
        label="Permission Review",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    target_stage = pipeline_service.get_stage_by_key(db, pipeline.id, "contacted")
    assert target_stage is not None
    _create_donor_for_stage(
        db,
        org_id=test_org.id,
        donor_type="egg",
        stage=custom_stage,
    )
    db.commit()
    user = _admin_with_revoked_pipeline_permissions(
        db,
        org_id=test_org.id,
        permissions=[P.DONORS_CHANGE_STATUS],
    )

    async with _pipeline_client_for(db, org_id=test_org.id, user=user) as client:
        detail = await client.get(f"/settings/pipelines/{pipeline.id}")
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        remap = await client.put(
            f"/settings/pipelines/{pipeline.id}/apply-draft",
            json={
                "name": payload["name"],
                "stages": [
                    _draft_stage_payload(stage, index + 1)
                    for index, stage in enumerate(
                        stage
                        for stage in payload["stages"]
                        if stage["id"] != str(custom_stage.id)
                    )
                ],
                "feature_config": payload["feature_config"],
                "expected_version": payload["current_version"],
                "remaps": [
                    {
                        "removed_stage_key": custom_stage.stage_key,
                        "target_stage_key": target_stage.stage_key,
                    }
                ],
            },
        )
        config_only = await client.post(
            f"/settings/pipelines/{pipeline.id}/stages",
            json={
                "slug": "configuration_only",
                "label": "Configuration Only",
                "color": "#64748B",
                "stage_type": "intake",
            },
        )

    assert remap.status_code == 403
    assert config_only.status_code == 201, config_only.text


def test_donor_pipeline_rollback_rejects_snapshot_that_would_strand_active_donor(
    db,
    test_org,
    test_user,
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )
    target_version = pipeline.current_version
    custom_stage = pipeline_service.create_stage(
        db,
        pipeline.id,
        slug="rollback_review",
        label="Rollback Review",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    donor = _create_donor_for_stage(
        db,
        org_id=test_org.id,
        donor_type="egg",
        stage=custom_stage,
    )
    db.commit()
    db.refresh(pipeline)
    version_before = pipeline.current_version
    version_count_before = len(
        pipeline_service.get_pipeline_versions(db, test_org.id, pipeline.id)
    )

    updated, error = pipeline_service.rollback_pipeline(
        db,
        pipeline,
        target_version=target_version,
        user_id=test_user.id,
    )

    db.refresh(pipeline)
    db.refresh(custom_stage)
    db.refresh(donor)
    assert updated is None
    assert error == "Stage 'Rollback Review' requires a remap target before removal."
    assert pipeline.current_version == version_before
    assert custom_stage.is_active is True
    assert donor.stage_id == custom_stage.id
    assert len(pipeline_service.get_pipeline_versions(db, test_org.id, pipeline.id)) == (
        version_count_before
    )


@pytest.mark.parametrize(
    "entity_type",
    ["surrogate", INTENDED_PARENT_PIPELINE_ENTITY],
)
def test_existing_entity_pipeline_rollback_rejects_snapshot_that_would_strand_records(
    db,
    test_org,
    test_user,
    entity_type,
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=entity_type,
    )
    target_version = pipeline.current_version
    custom_stage = pipeline_service.create_stage(
        db,
        pipeline.id,
        slug="rollback_review",
        label="Rollback Review",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    if entity_type == INTENDED_PARENT_PIPELINE_ENTITY:
        record = _create_intended_parent_for_stage(
            db,
            org_id=test_org.id,
            stage=custom_stage,
        )
    else:
        record = _create_surrogate_for_stage(
            db,
            org_id=test_org.id,
            user_id=test_user.id,
            stage=custom_stage,
        )
    db.commit()
    db.refresh(pipeline)
    version_before = pipeline.current_version

    updated, error = pipeline_service.rollback_pipeline(
        db,
        pipeline,
        target_version=target_version,
        user_id=test_user.id,
    )

    db.refresh(pipeline)
    db.refresh(custom_stage)
    db.refresh(record)
    assert updated is None
    assert error == "Stage 'Rollback Review' requires a remap target before removal."
    assert pipeline.current_version == version_before
    assert custom_stage.is_active is True
    assert record.stage_id == custom_stage.id


def test_donor_pipeline_rollback_rejects_snapshot_with_workflow_dependency(
    db,
    test_org,
    test_user,
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )
    target_version = pipeline.current_version
    custom_stage = pipeline_service.create_stage(
        db,
        pipeline.id,
        slug="rollback_review",
        label="Rollback Review",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name=f"Egg rollback workflow {uuid.uuid4().hex[:8]}",
        subject_type=EGG_DONOR_PIPELINE_ENTITY,
        trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED.value,
        trigger_config={"to_stage_id": str(custom_stage.id)},
        conditions=[],
        actions=[],
        is_enabled=True,
        scope="org",
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()
    db.refresh(pipeline)
    version_before = pipeline.current_version

    updated, error = pipeline_service.rollback_pipeline(
        db,
        pipeline,
        target_version=target_version,
        user_id=test_user.id,
    )

    db.refresh(pipeline)
    db.refresh(custom_stage)
    assert updated is None
    assert error == "Stage 'Rollback Review' requires a remap target before removal."
    assert pipeline.current_version == version_before
    assert custom_stage.is_active is True


def test_donor_pipeline_rollback_applies_dependency_free_snapshot(
    db,
    test_org,
    test_user,
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )
    target_version = pipeline.current_version
    custom_stage = pipeline_service.create_stage(
        db,
        pipeline.id,
        slug="rollback_review",
        label="Rollback Review",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    db.refresh(pipeline)
    version_before = pipeline.current_version

    updated, error = pipeline_service.rollback_pipeline(
        db,
        pipeline,
        target_version=target_version,
        user_id=test_user.id,
    )

    db.refresh(custom_stage)
    assert error is None
    assert updated is not None
    assert updated.current_version == version_before + 1
    assert custom_stage.is_active is False


def test_donor_default_pipelines_are_created_and_listed_in_isolation(db, test_org, test_user):
    egg_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )
    sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=SPERM_DONOR_PIPELINE_ENTITY,
    )

    assert egg_pipeline.id != sperm_pipeline.id
    assert egg_pipeline.entity_type == EGG_DONOR_PIPELINE_ENTITY
    assert sperm_pipeline.entity_type == SPERM_DONOR_PIPELINE_ENTITY
    assert [stage.stage_key for stage in sorted(egg_pipeline.stages, key=lambda item: item.order)] == [
        stage["stage_key"] for stage in get_default_stage_defs(EGG_DONOR_PIPELINE_ENTITY)
    ]
    assert [
        pipeline.id
        for pipeline in pipeline_service.list_pipelines(
            db, test_org.id, EGG_DONOR_PIPELINE_ENTITY
        )
    ] == [egg_pipeline.id]
    assert [
        pipeline.id
        for pipeline in pipeline_service.list_pipelines(
            db, test_org.id, SPERM_DONOR_PIPELINE_ENTITY
        )
    ] == [sperm_pipeline.id]

    custom_egg_pipeline = pipeline_service.create_pipeline(
        db,
        test_org.id,
        test_user.id,
        "Egg Donor Review",
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )

    assert {
        pipeline.id
        for pipeline in pipeline_service.list_pipelines(
            db, test_org.id, EGG_DONOR_PIPELINE_ENTITY
        )
    } == {egg_pipeline.id, custom_egg_pipeline.id}
    assert pipeline_service.get_pipeline(
        db,
        test_org.id,
        custom_egg_pipeline.id,
        entity_type=SPERM_DONOR_PIPELINE_ENTITY,
    ) is None


@pytest.mark.parametrize(
    ("entity_type", "expected_stage_keys"),
    [
        (
            EGG_DONOR_PIPELINE_ENTITY,
            [
                "new",
                "contacted",
                "pre_screening",
                "application_submitted",
                "medical_records_review",
                "psychological_screening",
                "ready_to_match",
                "matched",
                "cycle_in_progress",
                "retrieval_complete",
                "on_hold",
                "disqualified",
                "closed",
            ],
        ),
        (
            SPERM_DONOR_PIPELINE_ENTITY,
            [
                "new",
                "contacted",
                "pre_screening",
                "application_submitted",
                "semen_analysis",
                "medical_genetic_screening",
                "available",
                "matched",
                "collection_in_progress",
                "donation_complete",
                "on_hold",
                "disqualified",
                "closed",
            ],
        ),
    ],
)
def test_donor_recommended_pipeline_draft_resets_to_its_own_defaults(
    db, test_org, test_user, entity_type, expected_stage_keys
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, test_user.id, entity_type=entity_type
    )

    draft = pipeline_service.build_recommended_pipeline_draft(pipeline)

    assert [stage["stage_key"] for stage in draft["stages"]] == expected_stage_keys


def test_donor_dependency_graph_does_not_reuse_surrogate_workflow_references(
    db, test_org, test_user
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )
    db.add(
        AutomationWorkflow(
            organization_id=test_org.id,
            name=f"Surrogate stage workflow {uuid.uuid4().hex[:8]}",
            trigger_type="status_changed",
            trigger_config={"to_stage_key": "ready_to_match"},
            conditions=[],
            actions=[],
            is_enabled=True,
            scope="org",
            created_by_user_id=test_user.id,
        )
    )
    db.commit()

    graph = pipeline_dependency_service.build_pipeline_dependency_graph(db, pipeline)

    assert all(stage["surrogate_count"] == 0 for stage in graph["stages"])
    assert all(stage["campaign_refs"] == [] for stage in graph["stages"])
    assert all(stage["workflow_refs"] == [] for stage in graph["stages"])


def test_donor_dependency_graph_includes_only_same_subtype_workflows(
    db, test_org, test_user
):
    egg_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )
    egg_workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name=f"Egg donor pipeline workflow {uuid.uuid4().hex[:8]}",
        subject_type=EGG_DONOR_PIPELINE_ENTITY,
        trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED.value,
        trigger_config={"to_stage_key": "contacted"},
        conditions=[],
        actions=[],
        is_enabled=True,
        scope="org",
        created_by_user_id=test_user.id,
    )
    sperm_workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name=f"Sperm donor pipeline workflow {uuid.uuid4().hex[:8]}",
        subject_type=SPERM_DONOR_PIPELINE_ENTITY,
        trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED.value,
        trigger_config={"to_stage_key": "contacted"},
        conditions=[],
        actions=[],
        is_enabled=True,
        scope="org",
        created_by_user_id=test_user.id,
    )
    db.add_all([egg_workflow, sperm_workflow])
    db.commit()

    graph = pipeline_dependency_service.build_pipeline_dependency_graph(db, egg_pipeline)
    contacted = next(stage for stage in graph["stages"] if stage["stage_key"] == "contacted")

    assert {item["id"] for item in contacted["workflow_refs"]} == {str(egg_workflow.id)}


def test_surrogate_dependency_graph_does_not_reuse_donor_workflow_references(
    db, test_org, test_user
):
    surrogate_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
    )
    donor_workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name=f"Donor-only pipeline workflow {uuid.uuid4().hex[:8]}",
        subject_type=EGG_DONOR_PIPELINE_ENTITY,
        trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED.value,
        trigger_config={"to_stage_key": "contacted"},
        conditions=[],
        actions=[],
        is_enabled=True,
        scope="org",
        created_by_user_id=test_user.id,
    )
    db.add(donor_workflow)
    db.commit()

    graph = pipeline_dependency_service.build_pipeline_dependency_graph(db, surrogate_pipeline)
    contacted = next(stage for stage in graph["stages"] if stage["stage_key"] == "contacted")

    assert contacted["workflow_refs"] == []


def test_donor_dependency_graph_counts_only_same_org_and_donor_type(
    db, test_org, test_user
):
    egg_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=EGG_DONOR_PIPELINE_ENTITY,
    )
    sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type=SPERM_DONOR_PIPELINE_ENTITY,
    )
    egg_new = next(stage for stage in egg_pipeline.stages if stage.stage_key == "new")
    sperm_new = next(stage for stage in sperm_pipeline.stages if stage.stage_key == "new")
    _create_donor_for_stage(db, org_id=test_org.id, donor_type="egg", stage=egg_new)
    _create_donor_for_stage(db, org_id=test_org.id, donor_type="sperm", stage=sperm_new)
    db.commit()

    egg_graph = pipeline_dependency_service.build_pipeline_dependency_graph(db, egg_pipeline)
    sperm_graph = pipeline_dependency_service.build_pipeline_dependency_graph(db, sperm_pipeline)

    egg_new_dependency = next(
        stage for stage in egg_graph["stages"] if stage["stage_key"] == "new"
    )
    sperm_new_dependency = next(
        stage for stage in sperm_graph["stages"] if stage["stage_key"] == "new"
    )
    assert egg_new_dependency["surrogate_count"] == 1
    assert sperm_new_dependency["surrogate_count"] == 1


def test_apply_egg_pipeline_remap_moves_only_egg_donors_and_refreshes_stage_state(
    db, test_org, test_user
):
    egg_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, test_user.id, entity_type=EGG_DONOR_PIPELINE_ENTITY
    )
    sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, test_user.id, entity_type=SPERM_DONOR_PIPELINE_ENTITY
    )
    custom_stage = pipeline_service.create_stage(
        db,
        egg_pipeline.id,
        slug="secondary_review",
        label="Secondary Review",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    egg_target = pipeline_service.get_stage_by_key(db, egg_pipeline.id, "contacted")
    sperm_stage = pipeline_service.get_stage_by_key(db, sperm_pipeline.id, "contacted")
    assert egg_target is not None
    assert sperm_stage is not None
    egg_donor = _create_donor_for_stage(
        db, org_id=test_org.id, donor_type="egg", stage=custom_stage
    )
    sperm_donor = _create_donor_for_stage(
        db, org_id=test_org.id, donor_type="sperm", stage=sperm_stage
    )
    assert egg_donor.stage.id == custom_stage.id
    assert sperm_donor.stage.id == sperm_stage.id
    db.commit()

    kept_stages = [
        stage
        for stage in pipeline_service.get_stages(db, egg_pipeline.id, include_inactive=True)
        if stage.is_active and stage.id != custom_stage.id
    ]
    pipeline_service.apply_pipeline_draft(
        db,
        egg_pipeline,
        name=egg_pipeline.name,
        stages=[
            {
                "id": str(stage.id),
                "stage_key": stage.stage_key,
                "slug": stage.slug,
                "label": stage.label,
                "color": stage.color,
                "order": index + 1,
                "category": stage.stage_type,
                "is_active": stage.is_active,
                "semantics": stage.semantics,
            }
            for index, stage in enumerate(kept_stages)
        ],
        feature_config=egg_pipeline.feature_config,
        remaps=[
            {
                "removed_stage_key": custom_stage.stage_key,
                "target_stage_key": egg_target.stage_key,
            }
        ],
        user_id=test_user.id,
    )

    assert egg_donor.stage_id == egg_target.id
    assert egg_donor.stage.id == egg_target.id
    assert sperm_donor.stage_id == sperm_stage.id
    assert sperm_donor.stage.id == sperm_stage.id


def test_apply_donor_pipeline_remap_updates_only_same_subtype_workflows(
    db, test_org, test_user
):
    egg_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, test_user.id, entity_type=EGG_DONOR_PIPELINE_ENTITY
    )
    sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, test_user.id, entity_type=SPERM_DONOR_PIPELINE_ENTITY
    )
    egg_custom = pipeline_service.create_stage(
        db,
        egg_pipeline.id,
        slug="secondary_review",
        label="Secondary Review",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    sperm_custom = pipeline_service.create_stage(
        db,
        sperm_pipeline.id,
        slug="secondary_review",
        label="Secondary Review",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    egg_target = pipeline_service.get_stage_by_key(db, egg_pipeline.id, "contacted")
    assert egg_target is not None
    egg_workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Egg donor remap workflow {uuid.uuid4().hex[:8]}",
            subject_type=EGG_DONOR_PIPELINE_ENTITY,
            trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED,
            trigger_config={"to_stage_id": str(egg_custom.id)},
            actions=[
                {
                    "action_type": "send_notification",
                    "title": "Egg donor stage changed",
                    "body": "Pipeline remap audit workflow",
                    "recipients": "owner",
                }
            ],
        ),
    )
    sperm_workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Sperm donor remap workflow {uuid.uuid4().hex[:8]}",
            subject_type=SPERM_DONOR_PIPELINE_ENTITY,
            trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED,
            trigger_config={"to_stage_id": str(sperm_custom.id)},
            actions=[
                {
                    "action_type": "send_notification",
                    "title": "Sperm donor stage changed",
                    "body": "Pipeline remap audit workflow",
                    "recipients": "owner",
                }
            ],
        ),
    )
    db.commit()

    kept_stages = [
        stage
        for stage in pipeline_service.get_stages(db, egg_pipeline.id, include_inactive=True)
        if stage.is_active and stage.id != egg_custom.id
    ]
    pipeline_service.apply_pipeline_draft(
        db,
        egg_pipeline,
        name=egg_pipeline.name,
        stages=[
            {
                "id": str(stage.id),
                "stage_key": stage.stage_key,
                "slug": stage.slug,
                "label": stage.label,
                "color": stage.color,
                "order": index + 1,
                "category": stage.stage_type,
                "is_active": stage.is_active,
                "semantics": stage.semantics,
            }
            for index, stage in enumerate(kept_stages)
        ],
        feature_config=egg_pipeline.feature_config,
        remaps=[
            {
                "removed_stage_key": egg_custom.stage_key,
                "target_stage_key": egg_target.stage_key,
            }
        ],
        user_id=test_user.id,
    )

    db.refresh(egg_workflow)
    db.refresh(sperm_workflow)
    assert egg_workflow.trigger_config["to_stage_key"] == egg_target.stage_key
    assert UUID(egg_workflow.trigger_config["to_stage_id"]) == egg_target.id
    assert sperm_workflow.trigger_config["to_stage_key"] == sperm_custom.stage_key
    assert UUID(sperm_workflow.trigger_config["to_stage_id"]) == sperm_custom.id


def test_delete_donor_stage_migrates_matching_subtype_records(db, test_org, test_user):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, test_user.id, entity_type=SPERM_DONOR_PIPELINE_ENTITY
    )
    custom_stage = pipeline_service.create_stage(
        db,
        pipeline.id,
        slug="repeat_analysis",
        label="Repeat Analysis",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    target_stage = pipeline_service.get_stage_by_key(db, pipeline.id, "semen_analysis")
    assert target_stage is not None
    donor = _create_donor_for_stage(
        db, org_id=test_org.id, donor_type="sperm", stage=custom_stage
    )
    assert donor.stage.id == custom_stage.id
    db.commit()

    migrated = pipeline_service.delete_stage(
        db,
        custom_stage,
        target_stage.id,
        user_id=test_user.id,
    )

    assert migrated == 1
    assert donor.stage_id == target_stage.id
    assert donor.stage.id == target_stage.id


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


def test_pipeline_service_count_paths_use_direct_aggregate_queries():
    source = Path("app/services/pipeline_service.py").read_text()
    create_stage_source = source[
        source.index("def create_stage(") : source.index("def update_stage(")
    ]
    apply_draft_source = source[
        source.index("def apply_pipeline_draft(") : source.index("def sync_surrogate_labels(")
    ]

    assert ".count()" not in create_stage_source
    assert ".count()" not in apply_draft_source


def test_apply_pipeline_draft_counts_removed_stage_entities_with_direct_count(
    db, test_org, test_user
):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)
    removed_stages = [
        pipeline_service.create_stage(
            db,
            pipeline.id,
            slug=f"cleanup_{uuid.uuid4().hex[:6]}",
            label=f"Cleanup {index}",
            color="#64748b",
            stage_type="paused",
            order=999,
            user_id=test_user.id,
        )
        for index in range(2)
    ]
    removed_stage_ids = {stage.id for stage in removed_stages}
    db.flush()

    draft_stages = [
        {
            "id": str(stage.id),
            "stage_key": stage.stage_key,
            "slug": stage.slug,
            "label": stage.label,
            "color": stage.color,
            "order": index + 1,
            "category": stage.stage_type,
            "is_active": stage.is_active,
            "semantics": stage.semantics or {},
        }
        for index, stage in enumerate(pipeline_service.get_stages(db, pipeline.id))
        if stage.id not in removed_stage_ids
    ]
    statements: list[str] = []

    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        pipeline_service.apply_pipeline_draft(
            db,
            pipeline,
            name=pipeline.name,
            stages=draft_stages,
            feature_config=pipeline.feature_config,
            remaps=[],
            user_id=test_user.id,
            comment="Remove unused cleanup stage",
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)

    aggregate_statements = [
        statement.lower()
        for statement in statements
        if "surrogates" in statement.lower() and "count(" in statement.lower()
    ]

    assert len(aggregate_statements) == 1
    assert "from (select" not in aggregate_statements[0]
    assert "group by" in aggregate_statements[0]


def test_resolve_stage_color_uses_keyword_presets_for_gray_custom_stages():
    assert (
        resolve_stage_color(
            color="#6B7280",
            label="Pending-DocuSign",
            slug="pending_docusign",
            stage_key="pending_docusign",
            stage_type="post_approval",
            order=18,
            is_locked=False,
        )
        == "#f59e0b"
    )
    assert (
        resolve_stage_color(
            color="#6B7280",
            label="Life Insurance Application Started",
            slug="life_insurance_application_started",
            stage_key="life_insurance_application_started",
            stage_type="post_approval",
            order=19,
            is_locked=False,
        )
        == "#0891b2"
    )
    assert (
        resolve_stage_color(
            color="#6B7280",
            label="PBO Process Started",
            slug="pbo_process_started",
            stage_key="pbo_process_started",
            stage_type="post_approval",
            order=20,
            is_locked=False,
        )
        == "#db2777"
    )


def test_serialize_stage_recolors_gray_custom_stage_payload(db, test_org, test_user):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id, test_user.id)

    stage = pipeline_service.create_stage(
        db=db,
        pipeline_id=pipeline.id,
        slug="pending_docusign_followup",
        label="Pending-DocuSign Follow-up",
        color="#6B7280",
        stage_type="post_approval",
        order=999,
        user_id=test_user.id,
    )

    serialized = pipeline_service._serialize_stage(stage, pipeline.entity_type)

    assert serialized["color"] == "#f59e0b"


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
async def test_pipeline_change_preview_requires_remap_for_pre_qualified_integrations(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    pre_qualified_stage = next(
        stage for stage in pipeline["stages"] if stage["stage_key"] == "pre_qualified"
    )
    pre_qualified_db = pipeline_service.get_stage_by_id(db, UUID(pre_qualified_stage["id"]))
    assert pre_qualified_db is not None
    _create_surrogate_for_stage(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=pre_qualified_db,
    )

    zapier_settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    zapier_settings.outbound_event_mapping = [
        {
            "stage_key": "pre_qualified",
            "event_name": "PreQualifiedLead",
            "enabled": True,
            "bucket": "qualified",
        }
    ]
    meta_settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    meta_settings.event_mapping = [
        {
            "stage_key": "pre_qualified",
            "event_name": "PreQualifiedLead",
            "enabled": True,
            "bucket": "qualified",
        }
    ]
    db.commit()

    preview_payload = {
        "name": pipeline["name"],
        "stages": [
            _draft_stage_payload(stage, index + 1)
            for index, stage in enumerate(
                stage for stage in pipeline["stages"] if stage["stage_key"] != "pre_qualified"
            )
        ],
        "feature_config": _remove_stage_key_refs(
            pipeline["feature_config"],
            "pre_qualified",
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
        item for item in preview["required_remaps"] if item["stage_key"] == "pre_qualified"
    )
    assert required_remap["surrogate_count"] == 1
    assert "active_surrogates" in required_remap["reasons"]
    assert "integrations" in required_remap["reasons"]
    assert any(
        "Pre-Qualified" in issue and "remap target" in issue for issue in preview["blocking_issues"]
    )

    pre_qualified_dependency = next(
        item
        for item in preview["dependency_graph"]["stages"]
        if item["stage_key"] == "pre_qualified"
    )
    assert pre_qualified_dependency["integration_refs"] == [
        "meta_crm_dataset",
        "zapier_outbound",
    ]


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
async def test_apply_pipeline_draft_removes_pre_qualified_and_remaps_integration_mappings(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    pre_qualified_stage = next(
        stage for stage in pipeline["stages"] if stage["stage_key"] == "pre_qualified"
    )
    contacted_stage = next(
        stage for stage in pipeline["stages"] if stage["stage_key"] == "contacted"
    )
    pre_qualified_db = pipeline_service.get_stage_by_id(db, UUID(pre_qualified_stage["id"]))
    contacted_db = pipeline_service.get_stage_by_id(db, UUID(contacted_stage["id"]))
    assert pre_qualified_db is not None
    assert contacted_db is not None
    surrogate = _create_surrogate_for_stage(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=pre_qualified_db,
    )

    zapier_settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    zapier_settings.outbound_event_mapping = [
        {
            "stage_key": "pre_qualified",
            "event_name": "PreQualifiedLead",
            "enabled": True,
            "bucket": "qualified",
        }
    ]
    meta_settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    meta_settings.event_mapping = [
        {
            "stage_key": "pre_qualified",
            "event_name": "PreQualifiedLead",
            "enabled": True,
            "bucket": "qualified",
        }
    ]
    db.commit()

    response = await authed_client.put(
        f"/settings/pipelines/{pipeline['id']}/apply-draft",
        json={
            "name": pipeline["name"],
            "stages": [
                _draft_stage_payload(stage, index + 1)
                for index, stage in enumerate(
                    stage for stage in pipeline["stages"] if stage["stage_key"] != "pre_qualified"
                )
            ],
            "feature_config": _remap_stage_key_refs(
                pipeline["feature_config"],
                "pre_qualified",
                "contacted",
            ),
            "expected_version": pipeline["current_version"],
            "comment": "Removed pre-qualified stage",
            "remaps": [
                {
                    "removed_stage_key": "pre_qualified",
                    "target_stage_key": "contacted",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert all(
        stage["stage_key"] != "pre_qualified" or not stage["is_active"]
        for stage in payload["stages"]
    )

    db.refresh(surrogate)
    db.refresh(zapier_settings)
    db.refresh(meta_settings)
    assert surrogate.stage_id == contacted_db.id
    assert surrogate.status_label == contacted_db.label

    zapier_stage_keys = {item["stage_key"] for item in zapier_settings.outbound_event_mapping}
    meta_stage_keys = {item["stage_key"] for item in meta_settings.event_mapping}
    assert "pre_qualified" not in zapier_stage_keys
    assert "pre_qualified" not in meta_stage_keys
    assert "contacted" in zapier_stage_keys
    assert "contacted" in meta_stage_keys


@pytest.mark.asyncio
async def test_apply_pipeline_draft_remaps_workflow_trigger_when_multiple_default_pipelines_exist(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    pipeline_service.get_or_create_default_pipeline(
        db,
        test_org.id,
        test_user.id,
        entity_type="intended_parent",
    )

    default_response = await authed_client.get("/settings/pipelines/default")
    assert default_response.status_code == 200, default_response.text
    pipeline = default_response.json()

    contacted_stage = next(
        stage for stage in pipeline["stages"] if stage["stage_key"] == "contacted"
    )
    contacted_stage_db = pipeline_service.get_stage_by_id(db, UUID(contacted_stage["id"]))
    assert contacted_stage_db is not None
    _create_surrogate_for_stage(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=contacted_stage_db,
    )
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Pipeline trigger remap {uuid.uuid4().hex[:8]}",
            trigger_type=WorkflowTriggerType.STATUS_CHANGED,
            trigger_config={"to_stage_key": "contacted"},
            conditions=[],
            actions=[
                {
                    "action_type": "send_notification",
                    "title": "Stage changed",
                    "body": "Pipeline remap audit workflow",
                    "recipients": "owner",
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
    if feature_config["analytics"]["conversion_stage_key"] == "contacted":
        feature_config["analytics"]["conversion_stage_key"] = "matching_review"

    draft_stages = []
    for stage in pipeline["stages"]:
        if stage["stage_key"] == "contacted":
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
        if stage["stage_key"] == "approved":
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

    response = await authed_client.put(
        f"/settings/pipelines/{pipeline['id']}/apply-draft",
        json={
            "name": pipeline["name"],
            "stages": draft_stages,
            "feature_config": feature_config,
            "expected_version": pipeline["current_version"],
            "comment": "Workflow trigger remap audit",
            "remaps": [
                {
                    "removed_stage_key": "contacted",
                    "target_stage_key": "matching_review",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text

    db.refresh(workflow)
    matching_review_stage = pipeline_service.get_stage_by_key(
        db, UUID(pipeline["id"]), "matching_review"
    )
    assert matching_review_stage is not None
    assert workflow.trigger_config["to_stage_key"] == "matching_review"
    assert str(workflow.trigger_config["to_stage_id"]) == str(matching_review_stage.id)


@pytest.mark.asyncio
async def test_apply_pipeline_draft_syncs_surrogate_status_labels_for_renamed_stage(
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
    db.commit()

    draft_stages = []
    for stage in pipeline["stages"]:
        stage_payload = {
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
        if stage["stage_key"] == "contacted":
            stage_payload["label"] = "Outreach Complete"
        draft_stages.append(stage_payload)

    response = await authed_client.put(
        f"/settings/pipelines/{pipeline['id']}/apply-draft",
        json={
            "name": pipeline["name"],
            "stages": draft_stages,
            "feature_config": pipeline["feature_config"],
            "expected_version": pipeline["current_version"],
            "comment": "Rename contacted stage for label sync audit",
            "remaps": [],
        },
    )

    assert response.status_code == 200, response.text

    db.refresh(surrogate)
    assert surrogate.status_label == "Outreach Complete"

    detail_response = await authed_client.get(f"/surrogates/{surrogate.id}")
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status_label"] == "Outreach Complete"


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
        effective_at=datetime.now(UTC),
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
