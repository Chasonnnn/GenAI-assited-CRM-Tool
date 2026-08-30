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
    route_capabilities: dict[str, dict[str, bool | str | None]] = {}
    if not (account_sid and api_key_sid and api_secret):
        return TwilioSettingsTestResponse(
            valid=False,
            account_status=None,
            twilio_edition=settings.twilio_edition,
            capabilities=capabilities,
            route_capabilities=route_capabilities,
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
            if route_override is not None and route_override.sender_phone_e164 is not None:
                sender = route_override.sender_phone_e164
            elif route.sender_phone_encrypted:
                sender = twilio_settings_service.decrypt_credential(route.sender_phone_encrypted)
            else:
                sender = None
            if not service_sid or not sender:
                route_statuses[route.purpose] = "not_configured"
                route_capabilities[route.purpose] = {
                    "service_verified": False,
                    "sender_in_pool": False,
                    "sms": False,
                    "mms": False,
                    "a2p_status": None,
                    "inbound_webhook_matches": False,
                    "status_callback_matches": False,
                }
                continue
            service_context = client.messaging.v1.services(service_sid)
            fetched = service_context.fetch()
            service_verified = fetched.sid == service_sid
            sender_resource = next(
                (
                    item
                    for item in service_context.phone_numbers.list(limit=1000)
                    if item.phone_number == sender
                ),
                None,
            )
            sender_capabilities = {
                str(item).upper() for item in (getattr(sender_resource, "capabilities", None) or [])
            }
            campaign_statuses = {
                str(item.campaign_status).upper()
                for item in service_context.us_app_to_person.list(limit=20)
                if getattr(item, "campaign_status", None)
            }
            a2p_status = (
                "VERIFIED"
                if "VERIFIED" in campaign_statuses
                else (sorted(campaign_statuses)[0] if campaign_statuses else "UNCONFIGURED")
            )
            inbound_url = twilio_settings_service.route_webhook_url(route.webhook_id, "inbound")
            status_url = twilio_settings_service.route_webhook_url(route.webhook_id, "status")
            route_capabilities[route.purpose] = {
                "service_verified": service_verified,
                "sender_in_pool": sender_resource is not None,
                "sms": "SMS" in sender_capabilities,
                "mms": "MMS" in sender_capabilities,
                "sender_type": (
                    "10dlc" if sender.startswith("+1") and a2p_status == "VERIFIED" else "unknown"
                ),
                "a2p_status": a2p_status,
                "inbound_webhook_matches": (
                    fetched.inbound_request_url == inbound_url
                    and str(fetched.inbound_method).upper() == "POST"
                    and not bool(fetched.use_inbound_webhook_on_number)
                ),
                "status_callback_matches": fetched.status_callback == status_url,
            }
            route_statuses[route.purpose] = (
                "verified"
                if all(
                    (
                        service_verified,
                        sender_resource is not None,
                        "SMS" in sender_capabilities,
                        a2p_status == "VERIFIED",
                    )
                )
                else "mismatch"
            )
        capabilities["messaging_services"] = bool(route_statuses) and all(
            status == "verified" for status in route_statuses.values()
        )
    except TwilioRestException as exc:
        return TwilioSettingsTestResponse(
            valid=False,
            account_status=None,
            twilio_edition=settings.twilio_edition,
            capabilities=capabilities,
            route_capabilities=route_capabilities,
            error=_sanitized_error_code(exc),
            warning=None,
        )

    return TwilioSettingsTestResponse(
        valid=account_status == "active" and capabilities["messaging_services"],
        account_status=account_status,
        twilio_edition=settings.twilio_edition,
        capabilities=capabilities,
        route_capabilities=route_capabilities,
        error=None,
        warning=(
            None
            if auth_token
            else "Primary Auth Token is not configured; webhook validation is unavailable."
        ),
    )
