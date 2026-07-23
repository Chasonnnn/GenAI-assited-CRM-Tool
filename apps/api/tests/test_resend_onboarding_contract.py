"""Resend onboarding contract tests.

These tests intentionally validate credentials through the domains endpoint only.
They must never issue a real email send.
"""

from __future__ import annotations

import httpx
import pytest


class _FakeDomainsClient:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, *, headers: dict[str, str]):
        self.requests.append({"method": "GET", "url": url, "headers": headers})
        return self.response


class _FakeTimeoutDomainsClient(_FakeDomainsClient):
    async def get(self, url: str, *, headers: dict[str, str]):
        self.requests.append({"method": "GET", "url": url, "headers": headers})
        raise httpx.ReadTimeout(
            "raw timeout detail",
            request=httpx.Request("GET", url, headers=headers),
        )


@pytest.mark.asyncio
async def test_resend_domains_restricted_key_is_valid_but_permission_limited(db, monkeypatch):
    from app.services import resend_control_plane, resend_settings_service

    client = _FakeDomainsClient(
        httpx.Response(
            401,
            json={
                "name": "restricted_api_key",
                "message": "This API key is restricted to only send emails.",
            },
        )
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )

    result = await resend_settings_service.test_api_key("re_sending_access", db=db)

    assert result.valid is True
    assert result.error is None
    assert result.verified_domains == []
    assert result.permission_limited is True
    assert result.warning
    assert "cannot list domains" in result.warning.lower()
    assert client.requests == [
        {
            "method": "GET",
            "url": "https://api.resend.com/domains",
            "headers": {"Authorization": "Bearer re_sending_access"},
        }
    ]


@pytest.mark.asyncio
async def test_resend_domains_invalid_key_is_rejected(db, monkeypatch):
    from app.services import resend_control_plane, resend_settings_service

    client = _FakeDomainsClient(
        httpx.Response(
            403,
            json={"name": "invalid_api_key", "message": "API key is invalid."},
        )
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )

    result = await resend_settings_service.test_api_key("re_invalid", db=db)

    assert result.valid is False
    assert result.error == "Invalid API key"
    assert result.verified_domains == []
    assert result.permission_limited is False
    assert result.warning is None
    assert len(client.requests) == 1
    assert client.requests[0]["url"] == "https://api.resend.com/domains"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "name"),
    [
        (401, "missing_api_key"),
        (401, "unexpected_auth_error"),
        (403, "validation_error"),
        (403, None),
    ],
)
async def test_resend_domains_unknown_auth_errors_fail_closed(
    db,
    monkeypatch,
    status_code,
    name,
):
    from app.services import resend_control_plane, resend_settings_service

    payload = {"message": "Authentication failed"}
    if name is not None:
        payload["name"] = name
    client = _FakeDomainsClient(httpx.Response(status_code, json=payload))
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )

    result = await resend_settings_service.test_api_key("re_untrusted", db=db)

    assert result.valid is False
    assert result.error == "Invalid API key"
    assert result.verified_domains == []
    assert result.permission_limited is False
    assert result.warning is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 503])
async def test_resend_transient_api_status_preserves_safe_onboarding_error(
    db,
    monkeypatch,
    status_code,
):
    from app.services import resend_control_plane, resend_settings_service

    client = _FakeDomainsClient(
        httpx.Response(
            status_code,
            text="raw provider error must be discarded",
        )
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )

    result = await resend_settings_service.test_api_key("re_transient", db=db)

    assert result.valid is False
    assert result.error == f"Resend API error: {status_code}"
    assert result.permission_limited is False


@pytest.mark.asyncio
async def test_resend_timeout_preserves_safe_onboarding_error(db, monkeypatch):
    from app.services import resend_control_plane, resend_settings_service

    client = _FakeTimeoutDomainsClient(httpx.Response(200))
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )

    result = await resend_settings_service.test_api_key("re_timeout", db=db)

    assert result.valid is False
    assert result.error == "Connection timeout"
    assert result.permission_limited is False


@pytest.mark.asyncio
async def test_resend_domains_200_returns_only_verified_domains(db, monkeypatch):
    from app.services import resend_control_plane, resend_settings_service

    client = _FakeDomainsClient(
        httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "00000000-0000-4000-8000-000000000001",
                        "name": "first.example",
                        "status": "verified",
                    },
                    {
                        "id": "00000000-0000-4000-8000-000000000002",
                        "name": "pending.example",
                        "status": "pending",
                    },
                    {
                        "id": "00000000-0000-4000-8000-000000000003",
                        "name": "second.example",
                        "status": "verified",
                    },
                ]
            },
        )
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )

    result = await resend_settings_service.test_api_key("re_full_access", db=db)

    assert result.valid is True
    assert result.error is None
    assert result.verified_domains == ["first.example", "second.example"]
    assert result.permission_limited is False
    assert result.warning is None


@pytest.mark.asyncio
async def test_key_test_endpoint_exposes_permission_limited_warning(
    authed_client,
    monkeypatch,
):
    from app.services import resend_settings_service

    warning = (
        "Resend accepted the key, but it cannot list domains. "
        "Enter a domain already verified in Resend."
    )

    async def fake_test_api_key(_api_key: str, **_kwargs):
        return resend_settings_service.ResendKeyValidationResult(
            valid=True,
            error=None,
            verified_domains=[],
            permission_limited=True,
            warning=warning,
        )

    monkeypatch.setattr(resend_settings_service, "test_api_key", fake_test_api_key)

    response = await authed_client.post(
        "/resend/settings/test",
        json={"api_key": "re_sending_access"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "error": None,
        "verified_domains": [],
        "permission_limited": True,
        "warning": warning,
    }


@pytest.mark.asyncio
async def test_new_key_requires_explicit_verified_domain_and_never_chooses_first(
    authed_client,
    db,
    test_org,
    monkeypatch,
):
    from app.services import resend_settings_service

    async def fake_test_api_key(_api_key: str, **_kwargs):
        return resend_settings_service.ResendKeyValidationResult(
            valid=True,
            error=None,
            verified_domains=["first.example", "second.example"],
            permission_limited=False,
            warning=None,
        )

    monkeypatch.setattr(resend_settings_service, "test_api_key", fake_test_api_key)

    response = await authed_client.patch(
        "/resend/settings",
        json={
            "email_provider": "resend",
            "api_key": "re_full_access",
            "from_email": "sender@first.example",
        },
    )

    assert response.status_code == 400
    assert "verified domain is required" in response.json()["detail"].lower()

    settings = resend_settings_service.get_resend_settings(db, test_org.id)
    assert settings is None


@pytest.mark.asyncio
async def test_new_key_requires_explicit_from_email(
    authed_client,
    monkeypatch,
):
    from app.services import resend_settings_service

    async def fake_test_api_key(_api_key: str, **_kwargs):
        return resend_settings_service.ResendKeyValidationResult(
            valid=True,
            error=None,
            verified_domains=["verified.example"],
            permission_limited=False,
            warning=None,
        )

    monkeypatch.setattr(resend_settings_service, "test_api_key", fake_test_api_key)

    response = await authed_client.patch(
        "/resend/settings",
        json={
            "email_provider": "resend",
            "api_key": "re_full_access",
            "verified_domain": "verified.example",
        },
    )

    assert response.status_code == 400
    assert "from email is required" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_full_access_key_accepts_explicit_nonfirst_verified_domain(
    authed_client,
    db,
    test_org,
    monkeypatch,
):
    from app.services import resend_settings_service

    async def fake_test_api_key(_api_key: str, **_kwargs):
        return resend_settings_service.ResendKeyValidationResult(
            valid=True,
            error=None,
            verified_domains=["first.example", "second.example"],
            permission_limited=False,
            warning=None,
        )

    monkeypatch.setattr(resend_settings_service, "test_api_key", fake_test_api_key)

    response = await authed_client.patch(
        "/resend/settings",
        json={
            "email_provider": "resend",
            "api_key": "re_full_access",
            "verified_domain": "second.example",
            "from_email": "sender@second.example",
        },
    )

    assert response.status_code == 200
    assert response.json()["verified_domain"] == "second.example"
    assert "api_key" not in response.json()
    assert "re_full_access" not in response.text

    stored = resend_settings_service.get_resend_settings(db, test_org.id)
    assert stored is not None
    assert stored.verified_domain == "second.example"
    assert resend_settings_service.decrypt_api_key(stored.api_key_encrypted) == "re_full_access"


@pytest.mark.asyncio
async def test_full_access_key_rejects_domain_outside_verified_list(
    authed_client,
    monkeypatch,
):
    from app.services import resend_settings_service

    async def fake_test_api_key(_api_key: str, **_kwargs):
        return resend_settings_service.ResendKeyValidationResult(
            valid=True,
            error=None,
            verified_domains=["verified.example"],
            permission_limited=False,
            warning=None,
        )

    monkeypatch.setattr(resend_settings_service, "test_api_key", fake_test_api_key)

    response = await authed_client.patch(
        "/resend/settings",
        json={
            "email_provider": "resend",
            "api_key": "re_full_access",
            "verified_domain": "unverified.example",
            "from_email": "sender@unverified.example",
        },
    )

    assert response.status_code == 400
    assert "not in the verified domains" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_permission_limited_key_accepts_explicit_domain_with_matching_sender(
    authed_client,
    db,
    test_org,
    monkeypatch,
):
    from app.services import resend_settings_service

    async def fake_test_api_key(_api_key: str, **_kwargs):
        return resend_settings_service.ResendKeyValidationResult(
            valid=True,
            error=None,
            verified_domains=[],
            permission_limited=True,
            warning="Domain listing is unavailable for this key.",
        )

    monkeypatch.setattr(resend_settings_service, "test_api_key", fake_test_api_key)

    response = await authed_client.patch(
        "/resend/settings",
        json={
            "email_provider": "resend",
            "api_key": "re_sending_access",
            "verified_domain": "explicit.example",
            "from_email": "sender@explicit.example",
        },
    )

    assert response.status_code == 200
    assert response.json()["verified_domain"] == "explicit.example"

    stored = resend_settings_service.get_resend_settings(db, test_org.id)
    assert stored is not None
    assert stored.verified_domain == "explicit.example"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "identity_update",
    [
        {
            "verified_domain": "new.example",
            "from_email": "sender@new.example",
        },
        {"from_email": "other@verified.example"},
    ],
)
async def test_sender_identity_change_requires_key_revalidation_in_same_request(
    authed_client,
    db,
    test_org,
    test_user,
    monkeypatch,
    identity_update,
):
    from app.services import resend_settings_service

    settings = resend_settings_service.update_resend_settings(
        db,
        test_org.id,
        test_user.id,
        email_provider="resend",
        api_key="re_existing",
        verified_domain="verified.example",
        from_email="sender@verified.example",
    )
    original_version = settings.current_version

    async def unexpected_validation(_api_key: str, **_kwargs):
        raise AssertionError("stored credentials must not be silently reused")

    monkeypatch.setattr(
        resend_settings_service,
        "test_api_key",
        unexpected_validation,
    )

    response = await authed_client.patch(
        "/resend/settings",
        json={
            **identity_update,
            "expected_version": original_version,
        },
    )

    assert response.status_code == 400
    assert "api key" in response.json()["detail"].lower()
    assert "revalid" in response.json()["detail"].lower()

    db.expire_all()
    stored = resend_settings_service.get_resend_settings(db, test_org.id)
    assert stored is not None
    assert stored.verified_domain == "verified.example"
    assert stored.from_email == "sender@verified.example"
    assert stored.current_version == original_version
