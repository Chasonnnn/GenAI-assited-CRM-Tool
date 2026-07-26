"""Production-safe reconciliation contracts for legacy running job claims."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from uuid import UUID, uuid4

import pytest

from app.db.enums import JobStatus, JobType
from app.db.models import Attachment, AuditLog, EmailLog, Job


WORKFLOW_JOB_ID = UUID("91000000-0000-4000-8000-000000000001")
TOKENED_JOB_ID = UUID("91000000-0000-4000-8000-000000000002")
ATTACHMENT_JOB_ID = UUID("91000000-0000-4000-8000-000000000003")
SYNC_JOB_ID = UUID("91000000-0000-4000-8000-000000000004")
ORG_DELETE_JOB_ID = UUID("91000000-0000-4000-8000-000000000005")
STALE_BEFORE = datetime(2026, 7, 24, tzinfo=timezone.utc)
EVALUATED_AT = datetime(2026, 7, 25, 22, 44, tzinfo=timezone.utc)
APPLIED_AT = datetime(2026, 7, 25, 23, 5, tzinfo=timezone.utc)
LEGACY_RUN_AT = datetime(2026, 5, 20, 5, 4, tzinfo=timezone.utc)


def _expected_single_decision_fingerprint(
    *,
    job_id: UUID,
    organization_id: UUID,
    job_type: str,
    target_status: str,
    reason_code: str,
    non_replayable: bool,
    evidence_flags: dict[str, bool],
    run_at: datetime = LEGACY_RUN_AT,
    attempts: int = 1,
    stale_before: datetime = STALE_BEFORE,
    evaluated_at: datetime = EVALUATED_AT,
) -> str:
    canonical_evidence = ",".join(
        f'"{key}":{str(value).lower()}' for key, value in sorted(evidence_flags.items())
    )
    canonical_plan = (
        f'{{"decisions":[{{"attempts":{attempts},'
        f'"evidence_flags":{{{canonical_evidence}}},"job_id":"{job_id}",'
        f'"job_type":"{job_type}",'
        f'"non_replayable":{str(non_replayable).lower()},'
        f'"organization_id":"{organization_id}","reason_code":"{reason_code}",'
        f'"run_at":"{run_at.isoformat()}","target_status":"{target_status}"}}],'
        f'"evaluated_at":"{evaluated_at.isoformat()}","schema_version":1,'
        f'"stale_before":"{stale_before.isoformat()}"}}'
    )
    return hashlib.sha256(canonical_plan.encode("utf-8")).hexdigest()


def _legacy_job(*, job_id: UUID, org_id: UUID, job_type: str, payload: dict) -> Job:
    return Job(
        id=job_id,
        organization_id=org_id,
        job_type=job_type,
        payload=payload,
        run_at=LEGACY_RUN_AT,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=None,
        claimed_at=None,
    )


def _mark_preexisting_running_jobs_as_actively_claimed(db) -> None:
    """Keep this module independent from unrelated rows in a shared local test DB."""
    db.query(Job).filter(
        Job.status == JobStatus.RUNNING.value,
        (Job.claim_token.is_(None) | Job.claimed_at.is_(None)),
    ).update(
        {
            Job.claim_token: uuid4(),
            Job.claimed_at: EVALUATED_AT,
        },
        synchronize_session=False,
    )
    db.flush()


def test_dry_run_classifies_only_unclaimed_legacy_work_and_leaves_tokened_work_invisible(
    db, test_org
):
    from app.services import legacy_job_reconciliation_service

    legacy_job = _legacy_job(
        job_id=WORKFLOW_JOB_ID,
        org_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={"recipient_email": "must-not-send@example.test"},
    )
    active_token = uuid4()
    tokened_job = Job(
        id=TOKENED_JOB_ID,
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={"recipient_email": "active-claim@example.test"},
        run_at=LEGACY_RUN_AT,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=active_token,
        claimed_at=EVALUATED_AT - timedelta(minutes=1),
    )
    db.add_all([legacy_job, tokened_job])
    db.commit()

    report = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db,
        stale_before=STALE_BEFORE,
        apply=False,
        evaluated_at=EVALUATED_AT,
    )

    assert report.mode == "dry_run"
    assert report.count == 1
    assert [decision.job_id for decision in report.decisions] == [legacy_job.id]
    assert report.decisions[0].run_at == LEGACY_RUN_AT
    assert report.decisions[0].attempts == 1
    assert report.decisions[0].evidence_flags == {
        "email_log_exists": False,
        "email_log_has_provider_id": False,
        "email_log_has_sent_at": False,
    }
    assert report.fingerprint == _expected_single_decision_fingerprint(
        job_id=WORKFLOW_JOB_ID,
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        target_status=JobStatus.FAILED.value,
        reason_code="workflow_email_no_local_delivery_evidence",
        non_replayable=True,
        evidence_flags={
            "email_log_exists": False,
            "email_log_has_provider_id": False,
            "email_log_has_sent_at": False,
        },
    )
    db.refresh(legacy_job)
    db.refresh(tokened_job)
    assert legacy_job.status == JobStatus.RUNNING.value
    assert "_reconciliation" not in legacy_job.payload
    assert tokened_job.status == JobStatus.RUNNING.value
    assert tokened_job.claim_token == active_token
    assert "_reconciliation" not in tokened_job.payload


def test_apply_requires_exact_review_and_quarantines_without_replaying(db, test_org):
    from app.services import legacy_job_reconciliation_service

    _mark_preexisting_running_jobs_as_actively_claimed(db)
    original_payload = {
        "template_id": str(uuid4()),
        "recipient_email": "must-not-send@example.test",
        "workflow_scope": "org",
    }
    job = _legacy_job(
        job_id=WORKFLOW_JOB_ID,
        org_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload=original_payload,
    )
    job.max_attempts = 3
    job.idempotency_key = "legacy-workflow-email:test"
    db.add(job)
    db.commit()
    expected_fingerprint = _expected_single_decision_fingerprint(
        job_id=WORKFLOW_JOB_ID,
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        target_status=JobStatus.FAILED.value,
        reason_code="workflow_email_no_local_delivery_evidence",
        non_replayable=True,
        evidence_flags={
            "email_log_exists": False,
            "email_log_has_provider_id": False,
            "email_log_has_sent_at": False,
        },
    )

    report = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db,
        stale_before=STALE_BEFORE,
        apply=True,
        evaluated_at=EVALUATED_AT,
        expected_count=1,
        expected_fingerprint=expected_fingerprint,
        review_reason="Weekend production cutover for legacy claims",
        clock=lambda: APPLIED_AT,
    )

    assert report.mode == "apply"
    assert report.count == 1
    assert report.fingerprint == expected_fingerprint
    db.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.claim_token is None
    assert job.claimed_at is None
    assert job.run_at == LEGACY_RUN_AT
    assert job.attempts == 1
    assert job.max_attempts == 3
    assert job.idempotency_key == "legacy-workflow-email:test"
    assert job.payload == {
        **original_payload,
        "_reconciliation": {
            "schema_version": 1,
            "non_replayable": True,
            "reason_code": "workflow_email_no_local_delivery_evidence",
            "evaluated_at": EVALUATED_AT.isoformat(),
            "applied_at": APPLIED_AT.isoformat(),
            "fingerprint": expected_fingerprint,
        },
    }

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.target_type == "job",
            AuditLog.target_id == job.id,
        )
        .one()
    )
    assert audit_log.actor_user_id is None
    assert audit_log.event_type == "job_legacy_claim_reconciled"
    assert audit_log.details == {
        "schema_version": 1,
        "target_status": JobStatus.FAILED.value,
        "reason_code": "workflow_email_no_local_delivery_evidence",
        "non_replayable": True,
        "fingerprint": expected_fingerprint,
        "review_reason": "Weekend production cutover for legacy claims",
        "evaluated_at": EVALUATED_AT.isoformat(),
        "applied_at": APPLIED_AT.isoformat(),
    }


def test_apply_preserves_the_audit_hash_chain_for_multiple_jobs_in_one_org(db, test_org):
    _mark_preexisting_running_jobs_as_actively_claimed(db)
    jobs = [
        _legacy_job(
            job_id=uuid4(),
            org_id=test_org.id,
            job_type=JobType.GOOGLE_CALENDAR_SYNC.value,
            payload={"user_id": str(uuid4())},
        ),
        _legacy_job(
            job_id=uuid4(),
            org_id=test_org.id,
            job_type=JobType.GOOGLE_TASKS_SYNC.value,
            payload={"user_id": str(uuid4())},
        ),
    ]
    db.add_all(jobs)
    db.commit()

    from app.services import legacy_job_reconciliation_service

    preview = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db,
        stale_before=STALE_BEFORE,
        apply=False,
        evaluated_at=EVALUATED_AT,
    )
    legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db,
        stale_before=STALE_BEFORE,
        apply=True,
        evaluated_at=EVALUATED_AT,
        expected_count=preview.count,
        expected_fingerprint=preview.fingerprint,
        review_reason="Reviewed two-job audit chain",
    )

    audit_logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == "job_legacy_claim_reconciled",
        )
        .order_by(AuditLog.created_at, AuditLog.id)
        .all()
    )
    assert len(audit_logs) == 2
    assert audit_logs[1].prev_hash == audit_logs[0].entry_hash


@pytest.mark.parametrize(
    ("expected_count", "expected_fingerprint"),
    [(2, "reviewed"), (1, "0" * 64)],
)
def test_apply_aborts_without_mutation_when_operator_review_has_drifted(
    db, test_org, expected_count, expected_fingerprint
):
    from app.services import legacy_job_reconciliation_service

    original_payload = {"recipient_email": "must-not-send@example.test"}
    job = _legacy_job(
        job_id=WORKFLOW_JOB_ID,
        org_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload=original_payload,
    )
    db.add(job)
    db.commit()
    if expected_fingerprint == "reviewed":
        expected_fingerprint = _expected_single_decision_fingerprint(
            job_id=WORKFLOW_JOB_ID,
            organization_id=test_org.id,
            job_type=JobType.WORKFLOW_EMAIL.value,
            target_status=JobStatus.FAILED.value,
            reason_code="workflow_email_no_local_delivery_evidence",
            non_replayable=True,
            evidence_flags={
                "email_log_exists": False,
                "email_log_has_provider_id": False,
                "email_log_has_sent_at": False,
            },
        )

    with pytest.raises(ValueError, match="review no longer matches"):
        legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
            db,
            stale_before=STALE_BEFORE,
            apply=True,
            evaluated_at=EVALUATED_AT,
            expected_count=expected_count,
            expected_fingerprint=expected_fingerprint,
            review_reason="Weekend production cutover for legacy claims",
        )

    db.refresh(job)
    assert job.status == JobStatus.RUNNING.value
    assert job.claim_token is None
    assert job.claimed_at is None
    assert job.payload == original_payload
    assert db.query(AuditLog).filter(AuditLog.target_id == job.id).count() == 0


def test_apply_rolls_back_when_any_tokenless_running_job_remains(db, test_org):
    """A reviewed subset must not commit while an old worker claim remains."""
    from app.services import legacy_job_reconciliation_service

    _mark_preexisting_running_jobs_as_actively_claimed(db)
    classified_job = _legacy_job(
        job_id=WORKFLOW_JOB_ID,
        org_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={"recipient_email": "must-not-send@example.test"},
    )
    unclassified_job = _legacy_job(
        job_id=uuid4(),
        org_id=test_org.id,
        job_type=JobType.SEND_EMAIL.value,
        payload={"recipient_email": "must-not-send-either@example.test"},
    )
    db.add_all([classified_job, unclassified_job])
    db.commit()

    preview = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db,
        stale_before=STALE_BEFORE,
        apply=False,
        evaluated_at=EVALUATED_AT,
    )
    assert [decision.job_id for decision in preview.decisions] == [classified_job.id]

    with pytest.raises(ValueError, match="tokenless running jobs remain"):
        legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
            db,
            stale_before=STALE_BEFORE,
            apply=True,
            evaluated_at=EVALUATED_AT,
            expected_count=preview.count,
            expected_fingerprint=preview.fingerprint,
            review_reason="Reviewed subset must remain atomic",
        )

    db.refresh(classified_job)
    db.refresh(unclassified_job)
    assert classified_job.status == JobStatus.RUNNING.value
    assert classified_job.payload == {"recipient_email": "must-not-send@example.test"}
    assert unclassified_job.status == JobStatus.RUNNING.value
    assert db.query(AuditLog).filter(AuditLog.target_id == classified_job.id).count() == 0


def test_apply_records_actual_time_separately_from_plan_evaluation(db, test_org):
    from app.services import legacy_job_reconciliation_service

    _mark_preexisting_running_jobs_as_actively_claimed(db)
    attachment = Attachment(
        organization_id=test_org.id,
        filename="already-scanned-at-apply.pdf",
        storage_key="tests/already-scanned-at-apply.pdf",
        content_type="application/pdf",
        file_size=128,
        checksum_sha256="b" * 64,
        scan_status="clean",
        scanned_at=datetime(2026, 3, 15, 21, 55, tzinfo=timezone.utc),
        quarantined=False,
    )
    db.add(attachment)
    db.flush()
    job = _legacy_job(
        job_id=ATTACHMENT_JOB_ID,
        org_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        payload={"attachment_id": str(attachment.id)},
    )
    db.add(job)
    db.commit()
    preview = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db,
        stale_before=STALE_BEFORE,
        apply=False,
        evaluated_at=EVALUATED_AT,
    )

    report = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db,
        stale_before=STALE_BEFORE,
        apply=True,
        evaluated_at=EVALUATED_AT,
        expected_count=preview.count,
        expected_fingerprint=preview.fingerprint,
        review_reason="Record the true cutover time",
        clock=lambda: APPLIED_AT,
    )

    db.refresh(job)
    assert report.applied_at == APPLIED_AT
    assert job.completed_at == APPLIED_AT
    assert job.payload["_reconciliation"] == {
        "schema_version": 1,
        "non_replayable": False,
        "reason_code": "attachment_scan_already_clean",
        "evaluated_at": EVALUATED_AT.isoformat(),
        "applied_at": APPLIED_AT.isoformat(),
        "fingerprint": preview.fingerprint,
    }
    audit_log = db.query(AuditLog).filter(AuditLog.target_id == job.id).one()
    assert audit_log.details["evaluated_at"] == EVALUATED_AT.isoformat()
    assert audit_log.details["applied_at"] == APPLIED_AT.isoformat()


def test_dry_run_uses_job_id_email_log_without_requiring_optional_source_columns(db, test_org):
    from app.services import legacy_job_reconciliation_service

    job = _legacy_job(
        job_id=WORKFLOW_JOB_ID,
        org_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={"recipient_email": "must-not-resend@example.test"},
    )
    db.add(job)
    db.flush()
    db.add(
        EmailLog(
            organization_id=test_org.id,
            job_id=job.id,
            recipient_email="must-not-resend@example.test",
            subject="Legacy workflow",
            body="<p>Provider outcome is unknown.</p>",
            status="pending",
        )
    )
    db.commit()

    report = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db,
        stale_before=STALE_BEFORE,
        apply=False,
        evaluated_at=EVALUATED_AT,
    )

    assert report.count == 1
    assert report.decisions[0].reason_code == "workflow_email_outcome_unknown"
    assert report.decisions[0].non_replayable is True


def test_review_fingerprint_changes_when_same_job_classification_changes(db, test_org):
    from app.services import legacy_job_reconciliation_service

    job = _legacy_job(
        job_id=WORKFLOW_JOB_ID,
        org_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={"recipient_email": "must-not-resend@example.test"},
    )
    db.add(job)
    db.commit()
    report_before = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db, stale_before=STALE_BEFORE, apply=False, evaluated_at=EVALUATED_AT
    )
    db.add(
        EmailLog(
            organization_id=test_org.id,
            job_id=job.id,
            recipient_email="must-not-resend@example.test",
            subject="Legacy workflow",
            body="<p>Provider outcome is now ambiguous.</p>",
            status="pending",
        )
    )
    db.commit()
    report_after = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db, stale_before=STALE_BEFORE, apply=False, evaluated_at=EVALUATED_AT
    )

    assert report_before.count == report_after.count == 1
    assert report_before.decisions[0].job_id == report_after.decisions[0].job_id
    assert report_before.decisions[0].reason_code == "workflow_email_no_local_delivery_evidence"
    assert report_after.decisions[0].reason_code == "workflow_email_outcome_unknown"
    assert report_before.fingerprint != report_after.fingerprint


def test_dry_run_completes_attachment_job_when_scan_already_finished(db, test_org):
    from app.services import legacy_job_reconciliation_service

    attachment = Attachment(
        organization_id=test_org.id,
        filename="already-scanned.pdf",
        storage_key="tests/already-scanned.pdf",
        content_type="application/pdf",
        file_size=128,
        checksum_sha256="a" * 64,
        scan_status="clean",
        scanned_at=datetime(2026, 3, 15, 21, 55, tzinfo=timezone.utc),
        quarantined=False,
    )
    db.add(attachment)
    db.flush()
    job = _legacy_job(
        job_id=ATTACHMENT_JOB_ID,
        org_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        payload={"attachment_id": str(attachment.id)},
    )
    db.add(job)
    db.commit()

    report = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db, stale_before=STALE_BEFORE, apply=False, evaluated_at=EVALUATED_AT
    )

    assert report.fingerprint == _expected_single_decision_fingerprint(
        job_id=ATTACHMENT_JOB_ID,
        organization_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        target_status=JobStatus.COMPLETED.value,
        reason_code="attachment_scan_already_clean",
        non_replayable=False,
        evidence_flags={
            "attachment_exists": True,
            "attachment_quarantined": False,
            "attachment_scan_clean": True,
            "attachment_scan_timestamp_present": True,
        },
    )
    assert report.decisions[0].target_status == JobStatus.COMPLETED.value
    assert report.decisions[0].non_replayable is False


@pytest.mark.parametrize("job_type", [JobType.GOOGLE_CALENDAR_SYNC, JobType.GOOGLE_TASKS_SYNC])
def test_dry_run_supersedes_expired_periodic_google_sync(db, test_org, job_type):
    from app.services import legacy_job_reconciliation_service

    job = _legacy_job(
        job_id=SYNC_JOB_ID,
        org_id=test_org.id,
        job_type=job_type.value,
        payload={"user_id": str(uuid4())},
    )
    db.add(job)
    db.commit()

    report = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db, stale_before=STALE_BEFORE, apply=False, evaluated_at=EVALUATED_AT
    )

    assert report.count == 1
    assert report.decisions[0].target_status == JobStatus.FAILED.value
    assert report.decisions[0].reason_code == "periodic_sync_superseded"
    assert report.decisions[0].non_replayable is True


def test_dry_run_quarantines_overdue_organization_delete_for_admin_review(db, test_org):
    from app.services import legacy_job_reconciliation_service

    test_org.deleted_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    test_org.purge_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    job = _legacy_job(
        job_id=ORG_DELETE_JOB_ID,
        org_id=test_org.id,
        job_type=JobType.ORG_DELETE.value,
        payload={"org_id": str(test_org.id)},
    )
    db.add(job)
    db.commit()

    report = legacy_job_reconciliation_service.reconcile_legacy_running_jobs(
        db, stale_before=STALE_BEFORE, apply=False, evaluated_at=EVALUATED_AT
    )

    assert report.count == 1
    assert report.decisions[0].target_status == JobStatus.FAILED.value
    assert report.decisions[0].reason_code == "organization_delete_requires_review"
    assert report.decisions[0].non_replayable is True
