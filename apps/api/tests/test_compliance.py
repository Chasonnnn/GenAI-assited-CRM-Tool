from datetime import datetime, timedelta
import csv
import json
import os

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


def test_export_job_redacts_phi(db, test_org, test_user, tmp_path):
    settings.EXPORT_STORAGE_BACKEND = "local"
    settings.EXPORT_LOCAL_DIR = str(tmp_path)
    settings.EXPORT_MAX_RECORDS = 1000

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


def test_export_job_full_mode_keeps_values(db, test_org, test_user, tmp_path):
    settings.EXPORT_STORAGE_BACKEND = "local"
    settings.EXPORT_LOCAL_DIR = str(tmp_path)
    settings.EXPORT_MAX_RECORDS = 1000

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
