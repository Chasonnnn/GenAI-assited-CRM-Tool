"""Security boundaries for independently authenticated ops CLI credentials."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.db.models import OpsCliToken


@pytest.fixture(autouse=True)
def reset_login_limits():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


async def _mint(authed_client, db, test_user):
    test_user.is_platform_admin = True
    db.commit()
    grant = (await authed_client.post("/platform/cli/login/start")).json()
    response = await authed_client.post(
        "/platform/cli/login/approve", json={"code": grant["user_code"]}
    )
    assert response.status_code == 200
    assert response.json() == {"approved": True}
    response = await authed_client.post(
        "/platform/cli/login/exchange", json={"device_code": grant["device_code"]}
    )
    assert response.status_code == 200
    from app.services.ops_cli_service import hash_token

    token = response.json()["token"]
    stored = db.query(OpsCliToken).filter_by(token_hash=hash_token(token)).one()
    return {"id": str(stored.id), "token": token}


@pytest.mark.asyncio
async def test_mint_requires_cookie_csrf_and_verified_mfa(client, authed_client, db, test_user):
    test_user.is_platform_admin = True
    db.commit()
    body = {"code": "ABCD-EFGH-JKLM"}
    assert (await client.post("/platform/cli/login/approve", json=body)).status_code == 403

    authed_client.headers.pop("X-CSRF-Token")
    assert (await authed_client.post("/platform/cli/login/approve", json=body)).status_code == 403


@pytest.mark.asyncio
async def test_mint_stores_only_hash_and_plaintext_is_once_displayed(authed_client, db, test_user):
    minted = await _mint(authed_client, db, test_user)
    stored = db.query(OpsCliToken).filter(OpsCliToken.id == minted["id"]).one()
    assert stored.token_hash != minted["token"]
    assert minted["token"] not in str(stored.__dict__)

    listed = (await authed_client.get("/platform/cli/tokens")).json()
    assert "token" not in listed[0]


@pytest.mark.asyncio
async def test_bearer_revalidates_lifecycle_user_and_scope(client, authed_client, db, test_user):
    minted = await _mint(authed_client, db, test_user)
    headers = {"Authorization": f"Bearer {minted['token']}"}
    assert (await authed_client.get("/platform/cli/whoami", headers=headers)).status_code == 200
    assert (await client.get("/platform/me", headers=headers)).status_code == 401

    stored = db.query(OpsCliToken).filter(OpsCliToken.id == minted["id"]).one()
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert (await authed_client.get("/platform/cli/whoami", headers=headers)).status_code == 401

    stored.expires_at = datetime.now(UTC) + timedelta(hours=1)
    stored.revoked_at = datetime.now(UTC)
    db.commit()
    assert (await authed_client.get("/platform/cli/whoami", headers=headers)).status_code == 401

    stored.revoked_at = None
    test_user.token_version += 1
    db.commit()
    assert (await authed_client.get("/platform/cli/whoami", headers=headers)).status_code == 401

    stored.token_version = test_user.token_version
    test_user.is_active = False
    db.commit()
    assert (await authed_client.get("/platform/cli/whoami", headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_production_bearer_rechecks_allowlist(authed_client, db, test_user, monkeypatch):
    minted = await _mint(authed_client, db, test_user)
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_EMAILS", "someone-else@example.com")
    stored = db.query(OpsCliToken).filter(OpsCliToken.id == minted["id"]).one()
    stored.environment = "production"
    db.commit()
    response = await authed_client.get(
        "/platform/cli/whoami",
        headers={"Authorization": f"Bearer {minted['token']}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unverified_mfa_cannot_mint_even_when_not_required(
    authed_client, db, test_user, test_org
):
    from app.core.deps import COOKIE_NAME
    from app.core.security import create_session_token
    from app.services import session_service

    test_user.is_platform_admin = True
    db.commit()
    token = create_session_token(
        test_user.id,
        test_org.id,
        "developer",
        test_user.token_version,
        mfa_verified=False,
        mfa_required=False,
    )
    session_service.create_session(
        db, user_id=test_user.id, org_id=test_org.id, token=token, request=None
    )
    authed_client.cookies.set(COOKIE_NAME, token)
    response = await authed_client.post(
        "/platform/cli/login/approve", json={"code": "ABCD-EFGH-JKLM"}
    )
    assert response.status_code == 403
    assert db.query(OpsCliToken).filter_by(user_id=test_user.id).count() == 0


@pytest.mark.asyncio
async def test_cross_user_credential_revoke_is_denied(authed_client, db, test_user):
    from uuid import uuid4

    from app.db.models import User
    from app.services import ops_cli_service

    test_user.is_platform_admin = True
    other = User(email=f"other-{uuid4()}@example.test", display_name="Other administrator")
    db.add(other)
    db.commit()
    credential, _ = ops_cli_service.mint_token(db, other)
    assert (await authed_client.delete(f"/platform/cli/tokens/{credential.id}")).status_code == 404
    assert (await authed_client.get("/platform/cli/tokens")).json() == []
    db.refresh(credential)
    assert credential.revoked_at is None


@pytest.mark.asyncio
async def test_revoke_only_owns_credentials(authed_client, db, test_user):
    import uuid

    minted = await _mint(authed_client, db, test_user)
    assert (await authed_client.delete(f"/platform/cli/tokens/{uuid.uuid4()}")).status_code == 404
    assert (await authed_client.delete(f"/platform/cli/tokens/{minted['id']}")).status_code == 204
    response = await authed_client.get(
        "/platform/cli/whoami", headers={"Authorization": f"Bearer {minted['token']}"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_is_device_bound_expiring_and_single_use(client, authed_client, db, test_user):
    from app.db.models.ops_cli import OpsCliLogin
    from app.services.ops_cli_service import hash_token

    test_user.is_platform_admin = True
    db.commit()
    grant = (await client.post("/platform/cli/login/start")).json()
    poll = {"device_code": grant["device_code"]}
    assert (await client.post("/platform/cli/login/exchange", json=poll)).json() == {
        "status": "pending"
    }
    assert (
        await client.post("/platform/cli/login/exchange", json={"device_code": "x" * 43})
    ).json() == {"status": "expired"}
    approval = {"code": grant["user_code"].lower()}
    assert (
        await authed_client.post("/platform/cli/login/approve", json=approval)
    ).status_code == 200
    assert (
        await authed_client.post("/platform/cli/login/approve", json=approval)
    ).status_code == 400
    response = await client.post("/platform/cli/login/exchange", json=poll)
    assert response.json()["status"] == "approved"
    assert response.headers["cache-control"] == "no-store"
    assert (await client.post("/platform/cli/login/exchange", json=poll)).json() == {
        "status": "expired"
    }
    stored = db.query(OpsCliLogin).filter_by(device_hash=hash_token(grant["device_code"])).one()
    assert grant["device_code"] not in str(stored.__dict__)
    assert stored.code_hash != grant["user_code"].replace("-", "")
    assert stored.consumed_at is not None
    assert (await authed_client.post("/platform/cli/tokens")).status_code == 405

    grant = (await client.post("/platform/cli/login/start")).json()
    stored = db.query(OpsCliLogin).filter_by(device_hash=hash_token(grant["device_code"])).one()
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert (
        await authed_client.post("/platform/cli/login/approve", json={"code": grant["user_code"]})
    ).status_code == 400
    assert (
        await client.post(
            "/platform/cli/login/exchange", json={"device_code": grant["device_code"]}
        )
    ).json() == {"status": "expired"}


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["inactive", "not_admin", "token_version", "environment"])
async def test_login_rechecks_access_after_approval(
    client, authed_client, db, test_user, change, monkeypatch
):
    test_user.is_platform_admin = True
    db.commit()
    grant = (await client.post("/platform/cli/login/start")).json()
    assert (
        await authed_client.post("/platform/cli/login/approve", json={"code": grant["user_code"]})
    ).status_code == 200
    if change == "inactive":
        test_user.is_active = False
    elif change == "not_admin":
        test_user.is_platform_admin = False
    elif change == "token_version":
        test_user.token_version += 1
    else:
        monkeypatch.setattr(settings, "ENV", "development")
    db.commit()
    assert (
        await client.post(
            "/platform/cli/login/exchange", json={"device_code": grant["device_code"]}
        )
    ).json() == {"status": "expired"}
    assert db.query(OpsCliToken).filter_by(user_id=test_user.id).count() == 0


@pytest.mark.asyncio
async def test_non_admin_cannot_approve_login(client, authed_client):
    grant = (await client.post("/platform/cli/login/start")).json()
    response = await authed_client.post(
        "/platform/cli/login/approve", json={"code": grant["user_code"]}
    )
    assert response.status_code == 403
    assert (
        await client.post(
            "/platform/cli/login/exchange", json={"device_code": grant["device_code"]}
        )
    ).json() == {"status": "pending"}


@pytest.mark.asyncio
async def test_login_start_is_rate_limited(client):
    for _ in range(10):
        assert (await client.post("/platform/cli/login/start")).status_code == 200
    assert (await client.post("/platform/cli/login/start")).status_code == 429
