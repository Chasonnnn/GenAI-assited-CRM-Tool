from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import OwnerType, Role
from app.db.models import Membership, Surrogate, User
from app.main import app
from app.services import pipeline_service, session_service
from app.utils.normalization import normalize_email


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


def _create_surrogate(db, org_id, owner_id, stage_key: str, name: str, created_at: datetime):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, stage_key)
    assert stage is not None
    email = normalize_email(f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}@example.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type=OwnerType.USER.value,
        owner_id=owner_id,
        created_by_user_id=owner_id,
        full_name=name,
        email=email,
        email_hash=hash_email(email),
        created_at=created_at,
    )
    db.add(surrogate)
    db.flush()
    return surrogate


@pytest.mark.asyncio
async def test_surrogates_list_owner_filter_for_case_manager_keeps_visibility_policy(db, test_org):
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
        db.add(
            Membership(
                id=uuid.uuid4(),
                user_id=other_user.id,
                organization_id=test_org.id,
                role=Role.INTAKE_SPECIALIST,
            )
        )
        db.flush()
        hidden = _create_surrogate(
            db,
            test_org.id,
            other_user.id,
            "under_review",
            "Hidden Other User Case",
            datetime.now(timezone.utc) - timedelta(days=1),
        )
        visible = _create_surrogate(
            db,
            test_org.id,
            other_user.id,
            "approved",
            "Visible Other User Case",
            datetime.now(timezone.utc),
        )

        response = await client.get(
            "/surrogates",
            params={"owner_id": str(other_user.id), "per_page": 100},
        )
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["items"]}
        assert str(visible.id) in ids
        assert str(hidden.id) not in ids


@pytest.mark.asyncio
async def test_surrogate_created_dates_owner_filter_for_case_manager_keeps_visibility_policy(
    db,
    test_org,
):
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
        db.add(
            Membership(
                id=uuid.uuid4(),
                user_id=other_user.id,
                organization_id=test_org.id,
                role=Role.INTAKE_SPECIALIST,
            )
        )
        db.flush()
        hidden_created_at = datetime(2026, 1, 3, tzinfo=timezone.utc)
        visible_created_at = datetime(2026, 1, 4, tzinfo=timezone.utc)
        _create_surrogate(
            db,
            test_org.id,
            other_user.id,
            "under_review",
            "Hidden Date Case",
            hidden_created_at,
        )
        _create_surrogate(
            db,
            test_org.id,
            other_user.id,
            "approved",
            "Visible Date Case",
            visible_created_at,
        )

        response = await client.get(
            "/surrogates/created-dates",
            params={"owner_id": str(other_user.id)},
        )
        assert response.status_code == 200
        assert response.json() == [visible_created_at.date().isoformat()]


@pytest.mark.asyncio
async def test_surrogates_list_owner_filter_allows_admin(db, test_org):
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
        db.add(
            Membership(
                id=uuid.uuid4(),
                user_id=other_user.id,
                organization_id=test_org.id,
                role=Role.CASE_MANAGER,
            )
        )
        db.flush()

        response = await client.get("/surrogates", params={"owner_id": str(other_user.id)})
        assert response.status_code == 200
