"""Contract tests for local-first Twilio Consent Management synchronization."""

from datetime import UTC, datetime, timedelta

import pytest

from app.db.enums import JobType
from app.db.models import Job, MessagingConsentState
from app.jobs.handlers import twilio as twilio_job_handler
from app.services import (
    messaging_consent_service,
    twilio_settings_service,
    twilio_transport,
)

PHONE = "+14155550110"
CONSENT_AT = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


def _configure_routes(db, test_org, *, consent_status: str = "available"):
    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    settings.enabled = True
    settings.account_sid_encrypted = twilio_settings_service.encrypt_credential("AC" + "1" * 32)
    settings.api_key_sid_encrypted = twilio_settings_service.encrypt_credential("SK" + "2" * 32)
    settings.api_secret_encrypted = twilio_settings_service.encrypt_credential("restricted-secret")
    for index, route in enumerate(sorted(settings.routes, key=lambda item: item.purpose), 3):
        route.enabled = True
        route.messaging_service_sid_encrypted = twilio_settings_service.encrypt_credential(
            "MG" + str(index) * 32
        )
        route.sender_phone_encrypted = twilio_settings_service.encrypt_credential(
            f"+1415555010{index}"
        )
        route.sender_phone_last4 = f"010{index}"
        route.a2p_status = "approved"
        route.consent_management_status = consent_status
        route.capability_evidence = {"sender_type": "10dlc"}
    db.commit()
    return settings


def _initial_opt_in(db, test_org):
    return messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=PHONE,
        purpose="operational",
        affirmative=True,
        disclosure_text="I agree to operational texts. Reply STOP to opt out.",
        source="website_intake",
        source_reference="lead-10",
        occurred_at=CONSENT_AT,
        idempotency_key="lead-10-operational",
        evidence_metadata={"form_version": "2026-07-31"},
    )


def _global_stop(db, test_org):
    return messaging_consent_service.record_global_stop(
        db,
        organization_id=test_org.id,
        phone=PHONE,
        instruction_text="STOP",
        source="twilio_inbound",
        source_reference="SM-stop",
        occurred_at=CONSENT_AT + timedelta(minutes=5),
        idempotency_key="SM-stop",
        evidence_metadata={"opt_out_type": "STOP"},
    )


def _external_reopt(db, test_org):
    return messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=PHONE,
        purpose="operational",
        affirmative=True,
        disclosure_text="I agree again to operational texts. Reply STOP to opt out.",
        source="preference_page",
        source_reference="preference-10",
        occurred_at=CONSENT_AT + timedelta(minutes=10),
        idempotency_key="preference-10-operational",
        evidence_metadata={"signed": True},
    )


def _sync_job(db, test_org, *, status: str) -> Job:
    return (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.TWILIO_CONSENT_SYNC.value,
            Job.payload["status"].astext == status,
        )
        .order_by(Job.created_at.desc())
        .first()
    )


def test_initial_form_opt_in_is_immediate_and_does_not_call_consent_api(db, test_org):
    _configure_routes(db, test_org)

    result = _initial_opt_in(db, test_org)
    state = (
        db.query(MessagingConsentState)
        .filter_by(contact_id=result.contact_id, purpose="operational")
        .one()
    )

    assert result.purpose_states["operational"] == "opted_in"
    assert state.provider_sync_status == "not_required"
    assert _sync_job(db, test_org, status="opt-in") is None


def test_global_stop_is_immediate_and_enqueues_both_route_opt_outs(db, test_org):
    _configure_routes(db, test_org)
    _initial_opt_in(db, test_org)

    result = _global_stop(db, test_org)
    jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.TWILIO_CONSENT_SYNC.value,
        )
        .all()
    )

    assert result.global_suppression_active is True
    assert result.purpose_states == {
        "operational": "opted_out",
        "promotional": "opted_out",
    }
    assert {job.payload["purpose"] for job in jobs} == {
        "operational",
        "promotional",
    }
    assert {job.payload["status"] for job in jobs} == {"opt-out"}
    assert all("phone" not in job.payload for job in jobs)


def test_external_reopt_stays_blocked_until_both_provider_items_succeed(db, test_org):
    _configure_routes(db, test_org)
    _initial_opt_in(db, test_org)
    _global_stop(db, test_org)

    result = _external_reopt(db, test_org)
    state = (
        db.query(MessagingConsentState)
        .filter_by(contact_id=result.contact_id, purpose="operational")
        .one()
    )
    job = _sync_job(db, test_org, status="opt-in")

    assert result.purpose_states["operational"] == "reopt_pending"
    assert result.purpose_states["promotional"] == "opted_out"
    assert result.global_suppression_active is True
    assert state.provider_sync_status == "pending"
    assert job is not None
    assert job.payload == {
        "consent_state_id": str(state.id),
        "evidence_id": str(result.evidence_id),
        "purpose": "operational",
        "provider_scope": "organization",
        "status": "opt-in",
    }


@pytest.mark.asyncio
async def test_external_reopt_success_clears_only_selected_purpose(db, test_org, monkeypatch):
    _configure_routes(db, test_org)
    _initial_opt_in(db, test_org)
    _global_stop(db, test_org)
    pending = _external_reopt(db, test_org)
    job = _sync_job(db, test_org, status="opt-in")
    calls: list[dict] = []

    def fake_upsert(**kwargs):
        calls.append(kwargs)
        return twilio_transport.TwilioConsentResult(
            success=True,
            correlation_ids=("one", "two"),
            item_error_codes=(0, 0),
        )

    monkeypatch.setattr(twilio_transport, "upsert_route_consent", fake_upsert)
    await twilio_job_handler.process_twilio_consent_sync(db, job)

    db.expire_all()
    state = (
        db.query(MessagingConsentState)
        .filter_by(contact_id=pending.contact_id, purpose="operational")
        .one()
    )
    promotional = (
        db.query(MessagingConsentState)
        .filter_by(contact_id=pending.contact_id, purpose="promotional")
        .one()
    )
    assert state.status == "opted_in"
    assert state.provider_sync_status == "synced"
    assert state.provider_synced_at is not None
    assert promotional.status == "opted_out"
    assert state.contact.suppression.active is False
    assert len(calls) == 1
    assert calls[0]["status"] == "opt-in"
    assert calls[0]["source"] == "website"
    assert calls[0]["contact_id"] == PHONE


@pytest.mark.asyncio
async def test_one_of_two_provider_updates_keeps_external_reopt_blocked(db, test_org, monkeypatch):
    _configure_routes(db, test_org)
    _initial_opt_in(db, test_org)
    _global_stop(db, test_org)
    pending = _external_reopt(db, test_org)
    job = _sync_job(db, test_org, status="opt-in")

    monkeypatch.setattr(
        twilio_transport,
        "upsert_route_consent",
        lambda **_kwargs: twilio_transport.TwilioConsentResult(
            success=False,
            correlation_ids=("one", "two"),
            item_error_codes=(0, 30007),
            failure_reason=twilio_transport.TwilioFailureReason.CONSENT_ITEM_REJECTED,
        ),
    )
    await twilio_job_handler.process_twilio_consent_sync(db, job)

    db.expire_all()
    state = (
        db.query(MessagingConsentState)
        .filter_by(contact_id=pending.contact_id, purpose="operational")
        .one()
    )
    assert state.status == "reopt_pending"
    assert state.provider_sync_status == "failed"
    assert state.provider_sync_error_code == "consent_item_rejected"
    assert state.contact.suppression.active is True


@pytest.mark.asyncio
async def test_transient_consent_provider_failure_retries_without_terminal_projection(
    db,
    test_org,
    monkeypatch,
):
    _configure_routes(db, test_org)
    _initial_opt_in(db, test_org)
    _global_stop(db, test_org)
    pending = _external_reopt(db, test_org)
    job = _sync_job(db, test_org, status="opt-in")
    monkeypatch.setattr(
        twilio_transport,
        "upsert_route_consent",
        lambda **_kwargs: twilio_transport.TwilioConsentResult(
            success=False,
            correlation_ids=("one", "two"),
            failure_reason=twilio_transport.TwilioFailureReason.RATE_LIMITED,
            provider_status_code=429,
            retryable=True,
        ),
    )

    with pytest.raises(RuntimeError, match="transient"):
        await twilio_job_handler.process_twilio_consent_sync(db, job)

    db.expire_all()
    state = (
        db.query(MessagingConsentState)
        .filter_by(contact_id=pending.contact_id, purpose="operational")
        .one()
    )
    assert state.status == "reopt_pending"
    assert state.provider_sync_status == "pending"
    assert state.provider_synced_at is None


@pytest.mark.asyncio
async def test_unavailable_or_toll_free_reopt_never_calls_provider(db, test_org, monkeypatch):
    settings = _configure_routes(db, test_org, consent_status="unavailable")
    next(
        route for route in settings.routes if route.purpose == "operational"
    ).capability_evidence = {"sender_type": "toll_free"}
    db.commit()
    _initial_opt_in(db, test_org)
    _global_stop(db, test_org)
    pending = _external_reopt(db, test_org)
    job = _sync_job(db, test_org, status="opt-in")
    monkeypatch.setattr(
        twilio_transport,
        "upsert_route_consent",
        lambda **_kwargs: pytest.fail("unavailable or toll-free routes must not call Twilio"),
    )

    await twilio_job_handler.process_twilio_consent_sync(db, job)

    db.expire_all()
    state = (
        db.query(MessagingConsentState)
        .filter_by(contact_id=pending.contact_id, purpose="operational")
        .one()
    )
    assert state.status == "reopt_pending"
    assert state.provider_sync_status == "unavailable"
    assert state.provider_sync_error_code == "text_start_required"


def test_start_restores_route_immediately_without_external_sync_job(db, test_org):
    _configure_routes(db, test_org)
    _initial_opt_in(db, test_org)
    _global_stop(db, test_org)

    result = messaging_consent_service.restore_purpose_from_keyword(
        db,
        organization_id=test_org.id,
        phone=PHONE,
        purpose="operational",
        instruction_text="START",
        source="twilio_inbound",
        source_reference="SM-start",
        occurred_at=CONSENT_AT + timedelta(minutes=10),
        idempotency_key="SM-start",
        evidence_metadata={"opt_out_type": "START"},
    )
    state = (
        db.query(MessagingConsentState)
        .filter_by(contact_id=result.contact_id, purpose="operational")
        .one()
    )

    assert result.purpose_states == {
        "operational": "opted_in",
        "promotional": "opted_out",
    }
    assert result.global_suppression_active is False
    assert state.provider_sync_status == "synced"
    assert _sync_job(db, test_org, status="opt-in") is None
