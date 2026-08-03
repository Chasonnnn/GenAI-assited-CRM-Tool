"""Signed, PII-free messaging preference tokens and consent transitions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.db.models import MessagingContact, TwilioSettings
from app.schemas.messaging import (
    MessagingPreferencePurposeResponse,
    MessagingPreferenceResponse,
)
from app.services import messaging_consent_service

TOKEN_VERSION = 1
TOKEN_TTL = timedelta(days=30)
PURPOSES = ("operational", "promotional")


class MessagingPreferenceInvalid(ValueError):
    pass


class MessagingPreferenceDisclosureStale(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreferenceToken:
    organization_id: uuid.UUID
    contact_id: uuid.UUID
    purposes: tuple[str, ...]
    disclosure_hashes: dict[str, str]
    jti: str
    expires_at: datetime


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def _sign(payload: str, secret: str) -> str:
    return _b64encode(
        hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    )


def _disclosure(settings: TwilioSettings, purpose: str) -> str:
    value = (
        settings.operational_disclosure
        if purpose == "operational"
        else settings.promotional_disclosure
    )
    normalized = value.strip() if value else ""
    if not normalized:
        raise MessagingPreferenceInvalid(f"{purpose.title()} disclosure is unavailable")
    return normalized


def _disclosure_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def generate_preference_token(
    db: Session,
    *,
    organization_id: uuid.UUID,
    contact_id: uuid.UUID,
    purposes: list[str],
    now: datetime | None = None,
) -> str:
    selected = tuple(dict.fromkeys(purposes))
    if not selected or any(purpose not in PURPOSES for purpose in selected):
        raise MessagingPreferenceInvalid("A supported messaging purpose is required")
    contact = db.execute(
        select(MessagingContact).where(
            MessagingContact.id == contact_id,
            MessagingContact.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    settings = db.execute(
        select(TwilioSettings).where(TwilioSettings.organization_id == organization_id)
    ).scalar_one_or_none()
    if contact is None or settings is None:
        raise MessagingPreferenceInvalid("Messaging preference contact is unavailable")
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + TOKEN_TTL
    payload = {
        "v": TOKEN_VERSION,
        "org": str(organization_id),
        "contact": str(contact_id),
        "purposes": list(selected),
        "disclosures": {
            purpose: _disclosure_hash(_disclosure(settings, purpose))
            for purpose in selected
        },
        "jti": uuid.uuid4().hex,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    encoded = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    secrets = app_settings.jwt_secrets
    if not secrets:
        raise MessagingPreferenceInvalid("Messaging preference signing is unavailable")
    return f"{encoded}.{_sign(encoded, secrets[0])}"


def parse_preference_token(token: str, *, now: datetime | None = None) -> PreferenceToken:
    try:
        encoded, signature = token.split(".", 1)
        if not any(
            hmac.compare_digest(_sign(encoded, secret), signature)
            for secret in app_settings.jwt_secrets
        ):
            raise MessagingPreferenceInvalid("Messaging consent link is invalid or expired")
        payload = json.loads(_b64decode(encoded))
        purposes = tuple(payload["purposes"])
        parsed = PreferenceToken(
            organization_id=uuid.UUID(payload["org"]),
            contact_id=uuid.UUID(payload["contact"]),
            purposes=purposes,
            disclosure_hashes=dict(payload["disclosures"]),
            jti=str(payload["jti"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
        )
    except MessagingPreferenceInvalid:
        raise
    except Exception as exc:
        raise MessagingPreferenceInvalid("Messaging consent link is invalid or expired") from exc
    checked_at = now or datetime.now(UTC)
    if (
        payload.get("v") != TOKEN_VERSION
        or parsed.expires_at <= checked_at
        or not parsed.purposes
        or len(parsed.purposes) != len(set(parsed.purposes))
        or any(purpose not in PURPOSES for purpose in parsed.purposes)
    ):
        raise MessagingPreferenceInvalid("Messaging consent link is invalid or expired")
    return parsed


def _load_preference(db: Session, token: PreferenceToken):
    contact = db.execute(
        select(MessagingContact).where(
            MessagingContact.id == token.contact_id,
            MessagingContact.organization_id == token.organization_id,
        )
    ).scalar_one_or_none()
    settings = db.execute(
        select(TwilioSettings).where(
            TwilioSettings.organization_id == token.organization_id
        )
    ).scalar_one_or_none()
    if contact is None or settings is None:
        raise MessagingPreferenceInvalid("Messaging consent link is invalid or expired")
    disclosures = {purpose: _disclosure(settings, purpose) for purpose in token.purposes}
    if any(
        token.disclosure_hashes.get(purpose) != _disclosure_hash(value)
        for purpose, value in disclosures.items()
    ):
        raise MessagingPreferenceDisclosureStale(
            "This consent link uses an outdated disclosure"
        )
    return contact, settings, disclosures


def project_preference(
    db: Session,
    *,
    token: PreferenceToken,
) -> MessagingPreferenceResponse:
    contact, settings, _token_disclosures = _load_preference(db, token)
    disclosures = {
        purpose: value
        for purpose in PURPOSES
        if (value := (
            settings.operational_disclosure
            if purpose == "operational"
            else settings.promotional_disclosure
        ))
        and value.strip()
    }
    states = {state.purpose: state.status for state in contact.consent_states}
    suppression = contact.suppression
    return MessagingPreferenceResponse(
        legal_brand=(settings.legal_messaging_brand or "").strip(),
        masked_phone=f"••• ••• {contact.phone_last4}",
        support_contact=(settings.support_contact or "").strip(),
        expected_frequency=settings.expected_frequency,
        sms_terms_url=(settings.sms_terms_url or "").strip(),
        privacy_policy_url=(settings.privacy_policy_url or "").strip(),
        purposes={
            purpose: MessagingPreferencePurposeResponse(
                disclosure=disclosure,
                status=states.get(purpose, "unknown"),
            )
            for purpose, disclosure in disclosures.items()
        },
        global_suppression_active=bool(suppression and suppression.active),
        expires_at=token.expires_at,
    )


def update_preference(
    db: Session,
    *,
    token: PreferenceToken,
    action: str,
    purposes: list[str],
    affirmative: bool,
) -> MessagingPreferenceResponse:
    contact, _settings, disclosures = _load_preference(db, token)
    selected = tuple(dict.fromkeys(purposes))
    if not selected or any(purpose not in token.purposes for purpose in selected):
        raise MessagingPreferenceInvalid("Selected purpose is not available on this link")
    if not affirmative:
        raise MessagingPreferenceInvalid("An affirmative preference selection is required")
    now = datetime.now(UTC)
    if action == "opt_in":
        for purpose in selected:
            messaging_consent_service.record_opt_in(
                db,
                organization_id=token.organization_id,
                phone=contact.phone_e164,
                purpose=purpose,
                affirmative=True,
                disclosure_text=disclosures[purpose],
                source="preference_page",
                source_reference=token.jti,
                occurred_at=now,
                idempotency_key=f"preference:{token.jti}:opt-in:{purpose}",
                evidence_metadata={"affirmative_action": "selected_and_submitted"},
                commit=False,
            )
    elif action == "opt_out":
        if set(selected) == set(PURPOSES):
            messaging_consent_service.record_global_stop(
                db,
                organization_id=token.organization_id,
                phone=contact.phone_e164,
                instruction_text="Messaging preference page: stop all text messages",
                source="preference_page",
                source_reference=token.jti,
                occurred_at=now,
                idempotency_key=f"preference:{token.jti}:opt-out:all",
                evidence_metadata={"affirmative_action": "selected_and_submitted"},
                commit=False,
            )
        else:
            for purpose in selected:
                messaging_consent_service.record_purpose_opt_out(
                    db,
                    organization_id=token.organization_id,
                    phone=contact.phone_e164,
                    purpose=purpose,
                    instruction_text=f"Messaging preference page: stop {purpose} texts",
                    source="preference_page",
                    source_reference=token.jti,
                    occurred_at=now,
                    idempotency_key=f"preference:{token.jti}:opt-out:{purpose}",
                    evidence_metadata={"affirmative_action": "selected_and_submitted"},
                    commit=False,
                )
    else:
        raise MessagingPreferenceInvalid("Unsupported messaging preference action")
    db.commit()
    db.expire(contact)
    return project_preference(db, token=token)
