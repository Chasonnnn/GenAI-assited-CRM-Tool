import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role, OwnerType, CaseSource
from app.db.models import Case, Membership, User
from app.main import app


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
    async def test_cases_export_requires_developer(self, non_dev_client):
        response = await non_dev_client.get("/admin/exports/cases")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_cases_export_csv(self, authed_client):
        response = await authed_client.get("/admin/exports/cases")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "case_number" in response.text.splitlines()[0]

    @pytest.mark.asyncio
    async def test_cases_export_csv_escapes_formula(self, authed_client, db, test_org, test_user, default_stage):
        case = Case(
            id=uuid.uuid4(),
            case_number=str(uuid.uuid4().int)[-5:],
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            stage_id=default_stage.id,
            status_label=default_stage.label,
            source=CaseSource.IMPORT.value,
            full_name="=HACK",
            email="=bad@example.com",
        )
        db.add(case)
        db.commit()

        response = await authed_client.get("/admin/exports/cases")
        assert response.status_code == 200
        assert "'=HACK" in response.text

    @pytest.mark.asyncio
    async def test_config_export_zip(self, authed_client):
        response = await authed_client.get("/admin/exports/config")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")

    @pytest.mark.asyncio
    async def test_analytics_export_zip(self, authed_client):
        response = await authed_client.get("/admin/exports/analytics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")
