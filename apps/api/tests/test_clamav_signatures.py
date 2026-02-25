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


def test_upload_archive_uses_put_object_with_static_body(monkeypatch, tmp_path):
    sig_dir = tmp_path / "clamav"
    sig_dir.mkdir()
    (sig_dir / "main.cvd").write_bytes(b"main-signature")
    (sig_dir / "daily.cvd").write_bytes(b"daily-signature")

    captured: dict[str, object] = {}

    class StubClient:
        def put_object(self, **kwargs):  # noqa: ANN003 - boto style kwargs
            body = kwargs["Body"]
            assert isinstance(body, bytes)
            captured["BodyBytes"] = body
            captured["Bucket"] = kwargs["Bucket"]
            captured["Key"] = kwargs["Key"]
            captured["ContentType"] = kwargs.get("ContentType")
            captured["ContentLength"] = kwargs.get("ContentLength")

    monkeypatch.setattr(storage_client, "get_s3_client", lambda: StubClient())

    clamav_signature_service._upload_archive("test-bucket", "clamav/signatures.tar.gz", str(sig_dir))

    assert captured["Bucket"] == "test-bucket"
    assert captured["Key"] == "clamav/signatures.tar.gz"
    assert captured["ContentType"] == "application/gzip"
    assert captured["ContentLength"] == len(captured["BodyBytes"])
    assert captured["BodyBytes"]


def test_upload_archive_retries_with_auto_region_on_signature_mismatch(monkeypatch, tmp_path):
    sig_dir = tmp_path / "clamav"
    sig_dir.mkdir()
    (sig_dir / "main.cvd").write_bytes(b"main-signature")

    calls: list[str | None] = []
    captured: dict[str, object] = {}

    class FailingClient:
        def put_object(self, **_kwargs):  # noqa: ANN003 - boto style kwargs
            raise ClientError({"Error": {"Code": "SignatureDoesNotMatch"}}, "PutObject")

    class SuccessClient:
        def put_object(self, **kwargs):  # noqa: ANN003 - boto style kwargs
            calls.append("put")
            captured["Bucket"] = kwargs["Bucket"]
            captured["Key"] = kwargs["Key"]

    def _fake_client(*, region=None, endpoint_url=None, signature_version=None):  # noqa: ANN001, ARG001
        calls.append(region)
        if region == "auto":
            return SuccessClient()
        return FailingClient()

    monkeypatch.setattr(storage_client, "get_s3_client", _fake_client)

    clamav_signature_service._upload_archive_with_signature_retry(
        "test-bucket", "clamav/signatures.tar.gz", str(sig_dir)
    )

    assert calls[0] is None
    assert calls[1] == "auto"
    assert calls[-1] == "put"
    assert captured["Bucket"] == "test-bucket"
    assert captured["Key"] == "clamav/signatures.tar.gz"


def test_upload_archive_retries_with_s3_signature_after_auto_region_failure(
    monkeypatch, tmp_path
):
    sig_dir = tmp_path / "clamav"
    sig_dir.mkdir()
    (sig_dir / "main.cvd").write_bytes(b"main-signature")

    calls: list[tuple[str | None, str | None] | str] = []
    captured: dict[str, object] = {}

    class FailingClient:
        def put_object(self, **_kwargs):  # noqa: ANN003 - boto style kwargs
            raise ClientError({"Error": {"Code": "SignatureDoesNotMatch"}}, "PutObject")

    class SuccessClient:
        def put_object(self, **kwargs):  # noqa: ANN003 - boto style kwargs
            calls.append("put")
            captured["Bucket"] = kwargs["Bucket"]
            captured["Key"] = kwargs["Key"]

    def _fake_client(*, region=None, endpoint_url=None, signature_version=None):  # noqa: ANN001, ARG001
        calls.append((region, signature_version))
        if signature_version == "s3":
            return SuccessClient()
        return FailingClient()

    monkeypatch.setattr(storage_client, "get_s3_client", _fake_client)

    clamav_signature_service._upload_archive_with_signature_retry(
        "test-bucket", "clamav/signatures.tar.gz", str(sig_dir)
    )

    assert calls[0] == (None, None)
    assert calls[1] == ("auto", None)
    assert calls[2] == ("auto", "s3")
    assert calls[-1] == "put"
    assert captured["Bucket"] == "test-bucket"
    assert captured["Key"] == "clamav/signatures.tar.gz"
