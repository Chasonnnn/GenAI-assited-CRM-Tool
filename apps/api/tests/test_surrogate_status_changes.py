from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import UUID
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import OwnerType, Role
from app.db.models import Membership, StatusChangeRequest, Surrogate, SurrogateStatusHistory, User
from app.main import app
from app.services import pipeline_service
from app.services import session_service


def _org_timezone() -> ZoneInfo:
    return ZoneInfo("America/Los_Angeles")


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


async def _create_surrogate(authed_client):
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Status Change Test",
            "email": f"status-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@asynccontextmanager
async def _client_for_role(db, org_id: UUID, role: Role):
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        display_name=f"{role.value} user",
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
            role=role,
            is_active=True,
        )
    )
    db.flush()

    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
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
            yield user, client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_surrogate_status_change_backdate_requires_reason(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    target_stage = _get_stage(db, test_auth.org.id, "contacted")

    # Set surrogate created_at to allow backdating to yesterday
    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    surrogate_row.created_at = datetime.now(_org_timezone()) - timedelta(days=7)
    db.commit()

    yesterday = (datetime.now(_org_timezone()).date() - timedelta(days=1)).isoformat()

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(target_stage.id), "effective_at": yesterday},
    )
    assert response.status_code == 403
    assert "Reason required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_surrogate_status_change_today_date_no_time_is_effective_now(
    authed_client, db, test_auth
):
    surrogate = await _create_surrogate(authed_client)
    target_stage = _get_stage(db, test_auth.org.id, "contacted")

    today = datetime.now(_org_timezone()).date().isoformat()
    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(target_stage.id), "effective_at": today},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "applied"

    surrogate_id = UUID(surrogate["id"])
    history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate_id)
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert history is not None
    assert history.effective_at is not None
    delta_seconds = abs((history.recorded_at - history.effective_at).total_seconds())
    assert delta_seconds < 10


@pytest.mark.asyncio
async def test_surrogate_status_regression_creates_pending_request_for_non_admin(db, test_org):
    """Regression outside the 5-minute undo grace period requires admin approval."""
    contacted_stage = _get_stage(db, test_org.id, "contacted")
    new_unread_stage = _get_stage(db, test_org.id, "new_unread")

    async with _client_for_role(db, test_org.id, Role.INTAKE_SPECIALIST) as (_, client):
        surrogate = await _create_surrogate(client)

        response = await client.patch(
            f"/surrogates/{surrogate['id']}/status",
            json={"stage_id": str(contacted_stage.id)},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "applied"

        # Move the history record's recorded_at back to be outside the 5-minute undo grace period
        surrogate_id = UUID(surrogate["id"])
        history = (
            db.query(SurrogateStatusHistory)
            .filter(SurrogateStatusHistory.surrogate_id == surrogate_id)
            .first()
        )
        history.recorded_at = datetime.now(_org_timezone()) - timedelta(minutes=10)
        db.commit()

        regression = await client.patch(
            f"/surrogates/{surrogate['id']}/status",
            json={"stage_id": str(new_unread_stage.id), "reason": "Requested correction"},
        )
        assert regression.status_code == 200, regression.text
        regression_payload = regression.json()
        assert regression_payload["status"] == "pending_approval"

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == contacted_stage.id

    request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "surrogate",
            StatusChangeRequest.entity_id == surrogate_id,
        )
        .first()
    )
    assert request is not None
    assert request.status == "pending"
    assert request.target_stage_id == new_unread_stage.id

    # Only 1 history entry (from new_unread -> contacted), no new entry for pending regression
    history_count = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == surrogate_id)
        .count()
    )
    assert history_count == 1


@pytest.mark.asyncio
async def test_approve_status_change_request_applies_regression(db, test_org):
    """Admin approval of a regression request applies the change and records audit trail."""
    contacted_stage = _get_stage(db, test_org.id, "contacted")
    new_unread_stage = _get_stage(db, test_org.id, "new_unread")

    async with _client_for_role(db, test_org.id, Role.INTAKE_SPECIALIST) as (_, requester_client):
        surrogate = await _create_surrogate(requester_client)

        response = await requester_client.patch(
            f"/surrogates/{surrogate['id']}/status",
            json={"stage_id": str(contacted_stage.id)},
        )
        assert response.status_code == 200, response.text

        surrogate_id = UUID(surrogate["id"])
        history = (
            db.query(SurrogateStatusHistory)
            .filter(SurrogateStatusHistory.surrogate_id == surrogate_id)
            .first()
        )
        history.recorded_at = datetime.now(_org_timezone()) - timedelta(minutes=10)
        db.commit()

        regression = await requester_client.patch(
            f"/surrogates/{surrogate['id']}/status",
            json={"stage_id": str(new_unread_stage.id), "reason": "Regression request"},
        )
        assert regression.status_code == 200, regression.text
        assert regression.json()["status"] == "pending_approval"
        request_id = UUID(regression.json()["request_id"])

    async with _client_for_role(db, test_org.id, Role.DEVELOPER) as (approver, approver_client):
        approve = await approver_client.post(f"/status-change-requests/{request_id}/approve")
        assert approve.status_code == 200, approve.text
        assert approve.json()["status"] == "approved"

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == new_unread_stage.id

    regression_history = (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate_id,
            SurrogateStatusHistory.request_id == request_id,
        )
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert regression_history is not None
    assert regression_history.approved_by_user_id == approver.id


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.ADMIN, Role.DEVELOPER])
async def test_surrogate_status_regression_self_approves_for_admin_or_developer(
    db, test_org, role
):
    contacted_stage = _get_stage(db, test_org.id, "contacted")
    new_unread_stage = _get_stage(db, test_org.id, "new_unread")

    async with _client_for_role(db, test_org.id, role) as (user, client):
        surrogate = await _create_surrogate(client)

        response = await client.patch(
            f"/surrogates/{surrogate['id']}/status",
            json={"stage_id": str(contacted_stage.id)},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "applied"

        surrogate_id = UUID(surrogate["id"])
        history = (
            db.query(SurrogateStatusHistory)
            .filter(SurrogateStatusHistory.surrogate_id == surrogate_id)
            .order_by(SurrogateStatusHistory.recorded_at.desc())
            .first()
        )
        assert history is not None
        history.recorded_at = datetime.now(_org_timezone()) - timedelta(minutes=10)
        db.commit()

        regression = await client.patch(
            f"/surrogates/{surrogate['id']}/status",
            json={"stage_id": str(new_unread_stage.id), "reason": "Requested correction"},
        )
        assert regression.status_code == 200, regression.text
        assert regression.json()["status"] == "applied"
        assert regression.json()["request_id"] is None

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == new_unread_stage.id

    request_count = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_type == "surrogate",
            StatusChangeRequest.entity_id == surrogate_id,
            StatusChangeRequest.status == "pending",
        )
        .count()
    )
    assert request_count == 0

    regression_history = (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate_id,
            SurrogateStatusHistory.to_stage_id == new_unread_stage.id,
        )
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    assert regression_history is not None
    assert regression_history.request_id is None
    assert regression_history.changed_by_user_id == user.id
    assert regression_history.approved_by_user_id == user.id
    assert regression_history.approved_at is not None


@pytest.mark.asyncio
async def test_surrogate_status_undo_within_grace_period_bypasses_approval(
    authed_client, db, test_auth
):
    """Regression within 5-minute undo grace period by same user applies immediately."""
    surrogate = await _create_surrogate(authed_client)
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    new_unread_stage = _get_stage(db, test_auth.org.id, "new_unread")

    # Move to contacted
    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"

    # Undo immediately (within grace period) - should apply without approval
    undo = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(new_unread_stage.id), "reason": "Undoing mistake"},
    )
    assert undo.status_code == 200, undo.text
    undo_payload = undo.json()
    assert undo_payload["status"] == "applied"  # Immediate, not pending_approval

    surrogate_id = UUID(surrogate["id"])
    surrogate_row = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == new_unread_stage.id

    # Check history has is_undo=True
    undo_history = (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate_id,
            SurrogateStatusHistory.to_stage_id == new_unread_stage.id,
        )
        .first()
    )
    assert undo_history is not None
    assert undo_history.is_undo is True


@pytest.mark.asyncio
async def test_surrogate_status_change_still_applies_when_notification_side_effect_fails(
    authed_client, db, test_auth, monkeypatch
):
    surrogate = await _create_surrogate(authed_client)
    target_stage = _get_stage(db, test_auth.org.id, "contacted")

    owner = User(
        id=uuid.uuid4(),
        email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Owner User",
        token_version=1,
        is_active=True,
    )
    db.add(owner)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=owner.id,
            organization_id=test_auth.org.id,
            role=Role.CASE_MANAGER,
        )
    )

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    surrogate_row.owner_type = OwnerType.USER.value
    surrogate_row.owner_id = owner.id
    db.commit()

    from app.services import notification_facade, workflow_triggers

    def raise_notification_error(*_args, **_kwargs):
        raise RuntimeError("notification dispatch failed")

    monkeypatch.setattr(
        notification_facade,
        "notify_surrogate_status_changed",
        raise_notification_error,
    )
    monkeypatch.setattr(workflow_triggers, "trigger_status_changed", lambda *_args, **_kwargs: None)

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(target_stage.id)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"

    db.refresh(surrogate_row)
    assert surrogate_row.stage_id == target_stage.id


@pytest.mark.asyncio
async def test_surrogate_status_change_still_applies_when_workflow_trigger_fails(
    authed_client, db, test_auth, monkeypatch
):
    surrogate = await _create_surrogate(authed_client)
    target_stage = _get_stage(db, test_auth.org.id, "contacted")

    from app.services import workflow_triggers

    def raise_workflow_error(*_args, **_kwargs):
        raise RuntimeError("workflow trigger failed")

    monkeypatch.setattr(
        workflow_triggers,
        "trigger_status_changed",
        raise_workflow_error,
    )

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(target_stage.id)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == target_stage.id


@pytest.mark.asyncio
async def test_renamed_on_hold_stage_still_creates_pause_metadata_and_follow_up(
    authed_client, db, test_auth
):
    surrogate = await _create_surrogate(authed_client)
    on_hold_stage = _get_stage(db, test_auth.org.id, "on_hold")
    on_hold_stage.slug = "pause_for_review"
    db.commit()

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={
            "stage_id": str(on_hold_stage.id),
            "reason": "Waiting on coordinator review",
            "on_hold_follow_up_months": 3,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    assert surrogate_row.stage_id == on_hold_stage.id
    assert surrogate_row.paused_from_stage_id is not None
    assert surrogate_row.on_hold_follow_up_task_id is not None
