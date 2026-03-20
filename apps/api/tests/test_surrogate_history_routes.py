from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, Surrogate, User
from app.main import app
from app.services import pipeline_service, session_service


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


@asynccontextmanager
async def role_client(db, org, role: Role):
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
            organization_id=org.id,
            role=role,
        )
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
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org.id,
        token=token,
        request=None,
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
        yield client, user

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_surrogate_history_route_returns_dual_timestamps(authed_client, db, test_auth):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "History Timestamp Test",
            "email": f"history-dual-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = create_res.json()["id"]
    surrogate_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(surrogate_id)).first()
    assert surrogate_row is not None
    surrogate_row.created_at = datetime.now(timezone.utc) - timedelta(days=4)
    surrogate_row.updated_at = surrogate_row.created_at
    db.commit()

    target_stage = _get_stage(db, test_auth.org.id, "contacted")
    effective_at = datetime.now(timezone.utc) - timedelta(days=1, hours=2)

    update_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}/status",
        json={
            "stage_id": str(target_stage.id),
            "effective_at": effective_at.isoformat(),
            "reason": "Backdated history test",
        },
    )
    assert update_res.status_code == 200, update_res.text

    history_res = await authed_client.get(f"/surrogates/{surrogate_id}/history")
    assert history_res.status_code == 200, history_res.text
    history = history_res.json()

    assert len(history) >= 1
    latest = history[0]
    assert latest["to_stage_id"] == str(target_stage.id)
    assert latest["effective_at"] is not None
    assert latest["recorded_at"] is not None
    assert latest["changed_at"] == latest["effective_at"]
    assert latest["changed_by_name"] == test_auth.user.display_name


@pytest.mark.asyncio
async def test_surrogate_history_route_enforces_access(authed_client, db, test_org):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "History Access Test",
            "email": f"history-access-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = create_res.json()["id"]

    async with role_client(db, test_org, Role.INTAKE_SPECIALIST) as (intake_client, _user):
        history_res = await intake_client.get(f"/surrogates/{surrogate_id}/history")
        assert history_res.status_code == 403


@pytest.mark.asyncio
async def test_surrogate_activity_route_includes_stage_changes_in_chronological_order(
    authed_client, db, test_auth
):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Activity Timeline Stage Test",
            "email": f"activity-stage-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = create_res.json()["id"]
    surrogate_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(surrogate_id)).first()
    assert surrogate_row is not None
    surrogate_row.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    surrogate_row.updated_at = surrogate_row.created_at
    db.commit()

    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    qualified_stage = _get_stage(db, test_auth.org.id, "pre_qualified")

    contacted_at = datetime.now(timezone.utc) - timedelta(days=3)
    qualified_at = datetime.now(timezone.utc) - timedelta(days=2)

    contacted_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}/status",
        json={
            "stage_id": str(contacted_stage.id),
            "effective_at": contacted_at.isoformat(),
            "reason": "Backfilled contacted stage",
        },
    )
    assert contacted_res.status_code == 200, contacted_res.text

    qualified_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}/status",
        json={
            "stage_id": str(qualified_stage.id),
            "effective_at": qualified_at.isoformat(),
            "reason": "Backfilled qualified stage",
        },
    )
    assert qualified_res.status_code == 200, qualified_res.text

    activity_res = await authed_client.get(f"/surrogates/{surrogate_id}/activity")
    assert activity_res.status_code == 200, activity_res.text
    items = activity_res.json()["items"]

    status_entries = [item for item in items if item["activity_type"] == "status_changed"]
    assert len(status_entries) >= 2
    assert [entry["details"]["to"] for entry in status_entries[:2]] == [
        qualified_stage.label,
        contacted_stage.label,
    ]
    assert _parse_iso_datetime(status_entries[0]["created_at"]) == qualified_at
    assert _parse_iso_datetime(status_entries[0]["details"]["effective_at"]) == qualified_at
    assert status_entries[0]["details"]["recorded_at"] is not None
