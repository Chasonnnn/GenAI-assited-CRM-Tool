from http.cookies import SimpleCookie

import pyotp
import pytest

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME
from app.core.security import create_session_token
from app.db.enums import Role
from app.services import session_service


def _get_cookie_value(response, cookie_name: str) -> str:
    cookie = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookie.load(header)
    morsel = cookie.get(cookie_name)
    assert morsel, f"Missing cookie {cookie_name}"
    return morsel.value


@pytest.mark.asyncio
async def test_mfa_complete_creates_session_for_upgraded_token(client, db, test_user, test_org):
    secret = "JBSWY3DPEHPK3PXP"
    test_user.mfa_enabled = True
    test_user.totp_secret = secret
    db.commit()

    old_token = create_session_token(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.DEVELOPER.value,
        token_version=test_user.token_version,
        mfa_verified=False,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=test_user.id, org_id=test_org.id, token=old_token)

    csrf = generate_csrf_token()
    client.cookies.set(COOKIE_NAME, old_token)
    client.cookies.set(CSRF_COOKIE_NAME, csrf)

    code = pyotp.TOTP(secret).now()
    res = await client.post(
        "/mfa/complete",
        json={"code": code},
        headers={CSRF_HEADER: csrf},
    )
    assert res.status_code == 200

    new_token = _get_cookie_value(res, COOKIE_NAME)
    assert new_token != old_token

    # The upgraded token must be registered in the session table, otherwise
    # subsequent requests will 401 as "Session revoked or expired".
    new_hash = session_service.hash_token(new_token)
    assert session_service.get_session_by_token_hash(db, new_hash) is not None


@pytest.mark.asyncio
async def test_duo_callback_creates_session_for_upgraded_token(
    client, db, test_user, test_org, monkeypatch
):
    from app.services import duo_service

    monkeypatch.setattr(duo_service, "is_available", lambda: True)

    def fake_verify_callback(*, code, state, expected_state, username, redirect_uri=None):
        assert code == "duo-code"
        assert state == expected_state
        assert username == test_user.email
        assert redirect_uri  # should be derived from FRONTEND/OPS url
        return True, {"sub": "duo-subject"}

    monkeypatch.setattr(duo_service, "verify_callback", fake_verify_callback)

    old_token = create_session_token(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.DEVELOPER.value,
        token_version=test_user.token_version,
        mfa_verified=False,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=test_user.id, org_id=test_org.id, token=old_token)

    csrf = generate_csrf_token()
    client.cookies.set(COOKIE_NAME, old_token)
    client.cookies.set(CSRF_COOKIE_NAME, csrf)

    res = await client.post(
        "/mfa/duo/callback?expected_state=state123&return_to=ops",
        json={"code": "duo-code", "state": "state123"},
        headers={CSRF_HEADER: csrf},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True

    new_token = _get_cookie_value(res, COOKIE_NAME)
    assert new_token != old_token

    new_hash = session_service.hash_token(new_token)
    assert session_service.get_session_by_token_hash(db, new_hash) is not None
