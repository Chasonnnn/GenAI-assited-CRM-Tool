import pytest
from datetime import datetime, timedelta, timezone


@pytest.mark.asyncio
async def test_create_audit_export_requires_csrf(authed_client, db):
    """Audit export creation should require CSRF header."""
    start_date = datetime.now(timezone.utc) - timedelta(days=1)
    end_date = datetime.now(timezone.utc)
    payload = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "format": "csv",
        "redact_mode": "redacted",
    }

    # Create a client without CSRF header but with auth cookie
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.deps import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies=authed_client.cookies,
    ) as no_csrf_client:
        response = await no_csrf_client.post("/audit/exports", json=payload)
        assert response.status_code in (401, 403)

    app.dependency_overrides.clear()
