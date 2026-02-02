from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

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
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert headers["permissions-policy"] == "geolocation=(), microphone=(), camera=(), payment=()"
