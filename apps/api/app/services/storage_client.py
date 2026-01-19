"""Helpers for creating storage clients."""

from __future__ import annotations

import boto3
from botocore.client import BaseClient

from app.core.config import settings


def _normalize_endpoint(endpoint_url: str | None) -> str | None:
    if endpoint_url:
        return endpoint_url.rstrip("/")
    return None


def get_s3_client(
    *,
    region: str | None = None,
    endpoint_url: str | None = None,
) -> BaseClient:
    """Return a configured S3 client (supports S3-compatible endpoints)."""
    return boto3.client(
        "s3",
        region_name=region or settings.S3_REGION or None,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        endpoint_url=_normalize_endpoint(endpoint_url or settings.S3_ENDPOINT_URL),
    )


def get_export_s3_client() -> BaseClient:
    """Return a configured S3 client for export storage."""
    endpoint_url = settings.EXPORT_S3_ENDPOINT_URL or settings.S3_ENDPOINT_URL
    region = settings.EXPORT_S3_REGION or settings.S3_REGION
    return get_s3_client(region=region, endpoint_url=endpoint_url)
