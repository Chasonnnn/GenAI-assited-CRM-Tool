"""Organization-scoped messaging consent ledger transitions."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import hash_phone
from app.db.enums import JobScope, JobType
from app.db.models import (
    IntakeLead,
    MessagingConsentEvidence,
    MessagingConsentState,
    MessagingContact,
    MessagingGlobalSuppression,
    MetaLead,
    Surrogate,
)
from app.services import job_service
from app.services.messaging_opt_out_classifier import classify_consent_instruction
from app.utils.normalization import extract_phone_last4, normalize_phone

ConsentPurpose = Literal["operational", "promotional"]
PURPOSES: tuple[ConsentPurpose, ...] = ("operational", "promotional")


class MessagingConsentValidationError(ValueError):
    """Raised when consent evidence is incomplete or invalid."""


class MessagingConsentIdempotencyConflict(ValueError):
    """Raised when one idempotency key is reused for different evidence."""


class MessagingConsentEntityNotFound(ValueError):
    """Raised when a linked CRM entity is absent from the active organization."""


@dataclass(frozen=True)
class ConsentTransitionResult:
    contact_id: uuid.UUID
    phone_last4: str
    purpose_states: dict[str, str]
    global_suppression_active: bool
    global_suppression_reason: str
    evidence_id: uuid.UUID | None = None
    classification: str | None = None


def _normalize_required_phone(phone: str) -> str:
    try:
        normalized = normalize_phone(phone)
    except ValueError as exc:
        raise MessagingConsentValidationError(str(exc)) from exc
    if normalized is None:
        raise MessagingConsentValidationError("Phone number is required")
    return normalized


def _get_or_create_contact(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
) -> MessagingContact:
    normalized_phone = _normalize_required_phone(phone)
    phone_hash = hash_phone(normalized_phone)
    contact = (
        db.query(MessagingContact)
        .filter(
            MessagingContact.organization_id == organization_id,
            MessagingContact.phone_hash == phone_hash,
        )
        .first()
    )
    if contact is None:
        phone_last4 = extract_phone_last4(normalized_phone)
        if phone_last4 is None:
            raise MessagingConsentValidationError("Phone number is required")
        contact = MessagingContact(
            organization_id=organization_id,
            phone_e164=normalized_phone,
            phone_hash=phone_hash,
            phone_last4=phone_last4,
        )
        db.add(contact)
        db.flush()

    existing_states = {state.purpose: state for state in contact.consent_states}
    for purpose in PURPOSES:
        if purpose not in existing_states:
            state = MessagingConsentState(
                organization_id=organization_id,
                contact_id=contact.id,
                purpose=purpose,
                status="unknown",
            )
            db.add(state)
            contact.consent_states.append(state)

    if contact.suppression is None:
        contact.suppression = MessagingGlobalSuppression(
            organization_id=organization_id,
            contact_id=contact.id,
            active=False,
            reason="none",
        )
    db.flush()
    return contact


def _require_text(value: str | None, field_name: str) -> str:
    normalized = value.strip() if value else ""
    if not normalized:
        raise MessagingConsentValidationError(f"{field_name} is required")
    return normalized


def _normalize_occurred_at(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MessagingConsentValidationError("occurred_at must include a timezone")
    return value.astimezone(UTC)


def _validate_metadata(value: dict) -> dict:
    if not isinstance(value, dict):
        raise MessagingConsentValidationError("evidence_metadata must be an object")
    return value


def _validate_and_attach_entities(
    db: Session,
    contact: MessagingContact,
    *,
    organization_id: uuid.UUID,
    intake_lead_id: uuid.UUID | None,
    meta_lead_id: uuid.UUID | None,
    surrogate_id: uuid.UUID | None,
) -> None:
    links = (
        ("intake_lead_id", IntakeLead, intake_lead_id),
        ("meta_lead_id", MetaLead, meta_lead_id),
        ("surrogate_id", Surrogate, surrogate_id),
    )
    for attribute, model, entity_id in links:
        if entity_id is None:
            continue
        exists = db.scalar(
            select(model.id).where(
                model.id == entity_id,
                model.organization_id == organization_id,
            )
        )
        if exists is None:
            raise MessagingConsentEntityNotFound(
                "The linked entity was not found in this organization"
            )
        current_id = getattr(contact, attribute)
        if current_id is not None and current_id != entity_id:
            raise MessagingConsentValidationError(
                f"Contact is already linked to a different {attribute.removesuffix('_id')}"
            )
        setattr(contact, attribute, entity_id)


def _canonical_evidence_payload(
    *,
    contact_id: uuid.UUID,
    purpose: str,
    action: str,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    disclosure_text: str | None,
    instruction_text: str | None,
    evidence_metadata: dict,
    intake_lead_id: uuid.UUID | None,
    meta_lead_id: uuid.UUID | None,
    surrogate_id: uuid.UUID | None,
) -> str:
    return json.dumps(
        {
            "action": action,
            "contact_id": str(contact_id),
            "disclosure_text": disclosure_text,
            "evidence_metadata": evidence_metadata,
            "instruction_text": instruction_text,
            "intake_lead_id": str(intake_lead_id) if intake_lead_id else None,
            "meta_lead_id": str(meta_lead_id) if meta_lead_id else None,
            "occurred_at": occurred_at.isoformat(),
            "purpose": purpose,
            "source": source,
            "source_reference": source_reference,
            "surrogate_id": str(surrogate_id) if surrogate_id else None,
        },
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    )


def _append_evidence(
    db: Session,
    *,
    organization_id: uuid.UUID,
    contact: MessagingContact,
    purpose: str,
    action: str,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    idempotency_key: str,
    evidence_metadata: dict,
    disclosure_text: str | None = None,
    instruction_text: str | None = None,
    intake_lead_id: uuid.UUID | None = None,
    meta_lead_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
) -> tuple[MessagingConsentEvidence, bool]:
    normalized_source = _require_text(source, "source")
    normalized_reference = _require_text(source_reference, "source_reference")
    normalized_key = _require_text(idempotency_key, "idempotency_key")
    normalized_occurred_at = _normalize_occurred_at(occurred_at)
    normalized_metadata = _validate_metadata(evidence_metadata)
    payload = _canonical_evidence_payload(
        contact_id=contact.id,
        purpose=purpose,
        action=action,
        source=normalized_source,
        source_reference=normalized_reference,
        occurred_at=normalized_occurred_at,
        disclosure_text=disclosure_text,
        instruction_text=instruction_text,
        evidence_metadata=normalized_metadata,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
    )
    evidence_hash = hashlib.sha256(payload.encode()).hexdigest()
    existing = (
        db.query(MessagingConsentEvidence)
        .filter(
            MessagingConsentEvidence.organization_id == organization_id,
            MessagingConsentEvidence.idempotency_key == normalized_key,
        )
        .first()
    )
    if existing is not None:
        if existing.evidence_hash != evidence_hash:
            raise MessagingConsentIdempotencyConflict(
                "The idempotency key already identifies different consent evidence"
            )
        return existing, True

    evidence = MessagingConsentEvidence(
        organization_id=organization_id,
        contact_id=contact.id,
        purpose=purpose,
        action=action,
        source=normalized_source,
        source_reference=normalized_reference,
        idempotency_key=normalized_key,
        evidence_hash=evidence_hash,
        disclosure_text_snapshot=disclosure_text,
        disclosure_hash=(
            hashlib.sha256(disclosure_text.encode()).hexdigest() if disclosure_text else None
        ),
        instruction_text=instruction_text,
        evidence_metadata=normalized_metadata,
        occurred_at=normalized_occurred_at,
        recorded_by_user_id=recorded_by_user_id,
    )
    db.add(evidence)
    db.flush()
    return evidence, False


def _state_for(contact: MessagingContact, purpose: ConsentPurpose) -> MessagingConsentState:
    return next(state for state in contact.consent_states if state.purpose == purpose)


def _is_current_or_newer(effective_at: datetime | None, occurred_at: datetime) -> bool:
    if effective_at is None:
        return True
    return occurred_at >= effective_at


def _apply_state(
    state: MessagingConsentState,
    *,
    status: str,
    evidence: MessagingConsentEvidence,
) -> None:
    if not _is_current_or_newer(state.effective_at, evidence.occurred_at):
        return
    state.status = status
    state.latest_evidence_id = evidence.id
    state.effective_at = evidence.occurred_at
    state.updated_at = datetime.now(UTC)


def _set_provider_sync_state(
    state: MessagingConsentState,
    *,
    status: str,
    requested_at: datetime | None = None,
) -> None:
    state.provider_sync_status = status
    state.provider_sync_error_code = None
    state.provider_sync_requested_at = requested_at
    if status != "synced":
        state.provider_synced_at = None


def _enqueue_provider_sync(
    db: Session,
    *,
    organization_id: uuid.UUID,
    state: MessagingConsentState,
    evidence: MessagingConsentEvidence,
    provider_status: Literal["opt-in", "opt-out"],
) -> None:
    """Queue a PII-free, idempotent provider projection for one exact route."""
    job_service.enqueue_job(
        db,
        organization_id,
        JobType.TWILIO_CONSENT_SYNC,
        {
            "consent_state_id": str(state.id),
            "evidence_id": str(evidence.id),
            "purpose": state.purpose,
            "provider_scope": JobScope.ORGANIZATION.value,
            "status": provider_status,
        },
        idempotency_key=(
            f"twilio-consent:{evidence.id}:{state.purpose}:{provider_status}"
        ),
        commit=False,
    )


def _clear_suppression_if_current(
    contact: MessagingContact,
    *,
    evidence: MessagingConsentEvidence,
) -> None:
    suppression = contact.suppression
    if suppression is None or not _is_current_or_newer(
        suppression.effective_at, evidence.occurred_at
    ):
        return
    suppression.active = False
    suppression.reason = "none"
    suppression.latest_evidence_id = evidence.id
    suppression.effective_at = evidence.occurred_at
    suppression.updated_at = datetime.now(UTC)


def _common_contact_and_entities(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
    intake_lead_id: uuid.UUID | None,
    meta_lead_id: uuid.UUID | None,
    surrogate_id: uuid.UUID | None,
) -> MessagingContact:
    contact = _get_or_create_contact(
        db,
        organization_id=organization_id,
        phone=phone,
    )
    _validate_and_attach_entities(
        db,
        contact,
        organization_id=organization_id,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
    )
    return contact


def _project(
    contact: MessagingContact,
    *,
    evidence_id: uuid.UUID | None = None,
    classification: str | None = None,
) -> ConsentTransitionResult:
    states = {state.purpose: state.status for state in contact.consent_states}
    suppression = contact.suppression
    return ConsentTransitionResult(
        contact_id=contact.id,
        phone_last4=contact.phone_last4,
        purpose_states={purpose: states.get(purpose, "unknown") for purpose in PURPOSES},
        global_suppression_active=bool(suppression and suppression.active),
        global_suppression_reason=suppression.reason if suppression else "none",
        evidence_id=evidence_id,
        classification=classification,
    )


def _finalize(db: Session, *, commit: bool) -> None:
    if commit:
        db.commit()
    else:
        db.flush()


def record_opt_in(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
    purpose: ConsentPurpose,
    affirmative: bool,
    disclosure_text: str | None,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    idempotency_key: str,
    evidence_metadata: dict,
    intake_lead_id: uuid.UUID | None = None,
    meta_lead_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> ConsentTransitionResult:
    """Record an affirmative opt-in; unchecked input remains unknown."""
    if purpose not in PURPOSES:
        raise MessagingConsentValidationError("Purpose must be operational or promotional")
    contact = _common_contact_and_entities(
        db,
        organization_id=organization_id,
        phone=phone,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
    )
    if not affirmative:
        _finalize(db, commit=commit)
        return _project(contact)

    normalized_disclosure = _require_text(disclosure_text, "disclosure_text")
    evidence, replayed = _append_evidence(
        db,
        organization_id=organization_id,
        contact=contact,
        purpose=purpose,
        action="opt_in",
        source=source,
        source_reference=source_reference,
        occurred_at=occurred_at,
        idempotency_key=idempotency_key,
        evidence_metadata=evidence_metadata,
        disclosure_text=normalized_disclosure,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
        recorded_by_user_id=recorded_by_user_id,
    )
    if not replayed:
        state = _state_for(contact, purpose)
        newer = _is_current_or_newer(state.effective_at, evidence.occurred_at)
        suppression = contact.suppression
        requires_provider_reopt = newer and (
            state.status in {"opted_out", "reopt_pending"}
            or bool(suppression and suppression.active)
        )
        if requires_provider_reopt:
            _apply_state(state, status="reopt_pending", evidence=evidence)
            _set_provider_sync_state(
                state,
                status="pending",
                requested_at=datetime.now(UTC),
            )
            _enqueue_provider_sync(
                db,
                organization_id=organization_id,
                state=state,
                evidence=evidence,
                provider_status="opt-in",
            )
        else:
            _apply_state(state, status="opted_in", evidence=evidence)
            if newer:
                _set_provider_sync_state(state, status="not_required")
                _clear_suppression_if_current(contact, evidence=evidence)
    _finalize(db, commit=commit)
    return _project(contact, evidence_id=evidence.id)


def _record_instruction(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
    purpose: str,
    action: str,
    instruction_text: str,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    idempotency_key: str,
    evidence_metadata: dict,
    intake_lead_id: uuid.UUID | None = None,
    meta_lead_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
) -> tuple[MessagingContact, MessagingConsentEvidence, bool]:
    normalized_instruction = _require_text(instruction_text, "instruction_text")
    contact = _common_contact_and_entities(
        db,
        organization_id=organization_id,
        phone=phone,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
    )
    evidence, replayed = _append_evidence(
        db,
        organization_id=organization_id,
        contact=contact,
        purpose=purpose,
        action=action,
        source=source,
        source_reference=source_reference,
        occurred_at=occurred_at,
        idempotency_key=idempotency_key,
        evidence_metadata=evidence_metadata,
        instruction_text=normalized_instruction,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
        recorded_by_user_id=recorded_by_user_id,
    )
    return contact, evidence, replayed


def record_global_stop(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
    instruction_text: str,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    idempotency_key: str,
    evidence_metadata: dict,
    intake_lead_id: uuid.UUID | None = None,
    meta_lead_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> ConsentTransitionResult:
    """Apply an organization-wide STOP to both consent purposes."""
    contact, evidence, replayed = _record_instruction(
        db,
        organization_id=organization_id,
        phone=phone,
        purpose="all",
        action="opt_out",
        instruction_text=instruction_text,
        source=source,
        source_reference=source_reference,
        occurred_at=occurred_at,
        idempotency_key=idempotency_key,
        evidence_metadata=evidence_metadata,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
        recorded_by_user_id=recorded_by_user_id,
    )
    if not replayed:
        for purpose in PURPOSES:
            state = _state_for(contact, purpose)
            if _is_current_or_newer(state.effective_at, evidence.occurred_at):
                _apply_state(state, status="opted_out", evidence=evidence)
                _set_provider_sync_state(
                    state,
                    status="pending",
                    requested_at=datetime.now(UTC),
                )
                _enqueue_provider_sync(
                    db,
                    organization_id=organization_id,
                    state=state,
                    evidence=evidence,
                    provider_status="opt-out",
                )
        suppression = contact.suppression
        if suppression and _is_current_or_newer(suppression.effective_at, evidence.occurred_at):
            suppression.active = True
            suppression.reason = "global_opt_out"
            suppression.latest_evidence_id = evidence.id
            suppression.effective_at = evidence.occurred_at
            suppression.updated_at = datetime.now(UTC)
    _finalize(db, commit=commit)
    return _project(
        contact,
        evidence_id=evidence.id,
        classification="global_opt_out",
    )


def record_promotional_opt_out(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
    instruction_text: str,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    idempotency_key: str,
    evidence_metadata: dict,
    intake_lead_id: uuid.UUID | None = None,
    meta_lead_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> ConsentTransitionResult:
    """Revoke promotional consent while preserving operational consent."""
    return record_purpose_opt_out(
        db,
        organization_id=organization_id,
        phone=phone,
        purpose="promotional",
        instruction_text=instruction_text,
        source=source,
        source_reference=source_reference,
        occurred_at=occurred_at,
        idempotency_key=idempotency_key,
        evidence_metadata=evidence_metadata,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
        recorded_by_user_id=recorded_by_user_id,
        commit=commit,
        classification="promotional_opt_out",
    )


def record_purpose_opt_out(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
    purpose: ConsentPurpose,
    instruction_text: str,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    idempotency_key: str,
    evidence_metadata: dict,
    intake_lead_id: uuid.UUID | None = None,
    meta_lead_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    commit: bool = True,
    classification: str | None = None,
) -> ConsentTransitionResult:
    """Revoke exactly one explicitly selected purpose without guessing global scope."""
    if purpose not in PURPOSES:
        raise MessagingConsentValidationError("Purpose must be operational or promotional")
    contact, evidence, replayed = _record_instruction(
        db,
        organization_id=organization_id,
        phone=phone,
        purpose=purpose,
        action="opt_out",
        instruction_text=instruction_text,
        source=source,
        source_reference=source_reference,
        occurred_at=occurred_at,
        idempotency_key=idempotency_key,
        evidence_metadata=evidence_metadata,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
        recorded_by_user_id=recorded_by_user_id,
    )
    if not replayed:
        state = _state_for(contact, purpose)
        if _is_current_or_newer(state.effective_at, evidence.occurred_at):
            _apply_state(state, status="opted_out", evidence=evidence)
            _set_provider_sync_state(
                state,
                status="pending",
                requested_at=datetime.now(UTC),
            )
            _enqueue_provider_sync(
                db,
                organization_id=organization_id,
                state=state,
                evidence=evidence,
                provider_status="opt-out",
            )
        suppression = contact.suppression
        if (
            suppression
            and suppression.reason == "ambiguous_hold"
            and _is_current_or_newer(suppression.effective_at, evidence.occurred_at)
        ):
            _clear_suppression_if_current(contact, evidence=evidence)
    _finalize(db, commit=commit)
    return _project(
        contact,
        evidence_id=evidence.id,
        classification=classification or f"{purpose}_opt_out",
    )


def record_ambiguous_hold(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
    instruction_text: str,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    idempotency_key: str,
    evidence_metadata: dict,
    intake_lead_id: uuid.UUID | None = None,
    meta_lead_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> ConsentTransitionResult:
    """Apply a provisional send hold without guessing the requested scope."""
    contact, evidence, replayed = _record_instruction(
        db,
        organization_id=organization_id,
        phone=phone,
        purpose="all",
        action="ambiguous_hold",
        instruction_text=instruction_text,
        source=source,
        source_reference=source_reference,
        occurred_at=occurred_at,
        idempotency_key=idempotency_key,
        evidence_metadata=evidence_metadata,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
        recorded_by_user_id=recorded_by_user_id,
    )
    if not replayed:
        suppression = contact.suppression
        if (
            suppression
            and suppression.reason != "global_opt_out"
            and _is_current_or_newer(suppression.effective_at, evidence.occurred_at)
        ):
            suppression.active = True
            suppression.reason = "ambiguous_hold"
            suppression.latest_evidence_id = evidence.id
            suppression.effective_at = evidence.occurred_at
            suppression.updated_at = datetime.now(UTC)
    _finalize(db, commit=commit)
    return _project(contact, evidence_id=evidence.id, classification="ambiguous_hold")


def restore_purpose_from_keyword(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
    purpose: ConsentPurpose,
    instruction_text: str,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    idempotency_key: str,
    evidence_metadata: dict,
    intake_lead_id: uuid.UUID | None = None,
    meta_lead_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> ConsentTransitionResult:
    """Restore the route purpose addressed by an inbound START or UNSTOP."""
    if purpose not in PURPOSES:
        raise MessagingConsentValidationError("Purpose must be operational or promotional")
    if classify_consent_instruction(instruction_text) != "restore":
        raise MessagingConsentValidationError("Only START or UNSTOP can use keyword restore")
    contact, evidence, replayed = _record_instruction(
        db,
        organization_id=organization_id,
        phone=phone,
        purpose=purpose,
        action="restore",
        instruction_text=instruction_text,
        source=source,
        source_reference=source_reference,
        occurred_at=occurred_at,
        idempotency_key=idempotency_key,
        evidence_metadata=evidence_metadata,
        intake_lead_id=intake_lead_id,
        meta_lead_id=meta_lead_id,
        surrogate_id=surrogate_id,
        recorded_by_user_id=recorded_by_user_id,
    )
    if not replayed:
        state = _state_for(contact, purpose)
        if _is_current_or_newer(state.effective_at, evidence.occurred_at):
            _apply_state(state, status="opted_in", evidence=evidence)
            _set_provider_sync_state(state, status="synced")
            state.provider_synced_at = datetime.now(UTC)
            _clear_suppression_if_current(contact, evidence=evidence)
    _finalize(db, commit=commit)
    return _project(contact, evidence_id=evidence.id, classification="restore")


def apply_revocation_instruction(
    db: Session,
    *,
    organization_id: uuid.UUID,
    phone: str,
    instruction_text: str,
    route_purpose: ConsentPurpose,
    source: str,
    source_reference: str,
    occurred_at: datetime,
    idempotency_key: str,
    evidence_metadata: dict,
    intake_lead_id: uuid.UUID | None = None,
    meta_lead_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> ConsentTransitionResult:
    """Classify and atomically apply one inbound or staff-recorded instruction."""
    if route_purpose not in PURPOSES:
        raise MessagingConsentValidationError("Route purpose must be operational or promotional")
    classification = classify_consent_instruction(instruction_text)
    common = {
        "organization_id": organization_id,
        "phone": phone,
        "instruction_text": instruction_text,
        "source": source,
        "source_reference": source_reference,
        "occurred_at": occurred_at,
        "idempotency_key": idempotency_key,
        "evidence_metadata": evidence_metadata,
        "intake_lead_id": intake_lead_id,
        "meta_lead_id": meta_lead_id,
        "surrogate_id": surrogate_id,
        "recorded_by_user_id": recorded_by_user_id,
        "commit": commit,
    }
    if classification == "global_opt_out":
        return record_global_stop(db, **common)
    if classification == "promotional_opt_out":
        return record_promotional_opt_out(db, **common)
    if classification == "ambiguous_hold":
        return record_ambiguous_hold(db, **common)
    if classification == "restore":
        return restore_purpose_from_keyword(db, purpose=route_purpose, **common)
    raise MessagingConsentValidationError(
        "Instruction did not contain a recognized opt-out or restore request"
    )
