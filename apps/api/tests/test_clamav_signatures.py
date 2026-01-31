from __future__ import annotations

from botocore.exceptions import ClientError

from app.core.config import settings
from app.services import clamav_signature_service, storage_client


def test_ensure_signatures_download_only_skips_freshclam(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CLAMAV_SIGNATURES_DOWNLOAD_ONLY", True, raising=False)
    monkeypatch.setattr(settings, "CLAMAV_SIGNATURES_BUCKET", "test-bucket", raising=False)
    monkeypatch.setattr(settings, "CLAMAV_SIGNATURES_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "CLAMAV_SIGNATURES_MAX_AGE_HOURS", 0, raising=False)

    class StubClient:
        def head_object(self, Bucket, Key):  # noqa: N803 - matches boto3 signature
            raise ClientError({"Error": {"Code": "403"}}, "HeadObject")

    monkeypatch.setattr(storage_client, "get_s3_client", lambda: StubClient())

    called = {"freshclam": False}

    def _fake_freshclam():
        called["freshclam"] = True

    monkeypatch.setattr(clamav_signature_service, "_run_freshclam", _fake_freshclam)

    clamav_signature_service.ensure_signatures()

    assert called["freshclam"] is False


def test_ensure_signatures_runs_freshclam_when_allowed(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CLAMAV_SIGNATURES_DOWNLOAD_ONLY", False, raising=False)
    monkeypatch.setattr(settings, "CLAMAV_SIGNATURES_BUCKET", "test-bucket", raising=False)
    monkeypatch.setattr(settings, "CLAMAV_SIGNATURES_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "CLAMAV_SIGNATURES_MAX_AGE_HOURS", 0, raising=False)

    class StubClient:
        def head_object(self, Bucket, Key):  # noqa: N803 - matches boto3 signature
            raise ClientError({"Error": {"Code": "403"}}, "HeadObject")

    monkeypatch.setattr(storage_client, "get_s3_client", lambda: StubClient())

    called = {"freshclam": False}

    def _fake_freshclam():
        called["freshclam"] = True

    monkeypatch.setattr(clamav_signature_service, "_run_freshclam", _fake_freshclam)

    clamav_signature_service.ensure_signatures()

    assert called["freshclam"] is True
