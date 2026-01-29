from app.core.config import settings
from app.services import media_service


def test_get_signed_media_url_none():
    assert media_service.get_signed_media_url(None) is None


def test_get_signed_media_url_non_s3():
    url = "https://example.com/avatar.png"
    assert media_service.get_signed_media_url(url) == url


def test_get_signed_media_url_local():
    url = "/static/logos/org.png"
    expected = (
        f"{settings.API_BASE_URL.rstrip('/')}"
        "/settings/organization/signature/logo/local/logos/org.png"
    )
    assert media_service.get_signed_media_url(url) == expected


def test_get_signed_media_url_s3_virtual(monkeypatch):
    from app.services import attachment_service
    from app.core.config import settings

    monkeypatch.setattr(
        attachment_service,
        "generate_signed_url",
        lambda key, expires_in_seconds=None: f"signed:{key}",
    )
    monkeypatch.setattr(settings, "S3_BUCKET", "crm-attachments", raising=False)

    url = "https://crm-attachments.s3.amazonaws.com/avatars/org/user.png"
    assert media_service.get_signed_media_url(url) == "signed:avatars/org/user.png"


def test_get_signed_media_url_s3_path_style(monkeypatch):
    from app.services import attachment_service
    from app.core.config import settings

    monkeypatch.setattr(
        attachment_service,
        "generate_signed_url",
        lambda key, expires_in_seconds=None: f"signed:{key}",
    )
    monkeypatch.setattr(settings, "S3_BUCKET", "crm-attachments", raising=False)

    url = "https://s3.amazonaws.com/crm-attachments/logos/org/logo.png"
    assert media_service.get_signed_media_url(url) == "signed:logos/org/logo.png"


def test_get_signed_media_url_s3_regional(monkeypatch):
    from app.services import attachment_service
    from app.core.config import settings

    monkeypatch.setattr(
        attachment_service,
        "generate_signed_url",
        lambda key, expires_in_seconds=None: f"signed:{key}",
    )
    monkeypatch.setattr(settings, "S3_BUCKET", "crm-attachments", raising=False)

    url = "https://crm-attachments.s3.us-east-1.amazonaws.com/avatars/a.png?X-Amz-Signature=abc"
    assert media_service.get_signed_media_url(url) == "signed:avatars/a.png"


def test_get_signed_media_url_different_bucket():
    url = "https://other-bucket.s3.amazonaws.com/avatars/a.png"
    assert media_service.get_signed_media_url(url) == url
