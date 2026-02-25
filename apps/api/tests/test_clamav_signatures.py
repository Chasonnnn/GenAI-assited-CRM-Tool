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


def test_upload_archive_uses_put_object(monkeypatch, tmp_path):
    sig_dir = tmp_path / "clamav"
    sig_dir.mkdir()
    (sig_dir / "main.cvd").write_bytes(b"main-signature")
    (sig_dir / "daily.cvd").write_bytes(b"daily-signature")

    captured: dict[str, object] = {}

    class StubClient:
        def put_object(self, **kwargs):  # noqa: ANN003 - boto style kwargs
            body = kwargs["Body"]
            captured["BodyBytes"] = body.read()
            captured["Bucket"] = kwargs["Bucket"]
            captured["Key"] = kwargs["Key"]
            captured["ContentType"] = kwargs.get("ContentType")

    monkeypatch.setattr(storage_client, "get_s3_client", lambda: StubClient())

    clamav_signature_service._upload_archive("test-bucket", "clamav/signatures.tar.gz", str(sig_dir))

    assert captured["Bucket"] == "test-bucket"
    assert captured["Key"] == "clamav/signatures.tar.gz"
    assert captured["ContentType"] == "application/gzip"
    assert captured["BodyBytes"]
