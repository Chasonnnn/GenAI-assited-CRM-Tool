import uuid
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import OwnerType, Role
from app.db.models import Membership, Surrogate, Task, User
from app.main import app
from app.services import pipeline_service, queue_service, session_service
from app.utils.normalization import normalize_email, normalize_identifier, normalize_search_text


def _create_user(db, org_id: UUID, role: Role, name: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}@test.com",
        display_name=name,
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
            role=role.value,
            is_active=True,
        )
    )
    db.flush()
    return user


def _get_stage(db, org_id: UUID, stage_key: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, stage_key)
    assert stage is not None
    return stage


def _create_surrogate(
    db,
    org_id: UUID,
    *,
    owner_id: UUID,
    stage_key: str,
    name: str,
    paused_from_stage_key: str | None = None,
) -> Surrogate:
    stage = _get_stage(db, org_id, stage_key)
    paused_from_stage = _get_stage(db, org_id, paused_from_stage_key) if paused_from_stage_key else None
    email = normalize_email(f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}@example.com")
    surrogate_number = f"S{uuid.uuid4().int % 90000 + 10000:05d}"
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=surrogate_number,
        stage_id=stage.id,
        paused_from_stage_id=paused_from_stage.id if paused_from_stage else None,
        status_label=stage.label,
        owner_type=OwnerType.USER.value,
        owner_id=owner_id,
        created_by_user_id=owner_id,
        full_name=name,
        full_name_normalized=normalize_search_text(name),
        surrogate_number_normalized=normalize_identifier(surrogate_number),
        email=email,
        email_hash=hash_email(email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _create_queue_surrogate(
    db,
    org_id: UUID,
    *,
    queue_id: UUID,
    stage_key: str,
    name: str,
) -> Surrogate:
    stage = _get_stage(db, org_id, stage_key)
    email = normalize_email(f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}@example.com")
    surrogate_number = f"S{uuid.uuid4().int % 90000 + 10000:05d}"
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=surrogate_number,
        stage_id=stage.id,
        status_label=stage.label,
        owner_type=OwnerType.QUEUE.value,
        owner_id=queue_id,
        created_by_user_id=None,
        full_name=name,
        full_name_normalized=normalize_search_text(name),
        surrogate_number_normalized=normalize_identifier(surrogate_number),
        email=email,
        email_hash=hash_email(email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


@asynccontextmanager
async def _client_for_user(db, org_id: UUID, user: User, role: Role):
    from app.db.models import UserSession

    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    db.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.organization_id == org_id,
    ).delete(synchronize_session=False)
    db.flush()
    session_service.create_session(db=db, user_id=user.id, org_id=org_id, token=token, request=None)

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


@pytest.mark.asyncio
async def test_case_manager_sees_approved_onward_not_early_intake(db, test_org):
    owner = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Intake Owner")
    case_manager = _create_user(db, test_org.id, Role.CASE_MANAGER, "Case Manager")
    under_review = _create_surrogate(
        db,
        test_org.id,
        owner_id=owner.id,
        stage_key="under_review",
        name="Hidden Under Review",
    )
    approved = _create_surrogate(
        db,
        test_org.id,
        owner_id=owner.id,
        stage_key="approved",
        name="Visible Approved",
    )
    ready = _create_surrogate(
        db,
        test_org.id,
        owner_id=owner.id,
        stage_key="ready_to_match",
        name="Visible Ready Match",
    )
    visible_on_hold = _create_surrogate(
        db,
        test_org.id,
        owner_id=owner.id,
        stage_key="on_hold",
        paused_from_stage_key="approved",
        name="Visible Paused Approved",
    )
    hidden_on_hold = _create_surrogate(
        db,
        test_org.id,
        owner_id=owner.id,
        stage_key="on_hold",
        paused_from_stage_key="under_review",
        name="Hidden Paused Under Review",
    )

    async with _client_for_user(db, test_org.id, case_manager, Role.CASE_MANAGER) as client:
        list_response = await client.get("/surrogates", params={"per_page": 100})
        assert list_response.status_code == 200, list_response.text
        ids = {item["id"] for item in list_response.json()["items"]}
        assert str(under_review.id) not in ids
        assert str(hidden_on_hold.id) not in ids
        assert {str(approved.id), str(ready.id), str(visible_on_hold.id)} <= ids

        hidden_detail = await client.get(f"/surrogates/{under_review.id}")
        assert hidden_detail.status_code == 403, hidden_detail.text
        visible_detail = await client.get(f"/surrogates/{approved.id}")
        assert visible_detail.status_code == 200, visible_detail.text

        stats = await client.get("/surrogates/stats")
        assert stats.status_code == 200, stats.text
        assert stats.json()["total"] == 3

        search = await client.get("/search", params={"q": "Hidden Under Review", "types": "case"})
        assert search.status_code == 200, search.text
        assert search.json()["total"] == 0


@pytest.mark.asyncio
async def test_case_manager_can_edit_visible_unclaimed_case_but_not_change_status(db, test_org):
    owner = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Intake Owner")
    case_manager = _create_user(db, test_org.id, Role.CASE_MANAGER, "Case Manager")
    approved = _create_surrogate(
        db,
        test_org.id,
        owner_id=owner.id,
        stage_key="approved",
        name="Editable Approved",
    )
    ready_stage = _get_stage(db, test_org.id, "ready_to_match")

    async with _client_for_user(db, test_org.id, case_manager, Role.CASE_MANAGER) as client:
        update = await client.patch(
            f"/surrogates/{approved.id}",
            json={"full_name": "Case Manager Edited"},
        )
        assert update.status_code == 200, update.text
        assert update.json()["full_name"] == "Case Manager Edited"

        status_change = await client.patch(
            f"/surrogates/{approved.id}/status",
            json={"stage_id": str(ready_stage.id)},
        )
        assert status_change.status_code == 403, status_change.text
        assert "claimed" in status_change.json()["detail"]


@pytest.mark.asyncio
async def test_intake_default_surfaces_show_only_assigned_pool(db, test_org):
    intake = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Assigned Intake")
    other = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Other Intake")
    default_queue = queue_service.get_or_create_default_queue(db, test_org.id)

    assigned = _create_surrogate(
        db,
        test_org.id,
        owner_id=intake.id,
        stage_key="contacted",
        name="Assigned Intake Case",
    )
    other_case = _create_surrogate(
        db,
        test_org.id,
        owner_id=other.id,
        stage_key="contacted",
        name="Other Intake Case",
    )
    unassigned = _create_queue_surrogate(
        db,
        test_org.id,
        queue_id=default_queue.id,
        stage_key="contacted",
        name="Default Queue Case",
    )
    db.add_all(
        [
            Task(
                id=uuid.uuid4(),
                organization_id=test_org.id,
                surrogate_id=assigned.id,
                created_by_user_id=intake.id,
                owner_type=OwnerType.USER.value,
                owner_id=intake.id,
                title="Assigned case task",
                task_type="other",
            ),
            Task(
                id=uuid.uuid4(),
                organization_id=test_org.id,
                surrogate_id=other_case.id,
                created_by_user_id=intake.id,
                owner_type=OwnerType.USER.value,
                owner_id=intake.id,
                title="Other intake case task",
                task_type="other",
            ),
            Task(
                id=uuid.uuid4(),
                organization_id=test_org.id,
                surrogate_id=unassigned.id,
                created_by_user_id=intake.id,
                owner_type=OwnerType.USER.value,
                owner_id=intake.id,
                title="Default queue case task",
                task_type="other",
            ),
        ]
    )
    db.flush()

    async with _client_for_user(db, test_org.id, intake, Role.INTAKE_SPECIALIST) as client:
        list_response = await client.get("/surrogates", params={"per_page": 100})
        assert list_response.status_code == 200, list_response.text
        list_data = list_response.json()
        assert list_data["total"] == 1
        assert {item["id"] for item in list_data["items"]} == {str(assigned.id)}

        accessible_owners = await client.get("/surrogates/accessible-owners")
        assert accessible_owners.status_code == 200, accessible_owners.text
        assert accessible_owners.json() == []

        stats = await client.get("/surrogates/stats")
        assert stats.status_code == 200, stats.text
        assert stats.json()["total"] == 1

        by_status = await client.get("/analytics/surrogates/by-status")
        assert by_status.status_code == 200, by_status.text
        assert sum(item["count"] for item in by_status.json()) == 1

        trend = await client.get("/analytics/surrogates/trend")
        assert trend.status_code == 200, trend.text
        assert sum(item["count"] for item in trend.json()) == 1

        analytics_summary = await client.get("/analytics/summary")
        assert analytics_summary.status_code == 403, analytics_summary.text

        search = await client.get("/search", params={"q": "Default Queue", "types": "case"})
        assert search.status_code == 200, search.text
        assert search.json()["total"] == 0

        other_search = await client.get("/search", params={"q": "Other Intake", "types": "case"})
        assert other_search.status_code == 200, other_search.text
        assert other_search.json()["total"] == 0

        tasks = await client.get("/tasks", params={"per_page": 100})
        assert tasks.status_code == 200, tasks.text
        task_data = tasks.json()
        assert task_data["total"] == 1
        assert [item["title"] for item in task_data["items"]] == ["Assigned case task"]

        assert other_case.id != assigned.id
        assert unassigned.id != assigned.id


@pytest.mark.asyncio
async def test_stale_intake_pool_grant_does_not_expand_intake_visibility(db, test_org):
    admin = _create_user(db, test_org.id, Role.ADMIN, "Admin User")
    grantee = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Grantee Intake")
    source = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Source Intake")
    other = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Other Intake")
    own_case = _create_surrogate(
        db,
        test_org.id,
        owner_id=grantee.id,
        stage_key="contacted",
        name="Grantee Own Case",
    )
    source_case = _create_surrogate(
        db,
        test_org.id,
        owner_id=source.id,
        stage_key="contacted",
        name="Shared Source Case",
    )
    other_case = _create_surrogate(
        db,
        test_org.id,
        owner_id=other.id,
        stage_key="contacted",
        name="Other Intake Case",
    )

    async with _client_for_user(db, test_org.id, grantee, Role.INTAKE_SPECIALIST) as client:
        before = await client.get("/surrogates", params={"per_page": 100})
        assert before.status_code == 200, before.text
        assert str(source_case.id) not in {item["id"] for item in before.json()["items"]}

        forbidden_detail = await client.get(f"/surrogates/{source_case.id}")
        assert forbidden_detail.status_code == 403, forbidden_detail.text

    async with _client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        grant = await client.post(
            "/settings/permissions/intake-pool-grants",
            json={"source_user_id": str(source.id), "grantee_user_id": str(grantee.id)},
        )
        assert grant.status_code == 201, grant.text
        grant_id = grant.json()["id"]

    future_case = _create_surrogate(
        db,
        test_org.id,
        owner_id=source.id,
        stage_key="contacted",
        name="Future Shared Source Case",
    )

    async with _client_for_user(db, test_org.id, grantee, Role.INTAKE_SPECIALIST) as client:
        accessible_owners = await client.get("/surrogates/accessible-owners")
        assert accessible_owners.status_code == 200, accessible_owners.text
        assert accessible_owners.json() == []

        after = await client.get("/surrogates", params={"per_page": 100})
        assert after.status_code == 200, after.text
        ids = {item["id"] for item in after.json()["items"]}
        assert ids == {str(own_case.id)}
        assert str(source_case.id) not in ids
        assert str(future_case.id) not in ids
        assert str(other_case.id) not in ids

        filtered = await client.get("/surrogates", params={"owner_id": str(source.id)})
        assert filtered.status_code == 403, filtered.text

        blocked_filter = await client.get("/surrogates", params={"owner_id": str(other.id)})
        assert blocked_filter.status_code == 403, blocked_filter.text

        detail = await client.get(f"/surrogates/{source_case.id}")
        assert detail.status_code == 403, detail.text

        edit = await client.patch(
            f"/surrogates/{source_case.id}",
            json={"full_name": "Edited Shared Source Case"},
        )
        assert edit.status_code == 403, edit.text

        search = await client.get("/search", params={"q": "Future Shared Source", "types": "case"})
        assert search.status_code == 200, search.text
        assert search.json()["total"] == 0

    async with _client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        revoke = await client.delete(f"/settings/permissions/intake-pool-grants/{grant_id}")
        assert revoke.status_code == 200, revoke.text

    async with _client_for_user(db, test_org.id, grantee, Role.INTAKE_SPECIALIST) as client:
        after_revoke = await client.get("/surrogates", params={"per_page": 100})
        assert after_revoke.status_code == 200, after_revoke.text
        assert {item["id"] for item in after_revoke.json()["items"]} == {str(own_case.id)}
        assert str(source_case.id) not in {item["id"] for item in after_revoke.json()["items"]}


@pytest.mark.asyncio
async def test_intake_pool_grant_management_requires_admin_and_valid_intake_users(db, test_org):
    admin = _create_user(db, test_org.id, Role.ADMIN, "Admin User")
    case_manager = _create_user(db, test_org.id, Role.CASE_MANAGER, "Case Manager")
    source = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Source Intake")
    grantee = _create_user(db, test_org.id, Role.INTAKE_SPECIALIST, "Grantee Intake")

    async with _client_for_user(db, test_org.id, case_manager, Role.CASE_MANAGER) as client:
        denied = await client.post(
            "/settings/permissions/intake-pool-grants",
            json={"source_user_id": str(source.id), "grantee_user_id": str(grantee.id)},
        )
        assert denied.status_code == 403, denied.text

    async with _client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        self_grant = await client.post(
            "/settings/permissions/intake-pool-grants",
            json={"source_user_id": str(source.id), "grantee_user_id": str(source.id)},
        )
        assert self_grant.status_code == 400, self_grant.text

        non_intake = await client.post(
            "/settings/permissions/intake-pool-grants",
            json={"source_user_id": str(case_manager.id), "grantee_user_id": str(grantee.id)},
        )
        assert non_intake.status_code == 400, non_intake.text
