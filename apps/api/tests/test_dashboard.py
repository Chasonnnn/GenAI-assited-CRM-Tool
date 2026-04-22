from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Query

from app.core.encryption import hash_email
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import OwnerType, Role, SurrogateSource
from app.db.models import (
    Membership,
    PipelineStage,
    Surrogate,
    SurrogateActivityLog,
    SurrogateStatusHistory,
    User,
)
from app.main import app
from app.services import dashboard_service, pipeline_service, session_service


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
async def test_attention_unreached_excludes_recent_activity_logs(db, test_org, default_stage):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, user):
        now = datetime.now(timezone.utc)
        stale = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20010",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Truly Stale Lead",
            email="truly-stale@example.com",
            email_hash=hash_email("truly-stale@example.com"),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            last_contacted_at=None,
        )
        recently_active = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20011",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Recently Active Lead",
            email="recent-activity@example.com",
            email_hash=hash_email("recent-activity@example.com"),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            last_contacted_at=None,
        )
        db.add_all([stale, recently_active])
        db.flush()
        db.add(
            SurrogateActivityLog(
                surrogate_id=recently_active.id,
                organization_id=test_org.id,
                activity_type="note_added",
                actor_user_id=user.id,
                details={"text": "Follow-up note"},
                created_at=now - timedelta(days=1),
            )
        )
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
async def test_attention_stuck_excludes_on_hold(db, test_org):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, user):
        pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
        on_hold_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "on_hold")
        assert on_hold_stage is not None

        now = datetime.now(timezone.utc)
        paused = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20006",
            organization_id=test_org.id,
            stage_id=on_hold_stage.id,
            status_label=on_hold_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Paused Surrogate",
            email="paused@example.com",
            email_hash=hash_email("paused@example.com"),
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=30),
            last_contacted_at=now - timedelta(days=30),
        )
        db.add(paused)
        db.flush()

        response = await client.get("/dashboard/attention?days_stuck=14")
        assert response.status_code == 200
        data = response.json()
        assert data["unreached_count"] == 0
        assert data["stuck_count"] == 0
        assert data["stuck_surrogates"] == []


@pytest.mark.asyncio
async def test_attention_stuck_excludes_post_approval_stages_but_keeps_approved(db, test_org):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, user):
        pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
        approved_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "approved")
        ready_to_match_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "ready_to_match")
        assert approved_stage is not None
        assert ready_to_match_stage is not None

        now = datetime.now(timezone.utc)
        approved_stuck = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20007",
            organization_id=test_org.id,
            stage_id=approved_stage.id,
            status_label=approved_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Approved Stuck Surrogate",
            email="approved-stuck@example.com",
            email_hash=hash_email("approved-stuck@example.com"),
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=30),
            last_contacted_at=now,
        )
        post_approval_stuck = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20008",
            organization_id=test_org.id,
            stage_id=ready_to_match_stage.id,
            status_label=ready_to_match_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Post Approval Stuck Surrogate",
            email="post-approval-stuck@example.com",
            email_hash=hash_email("post-approval-stuck@example.com"),
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=30),
            last_contacted_at=now,
        )
        db.add_all([approved_stuck, post_approval_stuck])
        db.flush()

        response = await client.get("/dashboard/attention?days_stuck=14")
        assert response.status_code == 200
        data = response.json()

        stuck_ids = {item["id"] for item in data["stuck_surrogates"]}
        assert data["stuck_count"] == 1
        assert stuck_ids == {str(approved_stuck.id)}


@pytest.mark.asyncio
async def test_attention_stuck_excludes_terminal_and_paused_stage_keys_even_with_legacy_types(
    db, test_org, default_stage
):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, user):
        legacy_excluded_stages = [
            PipelineStage(
                id=uuid.uuid4(),
                pipeline_id=default_stage.pipeline_id,
                stage_key=slug,
                slug=slug,
                label=label,
                color="#EF4444",
                stage_type="intake",
                order=default_stage.order + offset,
                is_active=True,
                is_intake_stage=True,
            )
            for offset, (slug, label) in enumerate(
                (
                    ("on_hold", "On-Hold"),
                    ("lost", "Lost"),
                    ("disqualified", "Disqualified"),
                ),
                start=1,
            )
        ]
        db.add_all(legacy_excluded_stages)
        db.flush()

        now = datetime.now(timezone.utc)
        active_stuck = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20009",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Active Stuck Surrogate",
            email="active-stuck@example.com",
            email_hash=hash_email("active-stuck@example.com"),
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=30),
            last_contacted_at=now,
        )
        excluded_surrogates = [
            Surrogate(
                id=uuid.uuid4(),
                surrogate_number=f"S2001{index}",
                organization_id=test_org.id,
                stage_id=stage.id,
                status_label=stage.label,
                source=SurrogateSource.MANUAL.value,
                owner_type=OwnerType.USER.value,
                owner_id=user.id,
                full_name=f"Excluded {stage.label}",
                email=f"excluded-{stage.stage_key}@example.com",
                email_hash=hash_email(f"excluded-{stage.stage_key}@example.com"),
                created_at=now - timedelta(days=30),
                updated_at=now - timedelta(days=30),
                last_contacted_at=now,
            )
            for index, stage in enumerate(legacy_excluded_stages)
        ]
        db.add(active_stuck)
        db.add_all(excluded_surrogates)
        db.flush()

        response = await client.get("/dashboard/attention?days_stuck=14")
        assert response.status_code == 200
        data = response.json()

        stuck_ids = {item["id"] for item in data["stuck_surrogates"]}
        assert data["stuck_count"] == 1
        assert stuck_ids == {str(active_stuck.id)}


@pytest.mark.asyncio
async def test_attention_invalid_pipeline_id_returns_422(authed_client):
    response = await authed_client.get("/dashboard/attention?pipeline_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_attention_stuck_uses_latest_stage_history(db, test_org, default_stage):
    async with role_client(db, test_org, Role.CASE_MANAGER) as (client, user):
        now = datetime.now(timezone.utc)
        surrogate = Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S20999",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=user.id,
            full_name="Query Shape Surrogate",
            email="query-shape@example.com",
            email_hash=hash_email("query-shape@example.com"),
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=30),
            last_contacted_at=now,
        )
        db.add(surrogate)
        db.flush()

        db.add_all(
            [
                SurrogateStatusHistory(
                    organization_id=test_org.id,
                    surrogate_id=surrogate.id,
                    from_stage_id=None,
                    to_stage_id=default_stage.id,
                    changed_at=now - timedelta(days=30),
                ),
                SurrogateStatusHistory(
                    organization_id=test_org.id,
                    surrogate_id=surrogate.id,
                    from_stage_id=default_stage.id,
                    to_stage_id=default_stage.id,
                    changed_at=now - timedelta(days=3),
                ),
            ]
        )
        db.flush()

        response = await client.get("/dashboard/attention?days_stuck=14")
        assert response.status_code == 200
        data = response.json()
        assert data["stuck_count"] == 0


def test_attention_items_skip_count_queries_when_results_are_below_limit(
    db, test_org, default_stage, test_user, monkeypatch
):
    now = datetime.now(timezone.utc)
    db.add(
        Surrogate(
            id=uuid.uuid4(),
            surrogate_number="S21001",
            organization_id=test_org.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.MANUAL.value,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            full_name="Below Limit Surrogate",
            email="below-limit@example.com",
            email_hash=hash_email("below-limit@example.com"),
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=20),
            last_contacted_at=now - timedelta(days=20),
        )
    )
    db.flush()

    def _scalar_should_not_be_called(self, *args, **kwargs):
        raise AssertionError("get_attention_items should not call Query.scalar() below the limit")

    monkeypatch.setattr(Query, "scalar", _scalar_should_not_be_called)

    data = dashboard_service.get_attention_items(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
        limit=2,
    )

    assert data["unreached_count"] == 1
    assert data["stuck_count"] == 1
    assert data["overdue_count"] == 0


def test_attention_items_still_count_when_results_hit_limit(
    db, test_org, default_stage, test_user, monkeypatch
):
    now = datetime.now(timezone.utc)
    for index in range(2):
        email = f"hit-limit-{index}@example.com"
        db.add(
            Surrogate(
                id=uuid.uuid4(),
                surrogate_number=f"S2200{index + 1}",
                organization_id=test_org.id,
                stage_id=default_stage.id,
                status_label=default_stage.label,
                source=SurrogateSource.MANUAL.value,
                owner_type=OwnerType.USER.value,
                owner_id=test_user.id,
                full_name=f"Hit Limit {index + 1}",
                email=email,
                email_hash=hash_email(email),
                created_at=now - timedelta(days=20),
                updated_at=now - timedelta(days=20),
                last_contacted_at=now - timedelta(days=20),
            )
        )
    db.flush()

    original_scalar = Query.scalar
    scalar_calls = {"count": 0}

    def _counting_scalar(self, *args, **kwargs):
        scalar_calls["count"] += 1
        return original_scalar(self, *args, **kwargs)

    monkeypatch.setattr(Query, "scalar", _counting_scalar)

    data = dashboard_service.get_attention_items(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
        limit=2,
    )

    assert data["unreached_count"] == 2
    assert data["stuck_count"] == 2
    assert scalar_calls["count"] >= 2
