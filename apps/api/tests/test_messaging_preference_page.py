"""Public signed messaging preference page contracts."""

from datetime import UTC, datetime

from app.db.models import MessagingConsentState
from app.services import messaging_consent_service, twilio_settings_service

PHONE = "+14155550110"


def _configured_contact(db, test_org):
    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    settings.legal_messaging_brand = "EWI Surrogacy"
    settings.operational_disclosure = (
        "EWI Surrogacy operational texts. Frequency varies. Msg & data rates may apply. "
        "Reply STOP to opt out or HELP for help."
    )
    settings.promotional_disclosure = (
        "EWI Surrogacy promotional texts. Frequency varies. Msg & data rates may apply. "
        "Reply STOP to opt out or HELP for help."
    )
    settings.sms_terms_url = "https://example.com/sms-terms"
    settings.privacy_policy_url = "https://example.com/privacy"
    settings.support_contact = "support@example.com"
    db.commit()
    initial = messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=PHONE,
        purpose="operational",
        affirmative=True,
        disclosure_text=settings.operational_disclosure,
        source="website_intake",
        source_reference="lead-10",
        occurred_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        idempotency_key="lead-10-operational",
        evidence_metadata={},
    )
    return settings, initial.contact_id


async def test_public_preference_get_is_masked_and_returns_exact_disclosures(
    client, db, test_org
):
    from app.services import messaging_preference_service

    settings, contact_id = _configured_contact(db, test_org)
    token = messaging_preference_service.generate_preference_token(
        db,
        organization_id=test_org.id,
        contact_id=contact_id,
        purposes=["operational", "promotional"],
    )

    response = await client.get(f"/public/messaging-consent/{token}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["legal_brand"] == "EWI Surrogacy"
    assert payload["masked_phone"] == "••• ••• 0110"
    assert PHONE not in response.text
    assert payload["sms_terms_url"] == settings.sms_terms_url
    assert payload["privacy_policy_url"] == settings.privacy_policy_url
    assert payload["purposes"]["operational"]["disclosure"] == (
        settings.operational_disclosure
    )
    assert payload["purposes"]["operational"]["status"] == "opted_in"
    assert payload["purposes"]["promotional"]["status"] == "unknown"


async def test_public_written_reopt_is_pending_and_audited_without_start(
    client, db, test_org
):
    from app.services import messaging_preference_service

    _, contact_id = _configured_contact(db, test_org)
    messaging_consent_service.record_global_stop(
        db,
        organization_id=test_org.id,
        phone=PHONE,
        instruction_text="STOP",
        source="twilio_inbound",
        source_reference="SM-stop",
        occurred_at=datetime(2026, 8, 1, 12, 5, tzinfo=UTC),
        idempotency_key="SM-stop",
        evidence_metadata={},
    )
    token = messaging_preference_service.generate_preference_token(
        db,
        organization_id=test_org.id,
        contact_id=contact_id,
        purposes=["operational"],
    )

    response = await client.post(
        f"/public/messaging-consent/{token}",
        json={
            "action": "opt_in",
            "purposes": ["operational"],
            "affirmative": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["purposes"]["operational"]["status"] == "reopt_pending"
    state = (
        db.query(MessagingConsentState)
        .filter_by(contact_id=contact_id, purpose="operational")
        .one()
    )
    assert state.provider_sync_status == "pending"


async def test_public_preference_scoped_opt_out_does_not_suppress_other_purpose(
    client, db, test_org
):
    from app.services import messaging_preference_service

    settings, contact_id = _configured_contact(db, test_org)
    messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=PHONE,
        purpose="promotional",
        affirmative=True,
        disclosure_text=settings.promotional_disclosure,
        source="website_intake",
        source_reference="lead-10-promo",
        occurred_at=datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
        idempotency_key="lead-10-promotional",
        evidence_metadata={},
    )
    token = messaging_preference_service.generate_preference_token(
        db,
        organization_id=test_org.id,
        contact_id=contact_id,
        purposes=["promotional"],
    )

    response = await client.post(
        f"/public/messaging-consent/{token}",
        json={
            "action": "opt_out",
            "purposes": ["promotional"],
            "affirmative": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["purposes"]["operational"]["status"] == "opted_in"
    assert payload["purposes"]["promotional"]["status"] == "opted_out"
    assert payload["global_suppression_active"] is False


async def test_stale_disclosure_token_is_rejected(client, db, test_org):
    from app.services import messaging_preference_service

    settings, contact_id = _configured_contact(db, test_org)
    token = messaging_preference_service.generate_preference_token(
        db,
        organization_id=test_org.id,
        contact_id=contact_id,
        purposes=["operational"],
    )
    settings.operational_disclosure = "A newly counsel-approved disclosure"
    db.commit()

    response = await client.post(
        f"/public/messaging-consent/{token}",
        json={
            "action": "opt_in",
            "purposes": ["operational"],
            "affirmative": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "This consent link uses an outdated disclosure"
