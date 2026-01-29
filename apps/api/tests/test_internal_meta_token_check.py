import pytest
from datetime import datetime, timedelta, timezone


@pytest.mark.asyncio
async def test_internal_token_check_tracks_oauth_expiry(client, db, monkeypatch, test_auth):
    from app.core.config import settings
    from app.core.encryption import encrypt_token
    from app.db.models import MetaOAuthConnection, SystemAlert
    from app.routers import internal as internal_router

    monkeypatch.setattr(settings, "INTERNAL_SECRET", "secret")

    class _TestSession:
        def __enter__(self):
            return db

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(internal_router, "SessionLocal", lambda: _TestSession())

    now = datetime.now(timezone.utc)
    expired_conn = MetaOAuthConnection(
        organization_id=test_auth.org.id,
        meta_user_id="expired-user",
        meta_user_name="Expired User",
        access_token_encrypted=encrypt_token("expired-token"),
        token_expires_at=now - timedelta(days=1),
        granted_scopes=["ads_management"],
        connected_by_user_id=test_auth.user.id,
        is_active=True,
    )
    expiring_conn = MetaOAuthConnection(
        organization_id=test_auth.org.id,
        meta_user_id="expiring-user",
        meta_user_name="Expiring User",
        access_token_encrypted=encrypt_token("expiring-token"),
        token_expires_at=now + timedelta(days=3),
        granted_scopes=["ads_management"],
        connected_by_user_id=test_auth.user.id,
        is_active=True,
    )

    db.add_all([expired_conn, expiring_conn])
    db.commit()

    response = await client.post(
        "/internal/scheduled/token-check",
        headers={"X-Internal-Secret": "secret"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["oauth_connections_checked"] == 2
    assert data["oauth_expired"] == 1
    assert data["oauth_expiring_soon"] == 1
    assert data["oauth_alerts_created"] == 2

    alerts = (
        db.query(SystemAlert)
        .filter(SystemAlert.organization_id == test_auth.org.id)
        .all()
    )
    assert len(alerts) >= 2
