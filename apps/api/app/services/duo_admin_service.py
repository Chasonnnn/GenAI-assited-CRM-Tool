"""Duo Admin API integration for MFA reset workflows."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.core.config import settings

_INVISIBLE_CHARS = ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060")


def _strip_invisible(value: str) -> str:
    return "".join(ch for ch in value if ch not in _INVISIBLE_CHARS)


def _sanitize_host(value: str) -> str:
    host = _strip_invisible(value or "").strip().strip('"').strip("'")
    if "://" in host:
        parsed = urlparse(host)
        host = parsed.hostname or host
    return host.rstrip("/")


def _sanitize_integration_key(value: str) -> str:
    raw_value = _strip_invisible(value or "")
    return re.sub(r"[^A-Za-z0-9]", "", raw_value)


def _sanitize_secret(value: str) -> str:
    return _strip_invisible(value or "").strip().strip('"').strip("'")


def _canonical_query(params: dict[str, Any] | None) -> str:
    if not params:
        return ""
    items = sorted((str(key), str(value)) for key, value in params.items() if value is not None)
    return "&".join(f"{quote(key, safe='~')}={quote(value, safe='~')}" for key, value in items)


def _extract_message(payload: dict[str, Any] | None, fallback: str) -> str:
    if not isinstance(payload, dict):
        return fallback

    for key in ("message_detail", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    response = payload.get("response")
    if isinstance(response, dict):
        for key in ("message_detail", "message"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return fallback


@dataclass
class DuoAdminResetResult:
    duo_user_id: str | None
    username: str
    found: bool
    deleted_user: bool = False
    actions: list[str] = field(default_factory=list)


class DuoAdminError(RuntimeError):
    """Base error for Duo Admin operations."""


class DuoAdminConfigError(DuoAdminError):
    """Raised when Duo Admin API is not configured."""


class DuoAdminAPIError(DuoAdminError):
    """Raised when a Duo Admin API request fails."""

    def __init__(
        self,
        message: str,
        *,
        step: str,
        status_code: int | None = None,
        duo_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.step = step
        self.status_code = status_code
        self.duo_code = duo_code


class DuoAdminClient:
    """Thin sync client for Duo Admin API requests."""

    def __init__(self) -> None:
        self.integration_key = _sanitize_integration_key(settings.DUO_ADMIN_INTEGRATION_KEY)
        self.secret_key = _sanitize_secret(settings.DUO_ADMIN_SECRET_KEY)
        self.host = _sanitize_host(settings.duo_admin_host)
        self.timeout = settings.DUO_ADMIN_TIMEOUT_SECONDS

        if not (self.integration_key and self.secret_key and self.host):
            raise DuoAdminConfigError(
                "Duo Admin API is not configured. Set DUO_ADMIN_INTEGRATION_KEY, "
                "DUO_ADMIN_SECRET_KEY, and DUO_ADMIN_API_HOST."
            )

        self.base_url = f"https://{self.host}"

    def _build_auth_header(
        self, method: str, path: str, params: dict[str, Any] | None, date: str
    ) -> str:
        canonical = "\n".join(
            [
                date,
                method.upper(),
                self.host.lower(),
                path,
                _canonical_query(params),
            ]
        )
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha1,
        ).hexdigest()
        token = base64.b64encode(f"{self.integration_key}:{signature}".encode("utf-8")).decode(
            "ascii"
        )
        return f"Basic {token}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        step: str,
        allow_not_found: bool = False,
    ) -> Any:
        normalized_params = {
            key: value for key, value in (params or {}).items() if value is not None
        }
        date_header = format_datetime(datetime.now(timezone.utc), usegmt=True)
        headers = {
            "Accept": "application/json",
            "Date": date_header,
            "Authorization": self._build_auth_header(method, path, normalized_params, date_header),
        }

        request_kwargs = {"params": normalized_params} if normalized_params else {}

        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                response = client.request(method, path, headers=headers, **request_kwargs)
        except httpx.TimeoutException as exc:
            raise DuoAdminAPIError(
                "Timed out while contacting Duo Admin API",
                step=step,
                status_code=504,
            ) from exc
        except httpx.RequestError as exc:
            raise DuoAdminAPIError(
                "Failed to contact Duo Admin API",
                step=step,
                status_code=502,
            ) from exc

        payload: dict[str, Any] | None = None
        try:
            body = response.json()
            payload = body if isinstance(body, dict) else None
        except ValueError:
            payload = None

        if allow_not_found and response.status_code == 404:
            return None

        if response.status_code >= 400:
            raise DuoAdminAPIError(
                _extract_message(payload, "Duo Admin API request failed"),
                step=step,
                status_code=response.status_code,
                duo_code=payload.get("code") if isinstance(payload, dict) else None,
            )

        if not isinstance(payload, dict) or payload.get("stat") != "OK":
            raise DuoAdminAPIError(
                _extract_message(payload, "Duo Admin API returned an invalid response"),
                step=step,
                status_code=response.status_code,
                duo_code=payload.get("code") if isinstance(payload, dict) else None,
            )

        return payload.get("response")

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            f"/admin/v1/users/{user_id}",
            step="get_user",
            allow_not_found=True,
        )
        return response if isinstance(response, dict) else None

    def find_user_by_username(self, username: str) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            "/admin/v1/users",
            params={"username": username},
            step="find_user_by_username",
        )
        users = response if isinstance(response, list) else []
        for user in users:
            if not isinstance(user, dict):
                continue
            if str(user.get("username", "")).lower() == username.lower():
                return user
        return None

    def list_webauthn_credentials(self, user_id: str) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"/admin/v2/users/{user_id}/webauthncredentials",
            step="list_webauthn_credentials",
        )
        return [item for item in response or [] if isinstance(item, dict)]

    def delete_webauthn_credential(self, user_id: str, credential_id: str) -> None:
        self._request(
            "DELETE",
            f"/admin/v2/users/{user_id}/webauthncredentials/{credential_id}",
            step="delete_webauthn_credential",
            allow_not_found=True,
        )

    def list_desktop_authenticators(self, user_id: str) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"/admin/v2/users/{user_id}/desktop_authenticators",
            step="list_desktop_authenticators",
        )
        return [item for item in response or [] if isinstance(item, dict)]

    def delete_desktop_authenticator(self, user_id: str, authenticator_id: str) -> None:
        self._request(
            "DELETE",
            f"/admin/v2/users/{user_id}/desktop_authenticators/{authenticator_id}",
            step="delete_desktop_authenticator",
            allow_not_found=True,
        )

    def list_hardware_tokens(self, user_id: str) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"/admin/v1/users/{user_id}/tokens",
            step="list_hardware_tokens",
        )
        return [item for item in response or [] if isinstance(item, dict)]

    def disassociate_hardware_token(self, user_id: str, token_id: str) -> None:
        self._request(
            "DELETE",
            f"/admin/v1/users/{user_id}/tokens/{token_id}",
            step="disassociate_hardware_token",
            allow_not_found=True,
        )

    def list_phones(self, user_id: str) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"/admin/v1/users/{user_id}/phones",
            step="list_phones",
        )
        return [item for item in response or [] if isinstance(item, dict)]

    def disassociate_phone(self, user_id: str, phone_id: str) -> None:
        self._request(
            "DELETE",
            f"/admin/v1/users/{user_id}/phones/{phone_id}",
            step="disassociate_phone",
            allow_not_found=True,
        )

    def get_phone(self, phone_id: str) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            f"/admin/v1/phones/{phone_id}",
            step="get_phone",
            allow_not_found=True,
        )
        return response if isinstance(response, dict) else None

    def delete_phone(self, phone_id: str) -> None:
        self._request(
            "DELETE",
            f"/admin/v1/phones/{phone_id}",
            step="delete_phone",
            allow_not_found=True,
        )

    def delete_user(self, user_id: str) -> None:
        self._request(
            "DELETE",
            f"/admin/v1/users/{user_id}",
            step="delete_user",
            allow_not_found=True,
        )

    def get_user_authenticator_summary(self, user_id: str) -> dict[str, Any] | None:
        return self.get_user(user_id)


def _has_remaining_authenticators(user: dict[str, Any] | None) -> bool:
    if not isinstance(user, dict):
        return False
    if bool(user.get("is_enrolled")):
        return True
    for key in ("phones", "tokens", "webauthncredentials", "desktop_authenticators"):
        value = user.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def reset_user_enrollment(*, username: str, duo_user_id: str | None = None) -> DuoAdminResetResult:
    """Reset a user's Duo enrollment by clearing factors or deleting the Duo user."""
    if not settings.duo_enabled:
        return DuoAdminResetResult(duo_user_id=duo_user_id, username=username, found=False)

    client = DuoAdminClient()
    result = DuoAdminResetResult(duo_user_id=duo_user_id, username=username, found=False)

    duo_user: dict[str, Any] | None = None
    if duo_user_id:
        duo_user = client.get_user(duo_user_id)
    if not duo_user:
        duo_user = client.find_user_by_username(username)

    if not duo_user:
        return result

    resolved_duo_user_id = str(duo_user.get("user_id") or duo_user_id or "")
    if not resolved_duo_user_id:
        raise DuoAdminAPIError(
            "Duo user lookup succeeded but returned no user id",
            step="find_user_by_username",
            status_code=502,
        )

    result.duo_user_id = resolved_duo_user_id
    result.found = True

    for credential in client.list_webauthn_credentials(resolved_duo_user_id):
        credential_id = credential.get("webauthnkey")
        if not credential_id:
            continue
        client.delete_webauthn_credential(resolved_duo_user_id, str(credential_id))
        result.actions.append(f"delete_webauthn:{credential_id}")

    for authenticator in client.list_desktop_authenticators(resolved_duo_user_id):
        authenticator_id = authenticator.get("key")
        if not authenticator_id:
            continue
        client.delete_desktop_authenticator(resolved_duo_user_id, str(authenticator_id))
        result.actions.append(f"delete_desktop_authenticator:{authenticator_id}")

    for token in client.list_hardware_tokens(resolved_duo_user_id):
        token_id = token.get("token_id")
        if not token_id:
            continue
        client.disassociate_hardware_token(resolved_duo_user_id, str(token_id))
        result.actions.append(f"disassociate_token:{token_id}")

    for phone in client.list_phones(resolved_duo_user_id):
        phone_id = phone.get("phone_id")
        if not phone_id:
            continue
        client.disassociate_phone(resolved_duo_user_id, str(phone_id))
        result.actions.append(f"disassociate_phone:{phone_id}")
        phone_record = client.get_phone(str(phone_id))
        remaining_users = phone_record.get("users") if isinstance(phone_record, dict) else []
        if not remaining_users:
            client.delete_phone(str(phone_id))
            result.actions.append(f"delete_phone:{phone_id}")

    summary = client.get_user_authenticator_summary(resolved_duo_user_id)
    if _has_remaining_authenticators(summary):
        client.delete_user(resolved_duo_user_id)
        result.deleted_user = True
        result.actions.append(f"delete_user:{resolved_duo_user_id}")

    return result
