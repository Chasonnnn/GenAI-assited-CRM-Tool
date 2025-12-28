from datetime import datetime, timedelta
import csv
import json
import os

import pytest

from app.core.config import settings
from app.db.enums import AuditEventType, TaskType
from app.db.models import AuditLog, Task
from app.services import compliance_service


def _create_audit_log(db, org_id, user_id, **overrides):
    log = AuditLog(
        organization_id=org_id,
        actor_user_id=user_id,
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS.value,
        target_type=overrides.get("target_type"),
        target_id=overrides.get("target_id"),
        details=overrides.get("details"),
        ip_address=overrides.get("ip_address"),
        prev_hash="0" * 64,
        entry_hash="1" * 64,
        created_at=overrides.get("created_at") or datetime.utcnow(),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@pytest.fixture
def export_settings(tmp_path):
    original = {
        "EXPORT_STORAGE_BACKEND": settings.EXPORT_STORAGE_BACKEND,
        "EXPORT_LOCAL_DIR": settings.EXPORT_LOCAL_DIR,
        "EXPORT_MAX_RECORDS": settings.EXPORT_MAX_RECORDS,
        "EXPORT_RATE_LIMIT_PER_HOUR": settings.EXPORT_RATE_LIMIT_PER_HOUR,
    }
    settings.EXPORT_STORAGE_BACKEND = "local"
    settings.EXPORT_LOCAL_DIR = str(tmp_path)
    settings.EXPORT_MAX_RECORDS = 1000
    yield
    for key, value in original.items():
        setattr(settings, key, value)


def test_export_job_redacts_phi(db, test_org, test_user, export_settings):
    _create_audit_log(
        db,
        test_org.id,
        test_user.id,
        target_type="=2+2",
        details={
            "email": "john@example.com",
            "phone": "415-555-1234",
            "note": "Call me at 415-555-1234",
        },
        ip_address="10.20.30.40",
        created_at=datetime.utcnow() - timedelta(seconds=5),  # Earlier to ensure first
    )

    start_date = datetime.utcnow() - timedelta(days=1)
    end_date = datetime.utcnow() + timedelta(days=1)

    job = compliance_service.create_export_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        export_type="audit",
        start_date=start_date,
        end_date=end_date,
        file_format="csv",
        redact_mode="redacted",
        acknowledgment=None,
    )

    compliance_service.process_export_job(db, job.id)

    file_path = compliance_service.resolve_local_export_path(job.file_path)
    assert os.path.exists(file_path)

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        row = next(reader)

    row_data = dict(zip(header, row))
    assert "***@example.com" in row_data["details"]
    assert "john@example.com" not in row_data["details"]
    assert "10.20.x.x" in row_data["ip_address"]
    assert row_data["target_type"].startswith("'=")
    assert len(row_data["created_at"]) == 7


def test_export_job_full_mode_keeps_values(db, test_org, test_user, export_settings):
    _create_audit_log(
        db,
        test_org.id,
        test_user.id,
        target_type="case",
        details={"email": "full@example.com"},
        created_at=datetime.utcnow() - timedelta(seconds=5),  # Earlier to ensure first
    )

    start_date = datetime.utcnow() - timedelta(days=1)
    end_date = datetime.utcnow() + timedelta(days=1)

    job = compliance_service.create_export_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        export_type="audit",
        start_date=start_date,
        end_date=end_date,
        file_format="json",
        redact_mode="full",
        acknowledgment="I UNDERSTAND",
    )

    compliance_service.process_export_job(db, job.id)

    file_path = compliance_service.resolve_local_export_path(job.file_path)
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data[0]["details"]["email"] == "full@example.com"
    assert "T" in data[0]["created_at"]


def test_legal_hold_blocks_purge_preview(db, test_org, test_user):
    policy = compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="tasks",
        retention_days=1,
        is_active=True,
    )
    assert policy.entity_type == "tasks"

    old_task = Task(
        organization_id=test_org.id,
        case_id=None,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Old Task",
        task_type=TaskType.OTHER.value,
        is_completed=True,
        completed_at=datetime.utcnow() - timedelta(days=10),
    )
    db.add(old_task)
    db.commit()

    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type=None,
        entity_id=None,
        reason="Investigation",
    )

    results = compliance_service.preview_purge(db, test_org.id)
    assert results == []


def test_export_empty_result(db, test_org, test_user, export_settings):
    """Export when no logs match the date range returns empty file."""
    # Use a date range far in the past where no logs exist
    start_date = datetime(2000, 1, 1)
    end_date = datetime(2000, 1, 2)

    job = compliance_service.create_export_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        export_type="audit",
        start_date=start_date,
        end_date=end_date,
        file_format="csv",
        redact_mode="redacted",
        acknowledgment=None,
    )

    compliance_service.process_export_job(db, job.id)

    file_path = compliance_service.resolve_local_export_path(job.file_path)
    assert os.path.exists(file_path)

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Only header, no data rows
    assert len(rows) <= 1
    assert job.record_count == 0


def test_specific_entity_legal_hold_blocks_related(db, test_org, test_user):
    """Legal hold on specific case blocks purge for that case only."""
    from app.db.models import Case, Pipeline, PipelineStage
    import uuid

    # Create retention policy for archived cases
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="cases",
        retention_days=1,
        is_active=True,
    )

    # Create default pipeline and stage for test org (required for Case.stage_id NOT NULL)
    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Test Pipeline",
        is_default=True,
        current_version=1,
    )
    db.add(pipeline)
    db.flush()

    stage = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=pipeline.id,
        slug="new_unread",
        label="New Unread",
        color="#3B82F6",
        stage_type="intake",
        order=1,
        is_active=True,
    )
    db.add(stage)
    db.flush()

    # Create two old archived cases
    case1 = Case(
        organization_id=test_org.id,
        case_number="TEST-001",
        stage_id=stage.id,
        status_label=stage.label,
        full_name="Case One",
        email="case1@test.com",
        source="manual",
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        archived_at=datetime.utcnow() - timedelta(days=30),
    )
    case2 = Case(
        organization_id=test_org.id,
        case_number="TEST-002",
        stage_id=stage.id,
        status_label=stage.label,
        full_name="Case Two",
        email="case2@test.com",
        source="manual",
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        archived_at=datetime.utcnow() - timedelta(days=30),
    )
    db.add_all([case1, case2])
    db.commit()
    db.refresh(case1)
    db.refresh(case2)

    # Create legal hold on case1 only
    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="case",
        entity_id=case1.id,
        reason="Litigation hold",
    )

    # Preview should show 1 case (case2 is purgeable, case1 is protected)
    results = compliance_service.preview_purge(db, test_org.id)
    case_result = next((r for r in results if r.entity_type == "cases"), None)
    assert case_result is not None
    assert case_result.count == 1  # Only case2


def test_rate_limit_exceeded(db, test_org, test_user, export_settings):
    """Export rate limit returns error when exceeded."""
    settings.EXPORT_RATE_LIMIT_PER_HOUR = 1
    start_date = datetime.utcnow() - timedelta(days=1)
    end_date = datetime.utcnow() + timedelta(days=1)

    # First export should succeed
    job1 = compliance_service.create_export_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        export_type="audit",
        start_date=start_date,
        end_date=end_date,
        file_format="csv",
        redact_mode="redacted",
        acknowledgment=None,
    )
    assert job1 is not None

    # Second export should fail due to rate limit
    with pytest.raises(ValueError, match="rate limit"):
        compliance_service.create_export_job(
            db=db,
            org_id=test_org.id,
            user_id=test_user.id,
            export_type="audit",
            start_date=start_date,
            end_date=end_date,
            file_format="csv",
            redact_mode="redacted",
            acknowledgment=None,
        )
