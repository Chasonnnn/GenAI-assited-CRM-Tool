from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_security_headers_present():
    """Test that security headers are present in the response."""
    response = client.get("/")
    assert response.status_code == 200
    headers = response.headers

    # CSP
    assert "content-security-policy" in headers
    # Verify strictness (in test env, it should be permissive for Swagger UI)
    csp = headers["content-security-policy"]
    if settings.is_dev:
        assert "default-src 'self'" in csp
        assert "unsafe-inline" in csp
    else:
        assert "default-src 'none'" in csp

    # Other headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["cross-origin-opener-policy"] == "same-origin"
    assert headers["cross-origin-resource-policy"] == "same-origin"
    assert headers["cross-origin-embedder-policy"] == "require-corp"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert headers["permissions-policy"] == "geolocation=(), microphone=(), camera=(), payment=()"


def test_ai_studio_assets_allow_cross_origin_embedding():
    """AI Studio images are rendered by the web app from the API origin."""
    from app.main import _resource_policy_for_path

    assert (
        _resource_policy_for_path("/ai/studio/assets/ai-studio/org-id/image.png") == "cross-origin"
    )


def test_local_attachment_assets_allow_cross_origin_embedding():
    """Authenticated local attachment images render from the separate web origin."""
    from app.main import _resource_policy_for_path

    assert (
        _resource_policy_for_path(
            "/attachments/local/org-id/donor-id/attachment-id.jpg"
        )
        == "cross-origin"
    )
