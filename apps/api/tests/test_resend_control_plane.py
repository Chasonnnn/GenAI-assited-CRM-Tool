"""Boundary tests for admitted, sanitized Resend control-plane reads."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import uuid

import httpx
import pytest


class _FakeGetClient:
    def __init__(self, responses: list[httpx.Response]):
        self._responses = iter(responses)
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, *, headers: dict[str, str]):
        self.requests.append({"method": "GET", "url": url, "headers": headers})
        return next(self._responses)


class _TimeoutGetClient(_FakeGetClient):
    async def get(self, url: str, *, headers: dict[str, str]):
        self.requests.append({"method": "GET", "url": url, "headers": headers})
        request = httpx.Request("GET", url, headers=headers)
        raise httpx.ReadTimeout("raw timeout detail", request=request)


@pytest.mark.asyncio
async def test_list_domains_reserves_admission_and_discards_provider_secrets(
    db,
    monkeypatch,
):
    from app.db.models import EmailProviderAdmission
    from app.services import resend_control_plane

    domain_id = str(uuid.uuid4())
    fake_client = _FakeGetClient(
        [
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": domain_id,
                            "name": "Example.COM",
                            "status": "verified",
                            "region": "us-east-1",
                            "capabilities": {
                                "sending": "enabled",
                                "receiving": "disabled",
                            },
                            "records": [
                                {
                                    "name": "resend._domainkey",
                                    "value": "must-never-leave-provider-boundary",
                                }
                            ],
                            "tracking_subdomain": "links",
                        }
                    ]
                },
            )
        ]
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )
    admission_identity = f"credential:test-control-plane-{uuid.uuid4()}"

    result = await resend_control_plane.ResendControlPlaneClient(
        db=db,
        api_key="re_synthetic",
        admission_identity=admission_identity,
    ).list_domains()

    assert result.status is resend_control_plane.ResendControlPlaneStatus.OK
    assert result.value is not None
    assert [asdict(domain) for domain in result.value] == [
        {
            "id": domain_id,
            "name": "example.com",
            "status": "verified",
            "sending": "enabled",
            "receiving": "disabled",
        }
    ]
    assert fake_client.requests == [
        {
            "method": "GET",
            "url": "https://api.resend.com/domains",
            "headers": {"Authorization": "Bearer re_synthetic"},
        }
    ]
    assert (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == admission_identity,
        )
        .one_or_none()
        is not None
    )


@pytest.mark.asyncio
async def test_domain_sanitizer_maps_untrusted_provider_enums_to_unknown(
    db,
    monkeypatch,
):
    from app.services import resend_control_plane

    domain_id = str(uuid.uuid4())
    fake_client = _FakeGetClient(
        [
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": domain_id,
                            "name": "example.com",
                            "status": ["unexpected"],
                            "capabilities": {
                                "sending": {"raw": "value"},
                                "receiving": 1,
                            },
                        }
                    ]
                },
            )
        ]
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )

    result = await resend_control_plane.ResendControlPlaneClient(
        db=db,
        api_key="re_synthetic",
        admission_identity=f"credential:untrusted-enums-{uuid.uuid4()}",
    ).list_domains()

    assert result.value is not None
    assert [asdict(domain) for domain in result.value] == [
        {
            "id": domain_id,
            "name": "example.com",
            "status": "unknown",
            "sending": "unknown",
            "receiving": "unknown",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_status", "expected_provider_status"),
    [
        (
            httpx.Response(
                401,
                json={
                    "name": "restricted_api_key",
                    "message": "remote detail must be discarded",
                },
            ),
            "limited",
            None,
        ),
        (
            httpx.Response(
                403,
                json={"name": "invalid_api_key", "message": "secret remote detail"},
            ),
            "fail",
            None,
        ),
        (
            httpx.Response(
                429,
                json={"name": "rate_limit_exceeded", "message": "try again later"},
            ),
            "unknown",
            429,
        ),
        (
            httpx.Response(
                503,
                text="provider body must never leave the boundary",
            ),
            "unknown",
            503,
        ),
    ],
)
async def test_control_plane_normalizes_provider_failures_without_remote_detail(
    db,
    monkeypatch,
    response,
    expected_status,
    expected_provider_status,
):
    from app.services import resend_control_plane

    fake_client = _FakeGetClient([response])
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )

    result = await resend_control_plane.ResendControlPlaneClient(
        db=db,
        api_key="re_synthetic",
        admission_identity=f"credential:failure-{uuid.uuid4()}",
    ).list_domains()

    assert result == resend_control_plane.ResendControlPlaneResult(
        status=resend_control_plane.ResendControlPlaneStatus(expected_status),
        provider_status_code=expected_provider_status,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("retry_after", "expected_seconds"),
    [
        ("17", 17),
        ("-5", None),
        ("not-a-number", None),
        ("999999", 3600),
    ],
)
async def test_rate_limit_normalizes_only_bounded_numeric_retry_after(
    db,
    monkeypatch,
    retry_after,
    expected_seconds,
):
    from app.services import resend_control_plane

    fake_client = _FakeGetClient(
        [
            httpx.Response(
                429,
                headers={
                    "Retry-After": retry_after,
                    "X-Provider-Internal": "must-not-cross-boundary",
                },
                json={
                    "name": "rate_limit_exceeded",
                    "message": "raw provider detail",
                },
            )
        ]
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )

    result = await resend_control_plane.ResendControlPlaneClient(
        db=db,
        api_key="re_synthetic",
        admission_identity=f"credential:retry-after-{uuid.uuid4()}",
    ).list_domains()

    assert result.status is resend_control_plane.ResendControlPlaneStatus.UNKNOWN
    assert result.provider_status_code == 429
    assert result.retry_after_seconds == expected_seconds


@pytest.mark.asyncio
async def test_rate_limit_defers_the_shared_admission_lane_by_bounded_retry_after(
    db,
    monkeypatch,
):
    from app.db.models import EmailProviderAdmission
    from app.services import resend_control_plane

    admission_identity = f"team:{'a' * 64}"
    fake_client = _FakeGetClient(
        [
            httpx.Response(
                429,
                headers={"Retry-After": "999999"},
                json={
                    "name": "rate_limit_exceeded",
                    "message": "raw provider detail",
                },
            )
        ]
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )
    before_request = datetime.now(timezone.utc)

    result = await resend_control_plane.ResendControlPlaneClient(
        db=db,
        api_key="re_synthetic",
        admission_identity=admission_identity,
    ).list_domains()

    after_request = datetime.now(timezone.utc)
    assert result.retry_after_seconds == 3600
    shared_admission = (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == admission_identity,
        )
        .one()
    )
    assert shared_admission.next_slot_at >= before_request + timedelta(seconds=3599)
    assert shared_admission.next_slot_at <= after_request + timedelta(seconds=3600)


@pytest.mark.asyncio
async def test_rate_limit_without_retry_after_applies_safe_shared_cooldown(
    db,
    monkeypatch,
):
    from app.db.models import EmailProviderAdmission
    from app.services import resend_control_plane

    admission_identity = f"team:{'b' * 64}"
    fake_client = _FakeGetClient(
        [
            httpx.Response(
                429,
                json={
                    "name": "rate_limit_exceeded",
                    "message": "raw provider detail",
                },
            )
        ]
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )
    before_request = datetime.now(timezone.utc)

    result = await resend_control_plane.ResendControlPlaneClient(
        db=db,
        api_key="re_synthetic",
        admission_identity=admission_identity,
    ).list_domains()

    after_request = datetime.now(timezone.utc)
    assert result.retry_after_seconds is None
    shared_admission = (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == admission_identity,
        )
        .one()
    )
    # PostgreSQL and the application clock can differ by a few milliseconds.
    assert shared_admission.next_slot_at >= before_request + timedelta(milliseconds=900)
    assert shared_admission.next_slot_at <= after_request + timedelta(seconds=1)


@pytest.mark.asyncio
async def test_control_plane_normalizes_timeout_as_unknown_after_admission(
    db,
    monkeypatch,
):
    from app.db.models import EmailProviderAdmission
    from app.services import resend_control_plane

    client = _TimeoutGetClient([])
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )
    admission_identity = f"credential:timeout-{uuid.uuid4()}"

    result = await resend_control_plane.ResendControlPlaneClient(
        db=db,
        api_key="re_synthetic",
        admission_identity=admission_identity,
    ).list_webhooks(expected_endpoint="https://private.example.test/resend")

    assert result == resend_control_plane.ResendControlPlaneResult(
        status=resend_control_plane.ResendControlPlaneStatus.UNKNOWN,
        reason=resend_control_plane.ResendControlPlaneReason.TIMEOUT,
    )
    assert (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == admission_identity,
        )
        .one_or_none()
        is not None
    )


@pytest.mark.asyncio
async def test_get_domain_is_admitted_and_returns_tracking_state_without_dns_values(
    db,
    monkeypatch,
):
    from app.db.models import EmailProviderAdmission
    from app.services import resend_control_plane

    domain_id = str(uuid.uuid4())
    fake_client = _FakeGetClient(
        [
            httpx.Response(
                200,
                json={
                    "id": domain_id,
                    "name": "mail.example.com",
                    "status": "partially_verified",
                    "region": "eu-west-1",
                    "open_tracking": True,
                    "click_tracking": False,
                    "tracking_subdomain": "click",
                    "capabilities": {
                        "sending": "enabled",
                        "receiving": "disabled",
                    },
                    "records": [
                        {
                            "record": "SPF",
                            "name": "resend._domainkey",
                            "status": "verified",
                            "value": "dns-value-must-be-discarded",
                        },
                        {
                            "record": "DKIM",
                            "name": "send",
                            "status": "pending",
                            "value": "second-dns-value-must-be-discarded",
                        },
                    ],
                },
            )
        ]
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )
    admission_identity = f"credential:domain-detail-{uuid.uuid4()}"

    result = await resend_control_plane.ResendControlPlaneClient(
        db=db,
        api_key="re_synthetic",
        admission_identity=admission_identity,
    ).get_domain(domain_id)

    assert result.status is resend_control_plane.ResendControlPlaneStatus.OK
    assert result.value is not None
    assert asdict(result.value) == {
        "id": domain_id,
        "name": "mail.example.com",
        "status": "partially_verified",
        "sending": "enabled",
        "receiving": "disabled",
        "open_tracking": True,
        "click_tracking": False,
        "spf_status": "verified",
        "dkim_status": "pending",
    }
    assert fake_client.requests == [
        {
            "method": "GET",
            "url": f"https://api.resend.com/domains/{domain_id}",
            "headers": {"Authorization": "Bearer re_synthetic"},
        }
    ]
    assert (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == admission_identity,
        )
        .one_or_none()
        is not None
    )


@pytest.mark.asyncio
async def test_list_webhooks_is_admitted_and_never_returns_endpoint_or_secret(
    db,
    monkeypatch,
):
    from app.db.models import EmailProviderAdmission
    from app.services import resend_control_plane

    webhook_id = str(uuid.uuid4())
    fake_client = _FakeGetClient(
        [
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": webhook_id,
                            "status": "enabled",
                            "endpoint": "https://private.example.test/resend",
                            "events": [
                                "email.sent",
                                "email.delivered",
                                "provider.future.untrusted",
                            ],
                            "signing_secret": "whsec_must_never_cross_boundary",
                        }
                    ]
                },
            )
        ]
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )
    admission_identity = f"credential:webhook-list-{uuid.uuid4()}"

    result = await resend_control_plane.ResendControlPlaneClient(
        db=db,
        api_key="re_synthetic",
        admission_identity=admission_identity,
    ).list_webhooks(expected_endpoint="https://private.example.test/resend")

    assert result.status is resend_control_plane.ResendControlPlaneStatus.OK
    assert result.value is not None
    assert [asdict(webhook) for webhook in result.value] == [
        {
            "id": webhook_id,
            "status": "enabled",
            "events": ("email.sent", "email.delivered"),
            "endpoint_matches": True,
        }
    ]
    assert fake_client.requests == [
        {
            "method": "GET",
            "url": "https://api.resend.com/webhooks",
            "headers": {"Authorization": "Bearer re_synthetic"},
        }
    ]
    assert (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == admission_identity,
        )
        .one_or_none()
        is not None
    )


@pytest.mark.asyncio
async def test_onboarding_key_validation_uses_exact_credential_admission(
    db,
    monkeypatch,
):
    from app.db.models import EmailProviderAdmission
    from app.services import resend_control_plane, resend_settings_service

    domain_id = str(uuid.uuid4())
    fake_client = _FakeGetClient(
        [
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": domain_id,
                            "name": "verified.example",
                            "status": "verified",
                            "capabilities": {
                                "sending": "enabled",
                                "receiving": "disabled",
                            },
                        }
                    ]
                },
            )
        ]
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )
    before = datetime.now(timezone.utc)

    result = await resend_settings_service.test_api_key("re_unclassified", db=db)

    assert result == resend_settings_service.ResendKeyValidationResult(
        valid=True,
        error=None,
        verified_domains=["verified.example"],
        permission_limited=False,
        warning=None,
    )
    admission = (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id
            == ("credential:c0265efcb3e9e3a8b918d4a6086561bea03c87b8691d90e814bed7383e173545"),
        )
        .one()
    )
    assert admission.next_slot_at >= before
    assert (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == "resend:unclassified",
        )
        .one_or_none()
        is None
    )
    assert fake_client.requests == [
        {
            "method": "GET",
            "url": "https://api.resend.com/domains",
            "headers": {"Authorization": "Bearer re_unclassified"},
        }
    ]


@pytest.mark.asyncio
async def test_onboarding_endpoint_routes_validation_through_admitted_get(
    authed_client,
    db,
    monkeypatch,
):
    from app.db.models import EmailProviderAdmission
    from app.services import resend_control_plane

    fake_client = _FakeGetClient(
        [
            httpx.Response(
                401,
                json={
                    "name": "restricted_api_key",
                    "message": "Sending-only key",
                },
            )
        ]
    )
    monkeypatch.setattr(
        resend_control_plane.httpx,
        "AsyncClient",
        lambda **_kwargs: fake_client,
    )

    response = await authed_client.post(
        "/resend/settings/test",
        json={"api_key": "re_endpoint_validation"},
    )

    assert response.status_code == 200
    assert response.json()["permission_limited"] is True
    assert (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id
            == ("credential:090277662d404b6fe62e46f813e59f8bc54fb8bacf6c451faf125734cbf8c8a4"),
        )
        .one_or_none()
        is not None
    )
    assert (
        db.query(EmailProviderAdmission)
        .filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == "resend:unclassified",
        )
        .one_or_none()
        is None
    )
    assert [request["method"] for request in fake_client.requests] == ["GET"]
