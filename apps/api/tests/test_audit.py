"""Tests for Audit Log system - Unit tests only."""

from app.services import audit_service
from app.services import version_service


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
