import logging
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_HEADER
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User
from app.services import session_service


def _records(caplog, message: str):
    return [
        record
        for record in caplog.records
        if record.name == "app.ops" and record.message == message
    ]


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
    assert not hasattr(record, "error_code")
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


@pytest.mark.parametrize(
    "message,expected",
    [
        (
            "Google event changed; review before editing",
            "google_event_changed_review_before_editing",
        ),
        (
            "Reconnect the appointment owner's Google Calendar",
            "reconnect_the_appointment_owner_s_google_calendar",
        ),
        (
            "Cannot cancel appointment with status cancelled",
            "cannot_cancel_appointment_with_status_cancelled",
        ),
        ("Reason required when moving to Ready to Match", None),
        ("Invalid email jane.doe@example.com", None),
        ("Slot 3 is taken", None),
        ("Surrogate Jane Doe is already matched", None),
        ({"field": "value"}, None),
    ],
)
def test_static_error_code_logs_only_fixed_messages(message, expected):
    from app.core.structured_logging import static_error_code

    assert static_error_code(message) == expected


@pytest.mark.asyncio
async def test_client_error_log_records_the_error_code(authed_client, caplog):
    with caplog.at_level(logging.INFO, logger="app.ops"):
        response = await authed_client.post(f"/appointments/{uuid.uuid4()}/cancel", json={})

    assert response.status_code == 404
    assert response.json() == {"detail": "Appointment not found"}
    record = _records(caplog, "api_request_completed")[-1]
    assert record.status == 404
    assert record.error_code == "appointment_not_found"


@pytest.mark.asyncio
async def test_client_error_log_omits_user_supplied_template_name(authed_client, caplog):
    template = {
        "name": "john doe",
        "subject": "Test subject",
        "body": "<p>Test body</p>",
        "scope": "org",
    }
    created = await authed_client.post("/email-templates", json=template)
    assert created.status_code == 201

    with caplog.at_level(logging.INFO, logger="app.ops"):
        response = await authed_client.post("/email-templates", json=template)

    assert response.status_code == 409
    assert response.json() == {"detail": "An organization template named 'john doe' already exists"}
    record = _records(caplog, "api_request_completed")[-1]
    assert record.error_code == "http_409"
    assert "john doe" not in str(record.json_fields)
    assert "john_doe" not in str(record.json_fields)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "valid_csrf,expected_status,expected_code",
    [(True, 422, "http_422"), (False, 403, "http_403")],
    ids=["request-validation", "csrf-middleware"],
)
async def test_client_error_log_falls_back_without_http_exception(
    authed_client, caplog, valid_csrf, expected_status, expected_code
):
    if not valid_csrf:
        del authed_client.headers[CSRF_HEADER]

    with caplog.at_level(logging.INFO, logger="app.ops"):
        response = await authed_client.post("/appointments/not-a-uuid/cancel", json={})

    assert response.status_code == expected_status
    record = _records(caplog, "api_request_completed")[-1]
    assert record.status == expected_status
    assert record.error_code == expected_code
