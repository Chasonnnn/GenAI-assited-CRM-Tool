"""Durable Gmail delivery for explicitly approved AI drafts.

An unknown EmailLog is committed before provider I/O. Replays can finish local
bookkeeping, but must never repeat a send whose outcome was not persisted.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.surrogate_access import check_surrogate_access
from app.db.enums import AuditEventType, JobType, Role, SurrogateActivityType
from app.db.models import AIActionApproval, EmailLog, Job, User
from app.services import (
    activity_service,
    ai_service,
    audit_service,
    email_service,
    gmail_service,
    job_service,
    membership_service,
    note_service,
    oauth_service,
    permission_service,
    surrogate_service,
)
from app.types import JsonObject

DELIVERY_UNKNOWN = (
    "Delivery could not be confirmed. Check Gmail Sent before creating another email. "
    "This draft will not be resent automatically."
)
SEND_FAILED = "Gmail did not accept the email. Check your Gmail connection and sending limits."


def queue_email(
    db: Session, approval: AIActionApproval, user_id: UUID, org_id: UUID, entity_id: UUID
) -> JsonObject:
    """Stage one immutable intent; the approval service owns the commit and audit."""
    payload = approval.action_payload or {}
    for field, label in (
        ("to", "Recipient email"),
        ("subject", "Email subject"),
        ("body", "Email body"),
    ):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            return {"success": False, "error": f"{label} is required"}
    if (
        len(payload["to"]) > 255
        or len(payload["subject"]) > 200
        or any(char in payload["to"] + payload["subject"] for char in "\r\n")
    ):
        return {"success": False, "error": "Invalid recipient or subject"}
    surrogate = surrogate_service.get_surrogate(db, org_id, entity_id)
    if not surrogate:
        return {"success": False, "error": "Surrogate not found"}
    integration = oauth_service.get_user_integration(db, user_id, "gmail")
    if not integration or not integration.access_token_encrypted or not integration.account_email:
        return {"success": False, "error": "Gmail not connected. Please connect Gmail in settings."}

    job = job_service.enqueue_job(
        db,
        org_id,
        JobType.AI_SEND_EMAIL,
        payload={"approval_id": str(approval.id)},
        idempotency_key=f"ai-email/{approval.id}",
        commit=False,
    )
    # Ignore model-supplied idempotency keys: identity belongs to this approval.
    key = f"ai:{approval.id}"
    email = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == org_id,
            EmailLog.idempotency_key == key,
        )
        .with_for_update()
        .one_or_none()
    )
    if email is None:
        email = EmailLog(
            organization_id=org_id,
            recipient_email=payload["to"],
            subject=payload["subject"],
            body=payload["body"],
            status="pending",
            idempotency_key=key,
        )
        db.add(email)
        legacy_key = payload.get("idempotency_key")
        if (
            isinstance(legacy_key, str)
            and legacy_key != key
            and db.query(EmailLog.id)
            .filter(
                EmailLog.organization_id == org_id,
                EmailLog.idempotency_key == legacy_key,
            )
            .first()
        ):
            # Old proposals could supply arbitrary keys. A match may represent
            # an earlier send, but does not prove ownership of that log's content.
            email.status, email.error = "unknown", DELIVERY_UNKNOWN
    elif email.status == "pending":
        # Old synchronous sends committed PENDING before I/O; absence of a result
        # is not evidence that Gmail never accepted the message.
        email.status = "unknown"
        email.error = DELIVERY_UNKNOWN
    elif email.status != "sent":
        # Legacy errors may contain raw provider details; do not copy them into
        # the approval audit or response.
        email.error = DELIVERY_UNKNOWN if email.status == "unknown" else SEND_FAILED
    email.job_id = job.id
    email.source_type = "ai_approval"
    email.source_id = approval.id
    email.actor_user_id = user_id
    email.surrogate_id = entity_id
    email.from_email = integration.account_email
    email.provider = "gmail"
    db.flush()
    return {
        "success": True,
        "action": "send_email",
        "email_log_id": str(email.id),
        "job_id": str(job.id),
    }


def _finish_delivery(db: Session, approval: AIActionApproval, email: EmailLog) -> UUID | None:
    """Caller holds the approval lock; all local effects share its transaction."""
    if approval.status == "delivery_unknown" and email.status in {"sent", "failed"}:
        # An original request can finish after a replacement worker reports
        # uncertainty. A subsequently persisted provider receipt is authoritative.
        approval.status = "approved"
    if approval.status != "approved":
        return None
    sent = email.status == "sent"
    approval.status = (
        "executed" if sent else ("delivery_unknown" if email.status == "unknown" else "failed")
    )
    approval.error_message = None if sent else email.error
    approval.executed_at = datetime.now(UTC)
    if not sent:
        audit_service.log_ai_action_failed(
            db,
            email.organization_id,
            email.actor_user_id,
            approval.id,
            "send_email",
            email.error,
        )
        return None

    surrogate = surrogate_service.get_surrogate(db, email.organization_id, email.surrogate_id)
    if not surrogate:
        # The provider receipt remains authoritative even if the record was deleted.
        return None
    note = note_service.create_note(
        db=db,
        entity_type="surrogate",
        entity_id=surrogate.id,
        org_id=email.organization_id,
        author_id=email.actor_user_id,
        content=f"📧 **Email ✓ Sent** (via AI Assistant)\n\n**To:** {email.recipient_email}\n"
        f"**Subject:** {email.subject}\n\n---\n\n{email.body}\n",
        commit=False,
        emit_events=False,
    )
    surrogate.last_contacted_at = email.sent_at
    surrogate.last_contact_method = "email"
    activity_service.log_activity(
        db=db,
        surrogate_id=surrogate.id,
        organization_id=email.organization_id,
        activity_type=SurrogateActivityType.EMAIL_SENT,
        actor_user_id=email.actor_user_id,
        details={
            "source": "ai",
            "approval_id": str(approval.id),
            "action_type": "send_email",
            "provider": "gmail",
        },
    )
    audit_service.log_event(
        db=db,
        org_id=email.organization_id,
        event_type=AuditEventType.DATA_EMAIL_SENT,
        actor_user_id=email.actor_user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        details={
            "email_log_id": str(email.id),
            "approval_id": str(approval.id),
            "provider": "gmail",
        },
    )
    return note.id


async def process_email(db: Session, job: Job) -> None:
    """Job replay is safe: only a committed PENDING snapshot can initiate I/O."""
    org_id = job.organization_id
    approval, _, _ = ai_service.get_approval_with_conversation(
        db,
        UUID(job.payload["approval_id"]),
        org_id,
    )
    if not approval or approval.action_type != "send_email":
        raise ValueError("AI email approval not found in job organization")
    email = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == org_id,
            EmailLog.job_id == job.id,
            EmailLog.source_type == "ai_approval",
            EmailLog.source_id == approval.id,
        )
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if email is None:
        raise ValueError("AI email snapshot not found in job organization")
    if approval.status not in {"approved", "delivery_unknown"}:
        return

    if email.status == "pending":
        membership = membership_service.get_membership_for_org(db, org_id, email.actor_user_id)
        user = db.get(User, email.actor_user_id) if email.actor_user_id else None
        permissions = (
            permission_service.get_effective_permissions(
                db,
                org_id,
                email.actor_user_id,
                membership.role,
            )
            if membership and user and user.is_active
            else set()
        )
        surrogate = surrogate_service.get_surrogate(db, org_id, email.surrogate_id)
        error = None
        if not {"approve_ai_actions", "edit_surrogates"}.issubset(permissions) or not surrogate:
            error = "Email not sent: approval access is no longer available."
        else:
            try:
                check_surrogate_access(
                    surrogate=surrogate,
                    user_role=Role(membership.role),
                    user_id=email.actor_user_id,
                    db=db,
                    org_id=org_id,
                )
            except HTTPException:
                error = "Email not sent: approval access is no longer available."
        if not error and email_service.is_email_suppressed(db, org_id, email.recipient_email):
            error = "Email not sent: recipient is suppressed."
        if error:
            email.status, email.error = "failed", error
        else:
            from app.services import org_service, unsubscribe_service

            org = org_service.get_org_by_id(db, org_id)
            headers = unsubscribe_service.build_list_unsubscribe_headers(
                db,
                org_id=org_id,
                email=email.recipient_email,
                base_url=org_service.get_org_portal_base_url(org),
            )
            # Persist the no-resend boundary before OAuth refresh (which commits)
            # or HTTP I/O. A crash even just before sending requires human recovery.
            email.status, email.error = "unknown", DELIVERY_UNKNOWN
            email_id, approval_id = email.id, approval.id
            send_args = dict(
                user_id=str(email.actor_user_id),
                to=email.recipient_email,
                subject=email.subject,
                body=email.body,
                html=False,
                headers=headers,
                max_attempts=1,
                expected_sender=email.from_email,
            )
            db.commit()
            try:
                result = await gmail_service.send_email(db=db, **send_args)
            except Exception:
                # Do not log provider exception text; it can include draft content.
                db.rollback()
                result = {"success": False, "delivery_unknown": True}

            approval, _, _ = ai_service.get_approval_with_conversation(db, approval_id, org_id)
            email = (
                db.query(EmailLog)
                .filter(
                    EmailLog.id == email_id,
                    EmailLog.organization_id == org_id,
                )
                .populate_existing()
                .with_for_update()
                .one()
            )
            if result.get("success") and result.get("message_id"):
                email.status, email.error = "sent", None
                email.external_id = result["message_id"]
                email.sent_at = datetime.now(UTC)
            elif result.get("delivery_unknown") or result.get("success"):
                email.status, email.error = "unknown", DELIVERY_UNKNOWN
            else:
                email.status, email.error = "failed", SEND_FAILED
            # Save the provider receipt separately so a failed local audit/note can
            # be retried without repeating the provider call.
            db.commit()
            approval, _, _ = ai_service.get_approval_with_conversation(db, approval_id, org_id)

    note_id = _finish_delivery(db, approval, email)
    db.commit()
    if note_id:
        note_service.dispatch_note_added(db, note_id=note_id, org_id=org_id)


def finish_failed_job(db: Session, job: Job) -> UUID | None:
    """Settle an exhausted/recovered job without performing provider I/O."""
    approval, _, _ = ai_service.get_approval_with_conversation(
        db,
        UUID(job.payload["approval_id"]),
        job.organization_id,
    )
    if not approval or approval.status not in {"approved", "delivery_unknown"}:
        return
    email = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == job.organization_id,
            EmailLog.job_id == job.id,
            EmailLog.source_type == "ai_approval",
            EmailLog.source_id == approval.id,
        )
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if email is None:
        return
    if email.status == "pending":
        email.status, email.error = "failed", "Email could not be queued for delivery."
    return _finish_delivery(db, approval, email)
