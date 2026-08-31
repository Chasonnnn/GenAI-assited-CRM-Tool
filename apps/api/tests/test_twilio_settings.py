"""Public API contracts for organization-scoped Twilio messaging settings."""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User
from app.main import app
from app.services import session_service


@asynccontextmanager
async def _authed_client_for_role(db, organization_id, role: Role):
    user = User(
        id=uuid.uuid4(),
        email=f"twilio-{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Twilio Settings User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=organization_id,
            role=role.value,
        )
    )
    db.flush()
    token = create_session_token(
        user_id=user.id,
        org_id=organization_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=organization_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def test_get_twilio_settings_creates_two_disabled_purpose_routes(authed_client):
    response = await authed_client.get("/twilio/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["account_sid_masked"] is None
    assert payload["api_key_sid_masked"] is None
    assert payload["api_secret_configured"] is False
    assert payload["auth_token_configured"] is False
    assert payload["current_version"] == 1
    assert set(payload["routes"]) == {"operational", "promotional"}

    for purpose in ("operational", "promotional"):
        route = payload["routes"][purpose]
        assert route["purpose"] == purpose
        assert route["enabled"] is False
        assert route["messaging_service_sid_masked"] is None
        assert route["sender_phone_masked"] is None
        assert route["a2p_status"] == "unconfigured"
        assert route["advanced_opt_out_status"] == "unconfigured"
        assert route["consent_management_status"] == "unknown"
        assert route["inbound_webhook_url"].startswith("http://localhost:8000/webhooks/twilio/")
        assert route["inbound_webhook_url"].endswith("/inbound")
        assert route["status_callback_url"].endswith("/status")

    assert (
        payload["routes"]["operational"]["webhook_id"]
        != payload["routes"]["promotional"]["webhook_id"]
    )


async def test_patch_twilio_settings_keeps_credentials_write_only(authed_client):
    initial = (await authed_client.get("/twilio/settings")).json()
    account_sid = "AC" + "1" * 32
    api_key_sid = "SK" + "2" * 32
    api_secret = "secret-" + "3" * 32
    auth_token = "4" * 32

    response = await authed_client.patch(
        "/twilio/settings",
        json={
            "expected_version": initial["current_version"],
            "account_sid": account_sid,
            "api_key_sid": api_key_sid,
            "api_secret": api_secret,
            "auth_token": auth_token,
            "legal_messaging_brand": "EWI Surrogacy",
            "operational_disclosure": "Application and candidate-process text updates.",
            "promotional_disclosure": "Surrogacy opportunity and event text updates.",
            "sms_terms_url": "https://example.com/sms-terms",
            "privacy_policy_url": "https://example.com/privacy",
            "support_contact": "support@example.com",
            "expected_frequency": "Message frequency varies",
            "routes": {
                "operational": {
                    "messaging_service_sid": "MG" + "5" * 32,
                    "sender_phone_e164": "+14155550101",
                },
                "promotional": {
                    "messaging_service_sid": "MG" + "6" * 32,
                    "sender_phone_e164": "+14155550102",
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_sid_masked"] == "AC11...1111"
    assert payload["api_key_sid_masked"] == "SK22...2222"
    assert payload["api_secret_configured"] is True
    assert payload["auth_token_configured"] is True
    assert payload["legal_messaging_brand"] == "EWI Surrogacy"
    assert payload["routes"]["operational"]["messaging_service_sid_masked"] == "MG55...5555"
    assert payload["routes"]["operational"]["sender_phone_masked"] == "+1•••0101"
    assert payload["routes"]["promotional"]["sender_phone_masked"] == "+1•••0102"
    assert payload["current_version"] == initial["current_version"] + 1

    serialized = response.text
    for secret in (account_sid, api_key_sid, api_secret, auth_token):
        assert secret not in serialized

    persisted = await authed_client.get("/twilio/settings")
    assert persisted.status_code == 200
    assert persisted.json() == payload


async def test_patch_twilio_settings_rejects_administrator_provider_evidence(authed_client):
    initial = (await authed_client.get("/twilio/settings")).json()

    for field, value in (
        ("a2p_status", "approved"),
        ("advanced_opt_out_status", "verified"),
        ("consent_management_status", "available"),
        ("capability_evidence", {"sms": True, "mms": True}),
    ):
        response = await authed_client.patch(
            "/twilio/settings",
            json={
                "expected_version": initial["current_version"],
                "routes": {"operational": {field: value}},
            },
        )

        assert response.status_code == 422


async def test_patch_twilio_settings_rejects_stale_version(authed_client):
    initial = (await authed_client.get("/twilio/settings")).json()
    first = await authed_client.patch(
        "/twilio/settings",
        json={
            "expected_version": initial["current_version"],
            "legal_messaging_brand": "First writer",
        },
    )
    assert first.status_code == 200

    stale = await authed_client.patch(
        "/twilio/settings",
        json={
            "expected_version": initial["current_version"],
            "legal_messaging_brand": "Stale writer",
        },
    )

    assert stale.status_code == 409
    assert stale.json()["detail"] == "Version conflict: expected 1, got 2"
    current = (await authed_client.get("/twilio/settings")).json()
    assert current["legal_messaging_brand"] == "First writer"


async def test_phi_messaging_requires_eligible_edition_baa_and_compliance_approval(
    authed_client,
):
    initial = (await authed_client.get("/twilio/settings")).json()
    blocked = await authed_client.patch(
        "/twilio/settings",
        json={"expected_version": initial["current_version"], "phi_enabled": True},
    )

    assert blocked.status_code == 400
    assert blocked.json()["detail"] == (
        "PHI messaging requires a verified HIPAA-eligible Twilio edition, "
        "signed BAA, and compliance approval."
    )

    approved_at = datetime(2026, 7, 31, 20, 0, tzinfo=UTC).isoformat()
    allowed = await authed_client.patch(
        "/twilio/settings",
        json={
            "expected_version": initial["current_version"],
            "twilio_edition": "hipaa_eligible",
            "baa_verified_at": approved_at,
            "compliance_approved_at": approved_at,
            "phi_enabled": True,
        },
    )

    assert allowed.status_code == 200
    assert allowed.json()["phi_enabled"] is True


async def test_twilio_settings_test_validates_account_and_routes_without_sending(
    authed_client,
    monkeypatch,
):
    initial = (await authed_client.get("/twilio/settings")).json()
    configured = await authed_client.patch(
        "/twilio/settings",
        json={
            "expected_version": initial["current_version"],
            "account_sid": "AC" + "1" * 32,
            "api_key_sid": "SK" + "2" * 32,
            "api_secret": "api-secret",
        },
    )
    assert configured.status_code == 200

    from app.services import twilio_provider_service

    fetched_services: list[str] = []
    expected_webhooks = {
        "MG" + "3" * 32: initial["routes"]["operational"],
        "MG" + "4" * 32: initial["routes"]["promotional"],
    }

    class FakeServiceContext:
        def __init__(self, sid: str):
            self.sid = sid

        def fetch(self):
            fetched_services.append(self.sid)
            urls = expected_webhooks[self.sid]
            return type(
                "Service",
                (),
                {
                    "sid": self.sid,
                    "inbound_request_url": urls["inbound_webhook_url"],
                    "inbound_method": "POST",
                    "use_inbound_webhook_on_number": False,
                    "status_callback": urls["status_callback_url"],
                },
            )()

        @property
        def phone_numbers(self):
            return type(
                "PhoneNumbers",
                (),
                {
                    "list": lambda _self, **_kwargs: [
                        type(
                            "Sender",
                            (),
                            {"phone_number": "+14155550101", "capabilities": ["SMS", "MMS"]},
                        )()
                    ]
                },
            )()

        @property
        def us_app_to_person(self):
            return type(
                "Campaigns",
                (),
                {
                    "list": lambda _self, **_kwargs: [
                        type("Campaign", (), {"campaign_status": "VERIFIED"})()
                    ]
                },
            )()

    class FakeServices:
        def __call__(self, sid: str):
            return FakeServiceContext(sid)

    class FakeAccounts:
        def __call__(self, sid: str):
            return type(
                "AccountContext",
                (),
                {"fetch": lambda _self: type("Account", (), {"status": "active"})()},
            )()

    class FakeClient:
        def __init__(self, api_key_sid: str, api_secret: str, account_sid: str):
            assert api_key_sid.startswith("SK")
            assert api_secret == "api-secret"
            assert account_sid.startswith("AC")
            self.api = type("Api", (), {"accounts": FakeAccounts()})()
            self.messaging = type(
                "Messaging",
                (),
                {"v1": type("V1", (), {"services": FakeServices()})()},
            )()

        @property
        def messages(self):
            raise AssertionError("Credential checks must never access the Messages API")

    monkeypatch.setattr(twilio_provider_service, "Client", FakeClient)

    response = await authed_client.post(
        "/twilio/settings/test",
        json={
            "routes": {
                "operational": {
                    "messaging_service_sid": "MG" + "3" * 32,
                    "sender_phone_e164": "+14155550101",
                },
                "promotional": {
                    "messaging_service_sid": "MG" + "4" * 32,
                    "sender_phone_e164": "+14155550101",
                },
            }
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "account_status": "active",
        "twilio_edition": None,
        "capabilities": {
            "account_api": True,
            "messaging_services": True,
            "webhook_validation": False,
        },
        "route_capabilities": {
            purpose: {
                "service_verified": True,
                    "sender_in_pool": True,
                    "sender_type": "10dlc",
                    "sms": True,
                "mms": True,
                "a2p_status": "VERIFIED",
                "inbound_webhook_matches": True,
                "status_callback_matches": True,
            }
            for purpose in ("operational", "promotional")
        },
        "error": None,
        "warning": "Primary Auth Token is not configured; webhook validation is unavailable.",
    }
    assert fetched_services == ["MG" + "3" * 32, "MG" + "4" * 32]


async def test_empty_twilio_identifiers_explicitly_clear_stored_values(authed_client):
    initial = (await authed_client.get("/twilio/settings")).json()
    configured = await authed_client.patch(
        "/twilio/settings",
        json={
            "expected_version": initial["current_version"],
            "account_sid": "AC" + "1" * 32,
            "api_key_sid": "SK" + "2" * 32,
            "api_secret": "secret",
            "auth_token": "token",
            "routes": {
                "operational": {
                    "messaging_service_sid": "MG" + "3" * 32,
                    "sender_phone_e164": "+14155550101",
                }
            },
        },
    )
    assert configured.status_code == 200

    cleared = await authed_client.patch(
        "/twilio/settings",
        json={
            "expected_version": configured.json()["current_version"],
            "account_sid": "",
            "api_key_sid": "",
            "api_secret": "",
            "auth_token": "",
            "routes": {
                "operational": {
                    "messaging_service_sid": "",
                    "sender_phone_e164": "",
                }
            },
        },
    )

    assert cleared.status_code == 200
    payload = cleared.json()
    assert payload["account_sid_masked"] is None
    assert payload["api_key_sid_masked"] is None
    assert payload["api_secret_configured"] is False
    assert payload["auth_token_configured"] is False
    assert payload["routes"]["operational"]["messaging_service_sid_masked"] is None
    assert payload["routes"]["operational"]["sender_phone_masked"] is None


async def test_rotate_twilio_webhook_changes_only_selected_purpose(authed_client):
    initial = (await authed_client.get("/twilio/settings")).json()

    response = await authed_client.post(
        "/twilio/settings/rotate-webhook",
        json={
            "purpose": "operational",
            "expected_version": initial["current_version"],
        },
    )

    assert response.status_code == 200
    rotated = response.json()
    assert rotated["current_version"] == initial["current_version"] + 1
    assert (
        rotated["routes"]["operational"]["webhook_id"]
        != initial["routes"]["operational"]["webhook_id"]
    )
    assert (
        rotated["routes"]["promotional"]["webhook_id"]
        == initial["routes"]["promotional"]["webhook_id"]
    )
    assert rotated["routes"]["operational"]["inbound_webhook_url"].endswith(
        f"/{rotated['routes']['operational']['webhook_id']}/inbound"
    )


async def test_twilio_admin_apis_reject_non_admin_even_with_permission_grant(
    db,
    test_org,
    monkeypatch,
):
    from app.services import permission_service

    monkeypatch.setattr(permission_service, "check_permission", lambda *_args, **_kwargs: True)

    async with _authed_client_for_role(db, test_org.id, Role.CASE_MANAGER) as client:
        get_response = await client.get("/twilio/settings")
        patch_response = await client.patch(
            "/twilio/settings",
            json={"expected_version": 1, "legal_messaging_brand": "Denied"},
        )

    assert get_response.status_code == 403
    assert patch_response.status_code == 403
