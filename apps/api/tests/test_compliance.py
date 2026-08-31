import csv
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.core.config import settings
from app.core.encryption import hash_email, hash_phone
from app.db.enums import AuditEventType, JobStatus, JobType, NotificationType, TaskType
from app.db.models import (
    AIActionApproval,
    AIConversation,
    AIEntitySummary,
    AIMessage,
    AIUsageLog,
    Attachment,
    AuditLog,
    AutomationWorkflow,
    Donor,
    EmailDelivery,
    EmailLog,
    EntityNote,
    Form,
    FormSubmission,
    FormSubmissionFile,
    IntakeLead,
    Job,
    MessageDelivery,
    MessagingContact,
    MessagingConversation,
    MessagingMessage,
    MetaLead,
    Notification,
    Organization,
    Task,
    TwilioRoute,
    TwilioSettings,
    WorkflowExecution,
)
from app.services import compliance_service, google_tasks_cleanup_service, pipeline_service
from app.utils.normalization import normalize_email
from app.utils.pagination import PaginationParams


def _pending_audit_logs(db) -> list[AuditLog]:
    return [obj for obj in db.new if isinstance(obj, AuditLog)]


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
        created_at=overrides.get("created_at") or datetime.now(UTC),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _create_archived_donor(db, *, org_id, suffix: str) -> Donor:
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type="egg_donor",
    )
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
    assert stage is not None
    email = normalize_email(f"retention-donor-{suffix}@example.com")
    donor = Donor(
        organization_id=org_id,
        donor_number=f"D{uuid4().int % 90000 + 10000:05d}",
        donor_type="egg",
        stage_id=stage.id,
        full_name=f"Retention Donor {suffix}",
        email=email,
        email_hash=hash_email(email),
        is_archived=True,
        archived_at=datetime.now(UTC) - timedelta(days=30),
    )
    db.add(donor)
    db.flush()
    return donor


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
        created_at=datetime.now(UTC) - timedelta(seconds=5),  # Earlier to ensure first
    )

    start_date = datetime.now(UTC) - timedelta(days=1)
    end_date = datetime.now(UTC) + timedelta(days=1)

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
        target_type="surrogate",
        details={"email": "full@example.com"},
        created_at=datetime.now(UTC) - timedelta(seconds=5),  # Earlier to ensure first
    )

    start_date = datetime.now(UTC) - timedelta(days=1)
    end_date = datetime.now(UTC) + timedelta(days=1)

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
        surrogate_id=None,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Old Task",
        task_type=TaskType.OTHER.value,
        is_completed=True,
        completed_at=datetime.now(UTC) - timedelta(days=10),
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


def test_default_retention_policies_include_donors(db, test_org):
    compliance_service.seed_default_retention_policies(db, test_org.id)

    policies = {
        policy.entity_type: policy
        for policy in compliance_service.list_retention_policies(db, test_org.id)
    }
    assert policies["donors"].retention_days == settings.DEFAULT_RETENTION_DAYS
    assert policies["donors"].is_active is True
    assert policies["donor_leads"].retention_days == settings.DEFAULT_RETENTION_DAYS
    assert policies["donor_leads"].is_active is True


def test_donor_lead_retention_purges_unconverted_sources_and_preserves_held_pair(
    db,
    test_org,
    test_user,
):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donor_leads",
        retention_days=1,
        is_active=True,
    )
    old_at = datetime.now(UTC) - timedelta(days=30)
    form = Form(
        organization_id=test_org.id,
        name="Old egg donor applications",
        purpose="lead_capture",
        lead_kind="egg_donor",
        created_by_user_id=test_user.id,
    )
    db.add(form)
    db.flush()

    purgeable_submission = FormSubmission(
        organization_id=test_org.id,
        form_id=form.id,
        lead_kind="egg_donor",
        answers_json={"full_name": "Old donor applicant"},
        submitted_at=old_at,
    )
    held_submission = FormSubmission(
        organization_id=test_org.id,
        form_id=form.id,
        lead_kind="egg_donor",
        answers_json={"full_name": "Held donor applicant"},
        submitted_at=old_at,
    )
    db.add_all([purgeable_submission, held_submission])
    db.flush()
    purgeable_intake = IntakeLead(
        organization_id=test_org.id,
        form_id=form.id,
        form_submission_id=purgeable_submission.id,
        lead_type="egg_donor",
        full_name="Old donor applicant",
        email="old-donor-applicant@example.com",
        created_at=old_at,
        updated_at=old_at,
    )
    held_intake = IntakeLead(
        organization_id=test_org.id,
        form_id=form.id,
        form_submission_id=held_submission.id,
        lead_type="egg_donor",
        full_name="Held donor applicant",
        email="held-donor-applicant@example.com",
        created_at=old_at,
        updated_at=old_at,
    )
    purgeable_file = FormSubmissionFile(
        organization_id=test_org.id,
        submission_id=purgeable_submission.id,
        filename="profile.png",
        field_key="profile_photo",
        storage_key=f"{test_org.id}/form-submissions/{purgeable_submission.id}/profile.png",
        content_type="image/png",
        file_size=64,
        checksum_sha256="c" * 64,
        scan_status="clean",
        quarantined=False,
    )
    old_meta_lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id=f"meta-{uuid4().hex}",
        lead_kind="sperm_donor",
        field_data={"email": "old-meta-donor@example.com"},
        is_converted=False,
        status="stored",
        received_at=old_at,
    )
    db.add_all([purgeable_intake, held_intake, purgeable_file, old_meta_lead])
    db.commit()

    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="form_submission",
        entity_id=held_submission.id,
        reason="Preserve this donor application",
    )
    ids = {
        "submission": purgeable_submission.id,
        "intake": purgeable_intake.id,
        "file": purgeable_file.id,
        "meta": old_meta_lead.id,
        "held_submission": held_submission.id,
        "held_intake": held_intake.id,
    }
    storage_key = purgeable_file.storage_key

    preview = {
        item.entity_type: item.count for item in compliance_service.preview_purge(db, test_org.id)
    }
    assert preview["donor_leads"] == 3

    executed = {
        item.entity_type: item.count
        for item in compliance_service.execute_purge(db, test_org.id, test_user.id)
    }
    assert executed["donor_leads"] == 3
    assert db.get(FormSubmission, ids["submission"]) is None
    assert db.get(IntakeLead, ids["intake"]) is None
    assert db.get(FormSubmissionFile, ids["file"]) is None
    assert db.get(MetaLead, ids["meta"]) is None
    assert db.get(FormSubmission, ids["held_submission"]) is not None
    assert db.get(IntakeLead, ids["held_intake"]) is not None
    cleanup_job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.STORAGE_DELETE.value,
        )
        .one()
    )
    assert cleanup_job.payload == {"storage_keys": [storage_key]}


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


def test_resolve_local_export_path_rejects_traversal(export_settings):
    with pytest.raises(ValueError, match="outside export directory"):
        compliance_service.resolve_local_export_path("../escape.csv")


def test_retention_preview_includes_ai_tables(db, test_org, test_user):
    cutoff = datetime.now(UTC) - timedelta(days=30)

    conversation = AIConversation(
        organization_id=test_org.id,
        user_id=test_user.id,
        entity_type="surrogate",
        entity_id=uuid4(),
        created_at=cutoff,
        updated_at=cutoff,
    )
    db.add(conversation)
    db.flush()

    message = AIMessage(
        conversation_id=conversation.id,
        role="user",
        content="Hello",
        created_at=cutoff,
    )
    db.add(message)
    db.flush()

    approval = AIActionApproval(
        message_id=message.id,
        action_index=0,
        action_type="add_note",
        action_payload={"content": "Note"},
        status="pending",
        created_at=cutoff,
    )
    db.add(approval)
    db.flush()

    usage_log = AIUsageLog(
        organization_id=test_org.id,
        user_id=test_user.id,
        conversation_id=conversation.id,
        model="gemini-3.7-flash",
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        created_at=cutoff,
    )
    db.add(usage_log)
    db.flush()

    summary = AIEntitySummary(
        organization_id=test_org.id,
        entity_type="surrogate",
        entity_id=uuid4(),
        summary_text="Summary",
        notes_plain_text=None,
        updated_at=cutoff,
    )
    db.add(summary)
    db.flush()

    for entity_type in [
        "ai_conversations",
        "ai_messages",
        "ai_action_approvals",
        "ai_usage_log",
        "ai_entity_summaries",
    ]:
        compliance_service.upsert_retention_policy(
            db=db,
            org_id=test_org.id,
            user_id=test_user.id,
            entity_type=entity_type,
            retention_days=1,
            is_active=True,
        )

    results = compliance_service.preview_purge(db, test_org.id)
    result_map = {item.entity_type: item.count for item in results}

    assert result_map["ai_conversations"] >= 1
    assert result_map["ai_messages"] >= 1
    assert result_map["ai_action_approvals"] >= 1
    assert result_map["ai_usage_log"] >= 1
    assert result_map["ai_entity_summaries"] >= 1


def test_specific_entity_legal_hold_blocks_related(db, test_org, test_user):
    """Legal hold on specific surrogate blocks purge for that surrogate only."""
    import uuid

    from app.db.models import Pipeline, PipelineStage, Surrogate

    # Create retention policy for archived surrogates
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="surrogates",
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

    # Create two old archived surrogates
    surrogate1_email = normalize_email("surrogate1@test.com")
    surrogate1 = Surrogate(
        organization_id=test_org.id,
        surrogate_number="S10001",
        stage_id=stage.id,
        status_label=stage.label,
        full_name="Surrogate One",
        email=surrogate1_email,
        email_hash=hash_email(surrogate1_email),
        source="manual",
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        archived_at=datetime.now(UTC) - timedelta(days=30),
    )
    surrogate2_email = normalize_email("surrogate2@test.com")
    surrogate2 = Surrogate(
        organization_id=test_org.id,
        surrogate_number="S10002",
        stage_id=stage.id,
        status_label=stage.label,
        full_name="Surrogate Two",
        email=surrogate2_email,
        email_hash=hash_email(surrogate2_email),
        source="manual",
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        archived_at=datetime.now(UTC) - timedelta(days=30),
    )
    db.add_all([surrogate1, surrogate2])
    db.commit()
    db.refresh(surrogate1)
    db.refresh(surrogate2)

    # Create legal hold on surrogate1 only
    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="surrogate",
        entity_id=surrogate1.id,
        reason="Litigation hold",
    )

    # Preview should show 1 surrogate (surrogate2 is purgeable, surrogate1 is protected)
    results = compliance_service.preview_purge(db, test_org.id)
    surrogate_result = next((r for r in results if r.entity_type == "surrogates"), None)
    assert surrogate_result is not None
    assert surrogate_result.count == 1  # Only surrogate2


def test_donor_legal_hold_blocks_donor_retention_purge(db, test_org, test_user):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donors",
        retention_days=1,
        is_active=True,
    )
    protected = _create_archived_donor(db, org_id=test_org.id, suffix="protected")
    purgeable = _create_archived_donor(db, org_id=test_org.id, suffix="purgeable")
    db.commit()
    protected_id = protected.id
    purgeable_id = purgeable.id

    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donor",
        entity_id=protected.id,
        reason="Donor record hold",
    )

    preview = {
        item.entity_type: item.count for item in compliance_service.preview_purge(db, test_org.id)
    }
    assert preview["donors"] == 1

    executed = {
        item.entity_type: item.count
        for item in compliance_service.execute_purge(db, test_org.id, test_user.id)
    }
    assert executed["donors"] == 1
    assert db.get(Donor, protected_id) is not None
    assert db.get(Donor, purgeable_id) is None


def test_donor_legal_hold_protects_related_completed_tasks(db, test_org, test_user):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="tasks",
        retention_days=1,
        is_active=True,
    )
    protected = _create_archived_donor(db, org_id=test_org.id, suffix="task-protected")
    purgeable = _create_archived_donor(db, org_id=test_org.id, suffix="task-purgeable")
    protected_task = Task(
        organization_id=test_org.id,
        donor_id=protected.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Protected donor task",
        task_type=TaskType.OTHER.value,
        is_completed=True,
        completed_at=datetime.now(UTC) - timedelta(days=30),
    )
    purgeable_task = Task(
        organization_id=test_org.id,
        donor_id=purgeable.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Purgeable donor task",
        task_type=TaskType.OTHER.value,
        is_completed=True,
        completed_at=datetime.now(UTC) - timedelta(days=30),
    )
    db.add_all([protected_task, purgeable_task])
    db.commit()
    protected_task_id = protected_task.id
    purgeable_task_id = purgeable_task.id

    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donor",
        entity_id=protected.id,
        reason="Donor task hold",
    )

    preview = {
        item.entity_type: item.count for item in compliance_service.preview_purge(db, test_org.id)
    }
    assert preview["tasks"] == 1

    compliance_service.execute_purge(db, test_org.id, test_user.id)
    assert db.get(Task, protected_task_id) is not None
    assert db.get(Task, purgeable_task_id) is None


def test_donor_retention_enqueues_google_task_cleanup_before_local_erasure(
    db,
    test_org,
    test_user,
):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donors",
        retention_days=1,
        is_active=True,
    )
    donor = _create_archived_donor(db, org_id=test_org.id, suffix="google-cleanup")
    task = Task(
        organization_id=test_org.id,
        donor_id=donor.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Remove remote donor task",
        task_type=TaskType.OTHER.value,
        google_task_id="remote-donor-task",
        google_task_list_id="donor-list",
    )
    db.add(task)
    db.commit()
    donor_id = donor.id
    task_id = task.id

    compliance_service.execute_purge(db, test_org.id, test_user.id)

    assert db.get(Donor, donor_id) is None
    assert db.get(Task, task_id) is None
    cleanup_job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value,
        )
        .one()
    )
    assert cleanup_job.status == JobStatus.PENDING.value
    assert cleanup_job.payload == {
        "user_id": str(test_user.id),
        "source_task_id": str(task_id),
        "google_task_id": "remote-donor-task",
        "google_task_list_id": "donor-list",
    }


def test_google_task_cleanup_rejects_cross_org_donor_task(db, test_org, test_user):
    other_org = Organization(
        name="Foreign Google Cleanup Org",
        slug=f"foreign-google-cleanup-{uuid4().hex}",
    )
    db.add(other_org)
    db.flush()
    donor = _create_archived_donor(db, org_id=other_org.id, suffix="foreign-google-cleanup")
    task = Task(
        organization_id=other_org.id,
        donor_id=donor.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Foreign cleanup task",
        task_type=TaskType.OTHER.value,
        google_task_id="foreign-remote",
        google_task_list_id="foreign-list",
    )
    db.add(task)
    db.commit()

    with pytest.raises(ValueError, match="outside the organization"):
        google_tasks_cleanup_service.enqueue_donor_task_remote_deletions(
            db,
            org_id=test_org.id,
            task_ids={task.id},
        )

    assert (
        db.query(Job).filter(Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value).count() == 0
    )


def test_task_legal_hold_prevents_parent_donor_purge(db, test_org, test_user):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donors",
        retention_days=1,
        is_active=True,
    )
    donor = _create_archived_donor(db, org_id=test_org.id, suffix="held-task-parent")
    task = Task(
        organization_id=test_org.id,
        donor_id=donor.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Legally held donor task",
        task_type=TaskType.OTHER.value,
        is_completed=True,
        completed_at=datetime.now(UTC) - timedelta(days=30),
    )
    db.add(task)
    db.commit()
    donor_id = donor.id

    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="task",
        entity_id=task.id,
        reason="Task-specific hold",
    )

    preview = {
        item.entity_type: item.count for item in compliance_service.preview_purge(db, test_org.id)
    }
    assert preview["donors"] == 0
    compliance_service.execute_purge(db, test_org.id, test_user.id)
    assert db.get(Donor, donor_id) is not None


def test_form_submission_file_legal_hold_prevents_parent_donor_purge(
    db,
    test_org,
    test_user,
):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donors",
        retention_days=1,
        is_active=True,
    )
    donor = _create_archived_donor(db, org_id=test_org.id, suffix="held-submission-file")
    form = Form(
        organization_id=test_org.id,
        name="Held donor submission file",
        purpose="lead_capture",
        lead_kind="egg_donor",
        created_by_user_id=test_user.id,
    )
    db.add(form)
    db.flush()
    submission = FormSubmission(
        organization_id=test_org.id,
        form_id=form.id,
        donor_id=donor.id,
        lead_kind="egg_donor",
        answers_json={"full_name": donor.full_name},
    )
    db.add(submission)
    db.flush()
    submission_file = FormSubmissionFile(
        organization_id=test_org.id,
        submission_id=submission.id,
        filename="held-profile.png",
        field_key="profile_photo",
        storage_key=f"{test_org.id}/forms/{submission.id}/held-profile.png",
        content_type="image/png",
        file_size=64,
        checksum_sha256="f" * 64,
        scan_status="clean",
        quarantined=False,
    )
    db.add(submission_file)
    db.commit()

    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="form_submission_file",
        entity_id=submission_file.id,
        reason="Preserve donor submission file",
    )

    preview = {
        item.entity_type: item.count for item in compliance_service.preview_purge(db, test_org.id)
    }
    assert preview["donors"] == 0
    compliance_service.execute_purge(db, test_org.id, test_user.id)
    assert db.get(Donor, donor.id) is not None
    assert db.get(FormSubmissionFile, submission_file.id) is not None


def test_canonical_entity_notes_legal_hold_prevents_parent_donor_purge(
    db,
    test_org,
    test_user,
):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donors",
        retention_days=1,
        is_active=True,
    )
    donor = _create_archived_donor(db, org_id=test_org.id, suffix="held-note")
    note = EntityNote(
        organization_id=test_org.id,
        entity_type="donor",
        entity_id=donor.id,
        author_id=test_user.id,
        content="Held donor note",
    )
    db.add(note)
    db.commit()

    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="entity_notes",
        entity_id=note.id,
        reason="Preserve donor note",
    )

    preview = {
        item.entity_type: item.count for item in compliance_service.preview_purge(db, test_org.id)
    }
    assert preview["donors"] == 0
    compliance_service.execute_purge(db, test_org.id, test_user.id)
    assert db.get(Donor, donor.id) is not None
    assert db.get(EntityNote, note.id) is not None


def test_donor_retention_removes_attachment_storage_objects(
    db,
    test_org,
    test_user,
):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donors",
        retention_days=1,
        is_active=True,
    )
    donor = _create_archived_donor(db, org_id=test_org.id, suffix="stored-photo")
    attachment = Attachment(
        organization_id=test_org.id,
        donor_id=donor.id,
        uploaded_by_user_id=test_user.id,
        filename="profile.png",
        storage_key=f"{test_org.id}/donors/{donor.id}/profile.png",
        content_type="image/png",
        file_size=64,
        checksum_sha256="a" * 64,
        scan_status="clean",
        quarantined=False,
    )
    db.add(attachment)
    db.flush()
    donor.profile_photo_attachment_id = attachment.id
    db.commit()
    storage_key = attachment.storage_key

    compliance_service.execute_purge(db, test_org.id, test_user.id)

    cleanup_job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.STORAGE_DELETE.value,
        )
        .one()
    )
    assert cleanup_job.payload == {"storage_keys": [storage_key]}
    assert (
        db.query(Attachment)
        .filter(Attachment.organization_id == test_org.id, Attachment.storage_key == storage_key)
        .count()
        == 0
    )


def test_donor_retention_removes_linked_source_and_workflow_pii(
    db,
    test_org,
    test_user,
):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donors",
        retention_days=1,
        is_active=True,
    )
    donor = _create_archived_donor(db, org_id=test_org.id, suffix="linked-pii")
    form = Form(
        organization_id=test_org.id,
        name="Egg donor retention form",
        purpose="lead_capture",
        lead_kind="egg_donor",
        created_by_user_id=test_user.id,
    )
    db.add(form)
    db.flush()
    submission = FormSubmission(
        organization_id=test_org.id,
        form_id=form.id,
        donor_id=donor.id,
        lead_kind="egg_donor",
        answers_json={"full_name": "Retention Donor linked-pii"},
    )
    db.add(submission)
    db.flush()
    submission_file = FormSubmissionFile(
        organization_id=test_org.id,
        submission_id=submission.id,
        filename="profile.png",
        field_key="profile_photo",
        storage_key=f"{test_org.id}/forms/{submission.id}/profile.png",
        content_type="image/png",
        file_size=64,
        checksum_sha256="b" * 64,
        scan_status="clean",
        quarantined=False,
    )
    intake_lead = IntakeLead(
        organization_id=test_org.id,
        form_id=form.id,
        form_submission_id=submission.id,
        lead_type="egg_donor",
        full_name="Retention Donor linked-pii",
        email="linked-pii@example.com",
        promoted_donor_id=donor.id,
    )
    meta_lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id=f"meta-{uuid4().hex}",
        lead_kind="egg_donor",
        field_data={"email": "linked-pii@example.com"},
        converted_donor_id=donor.id,
        is_converted=True,
        status="converted",
    )
    note = EntityNote(
        organization_id=test_org.id,
        entity_type="donor",
        entity_id=donor.id,
        author_id=test_user.id,
        content="Donor-specific note",
    )
    task = Task(
        organization_id=test_org.id,
        donor_id=donor.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Donor-specific task",
        task_type=TaskType.OTHER.value,
    )
    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name=f"Retention donor workflow {uuid4().hex[:8]}",
        subject_type="egg_donor",
        trigger_type="donor_created",
        trigger_config={},
        conditions=[],
        actions=[],
        scope="org",
        is_enabled=True,
    )
    db.add_all([submission_file, intake_lead, meta_lead, note, task, workflow])
    db.flush()
    execution = WorkflowExecution(
        organization_id=test_org.id,
        workflow_id=workflow.id,
        event_id=uuid4(),
        depth=0,
        event_source="user",
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        trigger_event={"full_name": donor.full_name},
        matched_conditions=True,
        actions_executed=[],
        status="completed",
    )
    notification = Notification(
        organization_id=test_org.id,
        user_id=test_user.id,
        type=NotificationType.TASK_ASSIGNED.value,
        title=f"Task for {donor.donor_number}",
        entity_type="task",
        entity_id=task.id,
    )
    workflow_job = Job(
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        status=JobStatus.PENDING.value,
        payload={
            "recipient_email": donor.email,
            "variables": {"donor_name": donor.full_name},
            "subject_type": "egg_donor",
            "subject_id": str(donor.id),
            "workflow_execution_id": str(execution.id),
        },
    )
    db.add_all([execution, notification, workflow_job])
    db.commit()
    ids = {
        "donor": donor.id,
        "submission": submission.id,
        "submission_file": submission_file.id,
        "intake_lead": intake_lead.id,
        "meta_lead": meta_lead.id,
        "note": note.id,
        "task": task.id,
        "execution": execution.id,
        "notification": notification.id,
        "job": workflow_job.id,
    }
    storage_key = submission_file.storage_key

    compliance_service.execute_purge(db, test_org.id, test_user.id)

    assert db.get(Donor, ids["donor"]) is None
    assert db.get(FormSubmission, ids["submission"]) is None
    assert db.get(FormSubmissionFile, ids["submission_file"]) is None
    assert db.get(IntakeLead, ids["intake_lead"]) is None
    assert db.get(MetaLead, ids["meta_lead"]) is None
    assert db.get(EntityNote, ids["note"]) is None
    assert db.get(Task, ids["task"]) is None
    assert db.get(WorkflowExecution, ids["execution"]) is None
    assert db.get(Notification, ids["notification"]) is None
    assert db.get(Job, ids["job"]) is None
    cleanup_job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.STORAGE_DELETE.value,
        )
        .one()
    )
    assert storage_key in cleanup_job.payload["storage_keys"]


def test_donor_retention_refuses_to_race_a_running_workflow_job(
    db,
    test_org,
    test_user,
):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donors",
        retention_days=1,
        is_active=True,
    )
    donor = _create_archived_donor(db, org_id=test_org.id, suffix="running-job")
    running_job = Job(
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        status=JobStatus.RUNNING.value,
        payload={
            "recipient_email": donor.email,
            "subject_type": "egg_donor",
            "subject_id": str(donor.id),
        },
    )
    db.add(running_job)
    db.commit()
    donor_id = donor.id

    statements: list[str] = []

    def capture_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    connection = db.connection()
    event.listen(connection, "before_cursor_execute", capture_statement)
    try:
        with pytest.raises(ValueError, match="donor-related background job is running"):
            compliance_service.execute_purge(db, test_org.id, test_user.id)
    finally:
        event.remove(connection, "before_cursor_execute", capture_statement)

    assert db.get(Donor, donor_id) is not None
    assert db.get(Job, running_job.id) is not None
    assert any("FROM jobs" in statement and "FOR UPDATE" in statement for statement in statements)


def test_donor_retention_refuses_to_race_a_leased_email_delivery(
    db,
    test_org,
    test_user,
):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="donors",
        retention_days=1,
        is_active=True,
    )
    donor = _create_archived_donor(db, org_id=test_org.id, suffix="leased-email")
    workflow_job = Job(
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        status=JobStatus.PENDING.value,
        payload={
            "recipient_email": donor.email,
            "subject_type": "egg_donor",
            "subject_id": str(donor.id),
        },
    )
    db.add(workflow_job)
    db.flush()
    email_log = EmailLog(
        organization_id=test_org.id,
        job_id=workflow_job.id,
        source_type="workflow_job",
        source_id=workflow_job.id,
        recipient_email=donor.email,
        subject="Donor workflow email",
        body="<p>Donor workflow email</p>",
        status="pending",
        provider="resend",
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
    )
    db.add(email_log)
    db.flush()
    delivery = EmailDelivery(
        organization_id=test_org.id,
        email_log_id=email_log.id,
        provider="resend",
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        idempotency_key=f"leased-donor/{email_log.id}",
        request_fingerprint="d" * 64,
        status="leased",
        attempt_count=1,
        max_attempts=5,
        lease_token=uuid4(),
        lease_owner="retention-race-test",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.add(delivery)
    db.commit()
    donor_id = donor.id

    statements: list[str] = []

    def capture_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    connection = db.connection()
    event.listen(connection, "before_cursor_execute", capture_statement)
    try:
        with pytest.raises(ValueError, match="email delivery is leased"):
            compliance_service.execute_purge(db, test_org.id, test_user.id)
    finally:
        event.remove(connection, "before_cursor_execute", capture_statement)

    assert db.query(Donor).filter(Donor.id == donor_id).count() == 1
    assert db.get(EmailDelivery, delivery.id) is not None
    assert any(
        "FROM email_deliveries" in statement and "FOR UPDATE" in statement
        for statement in statements
    )


def test_donor_retention_locks_message_delivery_before_lease_check(db, test_org):
    twilio_settings = TwilioSettings(organization_id=test_org.id)
    db.add(twilio_settings)
    db.flush()
    route = TwilioRoute(
        settings_id=twilio_settings.id,
        organization_id=test_org.id,
        purpose="operational",
        sender_phone_hash=hash_phone("+14155550900"),
        sender_phone_last4="0900",
    )
    contact = MessagingContact(
        organization_id=test_org.id,
        phone_e164="+14155550123",
        phone_hash=hash_phone("+14155550123"),
        phone_last4="0123",
    )
    db.add_all([route, contact])
    db.flush()
    conversation = MessagingConversation(
        organization_id=test_org.id,
        contact_id=contact.id,
        route_id=route.id,
    )
    db.add(conversation)
    db.flush()
    message = MessagingMessage(
        organization_id=test_org.id,
        conversation_id=conversation.id,
        contact_id=contact.id,
        route_id=route.id,
        purpose="operational",
        direction="outbound",
        body="Donor campaign message",
        from_phone_hash=route.sender_phone_hash,
        from_phone_last4=route.sender_phone_last4,
        to_phone_hash=contact.phone_hash,
        to_phone_last4=contact.phone_last4,
    )
    db.add(message)
    db.flush()
    delivery = MessageDelivery(
        organization_id=test_org.id,
        message_id=message.id,
        contact_id=contact.id,
        route_id=route.id,
        purpose="operational",
        source_type="campaign",
        idempotency_key=f"donor-retention-lock/{message.id}",
        payload_fingerprint="e" * 64,
        status="leased",
        attempt_count=1,
        max_attempts=5,
        lease_token=uuid4(),
        lease_owner="retention-message-race-test",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.add(delivery)
    db.commit()

    statements: list[str] = []

    def capture_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    connection = db.connection()
    event.listen(connection, "before_cursor_execute", capture_statement)
    try:
        with pytest.raises(ValueError, match="message delivery is leased"):
            compliance_service._ensure_message_deliveries_not_leased(
                db,
                org_id=test_org.id,
                message_delivery_ids={delivery.id},
            )
    finally:
        event.remove(connection, "before_cursor_execute", capture_statement)

    assert any(
        "FROM message_deliveries" in statement and "FOR UPDATE" in statement
        for statement in statements
    )


def test_list_legal_holds_paginates(db, test_org, test_user):
    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type=None,
        entity_id=None,
        reason="Hold 1",
    )
    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type=None,
        entity_id=None,
        reason="Hold 2",
    )
    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type=None,
        entity_id=None,
        reason="Hold 3",
    )

    page_one = PaginationParams(page=1, per_page=2)
    items, total = compliance_service.list_legal_holds(db, test_org.id, page_one)
    assert total == 3
    assert len(items) == 2

    page_two = PaginationParams(page=2, per_page=2)
    items_two, total_two = compliance_service.list_legal_holds(db, test_org.id, page_two)
    assert total_two == 3
    assert len(items_two) == 1


def test_rate_limit_exceeded(db, test_org, test_user, export_settings):
    """Export rate limit returns error when exceeded."""
    settings.EXPORT_RATE_LIMIT_PER_HOUR = 1
    start_date = datetime.now(UTC) - timedelta(days=1)
    end_date = datetime.now(UTC) + timedelta(days=1)

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


def test_create_export_job_uses_direct_count_queries(
    db, test_org, test_user, export_settings, monkeypatch
):
    from sqlalchemy.orm import Query

    from app.db.models import AuditLog, ExportJob

    original_count = Query.count

    def _count_should_not_be_called(self, *args, **kwargs):
        entity = self.column_descriptions[0].get("entity") if self.column_descriptions else None
        if entity in {AuditLog, ExportJob}:
            raise AssertionError("create_export_job should use direct aggregate count queries")
        return original_count(self, *args, **kwargs)

    monkeypatch.setattr(Query, "count", _count_should_not_be_called)

    compliance_service.create_export_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        export_type="audit",
        start_date=datetime.now(UTC) - timedelta(days=1),
        end_date=datetime.now(UTC) + timedelta(days=1),
        file_format="csv",
        redact_mode="redacted",
        acknowledgment=None,
    )


def test_create_export_job_commits_audit_log(db, test_org, test_user, export_settings):
    start_date = datetime.now(UTC) - timedelta(days=1)
    end_date = datetime.now(UTC) + timedelta(days=1)

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

    assert _pending_audit_logs(db) == []


def test_upsert_retention_policy_commits_audit_log(db, test_org, test_user):
    compliance_service.upsert_retention_policy(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="tasks",
        retention_days=30,
        is_active=True,
    )

    assert _pending_audit_logs(db) == []


def test_create_legal_hold_commits_audit_log(db, test_org, test_user):
    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type=None,
        entity_id=None,
        reason="test hold",
    )

    assert _pending_audit_logs(db) == []


def test_release_legal_hold_commits_audit_log(db, test_org, test_user):
    from app.db.models import LegalHold

    hold = LegalHold(
        organization_id=test_org.id,
        entity_type=None,
        entity_id=None,
        reason="manual hold",
        created_by_user_id=test_user.id,
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)

    released = compliance_service.release_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        hold_id=hold.id,
    )
    assert released is not None

    assert _pending_audit_logs(db) == []


def test_execute_purge_commits_audit_log(db, test_org, test_user):
    results = compliance_service.execute_purge(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
    )

    assert results == []
    assert _pending_audit_logs(db) == []
