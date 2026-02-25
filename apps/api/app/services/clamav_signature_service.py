"""Utilities for syncing ClamAV signature databases via S3-compatible storage."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess  # nosec B404
import tarfile
import tempfile
from datetime import datetime, timezone

from botocore.exceptions import ClientError

from app.core.config import settings
from app.services import storage_client


logger = logging.getLogger(__name__)

SIGNATURE_FILES = (
    "main.cvd",
    "daily.cvd",
    "bytecode.cvd",
    "main.cld",
    "daily.cld",
    "bytecode.cld",
)
ARCHIVE_NAME = "signatures.tar.gz"


def _signature_dir() -> str:
    return settings.CLAMAV_SIGNATURES_DIR or "/var/lib/clamav"


def _signature_bucket() -> str:
    return settings.CLAMAV_SIGNATURES_BUCKET or settings.S3_BUCKET or ""


def _signature_prefix() -> str:
    return settings.CLAMAV_SIGNATURES_PREFIX.strip("/")


def _archive_key() -> str:
    prefix = _signature_prefix()
    return f"{prefix}/{ARCHIVE_NAME}" if prefix else ARCHIVE_NAME


def _local_signature_files(sig_dir: str) -> list[str]:
    files: list[str] = []
    for name in SIGNATURE_FILES:
        path = os.path.join(sig_dir, name)
        if os.path.exists(path):
            files.append(path)
    return files


def _local_latest_mtime(sig_dir: str) -> float | None:
    files = _local_signature_files(sig_dir)
    if not files:
        return None
    return max(os.path.getmtime(path) for path in files)


def _safe_extract(tar: tarfile.TarFile, path: str) -> None:
    abs_path = os.path.abspath(path)
    members = tar.getmembers()
    for member in members:
        if member.islnk() or member.issym():
            raise RuntimeError("Invalid signature archive contents")
        if not (member.isdir() or member.isreg()):
            raise RuntimeError("Invalid signature archive contents")
        member_path = os.path.abspath(os.path.join(path, member.name))
        if not member_path.startswith(abs_path + os.sep):
            raise RuntimeError("Invalid signature archive contents")
    for member in members:
        tar.extract(member, path)


def _run_freshclam() -> None:
    freshclam = shutil.which("freshclam")
    if not freshclam:
        raise RuntimeError("freshclam not found in PATH")
    subprocess.run([freshclam, "--quiet"], check=True, timeout=180)  # nosec B603


def _download_archive(bucket: str, key: str, sig_dir: str) -> bool:
    client = storage_client.get_s3_client()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = os.path.join(tmpdir, ARCHIVE_NAME)
            client.download_file(bucket, key, archive_path)
            with tarfile.open(archive_path, "r:gz") as tar:
                _safe_extract(tar, sig_dir)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404"}:
            return False
        logger.warning("ClamAV signature download failed: %s", exc)
        return False


def _upload_archive(bucket: str, key: str, sig_dir: str) -> None:
    files = _local_signature_files(sig_dir)
    if not files:
        logger.warning("No ClamAV signature files found to upload")
        return

    client = storage_client.get_s3_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, ARCHIVE_NAME)
        with tarfile.open(archive_path, "w:gz") as tar:
            for path in files:
                tar.add(path, arcname=os.path.basename(path))
        # Send a static body with explicit length to avoid streaming/chunked
        # signature mismatches on some S3-compatible endpoints.
        with open(archive_path, "rb") as archive_file:
            archive_bytes = archive_file.read()
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=archive_bytes,
            ContentLength=len(archive_bytes),
            ContentType="application/gzip",
        )


def _upload_archive_with_signature_retry(bucket: str, key: str, sig_dir: str) -> None:
    try:
        _upload_archive(bucket, key, sig_dir)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code != "SignatureDoesNotMatch":
            raise
        logger.warning(
            "ClamAV signature upload failed with SignatureDoesNotMatch; retrying with region=auto"
        )
        try:
            _upload_archive_with_region(bucket, key, sig_dir, region="auto")
            return
        except ClientError as retry_exc:
            retry_code = retry_exc.response.get("Error", {}).get("Code")
            if retry_code != "SignatureDoesNotMatch":
                raise
            logger.warning(
                "ClamAV signature upload still failed with region=auto; retrying with signature_version=s3"
            )
            _upload_archive_with_region_and_signature(
                bucket,
                key,
                sig_dir,
                region="auto",
                signature_version="s3",
            )


def _upload_archive_with_region(bucket: str, key: str, sig_dir: str, region: str) -> None:
    files = _local_signature_files(sig_dir)
    if not files:
        logger.warning("No ClamAV signature files found to upload")
        return

    client = storage_client.get_s3_client(region=region)
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, ARCHIVE_NAME)
        with tarfile.open(archive_path, "w:gz") as tar:
            for path in files:
                tar.add(path, arcname=os.path.basename(path))
        with open(archive_path, "rb") as archive_file:
            archive_bytes = archive_file.read()
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=archive_bytes,
            ContentLength=len(archive_bytes),
            ContentType="application/gzip",
        )


def _upload_archive_with_region_and_signature(
    bucket: str,
    key: str,
    sig_dir: str,
    *,
    region: str,
    signature_version: str,
) -> None:
    files = _local_signature_files(sig_dir)
    if not files:
        logger.warning("No ClamAV signature files found to upload")
        return

    client = storage_client.get_s3_client(region=region, signature_version=signature_version)
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, ARCHIVE_NAME)
        with tarfile.open(archive_path, "w:gz") as tar:
            for path in files:
                tar.add(path, arcname=os.path.basename(path))
        with open(archive_path, "rb") as archive_file:
            archive_bytes = archive_file.read()
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=archive_bytes,
            ContentLength=len(archive_bytes),
            ContentType="application/gzip",
        )


def ensure_signatures(max_age_hours: int | None = None) -> None:
    """Ensure ClamAV signatures exist and are reasonably fresh."""
    sig_dir = _signature_dir()
    os.makedirs(sig_dir, exist_ok=True)

    bucket = _signature_bucket()
    key = _archive_key()
    max_age = (
        max_age_hours if max_age_hours is not None else settings.CLAMAV_SIGNATURES_MAX_AGE_HOURS
    )

    local_mtime = _local_latest_mtime(sig_dir)
    local_dt = (
        datetime.fromtimestamp(local_mtime, tz=timezone.utc) if local_mtime is not None else None
    )

    if bucket:
        client = storage_client.get_s3_client()
        try:
            head = client.head_object(Bucket=bucket, Key=key)
            remote_dt = head.get("LastModified")
            if remote_dt and (local_dt is None or remote_dt > local_dt):
                if _download_archive(bucket, key, sig_dir):
                    logger.info("ClamAV signatures synced from %s/%s", bucket, key)
                    return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in {"NoSuchKey", "404"}:
                logger.warning("ClamAV signature metadata check failed: %s", exc)

    age_hours: float | None = None
    if local_dt is not None and max_age > 0:
        age_hours = (datetime.now(timezone.utc) - local_dt).total_seconds() / 3600
        if age_hours <= max_age:
            return

    if settings.CLAMAV_SIGNATURES_DOWNLOAD_ONLY:
        if not bucket:
            logger.warning("CLAMAV_SIGNATURES_DOWNLOAD_ONLY is enabled but no bucket is configured")
        elif local_dt is None:
            logger.warning("ClamAV signatures missing after download attempt; skipping refresh")
        elif age_hours is not None and max_age > 0:
            logger.warning("ClamAV signatures are older than %s hours; skipping refresh", max_age)
        else:
            logger.warning("ClamAV signatures stale; skipping refresh")
        return

    logger.info("Refreshing ClamAV signatures via freshclam")
    _run_freshclam()

    if bucket:
        try:
            _upload_archive(bucket, key, sig_dir)
            logger.info("Uploaded ClamAV signatures to %s/%s", bucket, key)
        except Exception as exc:  # noqa: BLE001 - best-effort cache upload
            logger.warning("Failed to upload ClamAV signatures: %s", exc)


def update_signatures() -> None:
    """Force a signature refresh and upload the archive."""
    sig_dir = _signature_dir()
    os.makedirs(sig_dir, exist_ok=True)

    logger.info("Updating ClamAV signatures via freshclam")
    _run_freshclam()

    bucket = _signature_bucket()
    if not bucket:
        logger.warning("CLAMAV_SIGNATURES_BUCKET/S3_BUCKET not set; skipping upload")
        return

    key = _archive_key()
    _upload_archive_with_signature_retry(bucket, key, sig_dir)
    logger.info("Uploaded ClamAV signatures to %s/%s", bucket, key)
