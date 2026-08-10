"""Authorization regressions for the developer-only ticket workspace APIs."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User
from app.main import app
from app.services import session_service


async def _client_with_role(db, test_org, role: Role) -> AsyncClient:
    user = User(
        id=uuid.uuid4(),
        email=f"ticket-access-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Ticket Access User",
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
            role=role.value,
        )
    )
    db.commit()

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
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
    csrf_token = generate_csrf_token()
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    )


@pytest.mark.asyncio
async def test_admin_cannot_access_ticket_or_messaging_inboxes(db, test_org):
    admin_client = await _client_with_role(db, test_org, Role.ADMIN)
    try:
        async with admin_client:
            tickets = await admin_client.get("/tickets")
            messages = await admin_client.get("/messaging/conversations")
    finally:
        app.dependency_overrides.clear()

    assert tickets.status_code == 403
    assert messages.status_code == 403
