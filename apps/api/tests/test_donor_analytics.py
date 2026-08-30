from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import OwnerType, Role
from app.db.models import (
    Donor,
    DonorStatusHistory,
    Membership,
    Organization,
    User,
    UserPermissionOverride,
)
from app.main import app
from app.services import donor_service, pipeline_service, session_service


@asynccontextmanager
async def _client_for(
    db,
    org: Organization,
    *,
    role: Role = Role.ADMIN,
    revokes: tuple[str, ...] = (),
):
    user = User(
        id=uuid.uuid4(),
        email=f"donor-analytics-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Donor Analytics User",
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
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
            headers={CSRF_HEADER: csrf_token},
        ) as client:
            yield client, user
    finally:
        app.dependency_overrides.clear()


def _create_donor(
    db,
    org_id,
    *,
    donor_type: str,
    stage_id,
    number: str,
    created_at: datetime,
    owner_id=None,
    state: str = "NY",
    archived: bool = False,
) -> Donor:
    email = f"{number.lower()}-{uuid.uuid4().hex[:6]}@example.com"
    donor = Donor(
        id=uuid.uuid4(),
        organization_id=org_id,
        donor_number=number,
        donor_type=donor_type,
        full_name=f"{donor_type.title()} {number}",
        email=email,
        email_hash=hash_email(email),
        state=state,
        owner_type=OwnerType.USER.value if owner_id else None,
        owner_id=owner_id,
        stage_id=stage_id,
        is_archived=archived,
        archived_at=created_at if archived else None,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(donor)
    db.flush()
    return donor


@pytest.mark.asyncio
async def test_donor_reports_require_both_report_and_donor_permissions(db, test_org):
    pipeline_service.get_or_create_default_pipeline(db, test_org.id, entity_type="egg_donor")
    async with _client_for(db, test_org, revokes=("view_donors",)) as (client, _user):
        response = await client.get("/analytics/donors/summary", params={"donor_type": "egg"})
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_routes_require_dashboard_permission_before_donor_payloads(
    db, test_org
):
    pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    async with _client_for(
        db,
        test_org,
        revokes=("view_dashboard",),
    ) as (client, _user):
        attention = await client.get("/dashboard/attention")
        upcoming = await client.get("/dashboard/upcoming")

    assert attention.status_code == 403
    assert upcoming.status_code == 403


@pytest.mark.asyncio
async def test_attention_hides_stuck_donors_without_donor_permission(db, test_org):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    active_stage = next(
        stage for stage in pipeline.stages if stage.stage_key == "contacted"
    )
    _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=active_stage.id,
        number="D70501",
        created_at=datetime.now(UTC) - timedelta(days=100),
    )

    async with _client_for(
        db,
        test_org,
        revokes=("view_donors",),
    ) as (client, _user):
        response = await client.get("/dashboard/attention", params={"days_stuck": 90})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["stuck_donors"] == []
    assert data["stuck_donor_count"] == 0
    assert data["stuck_donor_counts"] == {"egg": 0, "sperm": 0}


@pytest.mark.asyncio
async def test_donor_by_status_includes_zero_stages_and_excludes_archived_by_default(
    db, test_org
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    new_stage = next(stage for stage in pipeline.stages if stage.stage_key == "new")
    now = datetime.now(UTC)
    _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=new_stage.id,
        number="D71001",
        created_at=now,
    )
    _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=new_stage.id,
        number="D71002",
        created_at=now,
        archived=True,
    )

    async with _client_for(db, test_org) as (client, _user):
        response = await client.get(
            "/analytics/donors/by-status", params={"donor_type": "egg"}
        )
        assert response.status_code == 200, response.text
        rows = response.json()
        assert len(rows) == len([stage for stage in pipeline.stages if stage.is_active])
        assert next(row for row in rows if row["stage_id"] == str(new_stage.id))["count"] == 1
        assert any(row["count"] == 0 for row in rows)

        with_archived = await client.get(
            "/analytics/donors/by-status",
            params={"donor_type": "egg", "include_archived": True},
        )
        assert with_archived.status_code == 200, with_archived.text
        assert (
            next(
                row for row in with_archived.json() if row["stage_id"] == str(new_stage.id)
            )["count"]
            == 2
        )


@pytest.mark.asyncio
async def test_donor_analytics_rejects_cross_org_and_cross_subtype_pipelines(db, test_org):
    egg_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="sperm_donor"
    )
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Analytics Org",
        slug=f"other-analytics-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    other_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, other_org.id, entity_type="egg_donor"
    )

    async with _client_for(db, test_org) as (client, _user):
        for invalid_pipeline_id in (sperm_pipeline.id, other_pipeline.id):
            response = await client.get(
                "/analytics/donors/by-status",
                params={"donor_type": "egg", "pipeline_id": str(invalid_pipeline_id)},
            )
            assert response.status_code == 404

        valid = await client.get(
            "/analytics/donors/by-status",
            params={"donor_type": "egg", "pipeline_id": str(egg_pipeline.id)},
        )
        assert valid.status_code == 200, valid.text


@pytest.mark.asyncio
async def test_donor_dashboard_owner_filter_and_permission_are_enforced(db, test_org):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="sperm_donor"
    )
    other_owner = User(
        id=uuid.uuid4(),
        email=f"other-owner-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other Owner",
        token_version=1,
        is_active=True,
    )
    db.add(other_owner)
    db.flush()

    async with _client_for(db, test_org, role=Role.INTAKE_SPECIALIST) as (client, user):
        own = await client.get(
            "/dashboard/donors/by-status",
            params={"donor_type": "sperm", "owner_id": str(user.id)},
        )
        assert own.status_code == 200, own.text
        denied = await client.get(
            "/dashboard/donors/by-status",
            params={"donor_type": "sperm", "owner_id": str(other_owner.id)},
        )
        assert denied.status_code == 403

    assert pipeline.entity_type == "sperm_donor"
    async with _client_for(
        db,
        test_org,
        role=Role.ADMIN,
        revokes=("view_donors",),
    ) as (client, _user):
        denied = await client.get(
            "/dashboard/donors/by-status", params={"donor_type": "sperm"}
        )
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_donor_trend_honors_local_timezone_date_boundary_and_filters(db, test_org):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    new_stage = next(stage for stage in pipeline.stages if stage.stage_key == "new")
    _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=new_stage.id,
        number="D72001",
        created_at=datetime(2026, 1, 2, 4, 30, tzinfo=UTC),
        state="NY",
    )
    _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=new_stage.id,
        number="D72002",
        created_at=datetime(2026, 1, 2, 5, 30, tzinfo=UTC),
        state="CA",
    )

    async with _client_for(db, test_org) as (client, _user):
        response = await client.get(
            "/analytics/donors/trend",
            params={
                "donor_type": "egg",
                "from_date": "2026-01-01",
                "to_date": "2026-01-01",
                "timezone": "America/New_York",
                "state": "ny",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json() == [{"date": "2026-01-01", "count": 1}]


@pytest.mark.asyncio
async def test_donor_qualification_uses_eligible_stages_or_history_not_stage_order(
    db, test_org
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    stages = {stage.stage_key: stage for stage in pipeline.stages}
    now = datetime.now(UTC)
    qualified = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=stages["ready_to_match"].id,
        number="D72501",
        created_at=now,
    )
    _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=stages["on_hold"].id,
        number="D72502",
        created_at=now,
    )
    _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=stages["disqualified"].id,
        number="D72503",
        created_at=now,
    )
    _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=stages["closed"].id,
        number="D72504",
        created_at=now,
    )
    qualified_then_closed = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=stages["closed"].id,
        number="D72505",
        created_at=now,
    )
    db.add(
        DonorStatusHistory(
            id=uuid.uuid4(),
            donor_id=qualified_then_closed.id,
            organization_id=test_org.id,
            changed_by_user_id=None,
            old_stage_id=stages["medical_records_review"].id,
            new_stage_id=stages["ready_to_match"].id,
            old_status="medical_records_review",
            new_status="ready_to_match",
            old_label_snapshot=stages["medical_records_review"].label,
            new_label_snapshot=stages["ready_to_match"].label,
            reason="Qualified before closing",
            effective_at=now,
            recorded_at=now,
        )
    )
    db.flush()

    async with _client_for(db, test_org) as (client, _user):
        response = await client.get(
            "/analytics/donors/summary", params={"donor_type": "egg"}
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_donors"] == 5
    assert data["qualification_rate"] == 40.0
    assert qualified.id != qualified_then_closed.id


@pytest.mark.asyncio
async def test_donor_lifecycle_history_does_not_inflate_time_to_qualification(
    db,
    test_org,
    test_user,
):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    stages = {stage.stage_key: stage for stage in pipeline.stages}
    created_at = datetime.now(UTC) - timedelta(hours=10)
    qualified_at = created_at + timedelta(hours=2)
    donor = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=stages["ready_to_match"].id,
        number="D72506",
        created_at=created_at,
    )
    db.add(
        DonorStatusHistory(
            id=uuid.uuid4(),
            donor_id=donor.id,
            organization_id=test_org.id,
            changed_by_user_id=test_user.id,
            old_stage_id=stages["medical_records_review"].id,
            new_stage_id=stages["ready_to_match"].id,
            old_status="medical_records_review",
            new_status="ready_to_match",
            old_label_snapshot=stages["medical_records_review"].label,
            new_label_snapshot=stages["ready_to_match"].label,
            reason="Qualified",
            effective_at=qualified_at,
            recorded_at=qualified_at,
        )
    )
    db.commit()

    donor_service.archive_donor(db, donor, test_user.id)
    donor_service.restore_donor(db, donor, test_user.id)

    async with _client_for(db, test_org) as (client, _user):
        response = await client.get(
            "/analytics/donors/summary", params={"donor_type": "egg"}
        )

    assert response.status_code == 200, response.text
    assert response.json()["avg_time_to_qualification_hours"] == 2.0


@pytest.mark.asyncio
async def test_attention_includes_only_active_stuck_donors(db, test_org):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    active_stage = next(stage for stage in pipeline.stages if stage.stage_key == "contacted")
    paused_stage = next(stage for stage in pipeline.stages if stage.stage_type == "paused")
    terminal_stage = next(stage for stage in pipeline.stages if stage.stage_type == "terminal")
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    active = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=active_stage.id,
        number="D73001",
        created_at=old,
    )
    paused = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=paused_stage.id,
        number="D73002",
        created_at=old,
    )
    terminal = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=terminal_stage.id,
        number="D73003",
        created_at=old,
    )
    recent = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=active_stage.id,
        number="D73004",
        created_at=old,
    )
    db.add(
        DonorStatusHistory(
            id=uuid.uuid4(),
            donor_id=recent.id,
            organization_id=test_org.id,
            changed_by_user_id=None,
            old_stage_id=None,
            new_stage_id=active_stage.id,
            old_status=None,
            new_status=active_stage.stage_key,
            old_label_snapshot=None,
            new_label_snapshot=active_stage.label,
            reason="Recent move",
            effective_at=now - timedelta(days=2),
            recorded_at=now - timedelta(days=2),
        )
    )
    db.flush()

    async with _client_for(db, test_org) as (client, _user):
        response = await client.get("/dashboard/attention", params={"days_stuck": 90})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["stuck_donor_count"] == 1
        assert data["stuck_donor_counts"] == {"egg": 1, "sperm": 0}
        assert {item["id"] for item in data["stuck_donors"]} == {str(active.id)}
        assert data["total_count"] >= 1
        assert str(paused.id) not in {item["id"] for item in data["stuck_donors"]}
        assert str(terminal.id) not in {item["id"] for item in data["stuck_donors"]}

        donor_list = await client.get(
            "/donors",
            params={"donor_type": "egg", "dynamic_filter": "attention_stuck"},
        )
        assert donor_list.status_code == 200, donor_list.text
        assert {item["id"] for item in donor_list.json()["items"]} == {str(active.id)}


@pytest.mark.asyncio
async def test_attention_rejects_cross_org_and_cross_subtype_donor_stage_joins(
    db, test_org
):
    egg_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="sperm_donor"
    )
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Attention Org",
        slug=f"other-attention-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    other_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, other_org.id, entity_type="egg_donor"
    )
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    valid_stage = next(
        stage for stage in egg_pipeline.stages if stage.stage_key == "contacted"
    )
    sperm_stage = next(
        stage for stage in sperm_pipeline.stages if stage.stage_key == "contacted"
    )
    other_stage = next(
        stage for stage in other_pipeline.stages if stage.stage_key == "contacted"
    )
    valid = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=valid_stage.id,
        number="D74001",
        created_at=old,
    )
    cross_subtype = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=sperm_stage.id,
        number="D74002",
        created_at=old,
    )
    cross_org = _create_donor(
        db,
        test_org.id,
        donor_type="egg",
        stage_id=other_stage.id,
        number="D74003",
        created_at=old,
    )

    async with _client_for(db, test_org) as (client, _user):
        response = await client.get("/dashboard/attention", params={"days_stuck": 90})

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["stuck_donors"]}
    assert str(valid.id) in ids
    assert str(cross_subtype.id) not in ids
    assert str(cross_org.id) not in ids
