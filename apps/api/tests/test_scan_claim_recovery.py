from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db.enums import JobStatus, JobType
from app.db.models import Attachment, Job, Organization
from app.db.session import SessionLocal


def _stale_scan_job(*, org_id, resource_id, now, attempts=1, max_attempts=3):
    from app.services import scan_dispatch_service

    return Job(
        id=uuid4(),
        organization_id=org_id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(resource_id)},
        run_at=now - timedelta(hours=1),
        attempts=attempts,
        max_attempts=max_attempts,
        claim_token=uuid4(),
        claimed_at=now - timedelta(seconds=scan_dispatch_service.scan_stale_lease_seconds() + 1),
    )


def _attachment(*, org_id, resource_id, status="pending"):
    return Attachment(
        id=resource_id,
        organization_id=org_id,
        filename="recovery.pdf",
        storage_key=f"test/{resource_id}.pdf",
        content_type="application/pdf",
        file_size=1,
        checksum_sha256="6" * 64,
        scan_status=status,
        quarantined=status != "clean",
    )


def test_stale_ambiguous_scan_claim_requeues_without_user_request(db, test_org):
    from app.services import scan_claim_recovery_service

    now = datetime.now(timezone.utc)
    resource_id = uuid4()
    job = _stale_scan_job(org_id=test_org.id, resource_id=resource_id, now=now)
    db.add_all([_attachment(org_id=test_org.id, resource_id=resource_id), job])
    db.commit()

    report = scan_claim_recovery_service.recover_stale_remote_scan_claims(db, now=now)

    db.refresh(job)
    assert report.requeued == 1
    assert report.completed == 0
    assert report.quarantined == 0
    assert job.status == JobStatus.PENDING.value
    assert job.claim_token is None
    assert job.claimed_at is None
    assert "stale remote scan claim" in (job.last_error or "").lower()


def test_terminal_resource_completes_stale_scan_claim(db, test_org):
    from app.services import scan_claim_recovery_service

    now = datetime.now(timezone.utc)
    resource_id = uuid4()
    job = _stale_scan_job(org_id=test_org.id, resource_id=resource_id, now=now)
    db.add_all(
        [
            _attachment(org_id=test_org.id, resource_id=resource_id, status="clean"),
            job,
        ]
    )
    db.commit()

    report = scan_claim_recovery_service.recover_stale_remote_scan_claims(db, now=now)

    db.refresh(job)
    assert report.completed == 1
    assert report.requeued == 0
    assert job.status == JobStatus.COMPLETED.value
    assert job.claim_token is None
    assert job.claimed_at is None


def test_missing_scan_resource_is_quarantined_without_handler_call(db, test_org):
    from app.services import scan_claim_recovery_service

    now = datetime.now(timezone.utc)
    job = _stale_scan_job(org_id=test_org.id, resource_id=uuid4(), now=now)
    db.add(job)
    db.commit()

    report = scan_claim_recovery_service.recover_stale_remote_scan_claims(db, now=now)

    db.refresh(job)
    assert report.quarantined == 1
    assert job.status == JobStatus.FAILED.value
    assert job.payload["_claim_recovery"]["non_replayable"] is True


def test_active_locked_scan_claim_is_not_recovered(db_engine):
    from app.services import scan_claim_recovery_service

    now = datetime.now(timezone.utc)
    org_id = uuid4()
    resource_id = uuid4()
    setup = SessionLocal()
    setup.add(
        Organization(id=org_id, name="Active scan recovery", slug=f"active-scan-{org_id.hex}")
    )
    setup.add(_attachment(org_id=org_id, resource_id=resource_id))
    job = _stale_scan_job(org_id=org_id, resource_id=resource_id, now=now)
    setup.add(job)
    setup.commit()
    job_id = job.id
    setup.close()

    holder = SessionLocal()
    reaper = SessionLocal()
    try:
        holder.execute(select(Job).where(Job.id == job_id).with_for_update()).scalar_one()

        report = scan_claim_recovery_service.recover_stale_remote_scan_claims(
            reaper,
            now=now,
        )

        assert report.total == 0
        reaper.expire_all()
        current = reaper.query(Job).filter(Job.id == job_id).one()
        assert current.status == JobStatus.RUNNING.value
        assert current.claim_token is not None
    finally:
        holder.rollback()
        reaper.rollback()
        cleanup = SessionLocal()
        cleanup.query(Organization).filter(Organization.id == org_id).delete()
        cleanup.commit()
        cleanup.close()
        holder.close()
        reaper.close()
