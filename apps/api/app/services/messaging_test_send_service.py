"""Code-verified test phones and template test texts sent outside the outbox.

A test text goes only to a phone whose holder entered the code it received, so it needs no
recipient consent record, quiet hours, or opt-in confirmation first. A STOP from that phone
still blocks it, as it blocks every other text.

Successful changes are flushed, not committed: the router commits them together with their
audit event. Failures that must persist (a wrong code try, a text Twilio rejected) commit here.
"""

from __future__ import annotations

import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import hash_phone, hash_pii
from app.db.models import (
    MessageTemplate,
    MessagingConsentState,
    MessagingContact,
    MessagingGlobalSuppression,
    MessagingTestPhone,
    MessagingTestSend,
    Organization,
    TwilioRoute,
    TwilioSettings,
    User,
)
from app.services import (
    message_content_service,
    twilio_readiness_service,
    twilio_settings_service,
    twilio_transport,
)
from app.utils.normalization import normalize_phone

CODE_TTL = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5
MAX_LABEL_CHARACTERS = 80
_STATUS_RANK = {
    "accepted": 0,
    "queued": 0,
    "sending": 1,
    "sent": 2,
    "delivered": 3,
    "undelivered": 3,
    "failed": 3,
    "read": 4,
}
# The outbox worker is not involved in a test text.
_IGNORED_ROUTE_BLOCKERS = frozenset({"messaging_dispatch_worker_disabled"})


class MessagingTestError(ValueError):
    """A test phone or test text request that cannot proceed."""


class TestPhoneNotFound(MessagingTestError):
    pass


class TestSendRejected(MessagingTestError):
    """Twilio did not accept the text."""


@dataclass(frozen=True, slots=True)
class SmsVariable:
    name: str
    description: str
    sample: str


def sms_variables(organization_name: str) -> list[SmsVariable]:
    """Variables a text template can use, with the sample values test texts fill in."""
    return [
        SmsVariable("first_name", "Contact first name", "Jane"),
        SmsVariable("full_name", "Contact full name", "Jane Applicant"),
        SmsVariable("org_name", "Organization name", organization_name),
        SmsVariable("owner_name", "Case owner name", "Alex Coordinator"),
        SmsVariable("status_label", "Current status", "Application received"),
        SmsVariable("form_link", "Application form link", "https://example.com/apply"),
        SmsVariable("appointment_link", "Appointment booking link", "https://example.com/book"),
    ]


def _organization_name(db: Session, organization_id: uuid.UUID) -> str:
    return db.execute(
        select(Organization.name).where(Organization.id == organization_id)
    ).scalar_one()


def list_sms_variables(db: Session, organization_id: uuid.UUID) -> list[SmsVariable]:
    return sms_variables(_organization_name(db, organization_id))


def _code_hash(test_phone_id: uuid.UUID, code: str) -> str:
    return hash_pii(code, purpose=f"messaging-test-phone-code:{test_phone_id}")


def _settings(db: Session, organization_id: uuid.UUID) -> TwilioSettings:
    settings = db.execute(
        select(TwilioSettings).where(TwilioSettings.organization_id == organization_id)
    ).scalar_one_or_none()
    if settings is None:
        raise MessagingTestError("Set up Twilio messaging first")
    return settings


def _ready_route(db: Session, settings: TwilioSettings, purposes: tuple[str, ...]) -> TwilioRoute:
    """Return the first route of the given purposes that can send now."""
    first_blocker: str | None = None
    for purpose in purposes:
        route = db.execute(
            select(TwilioRoute).where(
                TwilioRoute.organization_id == settings.organization_id,
                TwilioRoute.purpose == purpose,
            )
        ).scalar_one_or_none()
        if route is None:
            first_blocker = first_blocker or f"The {purpose} route is not set up."
            continue
        blockers = [
            message
            for code, message in twilio_readiness_service.route_send_blockers(settings, route)
            if code not in _IGNORED_ROUTE_BLOCKERS
        ]
        if not blockers:
            return route
        first_blocker = first_blocker or blockers[0]
    raise MessagingTestError(first_blocker or "No messaging route can send now.")


def _send(
    db: Session,
    *,
    settings: TwilioSettings,
    route: TwilioRoute,
    to: str,
    body: str,
    kind: str,
    test_phone_id: uuid.UUID,
    template_id: uuid.UUID | None,
    sent_by_user_id: uuid.UUID,
) -> MessagingTestSend:
    from app.services.messaging_dispatch_service import app_base_url

    decrypt = twilio_settings_service.decrypt_credential
    result = twilio_transport.send_message(
        credentials=twilio_transport.TwilioCredentials(
            account_sid=decrypt(settings.account_sid_encrypted),
            api_key_sid=decrypt(settings.api_key_sid_encrypted),
            api_secret=decrypt(settings.api_secret_encrypted),
        ),
        to=to,
        from_=decrypt(route.sender_phone_encrypted),
        messaging_service_sid=decrypt(route.messaging_service_sid_encrypted),
        body=body,
        status_callback=f"{app_base_url()}/webhooks/twilio/{route.webhook_id}/status",
    )
    test_send = MessagingTestSend(
        organization_id=settings.organization_id,
        route_id=route.id,
        test_phone_id=test_phone_id,
        template_id=template_id,
        kind=kind,
        provider_message_sid=result.message_sid,
        provider_status=result.initial_status if result.success else "failed",
        error_code=(
            None
            if result.success
            else str(result.provider_error_code or result.failure_reason or "rejected")[:40]
        ),
        sent_by_user_id=sent_by_user_id,
    )
    db.add(test_send)
    db.flush()
    if not result.success:
        db.commit()
        if result.provider_opt_out:
            raise TestSendRejected("This phone replied STOP. Reply START from it to send again.")
        raise TestSendRejected("Twilio did not accept the text. Check the messaging settings.")
    return test_send


def _stopped_purposes(db: Session, organization_id: uuid.UUID, phone_hash: str) -> set[str]:
    """Purposes the phone opted out of; a global STOP covers both."""
    contact_id = db.execute(
        select(MessagingContact.id).where(
            MessagingContact.organization_id == organization_id,
            MessagingContact.phone_hash == phone_hash,
        )
    ).scalar_one_or_none()
    if contact_id is None:
        return set()
    suppressed = db.execute(
        select(MessagingGlobalSuppression.active).where(
            MessagingGlobalSuppression.organization_id == organization_id,
            MessagingGlobalSuppression.contact_id == contact_id,
        )
    ).scalar_one_or_none()
    if suppressed:
        return {"operational", "promotional"}
    return set(
        db.execute(
            select(MessagingConsentState.purpose).where(
                MessagingConsentState.organization_id == organization_id,
                MessagingConsentState.contact_id == contact_id,
                MessagingConsentState.status == "opted_out",
            )
        ).scalars()
    )


@dataclass(frozen=True, slots=True)
class TestPhoneView:
    phone: MessagingTestPhone
    stopped_purposes: frozenset[str]
    created_by_name: str | None


def _view(db: Session, phone: MessagingTestPhone) -> TestPhoneView:
    created_by_name = (
        db.execute(select(User.display_name).where(User.id == phone.created_by_user_id)).scalar()
        if phone.created_by_user_id
        else None
    )
    return TestPhoneView(
        phone=phone,
        stopped_purposes=frozenset(_stopped_purposes(db, phone.organization_id, phone.phone_hash)),
        created_by_name=created_by_name,
    )


def list_test_phones(db: Session, organization_id: uuid.UUID) -> list[TestPhoneView]:
    phones = db.execute(
        select(MessagingTestPhone)
        .where(MessagingTestPhone.organization_id == organization_id)
        .order_by(MessagingTestPhone.created_at)
    ).scalars()
    return [_view(db, phone) for phone in phones]


def _get_phone(
    db: Session, organization_id: uuid.UUID, test_phone_id: uuid.UUID
) -> MessagingTestPhone:
    phone = db.execute(
        select(MessagingTestPhone)
        .where(
            MessagingTestPhone.organization_id == organization_id,
            MessagingTestPhone.id == test_phone_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if phone is None:
        raise TestPhoneNotFound("Test phone not found")
    return phone


def add_test_phone(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    label: str,
    phone: str,
) -> TestPhoneView:
    """Add a phone, or a new code for one not yet verified, and text it the code."""
    normalized_label = " ".join(label.split())
    if not normalized_label:
        raise MessagingTestError("Label is required")
    if len(normalized_label) > MAX_LABEL_CHARACTERS:
        raise MessagingTestError(f"Label must not exceed {MAX_LABEL_CHARACTERS} characters")
    try:
        phone_e164 = normalize_phone(phone)
    except ValueError as exc:
        raise MessagingTestError("Enter a valid phone number") from exc
    if not phone_e164:
        raise MessagingTestError("Enter a valid phone number")
    settings = _settings(db, organization_id)
    route = _ready_route(db, settings, ("operational", "promotional"))

    phone_digest = hash_phone(phone_e164)
    test_phone = db.execute(
        select(MessagingTestPhone)
        .where(
            MessagingTestPhone.organization_id == organization_id,
            MessagingTestPhone.phone_hash == phone_digest,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if test_phone is not None and test_phone.verified_at is not None:
        raise MessagingTestError("This phone is already a verified test phone")
    if test_phone is None:
        test_phone = MessagingTestPhone(
            id=uuid.uuid4(),
            organization_id=organization_id,
            label=normalized_label,
            phone_e164=phone_e164,
            phone_hash=phone_digest,
            phone_last4=phone_e164[-4:],
            created_by_user_id=user_id,
        )
        db.add(test_phone)
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(UTC)
    test_phone.label = normalized_label
    test_phone.code_hash = _code_hash(test_phone.id, code)
    test_phone.code_expires_at = now + CODE_TTL
    test_phone.code_attempts = 0
    test_phone.updated_at = now
    db.flush()
    _send(
        db,
        settings=settings,
        route=route,
        to=phone_e164,
        body=(
            f"{settings.legal_messaging_brand}: Your test phone code is {code}. "
            "It expires in 10 minutes."
        ),
        kind="verification_code",
        test_phone_id=test_phone.id,
        template_id=None,
        sent_by_user_id=user_id,
    )
    db.flush()
    db.refresh(test_phone)
    return _view(db, test_phone)


def verify_test_phone(
    db: Session,
    *,
    organization_id: uuid.UUID,
    test_phone_id: uuid.UUID,
    code: str,
) -> TestPhoneView:
    test_phone = _get_phone(db, organization_id, test_phone_id)
    if test_phone.verified_at is not None:
        return _view(db, test_phone)
    now = datetime.now(UTC)
    if (
        test_phone.code_hash is None
        or test_phone.code_expires_at is None
        or test_phone.code_expires_at <= now
        or test_phone.code_attempts >= MAX_CODE_ATTEMPTS
    ):
        raise MessagingTestError("The code expired. Send a new code.")
    test_phone.code_attempts += 1
    test_phone.updated_at = now
    if not hmac.compare_digest(test_phone.code_hash, _code_hash(test_phone.id, code.strip())):
        db.commit()
        raise MessagingTestError("The code is not correct")
    test_phone.verified_at = now
    test_phone.code_hash = None
    test_phone.code_expires_at = None
    db.flush()
    db.refresh(test_phone)
    return _view(db, test_phone)


def remove_test_phone(db: Session, *, organization_id: uuid.UUID, test_phone_id: uuid.UUID) -> None:
    db.delete(_get_phone(db, organization_id, test_phone_id))
    db.flush()


def send_template_test(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    template_id: uuid.UUID,
    test_phone_id: uuid.UUID,
) -> MessagingTestSend:
    """Text one template version, filled with sample values, to a verified test phone."""
    template = db.execute(
        select(MessageTemplate).where(
            MessageTemplate.organization_id == organization_id,
            MessageTemplate.id == template_id,
        )
    ).scalar_one_or_none()
    if template is None:
        raise message_content_service.TemplateNotFound("Messaging template was not found")
    test_phone = _get_phone(db, organization_id, test_phone_id)
    if test_phone.verified_at is None:
        raise MessagingTestError("Verify this test phone first")
    if template.purpose in _stopped_purposes(db, organization_id, test_phone.phone_hash):
        raise MessagingTestError("This phone replied STOP. Reply START from it to send again.")
    if template.content_classification == "phi":
        message_content_service.require_phi_gate(db, organization_id)
    settings = _settings(db, organization_id)
    route = _ready_route(db, settings, (template.purpose,))
    variables = {
        variable.name: variable.sample
        for variable in sms_variables(_organization_name(db, organization_id))
    }
    test_send = _send(
        db,
        settings=settings,
        route=route,
        to=test_phone.phone_e164,
        body=message_content_service.render_message_body(template.body, variables),
        kind="template_test",
        test_phone_id=test_phone.id,
        template_id=template.id,
        sent_by_user_id=user_id,
    )
    db.refresh(test_send)
    return test_send


def record_status(
    db: Session,
    *,
    organization_id: uuid.UUID,
    route_id: uuid.UUID,
    provider_message_sid: str,
    provider_status: str,
    error_code: str | None,
) -> bool:
    """Apply a Twilio status callback to a test text; False when the SID is not one."""
    test_send = db.execute(
        select(MessagingTestSend).where(
            MessagingTestSend.organization_id == organization_id,
            MessagingTestSend.route_id == route_id,
            MessagingTestSend.provider_message_sid == provider_message_sid,
        )
    ).scalar_one_or_none()
    if test_send is None:
        return False
    # Callbacks can arrive out of order; never move back from a later status.
    if _STATUS_RANK.get(provider_status, 0) >= _STATUS_RANK.get(test_send.provider_status or "", 0):
        test_send.provider_status = provider_status[:30]
        test_send.error_code = error_code[:40] if error_code else None
        test_send.updated_at = datetime.now(UTC)
    return True
