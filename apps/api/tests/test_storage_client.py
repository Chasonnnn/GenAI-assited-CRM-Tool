from __future__ import annotations

from app.core.config import settings
from app.services import storage_client


def test_get_s3_client_uses_auto_region_for_gcs_endpoint(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_boto3_client(service_name, **kwargs):  # noqa: ANN001
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(storage_client.boto3, "client", _fake_boto3_client)
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "https://storage.googleapis.com", raising=False)
    monkeypatch.setattr(settings, "S3_REGION", "us-east-1", raising=False)
    monkeypatch.setattr(settings, "S3_URL_STYLE", "path", raising=False)

    storage_client.get_s3_client()

    kwargs = captured["kwargs"]
    assert captured["service_name"] == "s3"
    assert kwargs["region_name"] == "auto"
    assert kwargs["endpoint_url"] == "https://storage.googleapis.com"
    assert kwargs["config"].s3.get("addressing_style") == "path"


def test_get_s3_client_honors_virtual_style(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_boto3_client(service_name, **kwargs):  # noqa: ANN001
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(storage_client.boto3, "client", _fake_boto3_client)
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "https://s3.us-east-1.amazonaws.com", raising=False)
    monkeypatch.setattr(settings, "S3_REGION", "us-east-1", raising=False)
    monkeypatch.setattr(settings, "S3_URL_STYLE", "virtual", raising=False)

    storage_client.get_s3_client()

    kwargs = captured["kwargs"]
    assert captured["service_name"] == "s3"
    assert kwargs["region_name"] == "us-east-1"
    assert kwargs["config"].s3.get("addressing_style") == "virtual"


def test_get_s3_client_honors_signature_version_override(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_boto3_client(service_name, **kwargs):  # noqa: ANN001
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(storage_client.boto3, "client", _fake_boto3_client)
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "https://storage.googleapis.com", raising=False)
    monkeypatch.setattr(settings, "S3_REGION", "auto", raising=False)
    monkeypatch.setattr(settings, "S3_URL_STYLE", "path", raising=False)

    storage_client.get_s3_client(signature_version="s3")

    kwargs = captured["kwargs"]
    assert captured["service_name"] == "s3"
    assert kwargs["config"].signature_version == "s3"
