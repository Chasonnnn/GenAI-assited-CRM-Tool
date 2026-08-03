"""Signature-verified, tenant-bound Twilio messaging webhooks."""

from __future__ import annotations

import hmac
import json
from datetime import UTC, datetime

from fastapi import HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator

from app.core.config import settings as app_settings
from app.core.encryption import hash_phone, hash_pii
from app.db.enums import JobScope, JobType
from app.db.models.messaging import MessagingContact, TwilioRoute
from app.db.models.messaging_delivery import (
    MessageDelivery,
    MessageReconciliationCase,
    MessageWebhookEvent,
    MessagingConversation,
    MessagingMessage,
)
from app.services import job_service, messaging_consent_service, twilio_settings_service
from app.services.messaging_opt_out_classifier import classify_consent_instruction
from app.utils.normalization import normalize_phone

EMPTY_TWIML = "<Response></Response>"
STATUS_RANK = {
    "accepted": 10,
    "scheduled": 10,
    "queued": 20,
    "sending": 30,
    "sent": 40,
    "failed": 50,
    "undelivered": 50,
    "canceled": 50,
    "delivered": 60,
    "read": 70,
}


def _empty_twiml() -> Response:
    return Response(content=EMPTY_TWIML, media_type="application/xml")


def _canonical_url(webhook_id: str, suffix: str) -> str:
    return f"{app_settings.API_BASE_URL.rstrip('/')}/webhooks/twilio/{webhook_id}/{suffix}"


def _resolve_route(db: Session, webhook_id: str) -> TwilioRoute:
    route = db.execute(
        select(TwilioRoute).where(TwilioRoute.webhook_id == webhook_id)
    ).scalar_one_or_none()
    if route is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return route


async def _validated_form(
    request: Request,
    *,
    route: TwilioRoute,
    suffix: str,
):
    settings = route.settings
    if not settings.auth_token_encrypted:
        raise HTTPException(status_code=503, detail="Webhook verification is unavailable")
    signature = request.headers.get("X-Twilio-Signature", "")
    form = await request.form()
    auth_token = twilio_settings_service.decrypt_credential(settings.auth_token_encrypted)
    if not RequestValidator(auth_token).validate(
        _canonical_url(route.webhook_id, suffix), form, signature
    ):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    return form


def _secure_equal(actual: str | None, expected: str | None) -> bool:
    return bool(actual and expected and hmac.compare_digest(actual, expected))


def _assert_tenant_binding(route: TwilioRoute, fields, *, inbound: bool) -> None:
    settings = route.settings
    expected_account = (
        twilio_settings_service.decrypt_credential(settings.account_sid_encrypted)
        if settings.account_sid_encrypted
        else None
    )
    expected_service = (
        twilio_settings_service.decrypt_credential(route.messaging_service_sid_encrypted)
        if route.messaging_service_sid_encrypted
        else None
    )
    expected_sender = (
        twilio_settings_service.decrypt_credential(route.sender_phone_encrypted)
        if route.sender_phone_encrypted
        else None
    )
    signed_sender = fields.get("To" if inbound else "From")
    if not (
        _secure_equal(fields.get("AccountSid"), expected_account)
        and _secure_equal(fields.get("MessagingServiceSid"), expected_service)
        and _secure_equal(signed_sender, expected_sender)
    ):
        raise HTTPException(status_code=403, detail="Webhook route mismatch")


def _raw_fields_json(form) -> str:
    return json.dumps(
        list(form.multi_items()),
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _event_account_hash(account_sid: str) -> str:
    return hash_pii(account_sid, purpose="twilio-account")


def _get_or_create_unknown_contact(
    db: Session,
    *,
    organization_id,
    phone: str,
    provider_message_sid: str,
) -> MessagingContact:
    normalized_phone = normalize_phone(phone)
    if normalized_phone is None:
        raise HTTPException(status_code=422, detail="Invalid sender")
    phone_digest = hash_phone(normalized_phone)
    contact = db.execute(
        select(MessagingContact).where(
            MessagingContact.organization_id == organization_id,
            MessagingContact.phone_hash == phone_digest,
        )
    ).scalar_one_or_none()
    if contact is not None:
        return contact
    created = messaging_consent_service.record_opt_in(
        db,
        organization_id=organization_id,
        phone=normalized_phone,
        purpose="operational",
        affirmative=False,
        disclosure_text=None,
        source="twilio_inbound",
        source_reference=provider_message_sid,
        occurred_at=datetime.now(UTC),
        idempotency_key=f"inbound-contact:{provider_message_sid}",
        evidence_metadata={},
    )
    return db.get(MessagingContact, created.contact_id)


def _apply_inbound_consent_first(
    db: Session,
    *,
    route: TwilioRoute,
    fields,
    provider_message_sid: str,
) -> MessagingContact:
    body = str(fields.get("Body") or "")
    opt_out_type = str(fields.get("OptOutType") or "").upper()
    phone = str(fields.get("From") or "")
    common = {
        "organization_id": route.organization_id,
        "phone": phone,
        "instruction_text": body,
        "source": "twilio_inbound",
        "source_reference": provider_message_sid,
        "occurred_at": datetime.now(UTC),
        "idempotency_key": f"twilio-consent:{provider_message_sid}",
        "evidence_metadata": {
            "route_purpose": route.purpose,
            "advanced_opt_out_type": opt_out_type or None,
        },
    }
    if opt_out_type == "STOP":
        result = messaging_consent_service.record_global_stop(db, **common)
    elif opt_out_type == "START":
        result = messaging_consent_service.restore_purpose_from_keyword(
            db,
            purpose=route.purpose,
            **common,
        )
    else:
        classification = classify_consent_instruction(body)
        if classification != "none":
            result = messaging_consent_service.apply_revocation_instruction(
                db,
                route_purpose=route.purpose,
                **common,
            )
        else:
            return _get_or_create_unknown_contact(
                db,
                organization_id=route.organization_id,
                phone=phone,
                provider_message_sid=provider_message_sid,
            )
    contact = db.get(MessagingContact, result.contact_id)
    if contact is None:
        raise RuntimeError("Consent transition did not retain a messaging contact")
    return contact


async def handle_inbound(
    request: Request,
    db: Session,
    *,
    webhook_id: str,
) -> Response:
    """Apply revocation first, then retain encrypted inbound content."""
    route = _resolve_route(db, webhook_id)
    form = await _validated_form(request, route=route, suffix="inbound")
    _assert_tenant_binding(route, form, inbound=True)
    account_sid = str(form.get("AccountSid") or "")
    message_sid = str(form.get("MessageSid") or form.get("SmsSid") or "")
    if not message_sid:
        raise HTTPException(status_code=422, detail="MessageSid is required")
    account_hash = _event_account_hash(account_sid)
    event_key = f"inbound:{message_sid}"
    existing = db.execute(
        select(MessageWebhookEvent.id).where(
            MessageWebhookEvent.account_sid_hash == account_hash,
            MessageWebhookEvent.event_key == event_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _empty_twiml()

    contact = _apply_inbound_consent_first(
        db,
        route=route,
        fields=form,
        provider_message_sid=message_sid,
    )
    event = MessageWebhookEvent(
        organization_id=route.organization_id,
        route_id=route.id,
        account_sid_hash=account_hash,
        event_key=event_key,
        event_type="inbound",
        provider_message_sid=message_sid,
        provider_status=str(form.get("SmsStatus") or "received"),
        raw_fields=_raw_fields_json(form),
    )
    db.add(event)
    conversation = db.execute(
        select(MessagingConversation).where(
            MessagingConversation.organization_id == route.organization_id,
            MessagingConversation.contact_id == contact.id,
            MessagingConversation.route_id == route.id,
        )
    ).scalar_one_or_none()
    if conversation is None:
        conversation = MessagingConversation(
            organization_id=route.organization_id,
            contact_id=contact.id,
            route_id=route.id,
        )
        db.add(conversation)
        db.flush()
    existing_message = db.execute(
        select(MessagingMessage.id).where(
            MessagingMessage.organization_id == route.organization_id,
            MessagingMessage.provider_message_sid == message_sid,
        )
    ).scalar_one_or_none()
    if existing_message is None:
        message = MessagingMessage(
            organization_id=route.organization_id,
            conversation_id=conversation.id,
            contact_id=contact.id,
            route_id=route.id,
            purpose=route.purpose,
            direction="inbound",
            body=str(form.get("Body") or ""),
            provider_message_sid=message_sid,
            from_phone_hash=contact.phone_hash,
            from_phone_last4=contact.phone_last4,
            to_phone_hash=route.sender_phone_hash or hash_phone(str(form.get("To") or "")),
            to_phone_last4=route.sender_phone_last4 or str(form.get("To") or "")[-4:],
            provider_status=str(form.get("SmsStatus") or "received"),
            is_unread=True,
        )
        db.add(message)
        conversation.unread_count += 1
        conversation.last_message_at = datetime.now(UTC)
        conversation.updated_at = datetime.now(UTC)
    raw_num_media = str(form.get("NumMedia") or "0")
    if raw_num_media != "0":
        db.flush()
        job_service.enqueue_job(
            db,
            route.organization_id,
            JobType.TWILIO_INBOUND_MEDIA_FETCH,
            {
                "provider_scope": JobScope.ORGANIZATION.value,
                "webhook_event_id": str(event.id),
            },
            idempotency_key=f"twilio-inbound-media:{event.id}",
            commit=False,
        )
    event.processed_at = datetime.now(UTC)
    db.commit()
    return _empty_twiml()


def _should_advance(current: str | None, incoming: str) -> bool:
    if current is None:
        return True
    return STATUS_RANK.get(incoming, 0) >= STATUS_RANK.get(current, 0)


async def handle_status(
    request: Request,
    db: Session,
    *,
    webhook_id: str,
) -> Response:
    """Append every distinct callback and advance delivery state monotonically."""
    route = _resolve_route(db, webhook_id)
    form = await _validated_form(request, route=route, suffix="status")
    _assert_tenant_binding(route, form, inbound=False)
    account_sid = str(form.get("AccountSid") or "")
    message_sid = str(form.get("MessageSid") or "")
    status = str(form.get("MessageStatus") or form.get("SmsStatus") or "").lower()
    if not message_sid or not status:
        raise HTTPException(status_code=422, detail="MessageSid and MessageStatus are required")
    account_hash = _event_account_hash(account_sid)
    error_code = str(form.get("ErrorCode") or "")
    event_key = f"status:{message_sid}:{status}:{error_code or '-'}"
    existing = db.execute(
        select(MessageWebhookEvent.id).where(
            MessageWebhookEvent.account_sid_hash == account_hash,
            MessageWebhookEvent.event_key == event_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _empty_twiml()

    event = MessageWebhookEvent(
        organization_id=route.organization_id,
        route_id=route.id,
        account_sid_hash=account_hash,
        event_key=event_key,
        event_type="status",
        provider_message_sid=message_sid,
        provider_status=status,
        raw_fields=_raw_fields_json(form),
    )
    db.add(event)
    message = db.execute(
        select(MessagingMessage)
        .where(
            MessagingMessage.organization_id == route.organization_id,
            MessagingMessage.provider_message_sid == message_sid,
            MessagingMessage.route_id == route.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    delivery = db.execute(
        select(MessageDelivery)
        .where(
            MessageDelivery.organization_id == route.organization_id,
            MessageDelivery.provider_message_sid == message_sid,
            MessageDelivery.route_id == route.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if message is None or delivery is None:
        db.flush()
        db.add(
            MessageReconciliationCase(
                organization_id=route.organization_id,
                case_type="orphan_webhook",
                status="action_required",
                reason_code="status_message_not_found",
                webhook_event_id=event.id,
            )
        )
    elif _should_advance(message.provider_status, status):
        message.provider_status = status
        if status in {"delivered", "read"}:
            delivery.status = "delivered"
            delivery.completed_at = datetime.now(UTC)
            from app.services import campaign_service

            campaign_service.project_campaign_message_delivery(
                db,
                organization_id=route.organization_id,
                message_delivery_id=delivery.id,
                status="delivered",
                provider_message_id=message_sid,
                commit=False,
            )
        elif status in {"failed", "undelivered", "canceled"}:
            delivery.status = "failed"
            delivery.completed_at = datetime.now(UTC)
            delivery.last_error_type = f"twilio_{status}"
            delivery.last_error = "Twilio reported a terminal delivery failure"
            from app.services import campaign_service

            campaign_service.project_campaign_message_delivery(
                db,
                organization_id=route.organization_id,
                message_delivery_id=delivery.id,
                status="failed",
                provider_message_id=message_sid,
                error="Twilio reported a terminal delivery failure",
                commit=False,
            )
        else:
            delivery.status = "submitted"
        delivery.updated_at = datetime.now(UTC)
    event.processed_at = datetime.now(UTC)
    db.commit()
    return _empty_twiml()
