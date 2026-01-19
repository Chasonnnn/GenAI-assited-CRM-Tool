from app.core.config import settings
from app.services import storage_url_service


def test_build_public_url_default(monkeypatch):
    monkeypatch.setattr(settings, "S3_PUBLIC_BASE_URL", "")
    monkeypatch.setattr(settings, "S3_URL_STYLE", "path")

    url = storage_url_service.build_public_url("my-bucket", "path/to/file.png")
    assert url == "https://s3.amazonaws.com/my-bucket/path/to/file.png"
    assert storage_url_service.extract_storage_key(url, "my-bucket") == "path/to/file.png"


def test_build_public_url_gcs_path(monkeypatch):
    monkeypatch.setattr(settings, "S3_PUBLIC_BASE_URL", "https://storage.googleapis.com")
    monkeypatch.setattr(settings, "S3_URL_STYLE", "path")

    url = storage_url_service.build_public_url("gcs-bucket", "avatars/user.png")
    assert url == "https://storage.googleapis.com/gcs-bucket/avatars/user.png"
    assert storage_url_service.extract_storage_key(url, "gcs-bucket") == "avatars/user.png"


def test_build_public_url_gcs_virtual(monkeypatch):
    monkeypatch.setattr(settings, "S3_PUBLIC_BASE_URL", "https://storage.googleapis.com")
    monkeypatch.setattr(settings, "S3_URL_STYLE", "virtual")

    url = storage_url_service.build_public_url("gcs-bucket", "logos/org.png")
    assert url == "https://gcs-bucket.storage.googleapis.com/logos/org.png"
    assert storage_url_service.extract_storage_key(url, "gcs-bucket") == "logos/org.png"
