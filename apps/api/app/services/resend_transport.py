"""Shared Resend HTTP transport.

Keep provider-specific response and retry semantics in one place so platform
email and organization-owned Resend integrations cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

RESEND_SEND_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT_SECONDS = 20.0

_CONCURRENT_IDEMPOTENCY_ERROR = "concurrent_idempotent_requests"
_QUOTA_EXHAUSTION_ERRORS = {
    "daily_quota_exceeded",
    "monthly_quota_exceeded",
}


@dataclass(frozen=True, slots=True)
class ResendSendResult:
    """Normalized result returned by the Resend email endpoint."""

    success: bool
    message_id: str | None = None
    error: str | None = None
    error_type: str | None = None
    status_code: int | None = None
    retryable: bool = False
    retry_after_seconds: float | None = None
    ambiguous: bool = False


def _response_data(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _error_type(data: dict[str, Any]) -> str | None:
    for key in ("name", "type"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _error_message(data: dict[str, Any]) -> str | None:
    for key in ("message", "error"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _seconds_from_retry_after(value: str) -> float | None:
    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def _provider_retry_delay(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        parsed = _seconds_from_retry_after(retry_after)
        if parsed is not None:
            return parsed

    rate_limit_reset = response.headers.get("ratelimit-reset")
    if rate_limit_reset:
        try:
            return max(0.0, float(rate_limit_reset))
        except ValueError:
            return None

    return None


def _should_retry(response: httpx.Response, error_type: str | None) -> bool:
    if response.status_code == 409:
        return error_type == _CONCURRENT_IDEMPOTENCY_ERROR
    if response.status_code == 429:
        return error_type not in _QUOTA_EXHAUSTION_ERRORS
    return 500 <= response.status_code < 600


def _failure_from_response(
    response: httpx.Response,
    data: dict[str, Any],
    *,
    retryable: bool,
) -> ResendSendResult:
    detail = _error_message(data)
    error = f"Resend API error: {response.status_code}"
    if detail:
        error = f"{error} ({detail})"
    return ResendSendResult(
        success=False,
        error=error,
        error_type=_error_type(data),
        status_code=response.status_code,
        retryable=retryable,
        retry_after_seconds=_provider_retry_delay(response) if retryable else None,
    )


async def send_email(
    *,
    api_key: str,
    payload: dict[str, object],
    idempotency_key: str | None = None,
) -> ResendSendResult:
    """Make one admitted Resend request and classify its outcome.

    The durable dispatcher owns all retries so every provider HTTP request
    receives its own account-scoped admission slot and lease/idempotency check.
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    safe_to_retry = bool(idempotency_key)

    async with httpx.AsyncClient(timeout=RESEND_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(RESEND_SEND_URL, headers=headers, json=payload)
        except httpx.RequestError as exc:
            if isinstance(exc, httpx.TimeoutException):
                return ResendSendResult(
                    success=False,
                    error="Connection timeout",
                    error_type="timeout",
                    retryable=safe_to_retry,
                )
            return ResendSendResult(
                success=False,
                error=f"Connection error: {exc.__class__.__name__}",
                error_type="network_error",
                retryable=safe_to_retry,
            )

    data = _response_data(response)
    error_type = _error_type(data)
    if 200 <= response.status_code < 300:
        message_id = data.get("id")
        if isinstance(message_id, str) and message_id:
            return ResendSendResult(
                success=True,
                message_id=message_id,
                status_code=response.status_code,
            )
        return ResendSendResult(
            success=False,
            error="Resend API returned success without message id",
            error_type="invalid_success_response",
            status_code=response.status_code,
            ambiguous=True,
        )

    retryable = safe_to_retry and _should_retry(response, error_type)
    return _failure_from_response(response, data, retryable=retryable)
