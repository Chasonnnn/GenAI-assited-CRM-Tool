"""Record visibility must not imply write authority in legacy capability routers."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.surrogate_access import can_modify_surrogate, check_surrogate_access
from app.db.enums import Role
from app.db.models import (
    Membership,
    Organization,
    OrganizationPermissionPolicy,
    Queue,
    RolePermission,
    RoleRecordScope,
    Surrogate,
    UserPermissionOverride,
)
from app.schemas.interview import InterviewCreate
from app.services import interview_service, pipeline_service


@pytest.fixture
def record_context(db, test_org, test_user, default_stage):
    db.query(Membership).filter_by(
        user_id=test_user.id, organization_id=test_org.id
    ).one().role = "case_manager"
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.add(
        RoleRecordScope(
            organization_id=test_org.id,
            role="case_manager",
            module="surrogates",
            assignment="all",
            phase="all",
            stage_ids=[],
        )
    )
    surrogate = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_number="S10001",
        full_name="Synthetic record",
        email=f"{uuid4()}@example.test",
        email_hash=uuid4().hex,
        owner_type="user",
        owner_id=test_user.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
    )
    queue = Queue(organization_id=test_org.id, name="Test queue", is_active=True)
    db.add_all([surrogate, queue])
    db.flush()
    interview = interview_service.create_interview(
        db=db,
        org_id=test_org.id,
        surrogate_id=surrogate.id,
        user_id=test_user.id,
        data=InterviewCreate(
            interview_type="phone", conducted_at=datetime.now(UTC), status="draft"
        ),
    )
    db.flush()
    return SimpleNamespace(
        record=surrogate,
        queue=queue,
        interview=interview,
        session=SimpleNamespace(org_id=test_org.id, user_id=test_user.id, role=Role.CASE_MANAGER),
    )


def test_core_v2_visibility_requires_view_action(db, test_org, record_context):
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role="case_manager",
            permission="view_surrogates",
            is_granted=False,
        )
    )
    db.flush()
    with pytest.raises(HTTPException) as exc:
        check_surrogate_access(
            record_context.record,
            Role.CASE_MANAGER,
            record_context.session.user_id,
            db=db,
            org_id=test_org.id,
        )
    assert exc.value.status_code == 403
    assert not can_modify_surrogate(
        record_context.record,
        record_context.session.user_id,
        Role.CASE_MANAGER,
        db=db,
        org_id=test_org.id,
    )


def test_core_v2_modify_requires_edit_action_and_accepts_additions(db, test_org, record_context):
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role="case_manager",
            permission="edit_surrogates",
            is_granted=False,
        )
    )
    db.flush()
    assert not can_modify_surrogate(
        record_context.record,
        record_context.session.user_id,
        Role.CASE_MANAGER,
        db=db,
        org_id=test_org.id,
    )
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=record_context.session.user_id,
            permission="edit_surrogates",
            override_type="grant",
        )
    )
    db.flush()
    assert can_modify_surrogate(
        record_context.record,
        record_context.session.user_id,
        Role.CASE_MANAGER,
        db=db,
        org_id=test_org.id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    ["interview_create", "interview_note", "profile_override", "profile_hidden", "journey_image"],
)
async def test_v2_readable_record_without_edit_cannot_mutate_capabilities(
    authed_client, db, test_org, record_context, operation
):
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role="case_manager",
            permission="edit_surrogates",
            is_granted=False,
        )
    )
    db.flush()
    record_id = record_context.record.id
    requests = {
        "interview_create": (
            "POST",
            f"/surrogates/{record_id}/interviews",
            {
                "interview_type": "phone",
                "conducted_at": datetime.now(UTC).isoformat(),
                "status": "draft",
            },
        ),
        "interview_note": (
            "POST",
            f"/interviews/{record_context.interview.id}/notes",
            {"content": "Synthetic note"},
        ),
        "profile_override": (
            "PUT",
            f"/surrogates/{record_id}/profile/overrides",
            {"overrides": {"header_note": "Synthetic"}},
        ),
        "profile_hidden": (
            "POST",
            f"/surrogates/{record_id}/profile/hidden",
            {"field_key": "full_name", "hidden": True},
        ),
        "journey_image": (
            "PATCH",
            f"/journey/surrogates/{record_id}/milestones/unknown/featured-image",
            {"attachment_id": None},
        ),
    }
    method, path, data = requests[operation]
    response = await authed_client.request(method, path, json=data)
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["claim", "release", "assign"])
async def test_v2_queue_assignment_requires_record_scope(
    authed_client, db, test_org, record_context, operation
):
    db.query(RoleRecordScope).filter_by(
        organization_id=test_org.id, role="case_manager", module="surrogates"
    ).one().assignment = "none"
    db.flush()
    previous_owner = record_context.record.owner_id
    if operation == "claim":
        record_context.record.owner_type = "queue"
        record_context.record.owner_id = record_context.queue.id
        previous_owner = record_context.queue.id
        db.flush()
    response = await authed_client.post(
        f"/queues/surrogates/{record_context.record.id}/{operation}",
        json={"queue_id": str(record_context.queue.id)},
    )
    assert response.status_code == 403, response.text
    assert record_context.record.owner_id == previous_owner


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["interview_create", "profile_hidden", "journey_image", "queue_assign"]
)
async def test_v2_capability_writes_reject_other_organization(
    authed_client, db, record_context, operation
):
    other = Organization(id=uuid4(), name="Other org", slug=f"other-{uuid4()}")
    db.add(other)
    db.flush()
    pipeline = pipeline_service.get_or_create_default_pipeline(db, other.id)
    stage = min(pipeline.stages, key=lambda item: item.order)
    foreign = Surrogate(
        id=uuid4(),
        organization_id=other.id,
        surrogate_number="S10001",
        full_name="Other record",
        email=f"{uuid4()}@example.test",
        email_hash=uuid4().hex,
        owner_type="user",
        owner_id=record_context.session.user_id,
        stage_id=stage.id,
        status_label=stage.label,
    )
    db.add(foreign)
    db.flush()
    requests = {
        "interview_create": (
            "POST",
            f"/surrogates/{foreign.id}/interviews",
            {
                "interview_type": "phone",
                "conducted_at": datetime.now(UTC).isoformat(),
                "status": "draft",
            },
        ),
        "profile_hidden": (
            "POST",
            f"/surrogates/{foreign.id}/profile/hidden",
            {"field_key": "full_name", "hidden": True},
        ),
        "journey_image": (
            "PATCH",
            f"/journey/surrogates/{foreign.id}/milestones/unknown/featured-image",
            {"attachment_id": None},
        ),
        "queue_assign": (
            "POST",
            f"/queues/surrogates/{foreign.id}/assign",
            {"queue_id": str(record_context.queue.id)},
        ),
    }
    method, path, data = requests[operation]
    response = await authed_client.request(method, path, json=data)
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_v2_operations_readonly_then_explicit_edit_addition(
    authed_client, db, test_org, test_user, record_context
):
    db.query(Membership).filter_by(
        organization_id=test_org.id, user_id=test_user.id
    ).one().role = "operations"
    db.flush()
    path = f"/surrogates/{record_context.record.id}/interviews"
    payload = {
        "interview_type": "phone",
        "conducted_at": datetime.now(UTC).isoformat(),
        "status": "draft",
    }
    assert (await authed_client.get(path)).status_code == 200
    assert (await authed_client.post(path, json=payload)).status_code == 403
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=test_user.id,
            permission="edit_surrogates",
            override_type="grant",
        )
    )
    db.flush()
    assert (await authed_client.post(path, json=payload)).status_code == 201


@pytest.mark.asyncio
async def test_v2_interview_read_needs_module_view_action(
    authed_client, db, test_org, record_context
):
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role="case_manager",
            permission="view_surrogates",
            is_granted=False,
        )
    )
    db.flush()
    response = await authed_client.get(f"/interviews/{record_context.interview.id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_v2_capability_mutations_still_require_csrf(authed_client, record_context):
    from app.core.csrf import CSRF_HEADER

    del authed_client.headers[CSRF_HEADER]
    response = await authed_client.post(
        f"/surrogates/{record_context.record.id}/profile/hidden",
        json={"field_key": "full_name", "hidden": True},
    )
    assert response.status_code == 403
