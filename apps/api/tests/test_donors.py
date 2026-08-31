import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import (
    Donor,
    DonorStatusHistory,
    Membership,
    Notification,
    Organization,
    Pipeline,
    PipelineStage,
    StatusChangeRequest,
    User,
    UserPermissionOverride,
)
from app.main import app
from app.services import session_service


def _seed_donor_pipeline(db, org_id: UUID, donor_type: str) -> tuple[PipelineStage, PipelineStage]:
    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=org_id,
        entity_type=f"{donor_type}_donor",
        name=f"{donor_type.title()} Donors",
        is_default=True,
        current_version=1,
        feature_config={},
    )
    db.add(pipeline)
    db.flush()

    new_stage = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=pipeline.id,
        stage_key="new",
        slug="new",
        label="New",
        color="#3B82F6",
        stage_type="intake",
        order=1,
        is_active=True,
        is_intake_stage=True,
    )
    ready_stage = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=pipeline.id,
        stage_key="ready_to_match",
        slug="ready-to-match",
        label="Ready to Match",
        color="#F59E0B",
        stage_type="post_approval",
        order=2,
        is_active=True,
        is_intake_stage=False,
    )
    db.add_all([new_stage, ready_stage])
    db.flush()
    return new_stage, ready_stage


@asynccontextmanager
async def _client_for_org(
    db,
    org: Organization,
    *,
    role: Role = Role.DEVELOPER,
    revokes: tuple[str, ...] = (),
):
    user = User(
        id=uuid.uuid4(),
        email=f"donor-user-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Donor Test User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=org.id,
            role=role.value,
            is_active=True,
        )
    )
    db.add_all(
        [
            UserPermissionOverride(
                id=uuid.uuid4(),
                organization_id=org.id,
                user_id=user.id,
                permission=permission,
                override_type="revoke",
            )
            for permission in revokes
        ]
    )
    db.flush()

    token = create_session_token(
        user_id=user.id,
        org_id=org.id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=user.id, org_id=org.id, token=token, request=None)

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


async def _create_donor(client: AsyncClient, *, donor_type: str = "egg") -> dict:
    response = await client.post(
        "/donors",
        json={
            "donor_type": donor_type,
            "full_name": f"{donor_type.title()} Donor",
            "email": f"{donor_type}-{uuid.uuid4().hex[:8]}@example.com",
            "phone": "+1 (607) 555-0101",
            "state": "ny",
            "education": "Bachelor's degree",
            "source": "Meta",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_pending_donor_regression(
    db,
    org: Organization,
    client: AsyncClient,
    requester_user_id: UUID,
    *,
    donor_type: str = "egg",
) -> tuple[Donor, PipelineStage, PipelineStage, StatusChangeRequest]:
    new_stage, ready_stage = _seed_donor_pipeline(db, org.id, donor_type)
    created = await _create_donor(client, donor_type=donor_type)
    donor = db.query(Donor).filter(Donor.id == UUID(created["id"])).one()
    donor.stage_id = ready_stage.id
    donor.stage = ready_stage
    now = datetime.now(UTC)
    status_request = StatusChangeRequest(
        organization_id=org.id,
        entity_type="donor",
        entity_id=donor.id,
        target_stage_id=new_stage.id,
        effective_at=now,
        reason="Correcting donor screening stage",
        requested_by_user_id=requester_user_id,
        requested_at=now,
        status="pending",
    )
    db.add(status_request)
    db.commit()
    db.refresh(status_request)
    return donor, new_stage, ready_stage, status_request


@pytest.mark.asyncio
async def test_create_bootstraps_exact_subtype_pipeline_and_uses_protected_entry_stage(
    db, test_org, authed_client
):
    created = await _create_donor(authed_client, donor_type="sperm")

    pipeline = (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == test_org.id,
            Pipeline.entity_type == "sperm_donor",
            Pipeline.is_default.is_(True),
        )
        .one()
    )
    entry_stage = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == pipeline.id,
            PipelineStage.stage_key == "new",
        )
        .one()
    )
    assert created["stage_id"] == str(entry_stage.id)
    assert created["status"] == "new"
    assert (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == test_org.id,
            Pipeline.entity_type == "egg_donor",
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_create_list_and_get_donor_use_subtype_pipeline_and_d_number(
    db, test_org, authed_client
):
    egg_new, _ = _seed_donor_pipeline(db, test_org.id, "egg")
    _seed_donor_pipeline(db, test_org.id, "sperm")

    created = await _create_donor(authed_client)

    assert created["donor_number"] == "D10001"
    assert created["donor_type"] == "egg"
    assert created["stage_id"] == str(egg_new.id)
    assert created["status"] == "new"
    assert created["stage_key"] == "new"
    assert created["status_label"] == "New"
    assert created["phone"] == "+16075550101"
    assert created["state"] == "NY"

    second = await _create_donor(authed_client, donor_type="sperm")
    assert second["donor_number"] == "D10002"

    listed = await authed_client.get("/donors", params={"donor_type": "egg"})
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == created["id"]

    detail = await authed_client.get(f"/donors/{created['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json() == created

    duplicate = await authed_client.post(
        "/donors",
        json={
            "donor_type": "egg",
            "full_name": "Duplicate Donor",
            "email": created["email"].upper(),
        },
    )
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_update_preserves_donor_type_and_archive_hides_record_by_default(
    db, test_org, authed_client
):
    _seed_donor_pipeline(db, test_org.id, "egg")
    _seed_donor_pipeline(db, test_org.id, "sperm")
    created = await _create_donor(authed_client)

    update = await authed_client.patch(
        f"/donors/{created['id']}",
        json={"education": "Master's degree", "donor_type": "sperm"},
    )
    assert update.status_code == 422

    update = await authed_client.patch(
        f"/donors/{created['id']}",
        json={"education": "Master's degree", "full_name": "Updated Donor"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["education"] == "Master's degree"
    assert update.json()["donor_type"] == "egg"

    archived = await authed_client.post(f"/donors/{created['id']}/archive")
    assert archived.status_code == 200, archived.text
    assert archived.json()["is_archived"] is True
    assert archived.json()["archived_at"] is not None

    active_list = await authed_client.get("/donors")
    assert active_list.status_code == 200
    assert active_list.json()["total"] == 0

    archived_list = await authed_client.get("/donors", params={"include_archived": "true"})
    assert archived_list.status_code == 200
    assert archived_list.json()["total"] == 1
    archived_only = await authed_client.get("/donors", params={"archived_only": "true"})
    assert archived_only.status_code == 200
    assert archived_only.json()["total"] == 1
    assert archived_only.json()["items"][0]["is_archived"] is True

    restored = await authed_client.post(f"/donors/{created['id']}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["is_archived"] is False
    assert restored.json()["archived_at"] is None
    assert (await authed_client.get("/donors")).json()["total"] == 1


@pytest.mark.asyncio
async def test_restore_rejects_duplicate_active_email(db, test_org, authed_client):
    _seed_donor_pipeline(db, test_org.id, "egg")
    archived = await _create_donor(authed_client)
    assert (await authed_client.post(f"/donors/{archived['id']}/archive")).status_code == 200

    replacement = await authed_client.post(
        "/donors",
        json={
            "donor_type": "sperm",
            "full_name": "Replacement donor",
            "email": archived["email"],
        },
    )
    assert replacement.status_code == 201, replacement.text

    restore = await authed_client.post(f"/donors/{archived['id']}/restore")
    assert restore.status_code == 409
    assert "active donor" in restore.json()["detail"].lower()


@pytest.mark.asyncio
async def test_status_change_requires_stage_from_matching_donor_pipeline(
    db, test_org, authed_client
):
    _, egg_ready = _seed_donor_pipeline(db, test_org.id, "egg")
    _, sperm_ready = _seed_donor_pipeline(db, test_org.id, "sperm")
    other_org = Organization(
        id=uuid.uuid4(),
        name="Foreign Stage Organization",
        slug=f"foreign-stage-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    _, foreign_egg_ready = _seed_donor_pipeline(db, other_org.id, "egg")
    created = await _create_donor(authed_client)

    wrong_pipeline = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={"stage_id": str(sperm_ready.id), "reason": "Wrong subtype"},
    )
    assert wrong_pipeline.status_code == 400

    foreign_pipeline = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={"stage_id": str(foreign_egg_ready.id), "reason": "Wrong organization"},
    )
    assert foreign_pipeline.status_code == 400

    changed = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={"stage_id": str(egg_ready.id), "reason": "Screening complete"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["donor"]["status"] == "ready_to_match"
    assert changed.json()["history"]["old_status"] == "new"
    assert changed.json()["history"]["new_status"] == "ready_to_match"

    history = await authed_client.get(f"/donors/{created['id']}/history")
    assert history.status_code == 200, history.text
    assert [item["new_status"] for item in history.json()] == ["ready_to_match", "new"]


@pytest.mark.asyncio
async def test_status_change_applies_backdated_effective_at_with_reason(
    db, test_org, authed_client
):
    _new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    created = await _create_donor(authed_client)
    donor = db.query(Donor).filter_by(id=UUID(created["id"])).one()
    donor.created_at = datetime.now(UTC) - timedelta(days=7)
    db.commit()
    effective_at = datetime.now(UTC) - timedelta(days=1)

    changed = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={
            "stage_id": str(ready_stage.id),
            "reason": "Screening completed yesterday",
            "effective_at": effective_at.isoformat(),
        },
    )

    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "applied"
    assert changed.json()["donor"]["stage_id"] == str(ready_stage.id)
    history = await authed_client.get(f"/donors/{created['id']}/history")
    assert datetime.fromisoformat(history.json()[0]["effective_at"]) == effective_at


@pytest.mark.asyncio
async def test_status_change_rejects_future_precreation_and_unreasoned_backdate(
    db,
    test_org,
    authed_client,
):
    new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    created = await _create_donor(authed_client)
    donor = db.get(Donor, UUID(created["id"]))
    donor.created_at = datetime.now(UTC) - timedelta(days=7)
    db.commit()

    future = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={
            "stage_id": str(ready_stage.id),
            "effective_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    precreation = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={
            "stage_id": str(ready_stage.id),
            "effective_at": (donor.created_at - timedelta(seconds=1)).isoformat(),
            "reason": "Invalid historical correction",
        },
    )
    unreasoned_backdate = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={
            "stage_id": str(ready_stage.id),
            "effective_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        },
    )

    assert future.status_code == 400
    assert future.json()["detail"] == "Cannot set future date for donor stage change"
    assert precreation.status_code == 400
    assert precreation.json()["detail"] == "Cannot set date before donor was created"
    assert unreasoned_backdate.status_code == 400
    assert unreasoned_backdate.json()["detail"] == (
        "Reason required for backdated or regressed stage changes"
    )
    db.expire_all()
    assert db.get(Donor, UUID(created["id"])).stage_id == new_stage.id


@pytest.mark.asyncio
async def test_recent_donor_stage_change_can_be_undone_without_approval(
    db,
    test_org,
    authed_client,
):
    new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "sperm")
    created = await _create_donor(authed_client, donor_type="sperm")
    forward = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={"stage_id": str(ready_stage.id)},
    )
    undo = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={"stage_id": str(new_stage.id)},
    )

    assert forward.status_code == 200, forward.text
    assert undo.status_code == 200, undo.text
    assert undo.json()["status"] == "applied"
    assert undo.json()["request_id"] is None
    assert undo.json()["donor"]["stage_id"] == str(new_stage.id)
    assert undo.json()["history"]["is_undo"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("donor_type", ["egg", "sperm"])
async def test_non_admin_donor_regression_can_be_reviewed_and_approved(db, test_org, donor_type):
    new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, donor_type)
    new_stage.pipeline.feature_config = {
        "role_visibility": {
            Role.CASE_MANAGER.value: {
                "stage_types": ["intake", "post_approval"],
                "stage_keys": [],
                "capabilities": [],
            }
        },
        "role_mutation": {
            Role.CASE_MANAGER.value: {
                "stage_types": ["intake", "post_approval"],
                "stage_keys": [],
                "capabilities": [],
            }
        },
    }
    db.commit()

    original_user_ids = {row[0] for row in db.query(User.id).all()}
    async with _client_for_org(db, test_org, role=Role.CASE_MANAGER) as case_manager_client:
        requester_user = db.query(User).filter(User.id.notin_(original_user_ids)).one()
        created = await _create_donor(case_manager_client, donor_type=donor_type)
        forward = await case_manager_client.patch(
            f"/donors/{created['id']}/status",
            json={"stage_id": str(ready_stage.id)},
        )
        assert forward.status_code == 200, forward.text

        latest_history = (
            db.query(DonorStatusHistory)
            .filter(DonorStatusHistory.donor_id == UUID(created["id"]))
            .order_by(DonorStatusHistory.recorded_at.desc())
            .first()
        )
        assert latest_history is not None
        latest_history.recorded_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()

        regression = await case_manager_client.patch(
            f"/donors/{created['id']}/status",
            json={"stage_id": str(new_stage.id), "reason": "Correcting screening stage"},
        )

    assert regression.status_code == 200, regression.text
    assert regression.json()["status"] == "pending_approval"
    request_id = regression.json()["request_id"]
    db.refresh(db.query(Donor).filter_by(id=UUID(created["id"])).one())
    assert db.query(Donor).filter_by(id=UUID(created["id"])).one().stage_id == ready_stage.id

    existing_user_ids = {row[0] for row in db.query(User.id).all()}
    async with _client_for_org(db, test_org, role=Role.DEVELOPER) as admin_client:
        admin_user = db.query(User).filter(User.id.notin_(existing_user_ids)).one()
        details = await admin_client.get(f"/status-change-requests/{request_id}")
        assert details.status_code == 200, details.text
        assert details.json()["entity_name"] == f"{donor_type.title()} Donor"
        assert details.json()["entity_number"] == created["donor_number"]
        assert details.json()["target_stage_label"] == "New"
        assert details.json()["current_stage_label"] == "Ready to Match"

        approved = await admin_client.post(f"/status-change-requests/{request_id}/approve")
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"
        history_response = await admin_client.get(f"/donors/{created['id']}/history")
        assert history_response.status_code == 200, history_response.text
        approved_item = next(
            item for item in history_response.json() if item["request_id"] == request_id
        )
        assert approved_item["changed_by_user_id"] == str(requester_user.id)
        assert approved_item["changed_by_name"] == requester_user.display_name
        assert approved_item["approved_by_user_id"] == str(admin_user.id)
        assert approved_item["approved_by_name"] == admin_user.display_name
        assert approved_item["requested_at"] is not None
        assert approved_item["approved_at"] is not None
        assert approved_item["is_undo"] is False

    changed_donor = db.query(Donor).filter_by(id=UUID(created["id"])).one()
    db.refresh(changed_donor)
    assert changed_donor.stage_id == new_stage.id
    approved_history = (
        db.query(DonorStatusHistory).filter(DonorStatusHistory.request_id == UUID(request_id)).one()
    )
    assert approved_history.requested_at is not None
    assert approved_history.approved_by_user_id == admin_user.id
    assert approved_history.approved_at is not None


@pytest.mark.asyncio
async def test_archived_donor_pending_regression_cannot_be_approved(
    db,
    test_org,
    test_user,
    authed_client,
):
    donor, _new_stage, ready_stage, status_request = await _create_pending_donor_regression(
        db,
        test_org,
        authed_client,
        test_user.id,
    )
    donor.is_archived = True
    donor.archived_at = datetime.now(UTC)
    db.commit()

    response = await authed_client.post(f"/status-change-requests/{status_request.id}/approve")

    assert response.status_code == 400
    assert response.json()["detail"] == ("Cannot approve a stage change for an archived donor")
    db.expire_all()
    assert db.get(StatusChangeRequest, status_request.id).status == "pending"
    assert db.get(Donor, donor.id).stage_id == ready_stage.id
    assert (
        db.query(DonorStatusHistory)
        .filter(DonorStatusHistory.request_id == status_request.id)
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_rejected_donor_regression_notifies_authorized_requester(
    db,
    test_org,
    test_user,
    authed_client,
):
    donor, _new_stage, ready_stage, status_request = await _create_pending_donor_regression(
        db,
        test_org,
        authed_client,
        test_user.id,
    )

    rejected = await authed_client.post(
        f"/status-change-requests/{status_request.id}/reject",
        json={"reason": "Keep the donor in screening"},
    )

    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    db.expire_all()
    assert db.get(Donor, donor.id).stage_id == ready_stage.id
    notification = (
        db.query(Notification)
        .filter(
            Notification.user_id == test_user.id,
            Notification.type == "status_change_rejected",
            Notification.entity_type == "donor",
            Notification.entity_id == donor.id,
        )
        .one()
    )
    assert "Keep the donor in screening" in notification.body


@pytest.mark.asyncio
async def test_foreign_org_cannot_view_or_resolve_donor_regression(
    db,
    test_org,
    test_user,
    authed_client,
):
    donor, _new_stage, ready_stage, status_request = await _create_pending_donor_regression(
        db,
        test_org,
        authed_client,
        test_user.id,
    )
    other_org = Organization(
        id=uuid.uuid4(),
        name="Foreign Donor Request Organization",
        slug=f"foreign-donor-request-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.commit()

    async with _client_for_org(db, other_org) as foreign_client:
        detail = await foreign_client.get(f"/status-change-requests/{status_request.id}")
        approve = await foreign_client.post(f"/status-change-requests/{status_request.id}/approve")
        reject = await foreign_client.post(f"/status-change-requests/{status_request.id}/reject")

    assert detail.status_code == 404
    assert approve.status_code == 404
    assert reject.status_code == 404
    db.expire_all()
    assert db.get(StatusChangeRequest, status_request.id).status == "pending"
    assert db.get(Donor, donor.id).stage_id == ready_stage.id
    assert (
        db.query(DonorStatusHistory)
        .filter(DonorStatusHistory.request_id == status_request.id)
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_donor_regression_approval_retry_applies_once(
    db,
    test_org,
    test_user,
    authed_client,
    monkeypatch,
    caplog,
):
    donor, new_stage, _ready_stage, status_request = await _create_pending_donor_regression(
        db,
        test_org,
        authed_client,
        test_user.id,
    )
    from app.services import donor_service, notification_facade

    workflow_calls: list[UUID] = []
    monkeypatch.setattr(
        donor_service,
        "dispatch_stage_changed_workflow",
        lambda _db, *, donor, old_stage, new_stage: workflow_calls.append(donor.id),
    )

    def fail_resolved_notification(*args, **kwargs):
        raise RuntimeError("sensitive donor notification failure")

    monkeypatch.setattr(
        notification_facade,
        "notify_donor_status_change_request_resolved",
        fail_resolved_notification,
    )

    first = await authed_client.post(f"/status-change-requests/{status_request.id}/approve")
    retry = await authed_client.post(f"/status-change-requests/{status_request.id}/approve")

    assert first.status_code == 200, first.text
    assert retry.status_code == 400
    assert "not pending" in retry.json()["detail"]
    db.expire_all()
    assert db.get(Donor, donor.id).stage_id == new_stage.id
    assert (
        db.query(DonorStatusHistory)
        .filter(DonorStatusHistory.request_id == status_request.id)
        .count()
        == 1
    )
    assert workflow_calls == [donor.id]
    assert "sensitive donor notification failure" not in caplog.text


@pytest.mark.asyncio
async def test_second_pending_request_for_satisfied_donor_stage_is_rejected(
    db,
    test_org,
    test_user,
    authed_client,
):
    donor, new_stage, _ready_stage, first_request = await _create_pending_donor_regression(
        db,
        test_org,
        authed_client,
        test_user.id,
    )
    second_request = StatusChangeRequest(
        organization_id=test_org.id,
        entity_type="donor",
        entity_id=donor.id,
        target_stage_id=new_stage.id,
        effective_at=first_request.effective_at - timedelta(seconds=1),
        reason="Duplicate target with a different effective time",
        requested_by_user_id=test_user.id,
        requested_at=first_request.requested_at + timedelta(seconds=1),
        status="pending",
    )
    db.add(second_request)
    db.commit()

    first = await authed_client.post(f"/status-change-requests/{first_request.id}/approve")
    second = await authed_client.post(f"/status-change-requests/{second_request.id}/approve")

    assert first.status_code == 200, first.text
    assert second.status_code == 400
    assert second.json()["detail"] == "Donor is already in the requested target stage"
    db.expire_all()
    assert db.get(StatusChangeRequest, second_request.id).status == "pending"
    assert (
        db.query(DonorStatusHistory)
        .filter(DonorStatusHistory.request_id.in_([first_request.id, second_request.id]))
        .count()
        == 1
    )


def test_donor_regression_approval_rolls_back_all_writes_when_commit_fails(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from sqlalchemy.orm import Session

    from app.services import donor_service, status_change_request_service

    new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    donor = Donor(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        donor_number="D10001",
        donor_type="egg",
        full_name="Rollback Donor",
        email="rollback-donor@example.com",
        email_hash="rollback-donor-hash",
        stage_id=ready_stage.id,
    )
    now = datetime.now(UTC)
    status_request = StatusChangeRequest(
        organization_id=test_org.id,
        entity_type="donor",
        entity_id=donor.id,
        target_stage_id=new_stage.id,
        effective_at=now,
        reason="Rollback approval",
        requested_by_user_id=test_user.id,
        requested_at=now,
        status="pending",
    )
    db.add_all([donor, status_request])
    db.commit()
    db.refresh(status_request)
    donor_id = donor.id
    request_id = status_request.id
    ready_stage_id = ready_stage.id

    approval_db = Session(
        bind=db.get_bind(),
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    workflow_calls: list[UUID] = []
    notification_calls: list[UUID] = []
    monkeypatch.setattr(
        donor_service,
        "dispatch_stage_changed_workflow",
        lambda _db, *, donor, old_stage, new_stage: workflow_calls.append(donor.id),
    )
    monkeypatch.setattr(
        donor_service,
        "dispatch_status_request_resolved_notification",
        lambda _db, *, donor, status_request, approved, resolver_name, reason=None: (
            notification_calls.append(status_request.id)
        ),
    )
    original_commit = approval_db.commit

    def fail_commit():
        raise RuntimeError("forced approval commit failure")

    monkeypatch.setattr(approval_db, "commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="forced approval commit failure"):
            status_change_request_service.approve_request(
                approval_db,
                request_id,
                test_org.id,
                test_user.id,
                Role.DEVELOPER,
            )
    finally:
        monkeypatch.setattr(approval_db, "commit", original_commit)
        approval_db.close()

    db.expire_all()
    assert db.get(Donor, donor_id).stage_id == ready_stage_id
    assert db.get(StatusChangeRequest, request_id).status == "pending"
    assert (
        db.query(DonorStatusHistory).filter(DonorStatusHistory.request_id == request_id).count()
        == 0
    )
    assert workflow_calls == []
    assert notification_calls == []


@pytest.mark.asyncio
async def test_status_request_visibility_filters_donors_before_pagination(
    db,
    test_org,
    test_user,
    authed_client,
):
    _donor, new_stage, _ready_stage, donor_request = await _create_pending_donor_regression(
        db,
        test_org,
        authed_client,
        test_user.id,
    )
    surrogate_request = StatusChangeRequest(
        organization_id=test_org.id,
        entity_type="surrogate",
        entity_id=uuid.uuid4(),
        target_stage_id=new_stage.id,
        effective_at=datetime.now(UTC) - timedelta(days=1),
        reason="Older surrogate request",
        requested_by_user_id=test_user.id,
        requested_at=donor_request.requested_at - timedelta(minutes=1),
        status="pending",
    )
    db.add(surrogate_request)
    db.commit()

    async with _client_for_org(
        db,
        test_org,
        role=Role.ADMIN,
        revokes=("view_donors",),
    ) as admin_client:
        listed = await admin_client.get("/status-change-requests?per_page=1")
        donor_only = await admin_client.get("/status-change-requests?entity_type=donor&per_page=1")
        detail = await admin_client.get(f"/status-change-requests/{donor_request.id}")
        approve = await admin_client.post(f"/status-change-requests/{donor_request.id}/approve")
        reject = await admin_client.post(f"/status-change-requests/{donor_request.id}/reject")
        surrogate_detail = await admin_client.get(f"/status-change-requests/{surrogate_request.id}")

    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["pages"] == 1
    assert listed.json()["items"][0]["request"]["id"] == str(surrogate_request.id)
    assert donor_only.status_code == 200
    assert donor_only.json()["items"] == []
    assert donor_only.json()["total"] == 0
    assert detail.status_code == 404
    assert approve.status_code == 404
    assert reject.status_code == 404
    assert surrogate_detail.status_code == 200
    db.expire_all()
    assert db.get(StatusChangeRequest, donor_request.id).status == "pending"


@pytest.mark.asyncio
async def test_donor_only_requester_can_cancel_donor_but_not_surrogate_request(
    db,
    test_org,
):
    new_stage, _ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    existing_users = {row[0] for row in db.query(User.id).all()}
    async with _client_for_org(
        db,
        test_org,
        role=Role.CASE_MANAGER,
        revokes=("view_surrogates", "change_surrogate_status"),
    ) as donor_client:
        requester = db.query(User).filter(User.id.notin_(existing_users)).one()
        created = await _create_donor(donor_client)
        donor_request = StatusChangeRequest(
            organization_id=test_org.id,
            entity_type="donor",
            entity_id=UUID(created["id"]),
            target_stage_id=new_stage.id,
            effective_at=datetime.now(UTC),
            reason="Cancel donor request",
            requested_by_user_id=requester.id,
            status="pending",
        )
        surrogate_request = StatusChangeRequest(
            organization_id=test_org.id,
            entity_type="surrogate",
            entity_id=uuid.uuid4(),
            target_stage_id=new_stage.id,
            effective_at=datetime.now(UTC),
            reason="Cannot cancel surrogate request",
            requested_by_user_id=requester.id,
            status="pending",
        )
        db.add_all([donor_request, surrogate_request])
        db.commit()
        donor_cancel = await donor_client.post(f"/status-change-requests/{donor_request.id}/cancel")
        surrogate_cancel = await donor_client.post(
            f"/status-change-requests/{surrogate_request.id}/cancel"
        )

    assert donor_cancel.status_code == 200, donor_cancel.text
    assert donor_cancel.json()["status"] == "cancelled"
    assert donor_cancel.json()["cancelled_by_user_id"] == str(requester.id)
    assert surrogate_cancel.status_code == 403
    db.expire_all()
    assert db.get(StatusChangeRequest, surrogate_request.id).status == "pending"


@pytest.mark.asyncio
async def test_donor_status_request_notifications_require_effective_donor_view(
    db,
    test_org,
    test_user,
    authed_client,
):
    donor, new_stage, ready_stage, status_request = await _create_pending_donor_regression(
        db,
        test_org,
        authed_client,
        test_user.id,
    )

    def add_admin(*, revoke_donor_view: bool) -> User:
        user = User(
            id=uuid.uuid4(),
            email=f"donor-notification-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Donor Notification Admin",
            token_version=1,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(
            Membership(
                id=uuid.uuid4(),
                user_id=user.id,
                organization_id=test_org.id,
                role=Role.ADMIN.value,
                is_active=True,
            )
        )
        if revoke_donor_view:
            db.add(
                UserPermissionOverride(
                    id=uuid.uuid4(),
                    organization_id=test_org.id,
                    user_id=user.id,
                    permission="view_donors",
                    override_type="revoke",
                )
            )
        db.flush()
        return user

    eligible_admin = add_admin(revoke_donor_view=False)
    revoked_admin = add_admin(revoke_donor_view=True)
    db.commit()

    from app.services import notification_service

    notification_service.notify_donor_status_change_request_pending(
        db,
        status_request,
        donor,
        target_stage_label=new_stage.label,
        current_stage_label=ready_stage.label,
        requester_name=test_user.display_name,
    )

    eligible_pending = (
        db.query(Notification)
        .filter(
            Notification.user_id == eligible_admin.id,
            Notification.type == "status_change_requested",
            Notification.entity_type == "donor",
            Notification.entity_id == donor.id,
        )
        .one()
    )
    assert str(donor.donor_number) in eligible_pending.title
    assert (
        db.query(Notification)
        .filter(
            Notification.user_id == revoked_admin.id,
            Notification.entity_type == "donor",
        )
        .count()
        == 0
    )

    status_request.requested_by_user_id = revoked_admin.id
    db.commit()
    notification_service.notify_donor_status_change_request_resolved(
        db,
        status_request,
        donor,
        approved=True,
        resolver_name="Approver",
    )
    assert (
        db.query(Notification)
        .filter(
            Notification.user_id == revoked_admin.id,
            Notification.type == "status_change_approved",
        )
        .count()
        == 0
    )

    status_request.requested_by_user_id = eligible_admin.id
    db.commit()
    notification_service.notify_donor_status_change_request_resolved(
        db,
        status_request,
        donor,
        approved=True,
        resolver_name="Approver",
    )
    assert (
        db.query(Notification)
        .filter(
            Notification.user_id == eligible_admin.id,
            Notification.type == "status_change_approved",
            Notification.entity_type == "donor",
            Notification.entity_id == donor.id,
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_pending_donor_request_survives_sanitized_notification_failure(
    db,
    test_org,
    monkeypatch,
    caplog,
):
    new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    new_stage.pipeline.feature_config = {
        "role_visibility": {
            Role.CASE_MANAGER.value: {
                "stage_types": ["intake", "post_approval"],
                "stage_keys": [],
                "capabilities": [],
            }
        },
        "role_mutation": {
            Role.CASE_MANAGER.value: {
                "stage_types": ["intake", "post_approval"],
                "stage_keys": [],
                "capabilities": [],
            }
        },
    }
    db.commit()

    from app.services import notification_facade

    def fail_pending_notification(*args, **kwargs):
        raise RuntimeError("sensitive donor pending notification failure")

    monkeypatch.setattr(
        notification_facade,
        "notify_donor_status_change_request_pending",
        fail_pending_notification,
    )

    async with _client_for_org(db, test_org, role=Role.CASE_MANAGER) as client:
        created = await _create_donor(client)
        forward = await client.patch(
            f"/donors/{created['id']}/status",
            json={"stage_id": str(ready_stage.id)},
        )
        assert forward.status_code == 200, forward.text
        latest_history = (
            db.query(DonorStatusHistory)
            .filter(DonorStatusHistory.donor_id == UUID(created["id"]))
            .order_by(DonorStatusHistory.recorded_at.desc())
            .first()
        )
        latest_history.recorded_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()
        regression = await client.patch(
            f"/donors/{created['id']}/status",
            json={
                "stage_id": str(new_stage.id),
                "reason": "Correcting donor screening stage",
            },
        )

    assert regression.status_code == 200, regression.text
    assert regression.json()["status"] == "pending_approval"
    assert db.get(Donor, UUID(created["id"])).stage_id == ready_stage.id
    assert db.get(StatusChangeRequest, UUID(regression.json()["request_id"])).status == "pending"
    assert "sensitive donor pending notification failure" not in caplog.text


@pytest.mark.asyncio
async def test_status_change_enforces_donor_pipeline_role_mutation_rules(db, test_org):
    new_stage, ready_stage = _seed_donor_pipeline(db, test_org.id, "egg")
    contacted_stage = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=new_stage.pipeline_id,
        stage_key="contacted",
        slug="contacted",
        label="Contacted",
        color="#06B6D4",
        stage_type="intake",
        order=2,
        is_active=True,
        is_intake_stage=True,
    )
    ready_stage.order = 3
    new_stage.pipeline.feature_config = {
        "role_mutation": {
            Role.INTAKE_SPECIALIST.value: {
                "stage_types": ["intake"],
                "stage_keys": [],
                "capabilities": [],
            }
        }
    }
    db.add(contacted_stage)
    db.commit()

    async with _client_for_org(
        db,
        test_org,
        role=Role.INTAKE_SPECIALIST,
    ) as client:
        created = await _create_donor(client)
        allowed = await client.patch(
            f"/donors/{created['id']}/status",
            json={"stage_id": str(contacted_stage.id)},
        )
        denied = await client.patch(
            f"/donors/{created['id']}/status",
            json={"stage_id": str(ready_stage.id)},
        )

    assert allowed.status_code == 200, allowed.text
    assert denied.status_code == 400
    assert denied.json()["detail"] == "Role not permitted to change donor stage"


@pytest.mark.asyncio
async def test_on_hold_stage_requires_a_non_blank_reason(db, test_org, authed_client):
    egg_new, _egg_ready = _seed_donor_pipeline(db, test_org.id, "egg")
    on_hold = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=egg_new.pipeline_id,
        stage_key="on_hold",
        slug="on-hold",
        label="On-Hold",
        color="#B4536A",
        stage_type="paused",
        order=3,
        is_active=True,
        is_intake_stage=False,
    )
    db.add(on_hold)
    db.flush()
    created = await _create_donor(authed_client)

    missing_reason = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={"stage_id": str(on_hold.id)},
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"] == "Reason required for this stage"

    blank_reason = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={"stage_id": str(on_hold.id), "reason": "   "},
    )
    assert blank_reason.status_code == 400

    changed = await authed_client.patch(
        f"/donors/{created['id']}/status",
        json={"stage_id": str(on_hold.id), "reason": "Waiting on availability"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["donor"]["status"] == "on_hold"
    assert changed.json()["history"]["reason"] == "Waiting on availability"


@pytest.mark.asyncio
async def test_cross_org_donor_operations_are_denied(db, test_org, authed_client):
    _seed_donor_pipeline(db, test_org.id, "egg")
    _seed_donor_pipeline(db, test_org.id, "sperm")
    created = await _create_donor(authed_client)

    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Organization",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    _, other_ready = _seed_donor_pipeline(db, other_org.id, "egg")
    _seed_donor_pipeline(db, other_org.id, "sperm")

    async with _client_for_org(db, other_org) as other_client:
        assert (await other_client.get(f"/donors/{created['id']}")).status_code == 404
        assert (
            await other_client.patch(
                f"/donors/{created['id']}", json={"education": "Cross-org write"}
            )
        ).status_code == 404
        assert (await other_client.post(f"/donors/{created['id']}/archive")).status_code == 404
        assert (await other_client.post(f"/donors/{created['id']}/restore")).status_code == 404
        assert (
            await other_client.patch(
                f"/donors/{created['id']}/status",
                json={"stage_id": str(other_ready.id)},
            )
        ).status_code == 404


def test_create_donor_rolls_back_domain_write_when_audit_fails(
    db, test_org, test_user, monkeypatch
):
    _seed_donor_pipeline(db, test_org.id, "egg")

    from app.schemas.donor import DonorCreate
    from app.services import audit_service, donor_service

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(audit_service, "log_event", fail_audit)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        donor_service.create_donor(
            db=db,
            org_id=test_org.id,
            user_id=test_user.id,
            data=DonorCreate(
                donor_type="egg",
                full_name="Atomic Donor",
                email="atomic-donor@example.com",
            ),
        )

    from app.db.models import Donor

    assert (
        db.query(Donor)
        .filter(
            Donor.organization_id == test_org.id,
            Donor.email_hash.is_not(None),
        )
        .count()
        == 0
    )
