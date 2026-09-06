"""Durable record correspondence associations, independent of current contact email."""

from datetime import UTC
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, load_only

from app.db.enums import AuditEventType, JobType
from app.db.models import (
    Appointment,
    AppointmentEmailLog,
    Campaign,
    CampaignRecipient,
    CampaignRun,
    EmailLog,
    Job,
    RecordTicketLink,
    Ticket,
)
from app.schemas.auth import UserSession
from app.services import audit_service
from app.services.record_access_service import get_record_with_access


def list_correspondence(
    db: Session, session: UserSession, kind: str, record_id: UUID, *, limit: int, offset: int
) -> dict:
    record = get_record_with_access(db, session, kind, record_id)
    column = getattr(RecordTicketLink, f"{kind}_id")
    ticket_query = (
        db.query(Ticket)
        .options(
            load_only(
                Ticket.id,
                Ticket.subject,
                Ticket.status,
                Ticket.requester_email,
                Ticket.last_activity_at,
                Ticket.created_at,
                Ticket.ticket_code,
            )
        )
        .join(RecordTicketLink, RecordTicketLink.ticket_id == Ticket.id)
        .filter(
            Ticket.organization_id == session.org_id,
            RecordTicketLink.organization_id == session.org_id,
            column == record_id,
        )
    )
    ticket_total = ticket_query.count()
    tickets = (
        ticket_query.order_by(
            func.coalesce(Ticket.last_activity_at, Ticket.created_at).desc(), Ticket.id.desc()
        )
        .limit(offset + limit)
        .all()
    )
    appointment_ids = db.query(Appointment.id).filter(
        Appointment.organization_id == session.org_id,
        getattr(Appointment, f"{kind}_id") == record_id,
    )
    appointment_log_ids = db.query(AppointmentEmailLog.email_log_id).filter(
        AppointmentEmailLog.organization_id == session.org_id,
        AppointmentEmailLog.appointment_id.in_(appointment_ids),
    )
    email_links = [
        (EmailLog.source_type == kind) & (EmailLog.source_id == record_id),
        EmailLog.id.in_(appointment_log_ids),
    ]
    if kind == "donor":
        recipients = (
            db.query(CampaignRecipient)
            .join(CampaignRun, CampaignRun.id == CampaignRecipient.run_id)
            .join(Campaign, Campaign.id == CampaignRun.campaign_id)
            .filter(
                CampaignRun.organization_id == session.org_id,
                Campaign.organization_id == session.org_id,
                Campaign.recipient_type == record.pipeline_entity_type,
                CampaignRecipient.entity_type == record.pipeline_entity_type,
                CampaignRecipient.entity_id == record_id,
            )
        )
        workflow_ids = db.query(Job.id).filter(
            Job.organization_id == session.org_id,
            Job.job_type == JobType.WORKFLOW_EMAIL.value,
            Job.payload["subject_type"].astext == record.pipeline_entity_type,
            Job.payload["subject_id"].astext == str(record_id),
        )
        # Source references retain previous sends; the recipient pointer covers older logs.
        email_links.extend(
            [
                (EmailLog.source_type == "campaign_recipient")
                & EmailLog.source_id.in_(recipients.with_entities(CampaignRecipient.id)),
                EmailLog.id.in_(recipients.with_entities(CampaignRecipient.email_log_id)),
                (EmailLog.source_type == "workflow_job") & EmailLog.source_id.in_(workflow_ids),
            ]
        )
    email_query = (
        db.query(EmailLog)
        .options(
            load_only(
                EmailLog.id,
                EmailLog.subject,
                EmailLog.status,
                EmailLog.recipient_email,
                EmailLog.created_at,
            )
        )
        .filter(EmailLog.organization_id == session.org_id, or_(*email_links))
    )
    email_total = email_query.count()
    emails = (
        email_query.order_by(EmailLog.created_at.desc(), EmailLog.id.desc())
        .limit(offset + limit)
        .all()
    )
    items = [
        {
            "id": str(t.id),
            "kind": "ticket",
            "subject": t.subject or "No subject",
            "status": t.status.value,
            "recipient": t.requester_email,
            "occurred_at": t.last_activity_at or t.created_at,
            "ticket_code": t.ticket_code,
        }
        for t in tickets
    ]
    items += [
        {
            "id": str(e.id),
            "kind": "email",
            "subject": e.subject,
            "status": e.status,
            "recipient": e.recipient_email,
            "occurred_at": e.created_at,
            "ticket_code": None,
        }
        for e in emails
    ]
    for item in items:
        if item["occurred_at"].tzinfo is None:
            item["occurred_at"] = item["occurred_at"].replace(tzinfo=UTC)
    items.sort(key=lambda item: (item["occurred_at"], item["id"]), reverse=True)
    return {"items": items[offset : offset + limit], "total": ticket_total + email_total}


def link_ticket(
    db: Session,
    session: UserSession,
    kind: str,
    record_id: UUID,
    ticket_id: UUID,
    *,
    remove: bool = False,
) -> None:
    get_record_with_access(db, session, kind, record_id, action="edit")
    ticket = (
        db.query(Ticket)
        .filter(Ticket.organization_id == session.org_id, Ticket.id == ticket_id)
        .with_for_update()
        .first()
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    # A pre-existing surrogate link retains its record access restriction.
    if ticket.surrogate_id:
        get_record_with_access(db, session, "surrogate", ticket.surrogate_id)
    column = getattr(RecordTicketLink, f"{kind}_id")
    query = db.query(RecordTicketLink).filter(
        RecordTicketLink.organization_id == session.org_id,
        RecordTicketLink.ticket_id == ticket_id,
        column == record_id,
    )
    existing = query.first()
    if remove:
        if existing is None:
            return
        db.delete(existing)
    else:
        if existing is not None:
            return
        db.add(
            RecordTicketLink(
                organization_id=session.org_id,
                ticket_id=ticket_id,
                **{f"{kind}_id": record_id},
                created_by_user_id=session.user_id,
            )
        )
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        actor_user_id=session.user_id,
        event_type=AuditEventType.RECORD_CORRESPONDENCE_UNLINKED
        if remove
        else AuditEventType.RECORD_CORRESPONDENCE_LINKED,
        target_type=kind,
        target_id=record_id,
        details={"ticket_id": str(ticket_id)},
    )
    db.commit()
