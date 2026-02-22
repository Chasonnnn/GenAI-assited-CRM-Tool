"""Ticketing + mailbox ingestion job handlers."""

from __future__ import annotations

from uuid import UUID

from app.services import ticketing_service


def _uuid_from_payload(payload: dict, key: str) -> UUID:
    value = payload.get(key)
    if not value:
        raise ValueError(f"Missing {key} in job payload")
    return UUID(str(value))


async def process_mailbox_backfill(db, job) -> None:
    """Run full mailbox backfill."""
    payload = job.payload or {}
    org_id = _uuid_from_payload(payload, "organization_id")
    mailbox_id = _uuid_from_payload(payload, "mailbox_id")
    ticketing_service.process_mailbox_backfill(
        db,
        organization_id=org_id,
        mailbox_id=mailbox_id,
    )


async def process_mailbox_history_sync(db, job) -> None:
    """Run incremental mailbox history sync."""
    payload = job.payload or {}
    org_id = _uuid_from_payload(payload, "organization_id")
    mailbox_id = _uuid_from_payload(payload, "mailbox_id")
    ticketing_service.process_mailbox_history_sync(
        db,
        organization_id=org_id,
        mailbox_id=mailbox_id,
    )


async def process_mailbox_watch_refresh(db, job) -> None:
    """Ensure/renew Gmail watch subscription for a mailbox."""
    payload = job.payload or {}
    org_id = _uuid_from_payload(payload, "organization_id")
    mailbox_id = _uuid_from_payload(payload, "mailbox_id")
    ticketing_service.process_mailbox_watch_refresh(
        db,
        organization_id=org_id,
        mailbox_id=mailbox_id,
    )


async def process_email_occurrence_fetch_raw(db, job) -> None:
    """Fetch raw MIME payload for an email occurrence."""
    payload = job.payload or {}
    occurrence_id = _uuid_from_payload(payload, "occurrence_id")
    ticketing_service.process_occurrence_fetch_raw(db, occurrence_id=occurrence_id)


async def process_email_occurrence_parse(db, job) -> None:
    """Parse MIME payload for an occurrence and extract canonical content."""
    payload = job.payload or {}
    occurrence_id = _uuid_from_payload(payload, "occurrence_id")
    ticketing_service.process_occurrence_parse(db, occurrence_id=occurrence_id)


async def process_email_occurrence_stitch(db, job) -> None:
    """Stitch parsed occurrence onto an existing/new ticket."""
    payload = job.payload or {}
    occurrence_id = _uuid_from_payload(payload, "occurrence_id")
    ticketing_service.process_occurrence_stitch(db, occurrence_id=occurrence_id)


async def process_ticket_apply_linking(db, job) -> None:
    """Apply conservative surrogate-linking rules for a ticket."""
    payload = job.payload or {}
    org_id = _uuid_from_payload(payload, "organization_id")
    ticket_id = _uuid_from_payload(payload, "ticket_id")
    ticketing_service.apply_ticket_linking(
        db,
        org_id=org_id,
        ticket_id=ticket_id,
        actor_user_id=None,
    )


async def process_ticket_outbound_send(db, job) -> None:
    """Send queued outbound ticket email via Gmail."""
    payload = job.payload or {}
    await ticketing_service.process_ticket_outbound_send_job(
        db,
        job_id=UUID(str(job.id)),
        payload=payload,
    )
