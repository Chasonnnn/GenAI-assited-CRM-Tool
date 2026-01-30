from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.encryption import hash_email
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import OwnerType, Role, SurrogateSource
from app.db.models import Membership, Surrogate, User
from app.main import app
from app.services import session_service


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

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org.id,
        role=role,
    )
    db.add(membership)
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
async def test_attention_scoped_to_owner_when_owned(db, test_org, default_stage):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, user):
        other_user = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Other User",
            token_version=1,
            is_active=True,
        )
        db.add(other_user)
        db.flush()

        now = datetime.now(timezone.utc)
        owned = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20001",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Owned Surrogate",
            email="owned@example.com",
            email_hash=hash_email("owned@example.com"),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            last_contacted_at=now - timedelta(days=10),
        )
        other = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20002",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=other_user.id,
            full_name="Other Surrogate",
            email="other@example.com",
            email_hash=hash_email("other@example.com"),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            last_contacted_at=now - timedelta(days=10),
        )
        db.add_all([owned, other])
        db.flush()

        response = await client.get("/dashboard/attention")
        assert response.status_code == 200
        data = response.json()
        assert data["unreached_count"] == 1
        assert {item["id"] for item in data["unreached_leads"]} == {str(owned.id)}


@pytest.mark.asyncio
async def test_attention_case_manager_orgwide_when_no_owned(db, test_org, default_stage):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, _user):
        other_user = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Other User",
            token_version=1,
            is_active=True,
        )
        db.add(other_user)
        db.flush()

        now = datetime.now(timezone.utc)
        other = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20003",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=other_user.id,
            full_name="Other Org Surrogate",
            email="orgwide@example.com",
            email_hash=hash_email("orgwide@example.com"),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            last_contacted_at=now - timedelta(days=10),
        )
        db.add(other)
        db.flush()

        response = await client.get("/dashboard/attention")
        assert response.status_code == 200
        data = response.json()
        assert data["unreached_count"] == 1
        assert data["unreached_leads"][0]["id"] == str(other.id)


@pytest.mark.asyncio
async def test_attention_admin_sees_orgwide(db, test_org, default_stage):
    async with role_client(db, test_org, Role.ADMIN) as (client, _user):
        other_user = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Other User",
            token_version=1,
            is_active=True,
        )
        db.add(other_user)
        db.flush()

        now = datetime.now(timezone.utc)
        other = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20004",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=other_user.id,
            full_name="Admin Visible Surrogate",
            email="admin-visible@example.com",
            email_hash=hash_email("admin-visible@example.com"),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            last_contacted_at=now - timedelta(days=10),
        )
        db.add(other)
        db.flush()

        response = await client.get("/dashboard/attention")
        assert response.status_code == 200
        data = response.json()
        assert data["unreached_count"] == 1
        assert data["unreached_leads"][0]["id"] == str(other.id)


@pytest.mark.asyncio
async def test_attention_unreached_excludes_recent_updates(db, test_org, default_stage):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, user):
        now = datetime.now(timezone.utc)
        stale = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20007",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Stale Lead",
            email="stale@example.com",
            email_hash=hash_email("stale@example.com"),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            last_contacted_at=None,
        )
        recent_created = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20008",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Recent Lead",
            email="recent@example.com",
            email_hash=hash_email("recent@example.com"),
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
            last_contacted_at=None,
        )
        recent_updated = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20009",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Recently Updated Lead",
            email="updated@example.com",
            email_hash=hash_email("updated@example.com"),
            created_at=now - timedelta(days=12),
            updated_at=now - timedelta(days=2),
            last_contacted_at=None,
        )
        db.add_all([stale, recent_created, recent_updated])
        db.flush()

        response = await client.get("/dashboard/attention")
        assert response.status_code == 200
        data = response.json()
        assert data["unreached_count"] == 1
        assert {item["id"] for item in data["unreached_leads"]} == {str(stale.id)}


@pytest.mark.asyncio
async def test_attention_assignee_filter_requires_admin(db, test_org, default_stage):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, _user):
        other_user = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Other User",
            token_version=1,
            is_active=True,
        )
        db.add(other_user)
        db.flush()

        response = await client.get(f"/dashboard/attention?assignee_id={other_user.id}")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_attention_assignee_filter_admin(db, test_org, default_stage):
    async with role_client(db, test_org, Role.ADMIN) as (client, _user):
        other_user = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            display_name="Other User",
            token_version=1,
            is_active=True,
        )
        db.add(other_user)
        db.flush()

        membership = Membership(
            id=uuid.uuid4(),
            user_id=other_user.id,
            organization_id=test_org.id,
            role=Role.CASE_MANAGER,
        )
        db.add(membership)

        now = datetime.now(timezone.utc)
        other = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20006",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=other_user.id,
            full_name="Other Surrogate",
            email="other-admin@example.com",
            email_hash=hash_email("other-admin@example.com"),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            last_contacted_at=now - timedelta(days=10),
        )
        db.add(other)
        db.flush()

        response = await client.get(f"/dashboard/attention?assignee_id={other_user.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["unreached_count"] == 1
        assert data["unreached_leads"][0]["id"] == str(other.id)


@pytest.mark.asyncio
async def test_attention_stuck_includes_no_history(db, test_org, default_stage):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, user):
        now = datetime.now(timezone.utc)
        stuck = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20005",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Stuck Surrogate",
            email="stuck@example.com",
            email_hash=hash_email("stuck@example.com"),
            created_at=now - timedelta(days=30),
            last_contacted_at=now,
        )
        db.add(stuck)
        db.flush()

        response = await client.get("/dashboard/attention?days_stuck=14")
        assert response.status_code == 200
        data = response.json()
        assert data["stuck_count"] == 1
        assert data["stuck_surrogates"][0]["id"] == str(stuck.id)


@pytest.mark.asyncio
async def test_attention_invalid_pipeline_id_returns_422(authed_client):
    response = await authed_client.get("/dashboard/attention?pipeline_id=not-a-uuid")
    assert response.status_code == 422
