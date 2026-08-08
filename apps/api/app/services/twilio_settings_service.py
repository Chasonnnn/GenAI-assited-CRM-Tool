"""Persistence and safe projection for organization Twilio settings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.encryption import hash_phone
from app.db.models import Organization, TwilioRoute, TwilioSettings
from app.schemas.twilio import (
    TwilioRouteResponse,
    TwilioSettingsResponse,
    TwilioSettingsUpdate,
)

PURPOSES = ("operational", "promotional")


class TwilioSettingsVersionConflict(ValueError):
    """Raised when an administrator saves a stale settings version."""


class TwilioSettingsValidationError(ValueError):
    """Raised when settings would violate a compliance invariant."""


def _fernet() -> Fernet:
    key = app_settings.FERNET_KEY.get_secret_value()
    if not key:
        raise RuntimeError("FERNET_KEY not configured")
    return Fernet(key.encode())


def encrypt_credential(value: str) -> str:
    """Encrypt a Twilio credential or identifier before persistence."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_credential(value: str) -> str:
    """Decrypt a Twilio credential for a provider boundary only."""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Invalid or corrupted Twilio credential") from exc


def mask_credential(value: str | None) -> str | None:
    """Return a non-sensitive identifier projection."""
    if not value:
        return None
    try:
        decrypted = decrypt_credential(value)
    except ValueError:
        return "****"
    if len(decrypted) <= 8:
        return "****"
    return f"{decrypted[:4]}...{decrypted[-4:]}"


def get_settings(db: Session, organization_id: uuid.UUID) -> TwilioSettings | None:
    return (
        db.query(TwilioSettings).filter(TwilioSettings.organization_id == organization_id).first()
    )


def get_or_create_settings(
    db: Session,
    organization_id: uuid.UUID,
) -> TwilioSettings:
    db.query(Organization.id).filter(Organization.id == organization_id).with_for_update().one()
    existing = get_settings(db, organization_id)
    if existing is not None:
        return existing

    created = TwilioSettings(organization_id=organization_id)
    db.add(created)
    db.flush()
    for purpose in PURPOSES:
        db.add(
            TwilioRoute(
                settings_id=created.id,
                organization_id=organization_id,
                purpose=purpose,
                webhook_id=str(uuid.uuid4()),
            )
        )
    db.commit()
    db.refresh(created)
    return created


def _route_url(webhook_id: str, suffix: str) -> str:
    base_url = app_settings.API_BASE_URL.rstrip("/")
    return f"{base_url}/webhooks/twilio/{webhook_id}/{suffix}"


def project_settings(settings: TwilioSettings) -> TwilioSettingsResponse:
    routes: dict = {}
    for route in settings.routes:
        routes[route.purpose] = TwilioRouteResponse(
            purpose=route.purpose,
            enabled=route.enabled,
            messaging_service_sid_masked=mask_credential(route.messaging_service_sid_encrypted),
            sender_phone_masked=(
                f"+1•••{route.sender_phone_last4}" if route.sender_phone_last4 else None
            ),
            a2p_status=route.a2p_status,
            advanced_opt_out_status=route.advanced_opt_out_status,
            consent_management_status=route.consent_management_status,
            capability_evidence=route.capability_evidence or {},
            webhook_id=route.webhook_id,
            inbound_webhook_url=_route_url(route.webhook_id, "inbound"),
            status_callback_url=_route_url(route.webhook_id, "status"),
        )

    return TwilioSettingsResponse(
        enabled=settings.enabled,
        account_sid_masked=mask_credential(settings.account_sid_encrypted),
        api_key_sid_masked=mask_credential(settings.api_key_sid_encrypted),
        api_secret_configured=bool(settings.api_secret_encrypted),
        auth_token_configured=bool(settings.auth_token_encrypted),
        legal_messaging_brand=settings.legal_messaging_brand,
        operational_disclosure=settings.operational_disclosure,
        promotional_disclosure=settings.promotional_disclosure,
        sms_terms_url=settings.sms_terms_url,
        privacy_policy_url=settings.privacy_policy_url,
        support_contact=settings.support_contact,
        expected_frequency=settings.expected_frequency,
        counsel_approved_at=(
            settings.counsel_approved_at.isoformat() if settings.counsel_approved_at else None
        ),
        compliance_toolkit_enabled=settings.compliance_toolkit_enabled,
        twilio_edition=settings.twilio_edition,
        baa_verified_at=(
            settings.baa_verified_at.isoformat() if settings.baa_verified_at else None
        ),
        compliance_approved_at=(
            settings.compliance_approved_at.isoformat() if settings.compliance_approved_at else None
        ),
        phi_enabled=settings.phi_enabled,
        current_version=settings.current_version,
        routes=routes,
    )


def _normalized_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def update_settings(
    db: Session,
    organization_id: uuid.UUID,
    update: TwilioSettingsUpdate,
) -> TwilioSettings:
    """Atomically update one organization without ever persisting plaintext credentials."""
    get_or_create_settings(db, organization_id)
    current = (
        db.query(TwilioSettings)
        .filter(TwilioSettings.organization_id == organization_id)
        .with_for_update()
        .one()
    )
    if current.current_version != update.expected_version:
        raise TwilioSettingsVersionConflict(
            f"Version conflict: expected {update.expected_version}, got {current.current_version}"
        )

    effective_phi_enabled = (
        update.phi_enabled if "phi_enabled" in update.model_fields_set else current.phi_enabled
    )
    effective_edition = (
        _normalized_optional(update.twilio_edition)
        if "twilio_edition" in update.model_fields_set
        else current.twilio_edition
    )
    effective_baa_at = (
        update.baa_verified_at
        if "baa_verified_at" in update.model_fields_set
        else current.baa_verified_at
    )
    effective_compliance_at = (
        update.compliance_approved_at
        if "compliance_approved_at" in update.model_fields_set
        else current.compliance_approved_at
    )
    if effective_phi_enabled and not (
        effective_edition == "hipaa_eligible"
        and effective_baa_at is not None
        and effective_compliance_at is not None
    ):
        raise TwilioSettingsValidationError(
            "PHI messaging requires a verified HIPAA-eligible Twilio edition, "
            "signed BAA, and compliance approval."
        )

    fields = update.model_fields_set
    encrypted_fields = {
        "account_sid": "account_sid_encrypted",
        "api_key_sid": "api_key_sid_encrypted",
        "api_secret": "api_secret_encrypted",
        "auth_token": "auth_token_encrypted",
    }
    for input_name, stored_name in encrypted_fields.items():
        if input_name not in fields:
            continue
        plaintext = getattr(update, input_name)
        setattr(
            current,
            stored_name,
            encrypt_credential(plaintext.strip()) if plaintext and plaintext.strip() else None,
        )

    scalar_fields = (
        "enabled",
        "legal_messaging_brand",
        "operational_disclosure",
        "promotional_disclosure",
        "sms_terms_url",
        "privacy_policy_url",
        "support_contact",
        "expected_frequency",
        "counsel_approved_at",
        "compliance_toolkit_enabled",
        "twilio_edition",
        "baa_verified_at",
        "compliance_approved_at",
        "phi_enabled",
    )
    string_fields = {
        "legal_messaging_brand",
        "operational_disclosure",
        "promotional_disclosure",
        "sms_terms_url",
        "privacy_policy_url",
        "support_contact",
        "expected_frequency",
        "twilio_edition",
    }
    for field_name in scalar_fields:
        if field_name not in fields:
            continue
        value = getattr(update, field_name)
        if field_name in string_fields:
            value = _normalized_optional(value)
        setattr(current, field_name, value)

    if "routes" in fields and update.routes is not None:
        route_by_purpose = {route.purpose: route for route in current.routes}
        for purpose, route_update in update.routes.items():
            route = route_by_purpose[purpose]
            route_fields = route_update.model_fields_set
            if "messaging_service_sid" in route_fields:
                sid = route_update.messaging_service_sid
                route.messaging_service_sid_encrypted = (
                    encrypt_credential(sid.strip()) if sid else None
                )
            if "sender_phone_e164" in route_fields:
                phone = route_update.sender_phone_e164
                route.sender_phone_encrypted = encrypt_credential(phone) if phone else None
                route.sender_phone_hash = hash_phone(phone) if phone else None
                route.sender_phone_last4 = phone[-4:] if phone else None
            for field_name in (
                "enabled",
                "a2p_status",
                "advanced_opt_out_status",
                "consent_management_status",
                "capability_evidence",
            ):
                if field_name in route_fields:
                    setattr(route, field_name, getattr(route_update, field_name))
            route.updated_at = datetime.now(UTC)

    current.current_version += 1
    current.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(current)
    return current


def rotate_webhook(
    db: Session,
    organization_id: uuid.UUID,
    purpose: str,
    expected_version: int,
) -> TwilioSettings:
    """Rotate one opaque public route without affecting the other messaging purpose."""
    get_or_create_settings(db, organization_id)
    current = (
        db.query(TwilioSettings)
        .filter(TwilioSettings.organization_id == organization_id)
        .with_for_update()
        .one()
    )
    if current.current_version != expected_version:
        raise TwilioSettingsVersionConflict(
            f"Version conflict: expected {expected_version}, got {current.current_version}"
        )
    route = next(item for item in current.routes if item.purpose == purpose)
    route.webhook_id = str(uuid.uuid4())
    route.updated_at = datetime.now(UTC)
    current.current_version += 1
    current.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(current)
    return current
