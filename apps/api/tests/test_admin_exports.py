import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.core.encryption import hash_email
from app.db.enums import Role, OwnerType, SurrogateSource
from app.db.models import Surrogate, Membership, User
from app.main import app
from app.services import job_service
from app.worker import process_admin_export
from app.utils.normalization import normalize_email


@pytest.fixture(scope="function")
async def non_dev_client(db, test_org):
    user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Admin User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=test_org.id,
        role=Role.ADMIN,
    )
    db.add(membership)
    db.flush()

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role=Role.ADMIN.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    from app.services import session_service

    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=test_org.id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        yield client

    app.dependency_overrides.clear()


class TestAdminExports:
    @pytest.mark.asyncio
    async def test_surrogates_export_requires_developer(self, non_dev_client):
        response = await non_dev_client.post("/admin/exports/surrogates")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_surrogates_export_csv(self, authed_client, db, test_org):
        response = await authed_client.post("/admin/exports/surrogates")
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        job = job_service.get_job(db, uuid.UUID(job_id), test_org.id)
        assert job is not None
        await process_admin_export(db, job)
        job_service.mark_job_completed(db, job)

        download = await authed_client.get(f"/admin/exports/jobs/{job_id}/file")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("text/csv")
        assert "surrogate_number" in download.text.splitlines()[0]

    @pytest.mark.asyncio
    async def test_surrogates_export_csv_escapes_formula(
        self, authed_client, db, test_org, test_user, default_stage
    ):
        email = "=bad@example.com"
        normalized_email = normalize_email(email)
        case = Surrogate(
            id=uuid.uuid4(),
            surrogate_number=str(uuid.uuid4().int)[-5:],
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=SurrogateSource.IMPORT.value,
            full_name="=HACK",
            email=normalized_email,
            email_hash=hash_email(normalized_email),
        )
        db.add(case)
        db.commit()

        response = await authed_client.post("/admin/exports/surrogates")
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        job = job_service.get_job(db, uuid.UUID(job_id), test_org.id)
        assert job is not None
        await process_admin_export(db, job)
        job_service.mark_job_completed(db, job)

        download = await authed_client.get(f"/admin/exports/jobs/{job_id}/file")
        assert download.status_code == 200
        assert "'=HACK" in download.text

    @pytest.mark.asyncio
    async def test_config_export_zip(self, authed_client, db, test_org):
        response = await authed_client.post("/admin/exports/config")
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        job = job_service.get_job(db, uuid.UUID(job_id), test_org.id)
        assert job is not None
        await process_admin_export(db, job)
        job_service.mark_job_completed(db, job)

        download = await authed_client.get(f"/admin/exports/jobs/{job_id}/file")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("application/zip")

    @pytest.mark.asyncio
    async def test_analytics_export_zip(self, authed_client, db, test_org):
        response = await authed_client.post("/admin/exports/analytics")
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        job = job_service.get_job(db, uuid.UUID(job_id), test_org.id)
        assert job is not None
        await process_admin_export(db, job)
        job_service.mark_job_completed(db, job)

        download = await authed_client.get(f"/admin/exports/jobs/{job_id}/file")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("application/zip")
