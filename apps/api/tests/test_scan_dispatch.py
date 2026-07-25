from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.db.enums import JobStatus, JobType
from app.db.models import Job
from app.jobs.handlers import attachments, form_submissions


class _SessionProxy:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        return None


def test_remote_scan_payload_carries_the_exact_claim_token():
    from app.services import scan_dispatch_service

    claim_token = uuid4()
    payload = scan_dispatch_service._run_payload(
        scan_type="attachment",
        resource_id=uuid4(),
        job_id=uuid4(),
        claim_token=claim_token,
    )

    args = payload["overrides"]["containerOverrides"][0]["args"]
    assert args[-2:] == ["--claim-token", str(claim_token)]


@pytest.mark.asyncio
async def test_attachment_handler_dispatches_remote_scan_when_configured(monkeypatch):
    attachment_id = uuid4()
    claim_token = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=uuid4(),
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(attachment_id)},
        attempts=1,
        max_attempts=3,
        claim_token=claim_token,
        claimed_at=datetime.now(timezone.utc),
    )
    captured: dict[str, object] = {}

    from app.services import scan_dispatch_service

    monkeypatch.setattr(scan_dispatch_service, "remote_scan_dispatch_configured", lambda: True)

    async def _dispatch_attachment_scan_job(*, job_id, attachment_id, claim_token):
        captured["job_id"] = job_id
        captured["attachment_id"] = attachment_id
        captured["claim_token"] = claim_token

    monkeypatch.setattr(
        scan_dispatch_service,
        "dispatch_attachment_scan_job",
        _dispatch_attachment_scan_job,
    )

    should_auto_complete = await attachments.process_attachment_scan(None, job)

    assert should_auto_complete is False
    assert captured == {
        "job_id": job.id,
        "attachment_id": attachment_id,
        "claim_token": claim_token,
    }


@pytest.mark.asyncio
async def test_form_submission_handler_dispatches_remote_scan_when_configured(monkeypatch):
    submission_file_id = uuid4()
    claim_token = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=uuid4(),
        job_type=JobType.FORM_SUBMISSION_FILE_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"submission_file_id": str(submission_file_id)},
        attempts=1,
        max_attempts=3,
        claim_token=claim_token,
        claimed_at=datetime.now(timezone.utc),
    )
    captured: dict[str, object] = {}

    from app.services import scan_dispatch_service

    monkeypatch.setattr(scan_dispatch_service, "remote_scan_dispatch_configured", lambda: True)

    async def _dispatch_form_submission_file_scan_job(*, job_id, submission_file_id, claim_token):
        captured["job_id"] = job_id
        captured["submission_file_id"] = submission_file_id
        captured["claim_token"] = claim_token

    monkeypatch.setattr(
        scan_dispatch_service,
        "dispatch_form_submission_file_scan_job",
        _dispatch_form_submission_file_scan_job,
    )

    should_auto_complete = await form_submissions.process_form_submission_file_scan(None, job)

    assert should_auto_complete is False
    assert captured == {
        "job_id": job.id,
        "submission_file_id": submission_file_id,
        "claim_token": claim_token,
    }


def test_scan_job_runner_marks_job_completed(db, test_org, monkeypatch):
    from app import scan_job_runner

    attachment_id = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(attachment_id)},
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    monkeypatch.setattr(scan_job_runner, "SessionLocal", lambda: _SessionProxy(db))
    monkeypatch.setattr(scan_job_runner, "_prepare_scanner", lambda: None)
    monkeypatch.setattr(
        scan_job_runner, "scan_attachment_job", lambda resource_id: resource_id == attachment_id
    )

    exit_code = scan_job_runner.run_scan_job(
        scan_type="attachment",
        resource_id=attachment_id,
        job_id=job.id,
    )

    db.refresh(job)
    assert exit_code == 0
    assert job.status == JobStatus.COMPLETED.value


def test_scan_runner_rejects_stale_claim_before_invoking_scanner(db, test_org, monkeypatch):
    from app import scan_job_runner
    from app.services import job_service

    attachment_id = uuid4()
    current_token = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(attachment_id)},
        attempts=1,
        max_attempts=3,
        claim_token=current_token,
        claimed_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    calls = {"prepare": 0, "scan": 0}

    monkeypatch.setattr(scan_job_runner, "SessionLocal", lambda: _SessionProxy(db))
    monkeypatch.setattr(
        scan_job_runner,
        "_prepare_scanner",
        lambda: calls.__setitem__("prepare", calls["prepare"] + 1),
    )
    monkeypatch.setattr(
        scan_job_runner,
        "scan_attachment_job",
        lambda _resource_id: calls.__setitem__("scan", calls["scan"] + 1),
    )

    with pytest.raises(job_service.JobClaimLost, match="no longer current"):
        scan_job_runner.run_scan_job(
            scan_type="attachment",
            resource_id=attachment_id,
            job_id=job.id,
            claim_token=uuid4(),
        )

    db.refresh(job)
    assert calls == {"prepare": 0, "scan": 0}
    assert job.status == JobStatus.RUNNING.value
    assert job.claim_token == current_token


def test_legacy_scan_cannot_complete_after_claim_generation_changes(db, test_org, monkeypatch):
    from app import scan_job_runner
    from app.services import job_service

    attachment_id = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(attachment_id)},
        attempts=1,
        max_attempts=3,
        claim_token=None,
        claimed_at=None,
    )
    db.add(job)
    db.commit()
    newer_token = uuid4()

    def _scan_and_replace_claim(_resource_id):
        db.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(
                claim_token=newer_token,
                claimed_at=datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session=False)
        )
        db.flush()
        return True

    monkeypatch.setattr(scan_job_runner, "SessionLocal", lambda: _SessionProxy(db))
    monkeypatch.setattr(scan_job_runner, "_prepare_scanner", lambda: None)
    monkeypatch.setattr(scan_job_runner, "scan_attachment_job", _scan_and_replace_claim)

    with pytest.raises(job_service.JobClaimLost, match="no longer current"):
        scan_job_runner.run_scan_job(
            scan_type="attachment",
            resource_id=attachment_id,
            job_id=job.id,
            claim_token=None,
        )

    db.expire_all()
    current = db.query(Job).filter(Job.id == job.id).one()
    assert current.status == JobStatus.RUNNING.value
    assert current.claim_token == newer_token
    assert current.completed_at is None
