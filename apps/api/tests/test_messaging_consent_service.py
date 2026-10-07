import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from threading import Event

import pytest
from sqlalchemy import event, select

from app.db.models import (
    MessagingConsentEvidence,
    MessagingConsentState,
    MessagingContact,
    MetaLead,
    Organization,
)
from app.db.session import SessionLocal
from app.services import messaging_consent_service

OCCURRED_AT = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


def _record_opt_in(
    db,
    test_org,
    *,
    phone: str = "+14155550110",
    purpose: str = "operational",
    occurred_at: datetime = OCCURRED_AT,
    idempotency_key: str = "website-lead-10-operational",
    **overrides,
):
    values = {
        "organization_id": test_org.id,
        "phone": phone,
        "purpose": purpose,
        "affirmative": True,
        "disclosure_text": "I agree to receive process updates by text. Reply STOP to opt out.",
        "source": "website_intake",
        "source_reference": "lead-10",
        "occurred_at": occurred_at,
        "idempotency_key": idempotency_key,
        "evidence_metadata": {"form_version": "2026-07-31"},
    }
    values.update(overrides)
    return messaging_consent_service.record_opt_in(db, **values)


def test_unchecked_import_remains_unknown_without_consent_evidence(db, test_org) -> None:
    result = messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        purpose="operational",
        affirmative=False,
        disclosure_text=None,
        source="legacy_import",
        source_reference="legacy-row-10",
        occurred_at=OCCURRED_AT,
        idempotency_key="legacy-row-10-operational",
        evidence_metadata={},
    )

    assert result.purpose_states == {
        "operational": "unknown",
        "promotional": "unknown",
    }
    assert result.evidence_id is None
    assert result.global_suppression_active is False


def test_affirmative_opt_in_requires_complete_evidence(db, test_org) -> None:
    with pytest.raises(
        messaging_consent_service.MessagingConsentValidationError,
        match="disclosure",
    ):
        _record_opt_in(db, test_org, disclosure_text="  ")


def test_affirmative_opt_in_grants_only_selected_purpose_and_is_idempotent(db, test_org) -> None:
    first = _record_opt_in(db, test_org)
    replay = _record_opt_in(db, test_org)

    assert first.purpose_states == {
        "operational": "opted_in",
        "promotional": "unknown",
    }
    assert first.global_suppression_active is False
    assert first.evidence_id is not None
    assert replay.evidence_id == first.evidence_id
    assert (
        db.query(MessagingConsentEvidence)
        .filter(MessagingConsentEvidence.organization_id == test_org.id)
        .count()
        == 1
    )


def test_conflicting_idempotency_key_is_rejected(db, test_org) -> None:
    _record_opt_in(db, test_org)

    with pytest.raises(
        messaging_consent_service.MessagingConsentIdempotencyConflict,
        match="idempotency",
    ):
        _record_opt_in(
            db,
            test_org,
            purpose="promotional",
            idempotency_key="website-lead-10-operational",
        )


def test_global_stop_opts_out_both_purposes_and_suppresses_all_routes(db, test_org) -> None:
    _record_opt_in(db, test_org)
    _record_opt_in(
        db,
        test_org,
        purpose="promotional",
        idempotency_key="website-lead-10-promotional",
    )

    result = messaging_consent_service.record_global_stop(
        db,
        organization_id=test_org.id,
        phone="415-555-0110",
        instruction_text="STOP",
        source="twilio_inbound",
        source_reference="SM-stop-10",
        occurred_at=datetime(2026, 7, 31, 12, 5, tzinfo=UTC),
        idempotency_key="SM-stop-10",
        evidence_metadata={"route_purpose": "operational"},
    )

    assert result.purpose_states == {
        "operational": "opted_out",
        "promotional": "opted_out",
    }
    assert result.global_suppression_active is True
    assert result.global_suppression_reason == "global_opt_out"


def test_promotional_only_revocation_preserves_operational_consent(db, test_org) -> None:
    _record_opt_in(db, test_org)
    _record_opt_in(
        db,
        test_org,
        purpose="promotional",
        idempotency_key="website-lead-10-promotional",
    )

    result = messaging_consent_service.record_promotional_opt_out(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        instruction_text="Please stop promotional offers",
        source="staff_recorded_request",
        source_reference="ticket-32",
        occurred_at=datetime(2026, 7, 31, 12, 5, tzinfo=UTC),
        idempotency_key="ticket-32-promotional-stop",
        evidence_metadata={},
    )

    assert result.purpose_states == {
        "operational": "opted_in",
        "promotional": "opted_out",
    }
    assert result.global_suppression_active is False


def test_ambiguous_revocation_adds_provisional_hold_without_rewriting_purpose_states(
    db, test_org
) -> None:
    _record_opt_in(db, test_org)

    result = messaging_consent_service.record_ambiguous_hold(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        instruction_text="Stop this",
        source="twilio_inbound",
        source_reference="SM-ambiguous-10",
        occurred_at=datetime(2026, 7, 31, 12, 5, tzinfo=UTC),
        idempotency_key="SM-ambiguous-10",
        evidence_metadata={},
    )

    assert result.purpose_states == {
        "operational": "opted_in",
        "promotional": "unknown",
    }
    assert result.global_suppression_active is True
    assert result.global_suppression_reason == "ambiguous_hold"


def test_start_restores_only_the_message_route_purpose_after_global_stop(db, test_org) -> None:
    _record_opt_in(db, test_org)
    messaging_consent_service.record_global_stop(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        instruction_text="STOP",
        source="twilio_inbound",
        source_reference="SM-stop-10",
        occurred_at=datetime(2026, 7, 31, 12, 5, tzinfo=UTC),
        idempotency_key="SM-stop-10",
        evidence_metadata={},
    )

    result = messaging_consent_service.restore_purpose_from_keyword(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        purpose="operational",
        instruction_text="START",
        source="twilio_inbound",
        source_reference="SM-start-10",
        occurred_at=datetime(2026, 7, 31, 12, 10, tzinfo=UTC),
        idempotency_key="SM-start-10",
        evidence_metadata={},
    )

    assert result.purpose_states == {
        "operational": "opted_in",
        "promotional": "opted_out",
    }
    assert result.global_suppression_active is False
    assert result.global_suppression_reason == "none"


def test_late_historical_opt_in_evidence_does_not_override_newer_stop(db, test_org) -> None:
    messaging_consent_service.record_global_stop(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        instruction_text="STOP",
        source="twilio_inbound",
        source_reference="SM-stop-10",
        occurred_at=datetime(2026, 7, 31, 12, 5, tzinfo=UTC),
        idempotency_key="SM-stop-10",
        evidence_metadata={},
    )

    result = _record_opt_in(
        db,
        test_org,
        occurred_at=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
        idempotency_key="legacy-older-opt-in",
    )

    assert result.purpose_states["operational"] == "opted_out"
    assert result.global_suppression_active is True
    assert result.global_suppression_reason == "global_opt_out"
    assert (
        db.query(MessagingConsentEvidence)
        .filter(MessagingConsentEvidence.organization_id == test_org.id)
        .count()
        == 2
    )


def test_linked_entity_must_belong_to_the_same_organization(db, test_org) -> None:
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Organization",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    other_lead = MetaLead(
        organization_id=other_org.id,
        meta_lead_id=f"meta-{uuid.uuid4().hex}",
    )
    db.add(other_lead)
    db.flush()

    with pytest.raises(
        messaging_consent_service.MessagingConsentEntityNotFound,
        match="linked entity",
    ):
        _record_opt_in(db, test_org, meta_lead_id=other_lead.id)


def test_contact_phone_and_instruction_are_encrypted_at_rest(db, test_org) -> None:
    result = messaging_consent_service.record_global_stop(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        instruction_text="Please stop texting me",
        source="staff_recorded_request",
        source_reference="ticket-35",
        occurred_at=OCCURRED_AT,
        idempotency_key="ticket-35-stop",
        evidence_metadata={},
    )
    db.expire_all()

    contact_raw = (
        db.connection()
        .exec_driver_sql(
            "SELECT phone_e164 FROM messaging_contacts WHERE id = %s",
            (result.contact_id,),
        )
        .scalar_one()
    )
    instruction_raw = (
        db.connection()
        .exec_driver_sql(
            "SELECT instruction_text FROM messaging_consent_evidence WHERE id = %s",
            (result.evidence_id,),
        )
        .scalar_one()
    )

    assert "+14155550110" not in contact_raw
    assert "Please stop texting me" not in instruction_raw
    assert (
        db.query(MessagingContact).filter(MessagingContact.id == result.contact_id).one().phone_e164
        == "+14155550110"
    )


def test_consent_evidence_cannot_be_updated_after_insert(db, test_org) -> None:
    result = _record_opt_in(db, test_org)
    evidence = db.get(MessagingConsentEvidence, result.evidence_id)
    assert evidence is not None
    evidence.disclosure_text_snapshot = "replacement disclosure"

    with pytest.raises(ValueError, match="immutable"):
        db.flush()


def test_two_purpose_opt_ins_can_share_one_caller_owned_transaction(db, test_org) -> None:
    with pytest.raises(RuntimeError, match="abort both"):
        with db.begin_nested():
            _record_opt_in(db, test_org, commit=False)
            _record_opt_in(
                db,
                test_org,
                purpose="promotional",
                idempotency_key="website-lead-10-promotional",
                commit=False,
            )
            assert (
                db.query(MessagingConsentEvidence)
                .filter(MessagingConsentEvidence.organization_id == test_org.id)
                .count()
                == 2
            )
            raise RuntimeError("abort both")

    db.expire_all()
    assert (
        db.query(MessagingConsentEvidence)
        .filter(MessagingConsentEvidence.organization_id == test_org.id)
        .count()
        == 0
    )


def test_newer_stop_wins_when_an_older_opt_in_commits_later() -> None:
    organization_id = uuid.uuid4()
    phone = "+14155550119"
    older_commit_reached = Event()
    release_older_commit = Event()

    setup = SessionLocal()
    try:
        setup.add(
            Organization(
                id=organization_id,
                name="Consent Concurrency Test",
                slug=f"consent-concurrency-{organization_id.hex[:12]}",
            )
        )
        setup.commit()
        messaging_consent_service.record_opt_in(
            setup,
            organization_id=organization_id,
            phone=phone,
            purpose="operational",
            affirmative=True,
            disclosure_text="Operational disclosure",
            source="website_intake",
            source_reference="initial-opt-in",
            occurred_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
            idempotency_key="initial-opt-in",
            evidence_metadata={"affirmative_action": "checked"},
        )
    finally:
        setup.close()

    def record_older_opt_in() -> None:
        session = SessionLocal()

        def hold_before_commit(_session) -> None:
            older_commit_reached.set()
            assert release_older_commit.wait(timeout=5)

        event.listen(session, "before_commit", hold_before_commit, once=True)
        try:
            messaging_consent_service.record_opt_in(
                session,
                organization_id=organization_id,
                phone=phone,
                purpose="operational",
                affirmative=True,
                disclosure_text="Operational disclosure",
                source="website_intake",
                source_reference="delayed-opt-in",
                occurred_at=datetime(2026, 7, 31, 12, 5, tzinfo=UTC),
                idempotency_key="delayed-opt-in",
                evidence_metadata={"affirmative_action": "checked"},
            )
        finally:
            session.close()

    def record_newer_stop() -> None:
        session = SessionLocal()
        try:
            messaging_consent_service.record_global_stop(
                session,
                organization_id=organization_id,
                phone=phone,
                instruction_text="STOP",
                source="twilio_inbound",
                source_reference="newer-stop",
                occurred_at=datetime(2026, 7, 31, 12, 10, tzinfo=UTC),
                idempotency_key="newer-stop",
                evidence_metadata={},
            )
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            older = pool.submit(record_older_opt_in)
            assert older_commit_reached.wait(timeout=5)
            newer = pool.submit(record_newer_stop)
            try:
                newer.result(timeout=0.5)
            except FutureTimeoutError:
                pass
            finally:
                release_older_commit.set()
            older.result(timeout=5)
            newer.result(timeout=5)

        verify = SessionLocal()
        try:
            state = verify.scalar(
                select(MessagingConsentState)
                .join(MessagingContact)
                .where(
                    MessagingContact.organization_id == organization_id,
                    MessagingConsentState.purpose == "operational",
                )
            )
            assert state is not None
            assert state.status == "opted_out"
            assert state.effective_at == datetime(2026, 7, 31, 12, 10, tzinfo=UTC)
        finally:
            verify.close()
    finally:
        cleanup = SessionLocal()
        try:
            organization = cleanup.get(Organization, organization_id)
            if organization is not None:
                cleanup.delete(organization)
                cleanup.commit()
        finally:
            cleanup.close()
