"""Twilio readiness and messaging worker handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.enums import JobScope
from app.db.models import (
    MessagingConsentEvidence,
    MessagingConsentState,
    TwilioRoute,
    TwilioSettings,
)


async def process_twilio_readiness_check(db, job) -> None:
    """Run one trusted organization-scoped, no-send readiness check."""
    payload = job.payload if isinstance(job.payload, dict) else {}
    if (
        job.job_scope != JobScope.ORGANIZATION.value
        or job.organization_id is None
        or payload.get("provider_scope") != JobScope.ORGANIZATION.value
        or not isinstance(payload.get("settings_version"), int)
    ):
        raise ValueError("Invalid Twilio readiness job scope")
    from app.services import twilio_readiness_service

    persisted = twilio_readiness_service.refresh_readiness(
        db,
        organization_id=job.organization_id,
        expected_settings_version=payload["settings_version"],
    )
    if not persisted:
        # A configuration save fenced this result. A later operator check probes
        # the new route; stale evidence must never overwrite it.
        return


def _consent_source(evidence_source: str, provider_status: str) -> str:
    normalized = evidence_source.casefold()
    if normalized in {
        "website",
        "website_intake",
        "meta_lead",
        "meta_form",
        "preference_page",
    }:
        return "website"
    if any(token in normalized for token in ("offline", "legacy", "staff", "phone")):
        return "offline"
    if "twilio" in normalized or "inbound" in normalized:
        return "opt-in-message" if provider_status == "opt-in" else "opt-out-message"
    return "others"


def _mark_sync_unavailable(state: MessagingConsentState) -> None:
    state.provider_sync_status = "unavailable"
    state.provider_sync_error_code = "text_start_required"
    state.provider_synced_at = None
    state.updated_at = datetime.now(UTC)


async def process_twilio_consent_sync(db, job) -> None:
    """Project one locally authoritative consent transition to an exact Twilio route."""
    payload = job.payload if isinstance(job.payload, dict) else {}
    if (
        job.job_scope != JobScope.ORGANIZATION.value
        or job.organization_id is None
        or payload.get("provider_scope") != JobScope.ORGANIZATION.value
        or payload.get("purpose") not in {"operational", "promotional"}
        or payload.get("status") not in {"opt-in", "opt-out"}
    ):
        raise ValueError("Invalid Twilio consent synchronization job scope")

    try:
        state_id = UUID(str(payload["consent_state_id"]))
        evidence_id = UUID(str(payload["evidence_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid Twilio consent synchronization identity") from exc

    state = db.execute(
        select(MessagingConsentState)
        .where(
            MessagingConsentState.id == state_id,
            MessagingConsentState.organization_id == job.organization_id,
            MessagingConsentState.purpose == payload["purpose"],
        )
        .with_for_update()
    ).scalar_one_or_none()
    evidence = db.execute(
        select(MessagingConsentEvidence).where(
            MessagingConsentEvidence.id == evidence_id,
            MessagingConsentEvidence.organization_id == job.organization_id,
        )
    ).scalar_one_or_none()
    if state is None or evidence is None or evidence.contact_id != state.contact_id:
        raise ValueError("Twilio consent synchronization record was not found")

    # A later local transition always wins. Never project stale STOP or re-opt
    # state after a new evidence epoch has replaced this job's snapshot.
    if state.latest_evidence_id != evidence.id:
        return

    settings = db.execute(
        select(TwilioSettings).where(
            TwilioSettings.organization_id == job.organization_id
        )
    ).scalar_one_or_none()
    route = db.execute(
        select(TwilioRoute).where(
            TwilioRoute.organization_id == job.organization_id,
            TwilioRoute.purpose == state.purpose,
        )
    ).scalar_one_or_none()

    route_evidence = route.capability_evidence or {} if route is not None else {}
    provider_evidence = (
        route_evidence.get("provider")
        if isinstance(route_evidence.get("provider"), dict)
        else {}
    )
    sender_type = str(
        provider_evidence.get("sender_type") or route_evidence.get("sender_type") or ""
    ).casefold()
    configured = bool(
        settings is not None
        and settings.enabled
        and settings.account_sid_encrypted
        and settings.api_key_sid_encrypted
        and settings.api_secret_encrypted
        and route is not None
        and route.enabled
        and route.messaging_service_sid_encrypted
        and route.sender_phone_encrypted
        and route.a2p_status == "approved"
        and sender_type == "10dlc"
    )
    if not configured:
        _mark_sync_unavailable(state)
        db.commit()
        return

    from app.services import twilio_settings_service, twilio_transport

    credentials = twilio_transport.TwilioCredentials(
        account_sid=twilio_settings_service.decrypt_credential(
            settings.account_sid_encrypted
        ),
        api_key_sid=twilio_settings_service.decrypt_credential(
            settings.api_key_sid_encrypted
        ),
        api_secret=twilio_settings_service.decrypt_credential(
            settings.api_secret_encrypted
        ),
    )
    result = twilio_transport.upsert_route_consent(
        credentials=credentials,
        contact_id=state.contact.phone_e164,
        messaging_service_sid=twilio_settings_service.decrypt_credential(
            route.messaging_service_sid_encrypted
        ),
        sender_phone=twilio_settings_service.decrypt_credential(
            route.sender_phone_encrypted
        ),
        status=payload["status"],
        source=_consent_source(evidence.source, payload["status"]),
        date_of_consent=evidence.occurred_at,
        route_marker=sender_type,
    )

    if not result.success:
        if result.retryable:
            raise RuntimeError("Twilio consent synchronization transient failure")
        state.updated_at = datetime.now(UTC)
        state.provider_sync_status = "failed"
        state.provider_sync_error_code = (
            result.failure_reason.value if result.failure_reason is not None else "provider_failed"
        )
        state.provider_synced_at = None
        db.commit()
        return

    state.updated_at = datetime.now(UTC)
    state.provider_sync_status = "synced"
    state.provider_sync_error_code = None
    state.provider_synced_at = datetime.now(UTC)
    route.consent_management_status = "available"
    route_evidence = dict(route.capability_evidence or {})
    route_evidence["consent_management"] = {
        "source": "successful_upsert",
        "verified_at": datetime.now(UTC).isoformat(),
    }
    route.capability_evidence = route_evidence
    route.updated_at = datetime.now(UTC)
    if payload["status"] == "opt-in":
        state.status = "opted_in"
        suppression = state.contact.suppression
        if suppression is not None:
            suppression.active = False
            suppression.reason = "none"
            suppression.latest_evidence_id = evidence.id
            suppression.effective_at = evidence.occurred_at
            suppression.updated_at = datetime.now(UTC)
    db.commit()


async def process_twilio_inbound_media_fetch(db, job) -> None:
    """Fetch, scan-gate, persist, and remove Twilio's copy of inbound MMS media."""
    payload = job.payload if isinstance(job.payload, dict) else {}
    if (
        job.job_scope != JobScope.ORGANIZATION.value
        or job.organization_id is None
        or payload.get("provider_scope") != JobScope.ORGANIZATION.value
    ):
        raise ValueError("Invalid Twilio inbound media job scope")
    try:
        event_id = UUID(str(payload["webhook_event_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid Twilio inbound media event identity") from exc
    from app.services import twilio_inbound_media_service

    twilio_inbound_media_service.process_inbound_media_event(
        db,
        organization_id=job.organization_id,
        webhook_event_id=event_id,
    )
