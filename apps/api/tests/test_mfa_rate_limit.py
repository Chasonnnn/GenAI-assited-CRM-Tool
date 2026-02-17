
import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.deps import get_db, get_current_session, require_csrf_header
from app.schemas.auth import UserSession
from app.db.enums import Role
from uuid import uuid4
from fastapi import Request

@pytest.mark.asyncio
async def test_mfa_verify_rate_limit():
    """Test that MFA verification is rate limited."""

    # Mock dependencies to avoid DB requirement
    def override_get_db():
        yield MagicMock()

    def override_get_current_session():
        return UserSession(
            user_id=uuid4(),
            org_id=uuid4(),
            role=Role.DEVELOPER,
            email="test@example.com",
            display_name="Test User",
            mfa_verified=False,
            mfa_required=True,
            token_hash="hash"
        )

    def override_require_csrf_header(request: Request):
        pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_session] = override_get_current_session
    app.dependency_overrides[require_csrf_header] = override_require_csrf_header

    # Use a dummy client to trigger requests
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        limit_hit = False
        # Limit is 5 per minute. 6th request should fail.
        for i in range(10):
            response = await client.post(
                "/mfa/verify",
                json={"code": "123456"},
                headers={"X-Forwarded-For": "1.2.3.4"}
            )
            if response.status_code == 429:
                limit_hit = True
                break

        assert limit_hit, "Rate limit was not hit after 10 requests"

    app.dependency_overrides.clear()
