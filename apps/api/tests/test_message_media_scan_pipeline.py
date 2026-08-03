"""Durable worker and dedicated-runner contracts for outbound MMS scanning."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.db.enums import JobStatus, JobType
from app.db.models import Job, MessageMediaAsset


class _SessionProxy:
    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):
        return None


def _asset(*, organization_id, scan_status="pending") -> MessageMediaAsset:
    asset_id = uuid4()
    return MessageMediaAsset(
        id=asset_id,
        organization_id=organization_id,
        storage_key=f"messaging/{organization_id}/{asset_id.hex}.gif",
        original_filename="scan.gif",
        content_type="image/gif",
        byte_size=10,
        checksum_sha256="7" * 64,
        scan_status=scan_status,
        content_classification="no_phi",
    )


async def test_remote_worker_dispatches_message_media_without_auto_completing(monkeypatch):
    from app.jobs.handlers import message_media
    from app.services import scan_dispatch_service

    asset_id = uuid4()
    claim_token = uuid4()
    dispatched = []

    async def dispatch(**kwargs):
        dispatched.append(kwargs)

    monkeypatch.setattr(scan_dispatch_service, "remote_scan_dispatch_configured", lambda: True)
    monkeypatch.setattr(scan_dispatch_service, "dispatch_message_media_scan_job", dispatch)
    job = SimpleNamespace(
        id=uuid4(),
        claim_token=claim_token,
        payload={"media_asset_id": str(asset_id)},
    )

    assert await message_media.process_message_media_scan(None, job) is False
    assert dispatched == [
        {
            "job_id": job.id,
            "media_asset_id": asset_id,
            "claim_token": claim_token,
        }
    ]


def test_disabled_scanner_marks_media_clean_only_when_async_job_runs(
    db,
    test_org,
    monkeypatch,
):
    from app.jobs import scan_attachment

    asset = _asset(organization_id=test_org.id)
    db.add(asset)
    db.commit()
    monkeypatch.setattr(scan_attachment, "SessionLocal", lambda: _SessionProxy(db))
    monkeypatch.setattr(scan_attachment.settings, "ATTACHMENT_SCAN_ENABLED", False)

    assert scan_attachment.scan_message_media_asset_job(asset.id) is True
    db.refresh(asset)
    assert asset.scan_status == "clean"
    assert asset.quarantine_reason is None


def test_dedicated_scan_runner_supports_message_media_claims(db, test_org, monkeypatch):
    from app import scan_job_runner

    asset = _asset(organization_id=test_org.id)
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type=JobType.MESSAGE_MEDIA_SCAN.value,
        status=JobStatus.RUNNING.value,
        claim_token=uuid4(),
        claimed_at=datetime.now(UTC),
        payload={"media_asset_id": str(asset.id)},
        attempts=1,
        max_attempts=3,
    )
    db.add_all([asset, job])
    db.commit()
    monkeypatch.setattr(scan_job_runner, "SessionLocal", lambda: _SessionProxy(db))
    monkeypatch.setattr(scan_job_runner, "_prepare_scanner", lambda: None)
    monkeypatch.setattr(
        scan_job_runner,
        "scan_message_media_asset_job",
        lambda resource_id: resource_id == asset.id,
    )

    exit_code = scan_job_runner.run_scan_job(
        scan_type="message_media",
        resource_id=asset.id,
        job_id=job.id,
        claim_token=job.claim_token,
    )

    db.refresh(job)
    assert exit_code == 0
    assert job.status == JobStatus.COMPLETED.value
