from datetime import datetime, timedelta, timezone
import uuid

import pytest

from app.core.config import settings
from app.core.deps import COOKIE_NAME


@pytest.mark.asyncio
async def test_support_session_create_requires_platform_admin(authed_client, test_org):
    response = await authed_client.post(
        "/platform/support-sessions",
        json={
            "org_id": str(test_org.id),
            "role": "developer",
            "reason_code": "onboarding_setup",
            "reason_text": "assist setup",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_support_session_create_rejects_invalid_role(authed_client, db, test_user, test_org):
    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.post(
        "/platform/support-sessions",
        json={
            "org_id": str(test_org.id),
            "role": "not-a-role",
            "reason_code": "onboarding_setup",
            "reason_text": "assist setup",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_support_session_create_rejects_invalid_reason_code(authed_client, db, test_user, test_org):
    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.post(
        "/platform/support-sessions",
        json={
            "org_id": str(test_org.id),
            "role": "developer",
            "reason_code": "bad_reason",
            "reason_text": "assist setup",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_support_session_rejects_read_only_when_disabled(authed_client, db, test_user, test_org):
    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.post(
        "/platform/support-sessions",
        json={
            "org_id": str(test_org.id),
            "role": "developer",
            "reason_code": "onboarding_setup",
            "reason_text": "assist setup",
            "mode": "read_only",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_support_session_create_sets_role_and_org_override(
    authed_client, db, test_user, test_org
):
    from app.db.models import Organization

    test_user.is_platform_admin = True
    db.commit()

    other_org = Organization(
        id=uuid.uuid4(),
        name="Support Target Org",
        slug=f"support-org-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()

    response = await authed_client.post(
        "/platform/support-sessions",
        json={
            "org_id": str(other_org.id),
            "role": "developer",
            "reason_code": "onboarding_setup",
            "reason_text": "assist setup",
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert data["org_id"] == str(other_org.id)
    assert data["role"] == "developer"
    assert data["mode"] == "write"
    assert data["reason_code"] == "onboarding_setup"

    expires_at = data.get("expires_at")
    assert expires_at
    expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    assert now + timedelta(minutes=59) <= expires_dt <= now + timedelta(minutes=61)

    token = response.cookies.get(COOKIE_NAME) or authed_client.cookies.get(COOKIE_NAME)
    assert token

    me = await authed_client.get("/auth/me")
    assert me.status_code == 200
    me_data = me.json()
    assert me_data["org_id"] == str(other_org.id)
    assert me_data["role"] == "developer"


@pytest.mark.asyncio
async def test_support_session_revocation_blocks_access(
    authed_client, db, test_user, test_org
):
    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.post(
        "/platform/support-sessions",
        json={
            "org_id": str(test_org.id),
            "role": "admin",
            "reason_code": "onboarding_setup",
            "reason_text": "assist setup",
        },
    )
    assert response.status_code == 200

    session_id = response.json()["id"]

    revoke = await authed_client.post(f"/platform/support-sessions/{session_id}/revoke")
    assert revoke.status_code == 200

    me = await authed_client.get("/auth/me")
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_support_session_admin_log_excludes_reason_text(
    authed_client, db, test_user, test_org
):
    from app.db.models import AdminActionLog

    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.post(
        "/platform/support-sessions",
        json={
            "org_id": str(test_org.id),
            "role": "developer",
            "reason_code": "billing_help",
            "reason_text": "Customer asked about invoice history",
        },
    )
    assert response.status_code == 200
    session_id = response.json()["id"]

    log = (
        db.query(AdminActionLog)
        .filter(AdminActionLog.action == "support_session.create")
        .order_by(AdminActionLog.created_at.desc())
        .first()
    )
    assert log is not None
    assert log.metadata_ is not None
    assert log.metadata_.get("support_session_id") == session_id
    assert log.metadata_.get("role") == "developer"
    assert log.metadata_.get("mode") == "write"
    assert log.metadata_.get("reason_code") == "billing_help"
    assert "reason_text" not in log.metadata_


@pytest.mark.asyncio
async def test_support_session_read_only_blocks_mutations(authed_client, db, test_user, test_org):
    test_user.is_platform_admin = True
    db.commit()

    original_allow_read_only = settings.SUPPORT_SESSION_ALLOW_READ_ONLY
    settings.SUPPORT_SESSION_ALLOW_READ_ONLY = True
    try:
        response = await authed_client.post(
            "/platform/support-sessions",
            json={
                "org_id": str(test_org.id),
                "role": "developer",
                "reason_code": "bug_repro",
                "reason_text": "validate read-only",
                "mode": "read_only",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["mode"] == "read_only"

        create_res = await authed_client.post(
            "/surrogates",
            json={
                "full_name": "Read Only Attempt",
                "email": f"readonly-{uuid.uuid4().hex[:8]}@example.com",
            },
        )
        assert create_res.status_code == 403, create_res.text
        assert "read-only" in create_res.text.lower()

        logout_res = await authed_client.post("/auth/logout")
        assert logout_res.status_code == 200, logout_res.text

        me = await authed_client.get("/auth/me")
        assert me.status_code == 401, me.text
    finally:
        settings.SUPPORT_SESSION_ALLOW_READ_ONLY = original_allow_read_only
