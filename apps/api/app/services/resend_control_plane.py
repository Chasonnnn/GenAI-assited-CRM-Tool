"""Admitted, sanitized read-only access to Resend control-plane APIs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import logging
import re
from typing import Generic, TypeVar
from urllib.parse import urlsplit
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import email_provider_admission_service
from app.services.resend_event_contract import RESEND_SANITIZED_WEBHOOK_EVENT_TYPES

logger = logging.getLogger(__name__)
RESEND_API_BASE = "https://api.resend.com"
RESEND_CONTROL_PLANE_TIMEOUT_SECONDS = 10.0
MAX_RETRY_AFTER_SECONDS = 3600

_DOMAIN_NAME_PATTERN = re.compile(
    r"(?=.{1,253}\Z)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)
_DOMAIN_STATUSES = {
    "not_started",
    "pending",
    "verified",
    "partially_verified",
    "partially_failed",
    "failed",
    "temporary_failure",
}
_CAPABILITY_STATUSES = {"enabled", "disabled"}
_DNS_RECORD_STATUSES = {
    "not_started",
    "pending",
    "verified",
    "failed",
    "temporary_failure",
}
_WEBHOOK_STATUSES = {"enabled", "disabled"}


class ResendControlPlaneStatus(StrEnum):
    """Controlled provider-read outcome without remote error detail."""

    OK = "ok"
    LIMITED = "limited"
    FAIL = "fail"
    UNKNOWN = "unknown"


class ResendControlPlaneReason(StrEnum):
    """Controlled failure reason with no provider or exception detail."""

    ADMISSION_UNAVAILABLE = "admission_unavailable"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True, slots=True)
class ResendDomainState:
    """Domain fields safe to retain outside the provider boundary."""

    id: str
    name: str
    status: str
    sending: str
    receiving: str


@dataclass(frozen=True, slots=True)
class ResendDomainDetailState:
    """Domain readiness fields safe to retain from the detail response."""

    id: str
    name: str
    status: str
    sending: str
    receiving: str
    open_tracking: bool | None
    click_tracking: bool | None
    spf_status: str
    dkim_status: str


@dataclass(frozen=True, slots=True)
class ResendWebhookState:
    """Webhook readiness fields that exclude endpoint and signing material."""

    id: str
    status: str
    events: tuple[str, ...]
    endpoint_matches: bool


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ResendControlPlaneResult(Generic[T]):
    """Sanitized result returned by one provider GET."""

    status: ResendControlPlaneStatus
    value: T | None = None
    provider_status_code: int | None = None
    reason: ResendControlPlaneReason | None = None
    retry_after_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class _RawGetResult:
    status: ResendControlPlaneStatus
    value: dict[str, object] | None = None
    provider_status_code: int | None = None
    reason: ResendControlPlaneReason | None = None
    retry_after_seconds: int | None = None


@dataclass(slots=True)
class ResendControlPlaneClient:
    """Read-only Resend client that admits every individual HTTP request."""

    db: Session = field(repr=False)
    api_key: str = field(repr=False)
    admission_identity: str
    requests_per_second: int | None = None

    async def _get(self, path: str) -> _RawGetResult:
        try:
            reservation = email_provider_admission_service.reserve_provider_request_slot(
                self.db,
                provider="resend",
                provider_account_id=self.admission_identity,
                requests_per_second=(
                    self.requests_per_second
                    if self.requests_per_second is not None
                    else settings.RESEND_PROVIDER_REQUESTS_PER_SECOND
                ),
            )
        except Exception:
            return _RawGetResult(
                status=ResendControlPlaneStatus.UNKNOWN,
                reason=ResendControlPlaneReason.ADMISSION_UNAVAILABLE,
            )

        admitted_at = datetime.now(timezone.utc)
        wait_seconds = max(0.0, (reservation.send_at - admitted_at).total_seconds())
        if wait_seconds:
            await asyncio.sleep(wait_seconds)

        try:
            async with httpx.AsyncClient(timeout=RESEND_CONTROL_PLANE_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{RESEND_API_BASE}{path}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.TimeoutException:
            return _RawGetResult(
                status=ResendControlPlaneStatus.UNKNOWN,
                reason=ResendControlPlaneReason.TIMEOUT,
            )
        except httpx.RequestError:
            return _RawGetResult(
                status=ResendControlPlaneStatus.UNKNOWN,
                reason=ResendControlPlaneReason.NETWORK_ERROR,
            )

        if response.status_code != 200:
            if response.status_code == 401:
                try:
                    error_payload = response.json()
                except (TypeError, ValueError):
                    error_payload = {}
                if (
                    isinstance(error_payload, dict)
                    and error_payload.get("name") == "restricted_api_key"
                ):
                    return _RawGetResult(status=ResendControlPlaneStatus.LIMITED)
            if response.status_code == 429 or response.status_code >= 500:
                retry_after_seconds = (
                    _bounded_retry_after_seconds(response.headers.get("retry-after"))
                    if response.status_code == 429
                    else None
                )
                if response.status_code == 429:
                    try:
                        email_provider_admission_service.defer_provider_request_slot(
                            self.db,
                            provider="resend",
                            provider_account_id=self.admission_identity,
                            retry_after=timedelta(
                                seconds=(
                                    retry_after_seconds
                                    if retry_after_seconds and retry_after_seconds > 0
                                    else 1
                                )
                            ),
                            max_delay=timedelta(seconds=MAX_RETRY_AFTER_SECONDS),
                        )
                    except Exception as exc:
                        logger.warning(
                            "Resend control-plane cooldown could not be advanced",
                            extra={"error_type": type(exc).__name__},
                        )
                return _RawGetResult(
                    status=ResendControlPlaneStatus.UNKNOWN,
                    provider_status_code=response.status_code,
                    retry_after_seconds=retry_after_seconds,
                )
            return _RawGetResult(status=ResendControlPlaneStatus.FAIL)
        try:
            value = response.json()
        except (TypeError, ValueError):
            return _RawGetResult(
                status=ResendControlPlaneStatus.UNKNOWN,
                reason=ResendControlPlaneReason.INVALID_RESPONSE,
            )
        if not isinstance(value, dict):
            return _RawGetResult(
                status=ResendControlPlaneStatus.UNKNOWN,
                reason=ResendControlPlaneReason.INVALID_RESPONSE,
            )
        return _RawGetResult(status=ResendControlPlaneStatus.OK, value=value)

    async def list_domains(
        self,
    ) -> ResendControlPlaneResult[tuple[ResendDomainState, ...]]:
        """List domains without returning DNS records or provider metadata."""
        response = await self._get("/domains")
        if response.status is not ResendControlPlaneStatus.OK or response.value is None:
            return ResendControlPlaneResult(
                status=response.status,
                provider_status_code=response.provider_status_code,
                reason=response.reason,
                retry_after_seconds=response.retry_after_seconds,
            )

        raw_domains = response.value.get("data")
        if not isinstance(raw_domains, list):
            return ResendControlPlaneResult(status=ResendControlPlaneStatus.UNKNOWN)

        domains = tuple(
            domain
            for item in raw_domains
            if isinstance(item, dict)
            if (domain := _sanitize_domain(item)) is not None
        )
        return ResendControlPlaneResult(
            status=ResendControlPlaneStatus.OK,
            value=domains,
        )

    async def get_domain(
        self,
        domain_id: str,
    ) -> ResendControlPlaneResult[ResendDomainDetailState]:
        """Retrieve one domain without returning DNS or routing configuration."""
        try:
            normalized_domain_id = str(uuid.UUID(domain_id))
        except (ValueError, TypeError, AttributeError):
            return ResendControlPlaneResult(status=ResendControlPlaneStatus.FAIL)

        response = await self._get(f"/domains/{normalized_domain_id}")
        if response.status is not ResendControlPlaneStatus.OK or response.value is None:
            return ResendControlPlaneResult(
                status=response.status,
                provider_status_code=response.provider_status_code,
                reason=response.reason,
                retry_after_seconds=response.retry_after_seconds,
            )
        domain = _sanitize_domain_detail(response.value)
        if domain is None:
            return ResendControlPlaneResult(status=ResendControlPlaneStatus.UNKNOWN)
        return ResendControlPlaneResult(
            status=ResendControlPlaneStatus.OK,
            value=domain,
        )

    async def list_webhooks(
        self,
        *,
        expected_endpoint: str,
    ) -> ResendControlPlaneResult[tuple[ResendWebhookState, ...]]:
        """List webhooks without retrieving endpoint URLs or signing secrets."""
        expected_endpoint_key = _normalize_webhook_endpoint(expected_endpoint)
        if expected_endpoint_key is None:
            return ResendControlPlaneResult(status=ResendControlPlaneStatus.FAIL)
        response = await self._get("/webhooks")
        if response.status is not ResendControlPlaneStatus.OK or response.value is None:
            return ResendControlPlaneResult(
                status=response.status,
                provider_status_code=response.provider_status_code,
                reason=response.reason,
                retry_after_seconds=response.retry_after_seconds,
            )

        raw_webhooks = response.value.get("data")
        if not isinstance(raw_webhooks, list):
            return ResendControlPlaneResult(status=ResendControlPlaneStatus.UNKNOWN)
        webhooks = tuple(
            webhook
            for item in raw_webhooks
            if isinstance(item, dict)
            if (
                webhook := _sanitize_webhook(
                    item,
                    expected_endpoint_key=expected_endpoint_key,
                )
            )
            is not None
        )
        return ResendControlPlaneResult(
            status=ResendControlPlaneStatus.OK,
            value=webhooks,
        )


def _sanitize_domain(value: dict[str, object]) -> ResendDomainState | None:
    try:
        domain_id = str(uuid.UUID(str(value.get("id"))))
    except (ValueError, TypeError, AttributeError):
        return None

    raw_name = value.get("name")
    if not isinstance(raw_name, str):
        return None
    name = raw_name.strip().lower()
    if not _DOMAIN_NAME_PATTERN.fullmatch(name):
        return None

    raw_status = value.get("status")
    status = (
        raw_status if isinstance(raw_status, str) and raw_status in _DOMAIN_STATUSES else "unknown"
    )
    capabilities = value.get("capabilities")
    if not isinstance(capabilities, dict):
        capabilities = {}
    raw_sending = capabilities.get("sending")
    raw_receiving = capabilities.get("receiving")
    sending = (
        raw_sending
        if isinstance(raw_sending, str) and raw_sending in _CAPABILITY_STATUSES
        else "unknown"
    )
    receiving = (
        raw_receiving
        if isinstance(raw_receiving, str) and raw_receiving in _CAPABILITY_STATUSES
        else "unknown"
    )
    return ResendDomainState(
        id=domain_id,
        name=name,
        status=status,
        sending=sending,
        receiving=receiving,
    )


def _sanitize_domain_detail(
    value: dict[str, object],
) -> ResendDomainDetailState | None:
    domain = _sanitize_domain(value)
    if domain is None:
        return None
    raw_open_tracking = value.get("open_tracking")
    raw_click_tracking = value.get("click_tracking")
    return ResendDomainDetailState(
        id=domain.id,
        name=domain.name,
        status=domain.status,
        sending=domain.sending,
        receiving=domain.receiving,
        open_tracking=(raw_open_tracking if isinstance(raw_open_tracking, bool) else None),
        click_tracking=(raw_click_tracking if isinstance(raw_click_tracking, bool) else None),
        spf_status=_aggregate_dns_record_status(value.get("records"), "SPF"),
        dkim_status=_aggregate_dns_record_status(value.get("records"), "DKIM"),
    )


def _aggregate_dns_record_status(records: object, record_kind: str) -> str:
    if not isinstance(records, list):
        return "unknown"
    statuses: list[str] = []
    for record in records:
        if not isinstance(record, dict) or record.get("record") != record_kind:
            continue
        raw_status = record.get("status")
        statuses.append(
            raw_status
            if isinstance(raw_status, str) and raw_status in _DNS_RECORD_STATUSES
            else "unknown"
        )
    if not statuses or "unknown" in statuses:
        return "unknown"
    for status in ("failed", "temporary_failure", "not_started", "pending"):
        if status in statuses:
            return status
    return "verified"


def _sanitize_webhook(
    value: dict[str, object],
    *,
    expected_endpoint_key: tuple[str, str, int | None, str],
) -> ResendWebhookState | None:
    try:
        webhook_id = str(uuid.UUID(str(value.get("id"))))
    except (ValueError, TypeError, AttributeError):
        return None

    raw_status = value.get("status")
    status = (
        raw_status if isinstance(raw_status, str) and raw_status in _WEBHOOK_STATUSES else "unknown"
    )
    raw_events = value.get("events")
    events: list[str] = []
    if isinstance(raw_events, list):
        for event in raw_events:
            if (
                isinstance(event, str)
                and event in RESEND_SANITIZED_WEBHOOK_EVENT_TYPES
                and event not in events
            ):
                events.append(event)
    return ResendWebhookState(
        id=webhook_id,
        status=status,
        events=tuple(events),
        endpoint_matches=(
            _normalize_webhook_endpoint(value.get("endpoint")) == expected_endpoint_key
        ),
    )


def _normalize_webhook_endpoint(
    value: object,
) -> tuple[str, str, int | None, str] | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    if (
        scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return None
    if (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        port = None
    path = parsed.path.rstrip("/") or "/"
    return scheme, parsed.hostname.lower(), port, path


def _bounded_retry_after_seconds(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.strip()
    if not re.fullmatch(r"[0-9]+", normalized):
        return None
    try:
        seconds = int(normalized)
    except ValueError:
        return None
    return min(seconds, MAX_RETRY_AFTER_SECONDS)
