"""Retention must preserve case relationships, work and inherited legal holds."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models import (
    Appointment,
    Attachment,
    AuditLog,
    DataRetentionPolicy,
    EntityNote,
    IntendedParent,
    LegalHold,
    Match,
    MatchEvent,
    Organization,
    Surrogate,
    Task,
)
from app.db.models.matches import MatchAttempt
from app.services import compliance_service, ip_service, surrogate_service
from tests.test_compliance import _create_archived_donor
from tests.test_tasks_match_scope import _create_intended_parent, _create_surrogate

OLD = datetime.now(UTC) - timedelta(days=60)


def _policy(db, org_id, *types):
    for entity_type in types:
        db.add(
            DataRetentionPolicy(
                organization_id=org_id, entity_type=entity_type, retention_days=30, is_active=True
            )
        )
    db.flush()


def _case(db, org_id, user_id, **overrides):
    donor = _create_archived_donor(db, org_id=org_id, suffix=uuid4().hex)
    donor.archived_at = OLD
    ip = _create_intended_parent(db, org_id)
    ip.is_archived = True
    match = Match(
        organization_id=org_id,
        match_number=f"M{uuid4().int % 900000 + 100000}",
        match_kind="donor",
        donor_id=donor.id,
        intended_parent_id=ip.id,
        proposed_by_user_id=user_id,
        status="completed",
        created_at=OLD,
        closed_at=OLD,
        **overrides,
    )
    db.add(match)
    db.flush()
    return donor, ip, match


def _work(db, match, user_id):
    attempt = MatchAttempt(
        organization_id=match.organization_id,
        match_id=match.id,
        sequence=1,
        attempt_type="retrieval",
        status="completed",
    )
    db.add(attempt)
    db.flush()
    note = EntityNote(
        organization_id=match.organization_id,
        entity_type="match",
        entity_id=match.id,
        match_id=match.id,
        attempt_id=attempt.id,
        author_id=user_id,
        content="Preserved case note",
        work_source="ip",
        created_at=OLD,
    )
    task = Task(
        organization_id=match.organization_id,
        match_id=match.id,
        attempt_id=attempt.id,
        donor_id=match.donor_id,
        intended_parent_id=match.intended_parent_id,
        created_by_user_id=user_id,
        owner_type="user",
        owner_id=user_id,
        title="Preserved case task",
        task_type="other",
        is_completed=True,
        completed_at=OLD,
    )
    db.add_all([note, task])
    db.flush()
    return attempt, note, task


@pytest.mark.parametrize(
    "held_type",
    [
        "donor",
        "intended_parent",
        "ip",
        "match",
        "match_attempt",
        "attempt",
        "task",
        "entity_note",
        "entity_notes",
        "note",
    ],
)
def test_full_purge_preserves_direct_and_inherited_case_holds(db, test_org, test_user, held_type):
    donor, ip, match = _case(db, test_org.id, test_user.id)
    attempt, note, task = _work(db, match, test_user.id)
    held = {
        "donor": donor,
        "intended_parent": ip,
        "ip": ip,
        "match": match,
        "match_attempt": attempt,
        "attempt": attempt,
        "task": task,
        "entity_note": note,
        "entity_notes": note,
        "note": note,
    }[held_type]
    db.add(
        LegalHold(
            organization_id=test_org.id,
            entity_type=held_type,
            entity_id=held.id,
            reason="Preserve history",
        )
    )
    _policy(db, test_org.id, "donors", "matches", "tasks", "entity_notes")
    ids = [(type(row), row.id) for row in (donor, ip, match, attempt, note, task)]
    compliance_service.execute_purge(db, test_org.id, test_user.id)
    db.expire_all()
    for model, record_id in ids:
        assert db.get(model, record_id) is not None


def test_full_purge_skips_populated_cases_and_purges_unrelated_expired_rows(
    db, test_org, test_user
):
    donor, ip, match = _case(db, test_org.id, test_user.id)
    note = EntityNote(
        organization_id=test_org.id,
        entity_type="match",
        entity_id=match.id,
        match_id=match.id,
        author_id=test_user.id,
        content="Recent case work",
    )
    db.add(note)
    _, _, empty_case = _case(db, test_org.id, test_user.id)
    _policy(db, test_org.id, "donors", "matches", "entity_notes")
    retained_ids = [(type(row), row.id) for row in (donor, ip, match, note)]
    empty_id = empty_case.id
    results = {
        row.entity_type: row.count
        for row in compliance_service.execute_purge(db, test_org.id, test_user.id)
    }
    assert results["matches"] == 1
    db.expire_all()
    assert db.get(Match, empty_id) is None
    for model, record_id in retained_ids:
        assert db.get(model, record_id) is not None


def test_unrelated_surrogate_hold_and_other_org_holds_do_not_block_donor_case(
    db, test_org, test_user
):
    _, _, match = _case(db, test_org.id, test_user.id)
    other = Organization(name="Other retention organization", slug=f"retention-{uuid4().hex}")
    db.add(other)
    db.flush()
    db.add_all(
        [
            LegalHold(
                organization_id=test_org.id,
                entity_type="surrogate",
                entity_id=uuid4(),
                reason="Unrelated",
            ),
            LegalHold(
                organization_id=other.id,
                entity_type="match",
                entity_id=match.id,
                reason="Other tenant",
            ),
        ]
    )
    _policy(db, test_org.id, "matches")
    match_id = match.id
    results = compliance_service.execute_purge(db, test_org.id, test_user.id)
    assert results[0].count == 1
    db.expire_all()
    assert db.get(Match, match_id) is None


def test_purge_never_touches_another_organization_case(db, test_org, test_user):
    other = Organization(name="Other retention organization", slug=f"retention-{uuid4().hex}")
    db.add(other)
    db.flush()
    _, _, other_match = _case(db, other.id, test_user.id)
    _policy(db, test_org.id, "matches")
    other_id = other_match.id
    assert compliance_service.execute_purge(db, test_org.id, test_user.id)[0].count == 0
    db.expire_all()
    assert db.get(Match, other_id) is not None


def test_ip_hard_delete_blocks_existing_case_without_losing_work(db, test_org, test_user):
    _, ip, match = _case(db, test_org.id, test_user.id)
    _work(db, match, test_user.id)
    with pytest.raises(ValueError, match="match history"):
        ip_service.delete_intended_parent(db, ip)
    assert db.get(IntendedParent, ip.id) is not None


def test_surrogate_hard_delete_and_retention_preserve_case(db, test_org, test_user, default_stage):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    surrogate.is_archived = True
    surrogate.archived_at = OLD
    ip = _create_intended_parent(db, test_org.id)
    match = Match(
        organization_id=test_org.id,
        match_number="M900001",
        surrogate_id=surrogate.id,
        intended_parent_id=ip.id,
        proposed_by_user_id=test_user.id,
        status="accepted",
        created_at=OLD,
    )
    db.add(match)
    _policy(db, test_org.id, "surrogates", "matches")
    with pytest.raises(ValueError, match="match history"):
        surrogate_service.hard_delete_surrogate(db, surrogate)
    ids = surrogate.id, match.id
    compliance_service.execute_purge(db, test_org.id, test_user.id)
    db.expire_all()
    assert db.get(Surrogate, ids[0]) is not None
    assert db.get(Match, ids[1]) is not None


def test_full_purge_rolls_back_deletion_when_audit_fails(db, test_org, test_user, monkeypatch):
    _, _, match = _case(db, test_org.id, test_user.id)
    _policy(db, test_org.id, "matches")
    match_id = match.id
    db.commit()

    def fail_audit(**_kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(
        compliance_service.audit_service, "log_compliance_purge_executed", fail_audit
    )
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        with db.begin_nested():
            compliance_service.execute_purge(db, test_org.id, test_user.id)
    db.expire_all()
    assert db.get(Match, match_id) is not None
    assert db.query(AuditLog).filter(AuditLog.organization_id == test_org.id).count() == 0


@pytest.mark.parametrize("held_type", ["donor", "intended_parent", "match"])
def test_direct_party_holds_protect_even_empty_cases(db, test_org, test_user, held_type):
    donor, ip, match = _case(db, test_org.id, test_user.id)
    held = {"donor": donor, "intended_parent": ip, "match": match}[held_type]
    db.add(
        LegalHold(
            organization_id=test_org.id,
            entity_type=held_type,
            entity_id=held.id,
            reason="Case hold",
        )
    )
    _policy(db, test_org.id, "matches")
    match_id = match.id
    assert compliance_service.execute_purge(db, test_org.id, test_user.id)[0].count == 0
    db.expire_all()
    assert db.get(Match, match_id) is not None


@pytest.mark.parametrize("dependency", ["attempt", "event", "file", "appointment"])
def test_case_retention_does_not_cascade_history_without_its_own_policy(
    db, test_org, test_user, dependency
):
    _, _, match = _case(db, test_org.id, test_user.id)
    context = {"organization_id": test_org.id, "match_id": match.id}
    if dependency == "attempt":
        record = MatchAttempt(
            **context, sequence=1, attempt_type="retrieval", status="completed", created_at=OLD
        )
    elif dependency == "event":
        record = MatchEvent(
            **context,
            person_type="donor",
            event_type="custom",
            title="Historical event",
            all_day=True,
            start_date=OLD.date(),
        )
    elif dependency == "file":
        record = Attachment(
            **context,
            filename="case.txt",
            storage_key=f"case-{uuid4().hex}",
            content_type="text/plain",
            file_size=4,
            checksum_sha256="a" * 64,
        )
    else:
        record = Appointment(
            **context,
            user_id=test_user.id,
            donor_id=match.donor_id,
            client_name="Retention Client",
            client_email="retention@example.test",
            client_phone="2025550100",
            client_timezone="UTC",
            scheduled_start=OLD,
            scheduled_end=OLD + timedelta(minutes=30),
            duration_minutes=30,
            meeting_mode="phone",
            status="completed",
        )
    db.add(record)
    _policy(db, test_org.id, "matches")
    ids = match.id, record.id
    assert compliance_service.execute_purge(db, test_org.id, test_user.id)[0].count == 0
    db.expire_all()
    assert db.get(Match, ids[0]) is not None
    assert db.get(type(record), ids[1]) is not None


@pytest.mark.asyncio
async def test_ip_delete_returns_conflict_for_case_history_and_hides_other_tenant(
    authed_client, db, test_org, test_user
):
    _, ip, _ = _case(db, test_org.id, test_user.id)
    response = await authed_client.delete(f"/intended-parents/{ip.id}")
    assert response.status_code == 409, response.text
    assert "match history" in response.json()["detail"]
    other = Organization(name="Other deletion organization", slug=f"deletion-{uuid4().hex}")
    db.add(other)
    db.flush()
    other_ip = _create_intended_parent(db, other.id)
    other_ip.is_archived = True
    db.flush()
    response = await authed_client.delete(f"/intended-parents/{other_ip.id}")
    assert response.status_code == 404
    assert db.get(IntendedParent, other_ip.id) is not None


@pytest.mark.parametrize("entity_type", [None, "intended_parent", "ip"])
def test_ip_delete_respects_org_and_record_holds_without_matches(db, test_org, entity_type):
    ip = _create_intended_parent(db, test_org.id)
    ip.is_archived = True
    db.add(
        LegalHold(
            organization_id=test_org.id,
            entity_type=entity_type,
            entity_id=ip.id if entity_type else None,
            reason="Preserve record",
        )
    )
    db.flush()
    with pytest.raises(ValueError, match="legal hold"):
        ip_service.delete_intended_parent(db, ip)
    assert db.get(IntendedParent, ip.id) is not None


def test_purge_rechecks_history_after_waiting_for_concurrent_case_writer(db_engine, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic, sleep

    from sqlalchemy import event, text
    from sqlalchemy.orm import Session

    from app.db.models import User

    monkeypatch.setattr(
        compliance_service.audit_service, "log_compliance_purge_executed", lambda **kwargs: None
    )
    org_id, user_id = uuid4(), uuid4()
    with Session(db_engine) as setup:
        setup.add(
            Organization(id=org_id, name="Concurrent retention", slug=f"retention-race-{org_id}")
        )
        setup.add(
            User(id=user_id, email=f"retention-{user_id}@example.test", display_name="Retention QA")
        )
        setup.commit()
        _, _, match = _case(setup, org_id, user_id)
        match_id = match.id
        _policy(setup, org_id, "matches")
        setup.commit()

    inserted, selecting = Event(), Event()
    try:
        with Session(db_engine) as purge:
            connection = purge.connection()
            purge_pid = connection.execute(text("SELECT pg_backend_pid()")).scalar_one()

            def before_select(_conn, _cursor, statement, _parameters, _context, _many):
                if "FOR UPDATE" in statement and "matches.id" in statement:
                    selecting.set()

            event.listen(connection, "before_cursor_execute", before_select)

            def insert_attempt():
                with Session(db_engine) as writer:
                    attempt = MatchAttempt(
                        organization_id=org_id,
                        match_id=match_id,
                        sequence=1,
                        attempt_type="retrieval",
                        status="completed",
                    )
                    writer.add(attempt)
                    writer.flush()  # FK key-share lock blocks purge's FOR UPDATE.
                    attempt_id = attempt.id
                    inserted.set()
                    assert selecting.wait(5)
                    deadline = monotonic() + 5
                    while monotonic() < deadline:
                        if writer.execute(
                            text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": purge_pid}
                        ).scalar_one():
                            writer.commit()
                            return attempt_id
                        sleep(0.01)
                    raise AssertionError("Purge did not wait for the case writer")

            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(insert_attempt)
                assert inserted.wait(5)
                try:
                    results = compliance_service.execute_purge(purge, org_id, user_id)
                finally:
                    event.remove(connection, "before_cursor_execute", before_select)
                attempt_id = pending.result(timeout=10)
            assert results[0].count == 0
            assert purge.get(Match, match_id) is not None
            assert purge.get(MatchAttempt, attempt_id) is not None
    finally:
        with db_engine.begin() as cleanup:
            cleanup.execute(text("DELETE FROM organizations WHERE id=:id"), {"id": org_id})
            cleanup.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})


@pytest.mark.parametrize(
    "status", ["proposed", "reviewing", "accepted", "cancel_pending", "completed"]
)
def test_retention_preserves_open_or_recently_closed_cases(db, test_org, test_user, status):
    _, _, match = _case(db, test_org.id, test_user.id)
    match.status = status
    match.closed_at = datetime.now(UTC) if status == "completed" else None
    _policy(db, test_org.id, "matches")
    match_id = match.id
    assert compliance_service.execute_purge(db, test_org.id, test_user.id)[0].count == 0
    db.expire_all()
    assert db.get(Match, match_id) is not None


@pytest.mark.parametrize("updated_at", [OLD, datetime.now(UTC) - timedelta(days=1)])
def test_retention_preserves_legacy_case_with_unknown_closure(db, test_org, test_user, updated_at):
    _, _, match = _case(db, test_org.id, test_user.id)
    match.status = "cancelled"
    match.closed_at = None
    match.updated_at = updated_at
    _policy(db, test_org.id, "matches")
    match_id = match.id
    assert compliance_service.preview_purge(db, test_org.id)[0].count == 0
    assert compliance_service.execute_purge(db, test_org.id, test_user.id)[0].count == 0
    db.expire_all()
    assert db.get(Match, match_id) is not None


@pytest.mark.parametrize("operation", ["purge", "hard_delete"])
def test_hold_creation_serializes_before_destructive_preservation_checks(
    db_engine, monkeypatch, operation
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic, sleep

    from sqlalchemy import event, text
    from sqlalchemy.orm import Session

    from app.db.models import User
    from app.services.record_preservation_service import PreservationDependencyError

    monkeypatch.setattr(
        compliance_service.audit_service, "log_compliance_legal_hold_created", lambda **kwargs: None
    )
    monkeypatch.setattr(
        compliance_service.audit_service, "log_compliance_purge_executed", lambda **kwargs: None
    )
    org_id, user_id = uuid4(), uuid4()
    with Session(db_engine) as setup:
        setup.add(Organization(id=org_id, name="Concurrent hold", slug=f"hold-race-{org_id}"))
        setup.add(User(id=user_id, email=f"hold-{user_id}@example.test", display_name="Hold QA"))
        setup.commit()
        if operation == "purge":
            _, _, record = _case(setup, org_id, user_id)
            _policy(setup, org_id, "matches")
            entity_type, model = "match", Match
        else:
            record = _create_intended_parent(setup, org_id)
            record.is_archived = True
            entity_type, model = "ip", IntendedParent
        record_id = record.id
        setup.commit()

    hold_fenced, release_hold, deleting = Event(), Event(), Event()
    delete_pids = []

    def create_hold():
        with Session(db_engine) as writer:
            connection = writer.connection()

            def before_insert(_conn, _cursor, statement, _parameters, _context, _many):
                if "INSERT INTO legal_holds" in statement:
                    hold_fenced.set()
                    assert release_hold.wait(10)

            event.listen(connection, "before_cursor_execute", before_insert)
            try:
                compliance_service.create_legal_hold(
                    writer, org_id, user_id, entity_type, record_id, "Preserve concurrently"
                )
            finally:
                event.remove(connection, "before_cursor_execute", before_insert)

    def destroy_record():
        with Session(db_engine) as deleter:
            delete_pids.append(deleter.execute(text("SELECT pg_backend_pid()")).scalar_one())
            deleting.set()
            if operation == "purge":
                return compliance_service.execute_purge(deleter, org_id, user_id)[0].count
            try:
                ip_service.delete_intended_parent(deleter, deleter.get(IntendedParent, record_id))
            except PreservationDependencyError:
                return 0
            return 1

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            holding = pool.submit(create_hold)
            try:
                assert hold_fenced.wait(5)
                destroying = pool.submit(destroy_record)
                assert deleting.wait(5)
                deadline = monotonic() + 5
                with Session(db_engine) as observer:
                    while monotonic() < deadline:
                        if observer.execute(
                            text("SELECT cardinality(pg_blocking_pids(:pid))"),
                            {"pid": delete_pids[0]},
                        ).scalar_one():
                            break
                        sleep(0.01)
                    else:
                        raise AssertionError("Destruction did not wait for legal-hold creation")
            finally:
                release_hold.set()
            holding.result(timeout=10)
            assert destroying.result(timeout=10) == 0
        with Session(db_engine) as verify:
            assert verify.get(model, record_id) is not None
    finally:
        release_hold.set()
        with db_engine.begin() as cleanup:
            cleanup.execute(text("DELETE FROM organizations WHERE id=:id"), {"id": org_id})
            cleanup.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})


@pytest.mark.parametrize("operation", ["create", "release"])
def test_legal_hold_change_rolls_back_with_failed_audit(
    db, test_org, test_user, monkeypatch, operation
):
    hold = LegalHold(
        organization_id=test_org.id, entity_type="donor", entity_id=uuid4(), reason="Existing hold"
    )
    db.add(hold)
    db.commit()
    hold_id = hold.id

    def fail_audit(**_kwargs):
        raise RuntimeError("Hold audit unavailable")

    monkeypatch.setattr(
        compliance_service.audit_service,
        f"log_compliance_legal_hold_{'created' if operation == 'create' else 'released'}",
        fail_audit,
    )
    with pytest.raises(RuntimeError, match="Hold audit unavailable"), db.begin_nested():
        if operation == "create":
            compliance_service.create_legal_hold(
                db, test_org.id, test_user.id, "donor", uuid4(), "New hold"
            )
        else:
            compliance_service.release_legal_hold(db, test_org.id, test_user.id, hold_id)
    db.expire_all()
    assert db.query(LegalHold).filter(LegalHold.organization_id == test_org.id).count() == 1
    assert db.get(LegalHold, hold_id).released_at is None
