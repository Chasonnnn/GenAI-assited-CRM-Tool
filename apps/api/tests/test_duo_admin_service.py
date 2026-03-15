import base64
import hashlib
import hmac
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import quote

import httpx
import pytest


def _canonical_query(params: dict[str, str]) -> str:
    items = sorted((key, value) for key, value in params.items() if value is not None)
    return "&".join(
        f"{quote(str(key), safe='~')}={quote(str(value), safe='~')}" for key, value in items
    )


def _enable_duo(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DUO_CLIENT_ID", "DIXXXXXXXXXXXXXXX")
    monkeypatch.setattr(settings, "DUO_CLIENT_SECRET", "secret")
    monkeypatch.setattr(settings, "DUO_API_HOST", "api-85d6198d.duosecurity.com")


def test_duo_admin_client_signs_and_sanitizes_requests(monkeypatch):
    from app.core.config import settings
    from app.services import duo_admin_service

    monkeypatch.setattr(
        settings,
        "DUO_ADMIN_INTEGRATION_KEY",
        '"DIXXXXXXXXXXXXXXXXXX"' + chr(0x200B) + " \n",
    )
    monkeypatch.setattr(settings, "DUO_ADMIN_SECRET_KEY", "secret-admin-key\n")
    monkeypatch.setattr(
        settings,
        "DUO_ADMIN_API_HOST",
        "https://api-85d6198d.duosecurity.com/\n",
    )
    monkeypatch.setattr(settings, "DUO_ADMIN_TIMEOUT_SECONDS", 7.5)

    fixed_now = datetime(2026, 3, 9, 21, 30, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now.astimezone(tz or timezone.utc)

    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, *, base_url: str, timeout: float):
            captured["base_url"] = base_url
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method: str, path: str, *, params=None, data=None, headers=None):
            captured["method"] = method
            captured["path"] = path
            captured["params"] = params
            captured["data"] = data
            captured["headers"] = headers
            return httpx.Response(
                200,
                json={
                    "stat": "OK",
                    "response": [
                        {
                            "user_id": "DUUSER1",
                            "username": "cathyf@ewifamilyglobal.com",
                            "is_enrolled": False,
                        }
                    ],
                },
            )

    monkeypatch.setattr(duo_admin_service, "datetime", FixedDateTime)
    monkeypatch.setattr(duo_admin_service.httpx, "Client", FakeClient)

    client = duo_admin_service.DuoAdminClient()
    user = client.find_user_by_username("cathyf@ewifamilyglobal.com")

    assert user is not None
    assert captured["base_url"] == "https://api-85d6198d.duosecurity.com"
    assert captured["timeout"] == 7.5
    assert captured["method"] == "GET"
    assert captured["path"] == "/admin/v1/users"
    assert captured["params"] == {"username": "cathyf@ewifamilyglobal.com"}

    headers = captured["headers"]
    assert isinstance(headers, dict)
    expected_date = format_datetime(fixed_now, usegmt=True)
    assert headers["Date"] == expected_date

    canonical = "\n".join(
        [
            expected_date,
            "GET",
            "api-85d6198d.duosecurity.com",
            "/admin/v1/users",
            _canonical_query({"username": "cathyf@ewifamilyglobal.com"}),
        ]
    )
    expected_sig = hmac.new(
        b"secret-admin-key",
        canonical.encode("utf-8"),
        hashlib.sha1,
    ).hexdigest()
    expected_auth = base64.b64encode(f"DIXXXXXXXXXXXXXXXXXX:{expected_sig}".encode("utf-8")).decode(
        "ascii"
    )
    assert headers["Authorization"] == f"Basic {expected_auth}"


def test_reset_user_enrollment_cleans_factors_and_preserves_shared_phone(monkeypatch):
    _enable_duo(monkeypatch)
    from app.services import duo_admin_service

    calls: list[tuple[str, str, str | None]] = []

    class FakeClient:
        def get_user(self, user_id: str):
            calls.append(("get_user", user_id, None))
            return {
                "user_id": user_id,
                "username": "cathyf@ewifamilyglobal.com",
                "is_enrolled": True,
            }

        def find_user_by_username(self, username: str):
            calls.append(("find_user_by_username", username, None))
            return None

        def list_webauthn_credentials(self, user_id: str):
            calls.append(("list_webauthn_credentials", user_id, None))
            return [{"webauthnkey": "webauthn_1"}]

        def delete_webauthn_credential(self, user_id: str, credential_id: str):
            calls.append(("delete_webauthn_credential", user_id, credential_id))

        def list_desktop_authenticators(self, user_id: str):
            calls.append(("list_desktop_authenticators", user_id, None))
            return []

        def list_hardware_tokens(self, user_id: str):
            calls.append(("list_hardware_tokens", user_id, None))
            return []

        def disassociate_hardware_token(self, user_id: str, token_id: str):
            calls.append(("disassociate_hardware_token", user_id, token_id))

        def list_phones(self, user_id: str):
            calls.append(("list_phones", user_id, None))
            return [{"phone_id": "phone_1"}]

        def disassociate_phone(self, user_id: str, phone_id: str):
            calls.append(("disassociate_phone", user_id, phone_id))

        def get_phone(self, phone_id: str):
            calls.append(("get_phone", phone_id, None))
            return {"phone_id": phone_id, "users": [{"user_id": "other-user"}]}

        def get_user_authenticator_summary(self, user_id: str):
            calls.append(("get_user_authenticator_summary", user_id, None))
            return {
                "user_id": user_id,
                "username": "cathyf@ewifamilyglobal.com",
                "is_enrolled": False,
            }

        def delete_user(self, user_id: str):
            calls.append(("delete_user", user_id, None))

    monkeypatch.setattr(duo_admin_service, "DuoAdminClient", FakeClient)

    result = duo_admin_service.reset_user_enrollment(
        username="cathyf@ewifamilyglobal.com",
        duo_user_id="DUUSER1",
    )

    assert result.deleted_user is False
    assert result.duo_user_id == "DUUSER1"
    assert "delete_webauthn:webauthn_1" in result.actions
    assert "disassociate_phone:phone_1" in result.actions
    assert "delete_phone:phone_1" not in result.actions
    assert ("delete_user", "DUUSER1", None) not in calls


def test_reset_user_enrollment_falls_back_to_delete_user_when_still_enrolled(monkeypatch):
    _enable_duo(monkeypatch)
    from app.services import duo_admin_service

    calls: list[tuple[str, str, str | None]] = []

    class FakeClient:
        def get_user(self, user_id: str):
            calls.append(("get_user", user_id, None))
            return None

        def find_user_by_username(self, username: str):
            calls.append(("find_user_by_username", username, None))
            return {"user_id": "DUUSER1", "username": username, "is_enrolled": True}

        def list_webauthn_credentials(self, user_id: str):
            calls.append(("list_webauthn_credentials", user_id, None))
            return []

        def list_desktop_authenticators(self, user_id: str):
            calls.append(("list_desktop_authenticators", user_id, None))
            return []

        def list_hardware_tokens(self, user_id: str):
            calls.append(("list_hardware_tokens", user_id, None))
            return []

        def list_phones(self, user_id: str):
            calls.append(("list_phones", user_id, None))
            return []

        def get_user_authenticator_summary(self, user_id: str):
            calls.append(("get_user_authenticator_summary", user_id, None))
            return {
                "user_id": user_id,
                "username": "cathyf@ewifamilyglobal.com",
                "is_enrolled": True,
            }

        def delete_user(self, user_id: str):
            calls.append(("delete_user", user_id, None))

    monkeypatch.setattr(duo_admin_service, "DuoAdminClient", FakeClient)

    result = duo_admin_service.reset_user_enrollment(
        username="cathyf@ewifamilyglobal.com",
        duo_user_id=None,
    )

    assert result.deleted_user is True
    assert result.duo_user_id == "DUUSER1"
    assert "delete_user:DUUSER1" in result.actions
    assert ("find_user_by_username", "cathyf@ewifamilyglobal.com", None) in calls


def test_reset_user_enrollment_raises_config_error_without_admin_api(monkeypatch):
    from app.core.config import settings

    _enable_duo(monkeypatch)
    from app.services import duo_admin_service

    monkeypatch.setattr(settings, "DUO_ADMIN_INTEGRATION_KEY", "")
    monkeypatch.setattr(settings, "DUO_ADMIN_SECRET_KEY", "")
    monkeypatch.setattr(settings, "DUO_ADMIN_API_HOST", "")

    with pytest.raises(duo_admin_service.DuoAdminConfigError):
        duo_admin_service.reset_user_enrollment(
            username="cathyf@ewifamilyglobal.com",
            duo_user_id="DUUSER1",
        )
