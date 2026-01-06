import io
import json
import uuid
import zipfile
import csv

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User, Case, MetaLead
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


def _build_config_zip(payload: dict[str, object]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            archive.writestr(name, json.dumps(data, default=str))
    buffer.seek(0)
    return buffer.read()


def _build_cases_csv(rows: list[dict]) -> bytes:
    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


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
        membership = (
            db.query(Membership)
            .filter(
                Membership.organization_id == test_org.id,
                Membership.user_id == test_user.id,
            )
            .first()
        )
        assert membership is not None

        export_user_id = uuid.uuid4()
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
                    "id": str(export_user_id),
                    "email": test_user.email,
                    "display_name": "Imported User",
                    "is_active": True,
                }
            ],
            "memberships.json": [
                {
                    "id": str(membership.id),
                    "user_id": str(export_user_id),
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
        refreshed_user = db.query(User).filter(User.email == test_user.email).first()
        assert refreshed_user is not None
        assert refreshed_user.id == test_user.id
        assert refreshed_user.display_name == "Imported User"
        refreshed_membership = (
            db.query(Membership)
            .filter(
                Membership.organization_id == test_org.id,
                Membership.user_id == test_user.id,
            )
            .first()
        )
        assert refreshed_membership is not None
        assert refreshed_membership.role == Role.DEVELOPER.value

    @pytest.mark.asyncio
    async def test_import_cases_maps_user_by_email_and_imports_meta_payload(
        self, authed_client, db, test_org, test_user, default_stage
    ):
        meta_lead_id = uuid.uuid4()
        case_id = uuid.uuid4()
        export_user_id = uuid.uuid4()
        cases_csv = _build_cases_csv(
            [
                {
                    "id": str(case_id),
                    "case_number": "00001",
                    "status_label": default_stage.label,
                    "stage_id": str(default_stage.id),
                    "source": "import",
                    "owner_type": "user",
                    "owner_id": str(export_user_id),
                    "owner_email": test_user.email,
                    "full_name": "Test Case",
                    "email": "case@example.com",
                    "meta_lead_id": str(meta_lead_id),
                    "meta_lead_external_id": "lead_123",
                    "meta_lead_status": "converted",
                    "meta_lead_meta_created_time": "2024-01-01T00:00:00+00:00",
                    "meta_lead_received_at": "2024-01-01T01:00:00+00:00",
                    "meta_lead_field_data": json.dumps({"first_name": "Jane"}),
                    "meta_lead_raw_payload": json.dumps(
                        {"payload": {"id": "lead_123"}}
                    ),
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/cases",
            files={"cases_csv": ("cases.csv", cases_csv, "text/csv")},
        )
        assert response.status_code == 200

        imported_case = db.query(Case).filter(Case.id == case_id).first()
        assert imported_case is not None
        assert imported_case.owner_id == test_user.id

        imported_lead = db.query(MetaLead).filter(MetaLead.id == meta_lead_id).first()
        assert imported_lead is not None
        assert imported_lead.meta_lead_id == "lead_123"
        assert imported_lead.field_data == {"first_name": "Jane"}
        assert imported_lead.raw_payload == {"payload": {"id": "lead_123"}}
