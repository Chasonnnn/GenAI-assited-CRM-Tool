from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_platform_reset_mfa_requires_admin(authed_client, db, test_user, test_org):
    from app.db.models import Membership

    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == test_user.id,
            Membership.organization_id == test_org.id,
        )
        .first()
    )
    assert membership is not None

    response = await authed_client.post(
        f"/platform/orgs/{test_org.id}/members/{membership.id}/mfa/reset"
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_platform_reset_mfa_clears_fields_and_revokes_sessions(
    authed_client, db, test_user, test_org
):
    from app.db.models import Membership, UserSession, AdminActionLog
    from app.services import mfa_service

    test_user.is_platform_admin = True
    now = datetime.now(timezone.utc)
    test_user.mfa_enabled = True
    test_user.totp_secret = "JBSWY3DPEHPK3PXP"
    test_user.totp_enabled_at = now
    test_user.duo_user_id = "duo-test-user"
    test_user.duo_enrolled_at = now
    test_user.mfa_recovery_codes = mfa_service.hash_recovery_codes(["ABCD1234"])
    test_user.mfa_required_at = now
    db.commit()

    before_token_version = test_user.token_version

    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == test_user.id,
            Membership.organization_id == test_org.id,
        )
        .first()
    )
    assert membership is not None

    response = await authed_client.post(
        f"/platform/orgs/{test_org.id}/members/{membership.id}/mfa/reset"
    )
    assert response.status_code == 200

    db.refresh(test_user)
    assert test_user.mfa_enabled is False
    assert test_user.totp_secret is None
    assert test_user.totp_enabled_at is None
    assert test_user.duo_user_id is None
    assert test_user.duo_enrolled_at is None
    assert test_user.mfa_recovery_codes is None
    assert test_user.token_version == before_token_version + 1

    session_count = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == test_user.id,
            UserSession.organization_id == test_org.id,
        )
        .count()
    )
    assert session_count == 0

    log = (
        db.query(AdminActionLog)
        .filter(
            AdminActionLog.action == "member.mfa.reset",
            AdminActionLog.target_organization_id == test_org.id,
            AdminActionLog.target_user_id == test_user.id,
        )
        .first()
    )
    assert log is not None
