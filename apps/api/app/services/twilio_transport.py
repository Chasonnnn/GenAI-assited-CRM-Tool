"""Sanitized Twilio SDK boundary for messages, consent, and inbound media metadata.

Every REST client in this module authenticates with an Account SID plus a
Restricted API Key SID/secret. The Primary Auth Token is intentionally absent;
it belongs only at the webhook-signature validation boundary.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

import requests
from requests import exceptions as requests_exceptions
from twilio.base.exceptions import TwilioRestException
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

ConsentStatus = Literal["opt-in", "opt-out"]
ConsentSource = Literal[
    "website",
    "offline",
    "opt-in-message",
    "opt-out-message",
    "others",
]

_E164_PATTERN = re.compile(r"^\+[1-9][0-9]{1,14}$")
_MESSAGE_SID_PATTERN = re.compile(r"^(?:SM|MM)[0-9A-Za-z]{32}$")
_MEDIA_SID_PATTERN = re.compile(r"^ME[0-9A-Za-z]{32}$")
_MESSAGING_SERVICE_SID_PATTERN = re.compile(r"^MG[0-9A-Za-z]{32}$")
_CONTENT_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
_SAFE_INITIAL_STATUSES = {"accepted", "queued", "scheduled"}
_CONSENT_STATUSES = {"opt-in", "opt-out"}
_CONSENT_SOURCES = {
    "website",
    "offline",
    "opt-in-message",
    "opt-out-message",
    "others",
}
_MAX_CONTENT_TYPE_LENGTH = 127
_PROVIDER_OPT_OUT_CODE = 21610
TWILIO_REQUEST_TIMEOUT_SECONDS = 20.0


class TwilioFailureReason(StrEnum):
    """Controlled failure reasons that contain no provider prose or PII."""

    PROVIDER_OPT_OUT = "provider_opt_out"
    RATE_LIMITED = "rate_limited"
    PROVIDER_REJECTED = "provider_rejected"
    AMBIGUOUS_TRANSPORT = "ambiguous_transport"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    CONSENT_ITEM_REJECTED = "consent_item_rejected"


@dataclass(frozen=True, slots=True)
class TwilioCredentials:
    """Write-only REST credentials; repr deliberately reveals no identifiers."""

    account_sid: str = field(repr=False)
    api_key_sid: str = field(repr=False)
    api_secret: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class TwilioSendResult:
    """Sanitized outcome of one outbound Message resource creation."""

    success: bool
    message_sid: str | None = None
    initial_status: str | None = None
    failure_reason: TwilioFailureReason | None = None
    provider_error_code: int | None = None
    provider_status_code: int | None = None
    provider_opt_out: bool = False
    retryable: bool = False
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class TwilioConsentResult:
    """Sanitized outcome of one two-item Consent Management bulk upsert."""

    success: bool
    correlation_ids: tuple[str, str]
    item_error_codes: tuple[int, ...] = ()
    failure_reason: TwilioFailureReason | None = None
    provider_error_code: int | None = None
    provider_status_code: int | None = None
    retryable: bool = False
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class TwilioMediaMetadataResult:
    """Bounded, non-content metadata returned for an inbound Media resource."""

    success: bool
    media_sid: str | None = None
    content_type: str | None = None
    created_at: datetime | None = None
    failure_reason: TwilioFailureReason | None = None
    provider_error_code: int | None = None
    provider_status_code: int | None = None
    retryable: bool = False
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class TwilioMediaDeleteResult:
    """Sanitized result of deleting one inbound Media resource."""

    success: bool
    failure_reason: TwilioFailureReason | None = None
    provider_error_code: int | None = None
    provider_status_code: int | None = None
    retryable: bool = False
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class TwilioMediaDownloadResult:
    """Bounded media bytes fetched with a Restricted API key."""

    success: bool
    media_sid: str | None = None
    content_type: str | None = None
    content: bytes | None = field(default=None, repr=False)
    failure_reason: TwilioFailureReason | None = None
    provider_status_code: int | None = None
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class _Failure:
    reason: TwilioFailureReason
    provider_error_code: int | None = None
    provider_status_code: int | None = None
    provider_opt_out: bool = False
    retryable: bool = False
    ambiguous: bool = False


def _client(credentials: TwilioCredentials) -> Client:
    if not all((credentials.account_sid, credentials.api_key_sid, credentials.api_secret)):
        raise ValueError("Account SID and Restricted API Key credentials are required")
    return Client(
        credentials.api_key_sid,
        credentials.api_secret,
        credentials.account_sid,
        http_client=TwilioHttpClient(
            timeout=TWILIO_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        ),
    )


def _require_e164(value: str, *, label: str) -> None:
    if not _E164_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must use E.164 format")


def _require_sid(value: str, pattern: re.Pattern[str], *, label: str) -> None:
    if not pattern.fullmatch(value):
        raise ValueError(f"{label} is invalid")


def _safe_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _failure_from_rest_exception(exc: TwilioRestException) -> _Failure:
    provider_error_code = _safe_int(exc.code)
    provider_status_code = _safe_int(exc.status)
    if provider_error_code == _PROVIDER_OPT_OUT_CODE:
        return _Failure(
            reason=TwilioFailureReason.PROVIDER_OPT_OUT,
            provider_error_code=provider_error_code,
            provider_status_code=provider_status_code,
            provider_opt_out=True,
        )
    if provider_status_code == 429:
        return _Failure(
            reason=TwilioFailureReason.RATE_LIMITED,
            provider_error_code=provider_error_code,
            provider_status_code=provider_status_code,
            retryable=True,
        )
    return _Failure(
        reason=TwilioFailureReason.PROVIDER_REJECTED,
        provider_error_code=provider_error_code,
        provider_status_code=provider_status_code,
    )


def _ambiguous_transport_failure() -> _Failure:
    return _Failure(
        reason=TwilioFailureReason.AMBIGUOUS_TRANSPORT,
        ambiguous=True,
    )


def _send_failure_result(failure: _Failure) -> TwilioSendResult:
    return TwilioSendResult(
        success=False,
        failure_reason=failure.reason,
        provider_error_code=failure.provider_error_code,
        provider_status_code=failure.provider_status_code,
        provider_opt_out=failure.provider_opt_out,
        retryable=failure.retryable,
        ambiguous=failure.ambiguous,
    )


def send_message(
    *,
    credentials: TwilioCredentials,
    to: str,
    from_: str,
    messaging_service_sid: str,
    body: str | None,
    status_callback: str,
    media_urls: list[str] | tuple[str, ...] | None = None,
) -> TwilioSendResult:
    """Create exactly one SMS/MMS Message with a purpose-bound exact sender.

    This function never retries inline. Without a provider idempotency contract,
    any transport loss after the POST begins is ambiguous and must be reconciled
    instead of blindly creating a second Message.
    """

    _require_e164(to, label="destination")
    _require_e164(from_, label="sender")
    _require_sid(
        messaging_service_sid,
        _MESSAGING_SERVICE_SID_PATTERN,
        label="Messaging Service SID",
    )
    normalized_media_urls = list(media_urls or ())
    if len(normalized_media_urls) > 10:
        raise ValueError("A message can include at most 10 media URLs")
    if any(not isinstance(value, str) or not value for value in normalized_media_urls):
        raise ValueError("Media URLs must be non-empty strings")
    if body is None and not normalized_media_urls:
        raise ValueError("A message body or media URL is required")

    create_args: dict[str, object] = {
        "to": to,
        "from_": from_,
        "messaging_service_sid": messaging_service_sid,
        "status_callback": status_callback,
    }
    if body is not None:
        create_args["body"] = body
    if normalized_media_urls:
        create_args["media_url"] = normalized_media_urls

    try:
        message = _client(credentials).messages.create(**create_args)
    except TwilioRestException as exc:
        return _send_failure_result(_failure_from_rest_exception(exc))
    except requests_exceptions.RequestException:
        return _send_failure_result(_ambiguous_transport_failure())
    except Exception:
        return _send_failure_result(_ambiguous_transport_failure())

    message_sid = getattr(message, "sid", None)
    initial_status = getattr(message, "status", None)
    if (
        not isinstance(message_sid, str)
        or not _MESSAGE_SID_PATTERN.fullmatch(message_sid)
        or not isinstance(initial_status, str)
        or initial_status not in _SAFE_INITIAL_STATUSES
    ):
        return TwilioSendResult(
            success=False,
            failure_reason=TwilioFailureReason.INVALID_PROVIDER_RESPONSE,
            ambiguous=True,
        )
    return TwilioSendResult(
        success=True,
        message_sid=message_sid,
        initial_status=initial_status,
    )


def _consent_datetime(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Consent date must include a timezone")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_toll_free_marker(route_marker: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", route_marker.casefold())
    return "tollfree" in normalized


def _consent_failure_result(
    correlation_ids: tuple[str, str],
    failure: _Failure,
) -> TwilioConsentResult:
    return TwilioConsentResult(
        success=False,
        correlation_ids=correlation_ids,
        failure_reason=failure.reason,
        provider_error_code=failure.provider_error_code,
        provider_status_code=failure.provider_status_code,
        retryable=failure.retryable,
        ambiguous=failure.ambiguous,
    )


def upsert_route_consent(
    *,
    credentials: TwilioCredentials,
    contact_id: str,
    messaging_service_sid: str,
    sender_phone: str,
    status: ConsentStatus,
    source: ConsentSource,
    date_of_consent: datetime,
    route_marker: str,
) -> TwilioConsentResult:
    """Upsert the service-level and exact-sender consent records together.

    External re-opt is unavailable for US toll-free network opt-outs, so callers
    must provide the route marker and toll-free routes fail before provider I/O.
    """

    if _is_toll_free_marker(route_marker):
        raise ValueError("Consent API external re-opt is unsupported for toll-free routes")
    _require_e164(contact_id, label="contact")
    _require_e164(sender_phone, label="sender")
    _require_sid(
        messaging_service_sid,
        _MESSAGING_SERVICE_SID_PATTERN,
        label="Messaging Service SID",
    )
    if status not in _CONSENT_STATUSES:
        raise ValueError("Consent status is invalid")
    if source not in _CONSENT_SOURCES:
        raise ValueError("Consent source is invalid")
    consent_date = _consent_datetime(date_of_consent)

    correlation_ids = (uuid.uuid4().hex, uuid.uuid4().hex)
    if correlation_ids[0] == correlation_ids[1]:
        raise RuntimeError("Could not generate unique correlation identifiers")
    items = [
        {
            "contact_id": contact_id,
            "correlation_id": correlation_ids[0],
            "sender_id": messaging_service_sid,
            "date_of_consent": consent_date,
            "status": status,
            "source": source,
        },
        {
            "contact_id": contact_id,
            "correlation_id": correlation_ids[1],
            "sender_id": sender_phone,
            "date_of_consent": consent_date,
            "status": status,
            "source": source,
        },
    ]
    try:
        response = _client(credentials).accounts.v1.bulk_consents.create(items=items)
    except TwilioRestException as exc:
        return _consent_failure_result(
            correlation_ids,
            _failure_from_rest_exception(exc),
        )
    except requests_exceptions.RequestException:
        return _consent_failure_result(
            correlation_ids,
            _ambiguous_transport_failure(),
        )
    except Exception:
        return _consent_failure_result(
            correlation_ids,
            _ambiguous_transport_failure(),
        )

    response_items = getattr(response, "items", None)
    if not isinstance(response_items, list) or len(response_items) != 2:
        return TwilioConsentResult(
            success=False,
            correlation_ids=correlation_ids,
            failure_reason=TwilioFailureReason.INVALID_PROVIDER_RESPONSE,
            ambiguous=True,
        )

    error_code_by_correlation: dict[str, int] = {}
    for item in response_items:
        if not isinstance(item, dict):
            break
        correlation_id = item.get("correlation_id")
        error_code = _safe_int(item.get("error_code"))
        if (
            not isinstance(correlation_id, str)
            or correlation_id not in correlation_ids
            or correlation_id in error_code_by_correlation
            or error_code is None
        ):
            break
        error_code_by_correlation[correlation_id] = error_code

    if set(error_code_by_correlation) != set(correlation_ids):
        return TwilioConsentResult(
            success=False,
            correlation_ids=correlation_ids,
            failure_reason=TwilioFailureReason.INVALID_PROVIDER_RESPONSE,
            ambiguous=True,
        )
    item_error_codes = tuple(
        error_code_by_correlation[correlation_id] for correlation_id in correlation_ids
    )
    if any(error_code != 0 for error_code in item_error_codes):
        return TwilioConsentResult(
            success=False,
            correlation_ids=correlation_ids,
            item_error_codes=item_error_codes,
            failure_reason=TwilioFailureReason.CONSENT_ITEM_REJECTED,
        )
    return TwilioConsentResult(
        success=True,
        correlation_ids=correlation_ids,
        item_error_codes=item_error_codes,
    )


def _safe_content_type(value: object) -> str:
    if (
        isinstance(value, str)
        and len(value) <= _MAX_CONTENT_TYPE_LENGTH
        and _CONTENT_TYPE_PATTERN.fullmatch(value)
    ):
        return value.lower()
    return "application/octet-stream"


def _media_metadata_failure(failure: _Failure) -> TwilioMediaMetadataResult:
    return TwilioMediaMetadataResult(
        success=False,
        failure_reason=failure.reason,
        provider_error_code=failure.provider_error_code,
        provider_status_code=failure.provider_status_code,
        retryable=failure.retryable,
        ambiguous=failure.ambiguous,
    )


def fetch_inbound_media_metadata(
    *,
    credentials: TwilioCredentials,
    message_sid: str,
    media_sid: str,
) -> TwilioMediaMetadataResult:
    """Fetch bounded Media resource metadata through the authenticated SDK.

    The content URL and bytes deliberately remain outside this result. This
    boundary does not write media to a filesystem, database, or object store.
    """

    _require_sid(message_sid, _MESSAGE_SID_PATTERN, label="Message SID")
    _require_sid(media_sid, _MEDIA_SID_PATTERN, label="Media SID")
    try:
        media = _client(credentials).messages(message_sid).media(media_sid).fetch()
    except TwilioRestException as exc:
        return _media_metadata_failure(_failure_from_rest_exception(exc))
    except requests_exceptions.RequestException:
        return _media_metadata_failure(_ambiguous_transport_failure())
    except Exception:
        return _media_metadata_failure(_ambiguous_transport_failure())

    returned_media_sid = getattr(media, "sid", None)
    returned_parent_sid = getattr(media, "parent_sid", None)
    created_at = getattr(media, "date_created", None)
    if (
        returned_media_sid != media_sid
        or returned_parent_sid != message_sid
        or (created_at is not None and not isinstance(created_at, datetime))
    ):
        return TwilioMediaMetadataResult(
            success=False,
            failure_reason=TwilioFailureReason.INVALID_PROVIDER_RESPONSE,
        )
    return TwilioMediaMetadataResult(
        success=True,
        media_sid=media_sid,
        content_type=_safe_content_type(getattr(media, "content_type", None)),
        created_at=created_at,
    )


def parse_inbound_media_url(media_url: str) -> tuple[str, str, str]:
    """Return account, message, and media SIDs from an exact Twilio API URL."""
    parsed = urlsplit(media_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.twilio.com"
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Inbound media URL is not an approved Twilio API URL")
    match = re.fullmatch(
        r"/2010-04-01/Accounts/(AC[0-9A-Za-z]{32})/Messages/"
        r"((?:SM|MM)[0-9A-Za-z]{32})/Media/(ME[0-9A-Za-z]{32})(?:\.json)?",
        parsed.path,
    )
    if match is None:
        raise ValueError("Inbound media URL path is invalid")
    return match.group(1), match.group(2), match.group(3)


def download_inbound_media(
    *,
    credentials: TwilioCredentials,
    media_url: str,
    message_sid: str,
    media_sid: str,
    max_bytes: int,
) -> TwilioMediaDownloadResult:
    """Download one authenticated Media resource without redirects or unbounded buffering."""
    if max_bytes < 1 or max_bytes > 5 * 1024 * 1024:
        raise ValueError("Inbound media byte limit is invalid")
    account_from_url, message_from_url, media_from_url = parse_inbound_media_url(media_url)
    if (
        account_from_url != credentials.account_sid
        or message_from_url != message_sid
        or media_from_url != media_sid
    ):
        raise ValueError("Inbound media URL does not match the verified webhook")
    try:
        with requests.get(
            media_url,
            auth=(credentials.api_key_sid, credentials.api_secret),
            allow_redirects=False,
            stream=True,
            timeout=TWILIO_REQUEST_TIMEOUT_SECONDS,
        ) as response:
            if response.status_code != 200:
                return TwilioMediaDownloadResult(
                    success=False,
                    media_sid=media_sid,
                    failure_reason=TwilioFailureReason.PROVIDER_REJECTED,
                    provider_status_code=response.status_code,
                    retryable=response.status_code in {429, 500, 502, 503, 504},
                )
            declared_length = response.headers.get("Content-Length")
            if declared_length and int(declared_length) > max_bytes:
                return TwilioMediaDownloadResult(
                    success=False,
                    media_sid=media_sid,
                    failure_reason=TwilioFailureReason.INVALID_PROVIDER_RESPONSE,
                )
            buffer = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                buffer.extend(chunk)
                if len(buffer) > max_bytes:
                    return TwilioMediaDownloadResult(
                        success=False,
                        media_sid=media_sid,
                        failure_reason=TwilioFailureReason.INVALID_PROVIDER_RESPONSE,
                    )
            return TwilioMediaDownloadResult(
                success=True,
                media_sid=media_sid,
                content_type=_safe_content_type(response.headers.get("Content-Type")),
                content=bytes(buffer),
            )
    except requests_exceptions.RequestException, ValueError:
        return TwilioMediaDownloadResult(
            success=False,
            media_sid=media_sid,
            failure_reason=TwilioFailureReason.AMBIGUOUS_TRANSPORT,
            retryable=True,
        )


def _media_delete_failure(failure: _Failure) -> TwilioMediaDeleteResult:
    return TwilioMediaDeleteResult(
        success=False,
        failure_reason=failure.reason,
        provider_error_code=failure.provider_error_code,
        provider_status_code=failure.provider_status_code,
        retryable=failure.retryable,
        ambiguous=failure.ambiguous,
    )


def delete_inbound_media(
    *,
    credentials: TwilioCredentials,
    message_sid: str,
    media_sid: str,
) -> TwilioMediaDeleteResult:
    """Delete one Media resource without reading or persisting its content."""

    _require_sid(message_sid, _MESSAGE_SID_PATTERN, label="Message SID")
    _require_sid(media_sid, _MEDIA_SID_PATTERN, label="Media SID")
    try:
        deleted = _client(credentials).messages(message_sid).media(media_sid).delete()
    except TwilioRestException as exc:
        return _media_delete_failure(_failure_from_rest_exception(exc))
    except requests_exceptions.RequestException:
        return _media_delete_failure(_ambiguous_transport_failure())
    except Exception:
        return _media_delete_failure(_ambiguous_transport_failure())
    if deleted is not True:
        return TwilioMediaDeleteResult(
            success=False,
            failure_reason=TwilioFailureReason.INVALID_PROVIDER_RESPONSE,
        )
    return TwilioMediaDeleteResult(success=True)
