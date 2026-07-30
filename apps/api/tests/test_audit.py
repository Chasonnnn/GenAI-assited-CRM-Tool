"""Tests for the audit log system."""

import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from sqlalchemy import text

from app.db.enums import AuditEventType
from app.db.models import AuditLog, Organization
from app.db.session import SessionLocal
from app.services import audit_service, version_service

# =============================================================================
# Unit Tests (no DB required)
# =============================================================================


def test_compute_audit_hash_deterministic():
    """Audit hash computation should be deterministic."""
    hash1 = version_service.compute_audit_hash(
        prev_hash="abc123",
        entry_id="entry-1",
        org_id="org-1",
        event_type="TEST",
        created_at="2024-01-01T00:00:00",
        details_json='{"test": true}',
    )
    hash2 = version_service.compute_audit_hash(
        prev_hash="abc123",
        entry_id="entry-1",
        org_id="org-1",
        event_type="TEST",
        created_at="2024-01-01T00:00:00",
        details_json='{"test": true}',
    )
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex


def test_compute_audit_hash_different_inputs():
    """Different inputs should produce different hashes."""
    hash1 = version_service.compute_audit_hash(
        prev_hash="abc123",
        entry_id="entry-1",
        org_id="org-1",
        event_type="TEST",
        created_at="2024-01-01T00:00:00",
        details_json='{"test": true}',
    )
    hash2 = version_service.compute_audit_hash(
        prev_hash="abc123",
        entry_id="entry-2",  # Different entry_id
        org_id="org-1",
        event_type="TEST",
        created_at="2024-01-01T00:00:00",
        details_json='{"test": true}',
    )
    assert hash1 != hash2


def test_canonical_json_sorted():
    """canonical_json should sort keys and use compact separators."""
    result = audit_service.canonical_json({"b": 2, "a": 1})
    assert result == '{"a":1,"b":2}'


def test_canonical_json_nested():
    """canonical_json should handle nested objects."""
    result = audit_service.canonical_json({"b": {"d": 4, "c": 3}, "a": 1})
    assert result == '{"a":1,"b":{"c":3,"d":4}}'


def test_canonical_json_handles_none():
    """canonical_json should handle None input."""
    result = audit_service.canonical_json(None)
    assert result == "{}"


def test_canonical_json_empty_dict():
    """canonical_json should handle empty dict."""
    result = audit_service.canonical_json({})
    assert result == "{}"


def test_audit_event_type_references_are_defined():
    """All AuditEventType references in app code should map to defined enum members."""
    app_root = Path(__file__).resolve().parents[1] / "app"
    enum_members = {member.name for member in AuditEventType}
    pattern = re.compile(r"AuditEventType\.([A-Z0-9_]+)")

    missing: dict[str, list[str]] = {}
    for file_path in app_root.rglob("*.py"):
        text = file_path.read_text(encoding="utf-8")
        for match in pattern.findall(text):
            if match not in enum_members:
                missing.setdefault(match, []).append(str(file_path))

    assert not missing, f"Undefined AuditEventType references found: {missing}"


def test_concurrent_audit_appends_form_one_linear_org_chain(db_engine):
    """Concurrent commits for one org must not fork from the same predecessor."""
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Audit-chain concurrency requires PostgreSQL")

    setup_connection = db_engine.connect()
    setup_session = SessionLocal(bind=setup_connection)
    cleanup_connection = db_engine.connect()
    cleanup_session = SessionLocal(bind=cleanup_connection)
    org_id = uuid.uuid4()
    first_flushed = Event()
    release_first_commit = Event()
    second_started = Event()
    second_appended = Event()

    try:
        setup_session.add(
            Organization(
                id=org_id,
                name="Audit Chain Concurrency Org",
                slug=f"audit-chain-concurrency-{uuid.uuid4().hex[:8]}",
            )
        )
        setup_session.commit()

        def _append_first() -> uuid.UUID:
            connection = db_engine.connect()
            session = SessionLocal(bind=connection)
            try:
                entry = audit_service.log_event(
                    db=session,
                    org_id=org_id,
                    event_type=AuditEventType.AUTH_LOGIN_FAILED,
                    details={"attempt": "first"},
                )
                session.flush()
                first_flushed.set()
                assert release_first_commit.wait(timeout=5)
                session.commit()
                return entry.id
            finally:
                session.close()
                connection.close()

        def _append_second() -> uuid.UUID:
            connection = db_engine.connect()
            session = SessionLocal(bind=connection)
            try:
                assert first_flushed.wait(timeout=5)
                second_started.set()
                entry = audit_service.log_event(
                    db=session,
                    org_id=org_id,
                    event_type=AuditEventType.AUTH_LOGIN_FAILED,
                    details={"attempt": "second"},
                )
                session.flush()
                second_appended.set()
                session.commit()
                return entry.id
            finally:
                session.close()
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(_append_first)
            assert first_flushed.wait(timeout=5)
            second_future = executor.submit(_append_second)
            assert second_started.wait(timeout=5)

            second_returned_before_first_commit = second_appended.wait(timeout=0.5)
            release_first_commit.set()
            entry_ids = {first_future.result(timeout=5), second_future.result(timeout=5)}

        newest_first, total, _actor_names = audit_service.list_audit_logs(
            db=cleanup_session,
            org_id=org_id,
            page=1,
            per_page=10,
        )
        logs = list(reversed(newest_first))

        assert second_returned_before_first_commit is False
        assert total == 2
        assert {log.id for log in logs} == entry_ids
        assert len(logs) == 2
        assert logs[0].prev_hash == version_service.GENESIS_HASH
        assert logs[1].prev_hash == logs[0].entry_hash
    finally:
        release_first_commit.set()
        cleanup_session.execute(text("SET LOCAL session_replication_role = replica"))
        cleanup_session.query(AuditLog).filter(AuditLog.organization_id == org_id).delete()
        cleanup_session.query(Organization).filter(Organization.id == org_id).delete()
        cleanup_session.commit()
        cleanup_session.close()
        cleanup_connection.close()
        setup_session.close()
        setup_connection.close()
