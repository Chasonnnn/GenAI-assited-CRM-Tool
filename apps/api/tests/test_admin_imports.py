import io
import json
import uuid
import zipfile

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User
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


def _build_config_zip(payload: dict[str, object]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            archive.writestr(name, json.dumps(data, default=str))
    buffer.seek(0)
    return buffer.read()


class TestAdminImports:
    @pytest.mark.asyncio
    async def test_import_config_requires_developer(self, non_dev_client):
        zip_bytes = _build_config_zip({"organization.json": {}})
        response = await non_dev_client.post(
            "/admin/imports/config",
            files={"config_zip": ("config.zip", zip_bytes, "application/zip")},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_import_config_success(self, authed_client, db, test_user, test_org):
        membership = db.query(Membership).filter(
            Membership.organization_id == test_org.id,
            Membership.user_id == test_user.id,
        ).first()
        assert membership is not None

        config_payload = {
            "organization.json": {
                "id": str(test_org.id),
                "name": "Imported Org",
                "slug": test_org.slug,
                "timezone": "America/Los_Angeles",
                "ai_enabled": True,
                "current_version": 1,
            },
            "users.json": [
                {
                    "id": str(test_user.id),
                    "email": test_user.email,
                    "display_name": test_user.display_name,
                    "is_active": True,
                }
            ],
            "memberships.json": [
                {
                    "id": str(membership.id),
                    "user_id": str(test_user.id),
                    "organization_id": str(test_org.id),
                    "role": Role.DEVELOPER.value,
                }
            ],
            "queues.json": [],
            "queue_members.json": [],
            "role_permissions.json": [],
            "user_permission_overrides.json": [],
            "pipelines.json": [],
            "email_templates.json": [],
            "workflows.json": [],
            "notification_settings.json": [],
            "meta_pages.json": [],
            "ai_settings.json": None,
        }

        zip_bytes = _build_config_zip(config_payload)
        response = await authed_client.post(
            "/admin/imports/config",
            files={"config_zip": ("config.zip", zip_bytes, "application/zip")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["config"]["users"] == 1
