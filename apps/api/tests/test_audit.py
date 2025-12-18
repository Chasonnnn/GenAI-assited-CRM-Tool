"""Tests for Audit Log system."""
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.db.models import AuditLog, Pipeline
from app.services import audit_service


@pytest.mark.asyncio
async def test_audit_log_created_on_pipeline_create(
    authed_client: AsyncClient,
    db: Session,
    mock_session,
):
    """Creating a pipeline should create an audit log entry."""
    # Count existing audit logs for this org
    initial_count = db.query(AuditLog).filter(
        AuditLog.organization_id == mock_session.org_id
    ).count()
    
    # Create pipeline
    payload = {
        "name": "Audit Test Pipeline",
        "stages": [
            {"status": "new", "label": "New", "color": "#3B82F6"},
        ]
    }
    response = await authed_client.post("/pipelines", json=payload)
    assert response.status_code == 201
    
    # Check audit log was created
    new_count = db.query(AuditLog).filter(
        AuditLog.organization_id == mock_session.org_id
    ).count()
    
    # There should be at least one new audit log
    assert new_count > initial_count


@pytest.mark.asyncio
async def test_audit_log_has_hash(
    authed_client: AsyncClient,
    db: Session,
    mock_session,
):
    """Audit logs should have entry_hash set."""
    # Create pipeline to trigger audit
    payload = {
        "name": "Hash Test Pipeline",
        "stages": [
            {"status": "new", "label": "New", "color": "#3B82F6"},
        ]
    }
    await authed_client.post("/pipelines", json=payload)
    
    # Get most recent audit log
    audit = db.query(AuditLog).filter(
        AuditLog.organization_id == mock_session.org_id
    ).order_by(AuditLog.created_at.desc()).first()
    
    assert audit is not None
    assert audit.entry_hash is not None
    assert len(audit.entry_hash) == 64  # SHA256 hex


def test_compute_audit_hash_deterministic():
    """Audit hash computation should be deterministic."""
    from app.services import version_service
    
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


def test_canonical_json_sorted():
    """canonical_json should sort keys and use compact separators."""
    result = audit_service.canonical_json({"b": 2, "a": 1})
    assert result == '{"a":1,"b":2}'


def test_canonical_json_handles_none():
    """canonical_json should handle None input."""
    result = audit_service.canonical_json(None)
    assert result == "{}"
