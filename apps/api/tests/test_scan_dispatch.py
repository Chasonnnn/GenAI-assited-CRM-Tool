from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import update

from app.db.enums import JobStatus, JobType
from app.db.models import Attachment, Job, Organization
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


def test_scan_stale_lease_exceeds_remote_execution_timeout(monkeypatch):
    from app.core.config import settings
    from app.services import scan_dispatch_service

    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_STALE_RUNNING_SECONDS", 1)

    assert (
        scan_dispatch_service.scan_stale_lease_seconds()
        > scan_dispatch_service.SCAN_EXECUTION_TIMEOUT_SECONDS
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["status", "transport"])
async def test_async_scan_dispatch_posts_run_only_once_on_ambiguous_failure(
    monkeypatch,
    failure_kind,
):
    from app.services import scan_dispatch_service

    calls = 0

    class _AmbiguousClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            nonlocal calls
            calls += 1
            request = httpx.Request("POST", url)
            if failure_kind == "transport":
                raise httpx.ReadTimeout("outcome unknown", request=request)
            return httpx.Response(503, request=request)

    monkeypatch.setattr(scan_dispatch_service, "_access_token", lambda: "token")
    monkeypatch.setattr(scan_dispatch_service, "_run_job_url", lambda: "https://run.test/jobs:run")
    monkeypatch.setattr(scan_dispatch_service.httpx, "AsyncClient", _AmbiguousClient)

    with pytest.raises(scan_dispatch_service.ScanDispatchAmbiguousError):
        await scan_dispatch_service._dispatch_scan_job(
            scan_type="attachment",
            resource_id=uuid4(),
            job_id=uuid4(),
            claim_token=uuid4(),
        )

    assert calls == 1


@pytest.mark.parametrize("failure_kind", ["status", "transport"])
def test_sync_scan_dispatch_posts_run_only_once_on_ambiguous_failure(
    monkeypatch,
    failure_kind,
):
    from app.services import scan_dispatch_service

    calls = 0

    class _AmbiguousClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, *, headers, json):
            nonlocal calls
            calls += 1
            request = httpx.Request("POST", url)
            if failure_kind == "transport":
                raise httpx.ReadTimeout("outcome unknown", request=request)
            return httpx.Response(503, request=request)

    monkeypatch.setattr(scan_dispatch_service, "_access_token", lambda: "token")
    monkeypatch.setattr(scan_dispatch_service, "_run_job_url", lambda: "https://run.test/jobs:run")
    monkeypatch.setattr(scan_dispatch_service.httpx, "Client", _AmbiguousClient)

    with pytest.raises(scan_dispatch_service.ScanDispatchAmbiguousError):
        scan_dispatch_service._dispatch_scan_job_sync(
            scan_type="attachment",
            resource_id=uuid4(),
            job_id=uuid4(),
            claim_token=uuid4(),
        )

    assert calls == 1


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
async def test_attachment_handler_keeps_claim_on_ambiguous_dispatch(monkeypatch):
    from app.services import scan_dispatch_service

    job = Job(
        id=uuid4(),
        organization_id=uuid4(),
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(uuid4())},
        attempts=1,
        max_attempts=3,
        claim_token=uuid4(),
        claimed_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(scan_dispatch_service, "remote_scan_dispatch_configured", lambda: True)

    async def _ambiguous_dispatch(**_kwargs):
        raise scan_dispatch_service.ScanDispatchAmbiguousError("outcome unknown")

    monkeypatch.setattr(
        scan_dispatch_service,
        "dispatch_attachment_scan_job",
        _ambiguous_dispatch,
    )

    assert await attachments.process_attachment_scan(None, job) is False


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


@pytest.mark.asyncio
async def test_form_submission_handler_keeps_claim_on_ambiguous_dispatch(monkeypatch):
    from app.services import scan_dispatch_service

    job = Job(
        id=uuid4(),
        organization_id=uuid4(),
        job_type=JobType.FORM_SUBMISSION_FILE_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"submission_file_id": str(uuid4())},
        attempts=1,
        max_attempts=3,
        claim_token=uuid4(),
        claimed_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(scan_dispatch_service, "remote_scan_dispatch_configured", lambda: True)

    async def _ambiguous_dispatch(**_kwargs):
        raise scan_dispatch_service.ScanDispatchAmbiguousError("outcome unknown")

    monkeypatch.setattr(
        scan_dispatch_service,
        "dispatch_form_submission_file_scan_job",
        _ambiguous_dispatch,
    )

    assert await form_submissions.process_form_submission_file_scan(None, job) is False


def test_scan_job_runner_marks_job_completed(db, test_org, monkeypatch):
    from app import scan_job_runner

    attachment_id = uuid4()
    attachment = Attachment(
        id=attachment_id,
        organization_id=test_org.id,
        filename="scan.pdf",
        storage_key="test/scan.pdf",
        content_type="application/pdf",
        file_size=1,
        checksum_sha256="3" * 64,
        scan_status="pending",
        quarantined=True,
    )
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        claim_token=uuid4(),
        claimed_at=datetime.now(timezone.utc),
        payload={"attachment_id": str(attachment_id)},
        attempts=1,
        max_attempts=3,
    )
    db.add_all([attachment, job])
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
        claim_token=job.claim_token,
    )

    db.refresh(job)
    assert exit_code == 0
    assert job.status == JobStatus.COMPLETED.value


def test_terminal_scan_resource_completes_job_without_rescan(db, test_org, monkeypatch):
    from app import scan_job_runner

    attachment = Attachment(
        id=uuid4(),
        organization_id=test_org.id,
        filename="already-scanned.pdf",
        storage_key="test/already-scanned.pdf",
        content_type="application/pdf",
        file_size=1,
        checksum_sha256="0" * 64,
        scan_status="clean",
        quarantined=False,
    )
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(attachment.id)},
        attempts=1,
        max_attempts=3,
        claim_token=uuid4(),
        claimed_at=datetime.now(timezone.utc),
    )
    db.add_all([attachment, job])
    db.commit()
    calls = {"scan": 0}

    monkeypatch.setattr(scan_job_runner, "SessionLocal", lambda: _SessionProxy(db))
    monkeypatch.setattr(
        scan_job_runner,
        "_prepare_scanner",
        lambda: pytest.fail("terminal resources must not require scanner startup"),
    )
    monkeypatch.setattr(
        scan_job_runner,
        "scan_attachment_job",
        lambda _resource_id: calls.__setitem__("scan", calls["scan"] + 1),
    )

    exit_code = scan_job_runner.run_scan_job(
        scan_type="attachment",
        resource_id=attachment.id,
        job_id=job.id,
        claim_token=job.claim_token,
    )

    db.refresh(job)
    assert exit_code == 0
    assert calls["scan"] == 0
    assert job.status == JobStatus.COMPLETED.value


def test_scan_runner_rejects_resource_owned_by_another_organization(db, test_org, monkeypatch):
    from app import scan_job_runner

    other_org = Organization(
        id=uuid4(),
        name="Other scan organization",
        slug=f"other-scan-org-{uuid4().hex}",
    )
    attachment = Attachment(
        id=uuid4(),
        organization_id=other_org.id,
        filename="cross-org.pdf",
        storage_key="test/cross-org.pdf",
        content_type="application/pdf",
        file_size=1,
        checksum_sha256="1" * 64,
        scan_status="pending",
        quarantined=True,
    )
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(attachment.id)},
        attempts=1,
        max_attempts=1,
        claim_token=uuid4(),
        claimed_at=datetime.now(timezone.utc),
    )
    db.add_all([other_org, attachment, job])
    db.commit()
    calls = {"scan": 0}

    monkeypatch.setattr(scan_job_runner, "SessionLocal", lambda: _SessionProxy(db))
    monkeypatch.setattr(scan_job_runner, "_prepare_scanner", lambda: None)
    monkeypatch.setattr(
        scan_job_runner,
        "scan_attachment_job",
        lambda _resource_id: calls.__setitem__("scan", calls["scan"] + 1),
    )

    exit_code = scan_job_runner.run_scan_job(
        scan_type="attachment",
        resource_id=attachment.id,
        job_id=job.id,
        claim_token=job.claim_token,
    )

    db.refresh(job)
    assert exit_code == 1
    assert calls["scan"] == 0
    assert job.status == JobStatus.FAILED.value
    assert "organization" in (job.last_error or "").lower()


def test_two_scan_executions_with_same_token_invoke_scanner_once(db_engine, monkeypatch):
    from app import scan_job_runner
    from app.db.session import SessionLocal
    from app.services import job_service

    org_id = uuid4()
    job_id = uuid4()
    resource_id = uuid4()
    claim_token = uuid4()
    setup = SessionLocal()
    setup.add(Organization(id=org_id, name="Scan lock test", slug=f"scan-lock-{org_id.hex}"))
    setup.add(
        Attachment(
            id=resource_id,
            organization_id=org_id,
            filename="same-claim.pdf",
            storage_key="test/same-claim.pdf",
            content_type="application/pdf",
            file_size=1,
            checksum_sha256="4" * 64,
            scan_status="pending",
            quarantined=True,
        )
    )
    setup.add(
        Job(
            id=job_id,
            organization_id=org_id,
            job_type=JobType.ATTACHMENT_SCAN.value,
            status=JobStatus.RUNNING.value,
            payload={"attachment_id": str(resource_id)},
            attempts=1,
            max_attempts=3,
            claim_token=claim_token,
            claimed_at=datetime.now(timezone.utc),
        )
    )
    setup.commit()
    setup.close()

    scan_started = threading.Event()
    release_scan = threading.Event()
    calls = 0
    calls_lock = threading.Lock()

    def _scan_once(_resource_id):
        nonlocal calls
        with calls_lock:
            calls += 1
        scan_started.set()
        assert release_scan.wait(timeout=3)
        return True

    monkeypatch.setattr(scan_job_runner, "_prepare_scanner", lambda: None)
    monkeypatch.setattr(scan_job_runner, "scan_attachment_job", _scan_once)

    def _run():
        return scan_job_runner.run_scan_job(
            scan_type="attachment",
            resource_id=resource_id,
            job_id=job_id,
            claim_token=claim_token,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(_run)
            assert scan_started.wait(timeout=3)
            second = pool.submit(_run)
            time.sleep(0.2)
            assert calls == 1
            release_scan.set()
            assert first.result(timeout=3) == 0
            with pytest.raises(job_service.JobClaimLost):
                second.result(timeout=3)
    finally:
        cleanup = SessionLocal()
        cleanup.query(Organization).filter(Organization.id == org_id).delete()
        cleanup.commit()
        cleanup.close()


def test_two_scan_jobs_for_same_resource_invoke_scanner_once(db_engine, monkeypatch):
    from app import scan_job_runner
    from app.db.session import SessionLocal

    org_id = uuid4()
    resource_id = uuid4()
    job_ids = [uuid4(), uuid4()]
    claim_tokens = [uuid4(), uuid4()]
    setup = SessionLocal()
    setup.add(
        Organization(id=org_id, name="Scan resource lock", slug=f"scan-resource-{org_id.hex}")
    )
    setup.add(
        Attachment(
            id=resource_id,
            organization_id=org_id,
            filename="resource-lock.pdf",
            storage_key="test/resource-lock.pdf",
            content_type="application/pdf",
            file_size=1,
            checksum_sha256="2" * 64,
            scan_status="pending",
            quarantined=True,
        )
    )
    setup.add_all(
        [
            Job(
                id=job_id,
                organization_id=org_id,
                job_type=JobType.ATTACHMENT_SCAN.value,
                status=JobStatus.RUNNING.value,
                payload={"attachment_id": str(resource_id)},
                attempts=1,
                max_attempts=3,
                claim_token=claim_token,
                claimed_at=datetime.now(timezone.utc),
            )
            for job_id, claim_token in zip(job_ids, claim_tokens, strict=True)
        ]
    )
    setup.commit()
    setup.close()

    scan_started = threading.Event()
    release_scan = threading.Event()
    calls = 0
    calls_lock = threading.Lock()

    def _scan_once(_resource_id):
        nonlocal calls
        with calls_lock:
            calls += 1
        scan_started.set()
        assert release_scan.wait(timeout=3)
        update_db = SessionLocal()
        update_db.query(Attachment).filter(Attachment.id == resource_id).update(
            {"scan_status": "clean", "quarantined": False}
        )
        update_db.commit()
        update_db.close()
        return True

    monkeypatch.setattr(scan_job_runner, "_prepare_scanner", lambda: None)
    monkeypatch.setattr(scan_job_runner, "scan_attachment_job", _scan_once)

    def _run(index):
        return scan_job_runner.run_scan_job(
            scan_type="attachment",
            resource_id=resource_id,
            job_id=job_ids[index],
            claim_token=claim_tokens[index],
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(_run, 0)
            assert scan_started.wait(timeout=3)
            second = pool.submit(_run, 1)
            time.sleep(0.2)
            assert calls == 1
            release_scan.set()
            assert first.result(timeout=3) == 0
            assert second.result(timeout=3) == 0

        verify = SessionLocal()
        statuses = dict(verify.query(Job.id, Job.status).filter(Job.id.in_(job_ids)).all())
        verify.close()
        assert statuses == {job_id: JobStatus.COMPLETED.value for job_id in job_ids}
        assert calls == 1
    finally:
        cleanup = SessionLocal()
        cleanup.query(Organization).filter(Organization.id == org_id).delete()
        cleanup.commit()
        cleanup.close()


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
    attachment = Attachment(
        id=attachment_id,
        organization_id=test_org.id,
        filename="legacy-claim.pdf",
        storage_key="test/legacy-claim.pdf",
        content_type="application/pdf",
        file_size=1,
        checksum_sha256="5" * 64,
        scan_status="pending",
        quarantined=True,
    )
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
    db.add_all([attachment, job])
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
