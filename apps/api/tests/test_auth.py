"""
Authentication tests - PLACEHOLDER

NOTE: Integration tests for authentication are complex because:
1. require_roles() calls get_current_session() directly, not via Depends
2. DEV_BYPASS_AUTH=True in deps.py bypasses authentication
3. Need real JWT tokens or monkeypatching for proper testing

For proper integration tests, consider:
- Mint real JWT via create_session_token() and set crm_session cookie
- Monkeypatch app.core.deps.get_current_session
- Disable DEV_BYPASS_AUTH in test environment

These tests are placeholders for future implementation.
"""
import pytest


# Placeholder - auth tests need proper JWT minting
@pytest.mark.skip(reason="Needs proper auth infrastructure with real JWT tokens")
def test_login_redirects_to_google():
    """GET /auth/login should redirect to Google OAuth."""
    pass


@pytest.mark.skip(reason="Needs DEV_BYPASS_AUTH=False in test env")
def test_protected_endpoint_requires_session():
    """Protected endpoints should require authentication."""
    pass
