"""Helpers for creating storage clients."""

from __future__ import annotations

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from urllib.parse import urlparse

from app.core.config import settings


def _normalize_endpoint(endpoint_url: str | None) -> str | None:
    if endpoint_url:
        return endpoint_url.rstrip("/")
    return None


def _is_gcs_compat_endpoint(endpoint_url: str | None) -> bool:
    if not endpoint_url:
        return False
    hostname = (urlparse(endpoint_url).hostname or "").lower()
    return hostname == "storage.googleapis.com" or hostname.endswith(".storage.googleapis.com")


def _resolve_region(region: str | None, endpoint_url: str | None) -> str | None:
    selected = region or settings.S3_REGION or None
    if _is_gcs_compat_endpoint(endpoint_url) and (selected is None or selected == "us-east-1"):
        # GCS XML API expects region "auto" for SigV4 signing.
        return "auto"
    return selected


def _build_s3_config() -> Config | None:
    style = (settings.S3_URL_STYLE or "").strip().lower()
    if style in {"path", "virtual"}:
        return Config(s3={"addressing_style": style})
    return None


def get_s3_client(
    *,
    region: str | None = None,
    endpoint_url: str | None = None,
) -> BaseClient:
    """Return a configured S3 client (supports S3-compatible endpoints)."""
    normalized_endpoint = _normalize_endpoint(endpoint_url or settings.S3_ENDPOINT_URL)
    return boto3.client(
        "s3",
        region_name=_resolve_region(region, normalized_endpoint),
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        endpoint_url=normalized_endpoint,
        config=_build_s3_config(),
    )


def get_export_s3_client() -> BaseClient:
    """Return a configured S3 client for export storage."""
    endpoint_url = settings.EXPORT_S3_ENDPOINT_URL or settings.S3_ENDPOINT_URL
    region = settings.EXPORT_S3_REGION or settings.S3_REGION
    return get_s3_client(region=region, endpoint_url=endpoint_url)
