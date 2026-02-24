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


@pytest.mark.asyncio
async def test_download_audit_export_commits_audit_log(authed_client, db, test_auth, monkeypatch):
    from app.core.config import settings
    from app.db.enums import AuditEventType
    from app.db.models import AuditLog, ExportJob
    from app.services import compliance_service

    original_storage_backend = settings.EXPORT_STORAGE_BACKEND
    settings.EXPORT_STORAGE_BACKEND = "s3"

    try:
        job = ExportJob(
            organization_id=test_auth.org.id,
            created_by_user_id=test_auth.user.id,
            status=compliance_service.EXPORT_STATUS_COMPLETED,
            export_type="audit",
            format="csv",
            redact_mode="redacted",
            date_range_start=datetime.now(timezone.utc) - timedelta(days=1),
            date_range_end=datetime.now(timezone.utc),
            file_path="org/test.csv",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        monkeypatch.setattr(
            compliance_service,
            "generate_s3_download_url",
            lambda _file_path: "https://example.com/download.csv",
        )

        response = await authed_client.get(f"/audit/exports/{job.id}/download", follow_redirects=False)
        assert response.status_code == 307

        event = (
            db.query(AuditLog)
            .filter(
                AuditLog.organization_id == test_auth.org.id,
                AuditLog.event_type == AuditEventType.COMPLIANCE_EXPORT_DOWNLOADED.value,
                AuditLog.target_id == job.id,
                AuditLog.actor_user_id == test_auth.user.id,
            )
            .first()
        )
        assert event is not None
    finally:
        settings.EXPORT_STORAGE_BACKEND = original_storage_backend
