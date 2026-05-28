import logging
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User
from app.services import session_service


def _records(caplog, message: str):
    return [record for record in caplog.records if record.name == "app.ops" and record.message == message]


@pytest.mark.asyncio
async def test_api_request_completed_log_has_user_context_without_raw_email(
    authed_client,
    caplog,
    test_org,
    test_user,
):
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    with caplog.at_level(logging.INFO, logger="app.ops"):
        response = await authed_client.get(
            "/settings/permissions/effective/me",
            headers={"X-Request-ID": "request-123", "traceparent": traceparent},
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-123"

    request_logs = _records(caplog, "api_request_completed")
    assert request_logs
    record = request_logs[-1]
    assert record.request_id == "request-123"
    assert record.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert record.user_id == str(test_user.id)
    assert record.user_email_hash
    assert record.org_id == str(test_org.id)
    assert record.org_slug == test_org.slug
    assert record.role == Role.DEVELOPER.value
    assert record.route == "/settings/permissions/effective/me"
    assert record.path == "/settings/permissions/effective/me"
    assert record.method == "GET"
    assert record.status == 200
    assert isinstance(record.latency_ms, int)
    assert test_user.email not in str(record.__dict__)


@pytest.mark.asyncio
async def test_permission_denied_log_includes_missing_permission_and_request_context(
    db,
    test_org,
    caplog,
):
    from app.main import app

    user = User(
        id=uuid.uuid4(),
        email="niki.permission@example.com",
        display_name="Niki Permission",
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
            role=Role.INTAKE_SPECIALIST.value,
        )
    )
    db.flush()

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role=Role.INTAKE_SPECIALIST.value,
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
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token},
        ) as client:
            with caplog.at_level(logging.INFO, logger="app.ops"):
                response = await client.get(
                    "/intended-parents?per_page=100",
                    headers={"X-Request-ID": "request-denied"},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403

    denied_logs = _records(caplog, "permission_denied")
    assert denied_logs
    denied = denied_logs[-1]
    assert denied.request_id == "request-denied"
    assert denied.user_id == str(user.id)
    assert denied.user_email_hash
    assert denied.org_id == str(test_org.id)
    assert denied.org_slug == test_org.slug
    assert denied.role == Role.INTAKE_SPECIALIST.value
    assert denied.status == 403
    assert denied.error_code == "permission_denied"
    assert denied.permission == "view_intended_parents"
    assert user.email not in str(denied.__dict__)

    request_logs = _records(caplog, "api_request_completed")
    assert request_logs[-1].status == 403
    assert request_logs[-1].error_code == "permission_denied"
    assert request_logs[-1].permission == "view_intended_parents"
