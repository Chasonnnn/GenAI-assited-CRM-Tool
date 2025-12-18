"""
Pipeline tests - PLACEHOLDER

NOTE: Integration tests for pipelines are complex because:
1. Auth dependency override won't work with require_roles()
2. DB transaction fixture gets committed by app code
3. Need real JWT tokens or proper monkeypatching

For proper integration tests, consider:
- Mint real JWT via create_session_token()
- Use nested transaction/savepoint pattern for DB fixtures
- Add X-Requested-With header for CSRF

These tests are placeholders for future implementation.
"""
import pytest


@pytest.mark.skip(reason="Needs proper auth/DB infrastructure")
def test_create_pipeline():
    """Create a pipeline should return 201 with version=1."""
    pass


@pytest.mark.skip(reason="Needs proper auth/DB infrastructure")
def test_update_pipeline_increments_version():
    """Updating a pipeline should increment current_version."""
    pass


@pytest.mark.skip(reason="Needs proper auth/DB infrastructure")
def test_update_pipeline_version_conflict():
    """Updating with wrong expected_version should return 409."""
    pass
