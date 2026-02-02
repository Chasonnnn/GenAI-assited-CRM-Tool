import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.models import User
from app.main import app
from app.services import mfa_service, session_service


@pytest.mark.asyncio
async def test_mfa_status_allows_platform_admin_without_membership(db, test_org):
    user = User(
        id=uuid.uuid4(),
        email="ops-admin@test.com",
        display_name="Ops Admin",
        token_version=1,
        is_active=True,
        is_platform_admin=True,
    )
    db.add(user)
    db.flush()

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role="admin",
        token_version=user.token_version,
        mfa_verified=False,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=test_org.id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://api.surrogacyforce.com",
            cookies={COOKIE_NAME: token},
            headers={
                "origin": "https://ops.surrogacyforce.com",
                "host": "api.surrogacyforce.com",
            },
        ) as client:
            response = await client.get("/mfa/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["mfa_required"] is True


@pytest.mark.asyncio
async def test_mfa_complete_allows_platform_admin_without_membership(db, test_org, monkeypatch):
    user = User(
        id=uuid.uuid4(),
        email="ops-admin-complete@test.com",
        display_name="Ops Admin",
        token_version=1,
        is_active=True,
        is_platform_admin=True,
        mfa_enabled=True,
    )
    db.add(user)
    db.flush()

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role="admin",
        token_version=user.token_version,
        mfa_verified=False,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=test_org.id,
        token=token,
        request=None,
    )

    monkeypatch.setattr(mfa_service, "verify_mfa_code", lambda *_args, **_kwargs: (True, "totp"))

    csrf_token = generate_csrf_token()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://api.surrogacyforce.com",
            cookies={
                COOKIE_NAME: token,
                CSRF_COOKIE_NAME: csrf_token,
            },
            headers={
                CSRF_HEADER: csrf_token,
                "origin": "https://ops.surrogacyforce.com",
                "host": "api.surrogacyforce.com",
            },
        ) as client:
            response = await client.post("/mfa/complete", json={"code": "123456"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
