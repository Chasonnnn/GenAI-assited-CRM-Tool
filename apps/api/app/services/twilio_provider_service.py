"""Sanitized, no-send Twilio control-plane operations."""

from __future__ import annotations

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.db.models import TwilioSettings
from app.schemas.twilio import TwilioSettingsTestRequest, TwilioSettingsTestResponse
from app.services import twilio_settings_service


def _sanitized_error_code(exc: TwilioRestException) -> str:
    """Keep credentials, request URIs, phone numbers, and provider prose out of responses."""
    if exc.code is not None:
        return f"twilio_{exc.code}"
    if exc.status is not None:
        return f"twilio_http_{exc.status}"
    return "twilio_request_failed"


def _configured_or_override(override: str | None, encrypted: str | None) -> str | None:
    if override is not None:
        normalized = override.strip()
        return normalized or None
    if encrypted:
        return twilio_settings_service.decrypt_credential(encrypted)
    return None


def test_configuration(
    settings: TwilioSettings,
    request: TwilioSettingsTestRequest | None = None,
) -> TwilioSettingsTestResponse:
    """Validate ephemeral or stored credentials and routes without creating a Message."""
    request = request or TwilioSettingsTestRequest()
    account_sid = _configured_or_override(request.account_sid, settings.account_sid_encrypted)
    api_key_sid = _configured_or_override(request.api_key_sid, settings.api_key_sid_encrypted)
    api_secret = _configured_or_override(request.api_secret, settings.api_secret_encrypted)
    auth_token = _configured_or_override(request.auth_token, settings.auth_token_encrypted)
    capabilities = {
        "account_api": False,
        "messaging_services": False,
        "webhook_validation": bool(auth_token),
    }
    if not (account_sid and api_key_sid and api_secret):
        return TwilioSettingsTestResponse(
            valid=False,
            account_status=None,
            twilio_edition=settings.twilio_edition,
            capabilities=capabilities,
            error="Twilio REST credentials are not configured.",
            warning=None,
        )

    client = Client(api_key_sid, api_secret, account_sid)
    route_statuses: dict[str, str] = {}
    try:
        account = client.api.accounts(account_sid).fetch()
        account_status = str(account.status)
        capabilities["account_api"] = True
        purpose_order = {
            purpose: index for index, purpose in enumerate(twilio_settings_service.PURPOSES)
        }
        for route in sorted(settings.routes, key=lambda item: purpose_order[item.purpose]):
            route_override = (request.routes or {}).get(route.purpose)
            if route_override is not None:
                service_sid = route_override.messaging_service_sid
            elif route.messaging_service_sid_encrypted:
                service_sid = twilio_settings_service.decrypt_credential(
                    route.messaging_service_sid_encrypted
                )
            else:
                service_sid = None
            if not service_sid:
                route_statuses[route.purpose] = "not_configured"
                continue
            fetched = client.messaging.v1.services(service_sid).fetch()
            route_statuses[route.purpose] = "verified" if fetched.sid == service_sid else "mismatch"
        capabilities["messaging_services"] = bool(route_statuses) and all(
            status == "verified" for status in route_statuses.values()
        )
    except TwilioRestException as exc:
        return TwilioSettingsTestResponse(
            valid=False,
            account_status=None,
            twilio_edition=settings.twilio_edition,
            capabilities=capabilities,
            error=_sanitized_error_code(exc),
            warning=None,
        )

    return TwilioSettingsTestResponse(
        valid=account_status == "active" and capabilities["messaging_services"],
        account_status=account_status,
        twilio_edition=settings.twilio_edition,
        capabilities=capabilities,
        error=None,
        warning=(
            None
            if auth_token
            else "Primary Auth Token is not configured; webhook validation is unavailable."
        ),
    )
