from __future__ import annotations

from uuid import uuid4

import pytest

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


@pytest.mark.asyncio
async def test_attachment_handler_dispatches_remote_scan_when_configured(monkeypatch):
    attachment_id = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=uuid4(),
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(attachment_id)},
        attempts=1,
        max_attempts=3,
    )
    captured: dict[str, object] = {}

    from app.services import scan_dispatch_service

    monkeypatch.setattr(scan_dispatch_service, "remote_scan_dispatch_configured", lambda: True)

    async def _dispatch_attachment_scan_job(*, job_id, attachment_id):
        captured["job_id"] = job_id
        captured["attachment_id"] = attachment_id

    monkeypatch.setattr(
        scan_dispatch_service,
        "dispatch_attachment_scan_job",
        _dispatch_attachment_scan_job,
    )

    should_auto_complete = await attachments.process_attachment_scan(None, job)

    assert should_auto_complete is False
    assert captured == {"job_id": job.id, "attachment_id": attachment_id}


@pytest.mark.asyncio
async def test_form_submission_handler_dispatches_remote_scan_when_configured(monkeypatch):
    submission_file_id = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=uuid4(),
        job_type=JobType.FORM_SUBMISSION_FILE_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"submission_file_id": str(submission_file_id)},
        attempts=1,
        max_attempts=3,
    )
    captured: dict[str, object] = {}

    from app.services import scan_dispatch_service

    monkeypatch.setattr(scan_dispatch_service, "remote_scan_dispatch_configured", lambda: True)

    async def _dispatch_form_submission_file_scan_job(*, job_id, submission_file_id):
        captured["job_id"] = job_id
        captured["submission_file_id"] = submission_file_id

    monkeypatch.setattr(
        scan_dispatch_service,
        "dispatch_form_submission_file_scan_job",
        _dispatch_form_submission_file_scan_job,
    )

    should_auto_complete = await form_submissions.process_form_submission_file_scan(None, job)

    assert should_auto_complete is False
    assert captured == {"job_id": job.id, "submission_file_id": submission_file_id}


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
