import io
import json
import uuid
import zipfile
from datetime import date, datetime, time, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import COOKIE_NAME, get_db
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.security import create_session_token
from app.core.encryption import hash_email
from app.db.enums import Role, OwnerType, SurrogateSource
from app.db.models import (
    AvailabilityOverride,
    AvailabilityRule,
    AppointmentType,
    BookingLink,
    DataRetentionPolicy,
    Form,
    FormFieldMapping,
    FormLogo,
    LegalHold,
    Membership,
    OrgCounter,
    Surrogate,
    User,
    WorkflowTemplate,
)
from app.main import app
from app.services import admin_export_service, job_service
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

    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
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
            surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
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

    def test_config_export_includes_extended_config(self, db, test_org, test_user):
        test_org.portal_domain = "portal.example.com"
        test_org.signature_template = "modern"
        test_org.signature_logo_url = "logos/org.png"
        test_org.signature_primary_color = "#112233"
        test_org.signature_company_name = "Acme Surrogacy"
        test_org.signature_address = "123 Test St"
        test_org.signature_phone = "+1 555 0100"
        test_org.signature_website = "https://example.com"
        test_org.signature_social_links = [
            {"platform": "linkedin", "url": "https://linkedin.com/company/acme"}
        ]
        test_org.signature_disclaimer = "Confidential"

        test_user.phone = "+1 555 1111"
        test_user.title = "Case Manager"
        test_user.signature_name = "Signature Name"
        test_user.signature_title = "Signature Title"
        test_user.signature_phone = "+1 555 2222"
        test_user.signature_photo_url = "users/photos/signature.png"

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        form_id = uuid.uuid4()
        logo_id = uuid.uuid4()
        mapping_id = uuid.uuid4()
        appointment_type_id = uuid.uuid4()
        availability_rule_id = uuid.uuid4()
        availability_override_id = uuid.uuid4()
        booking_link_id = uuid.uuid4()
        workflow_template_id = uuid.uuid4()
        retention_policy_id = uuid.uuid4()
        legal_hold_id = uuid.uuid4()

        form = Form(
            id=form_id,
            organization_id=test_org.id,
            name="Test Form",
            description="Intake form",
            status="draft",
            schema_json={"title": "Draft"},
            published_schema_json={"title": "Published"},
            max_file_size_bytes=1048576,
            max_file_count=3,
            allowed_mime_types=["image/png"],
            created_by_user_id=test_user.id,
            updated_by_user_id=test_user.id,
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(form)
        db.flush()

        logo = FormLogo(
            id=logo_id,
            organization_id=test_org.id,
            storage_key="org/form-logos/logo.png",
            filename="logo.png",
            content_type="image/png",
            file_size=1234,
            created_by_user_id=test_user.id,
            created_at=created_at,
        )
        mapping = FormFieldMapping(
            id=mapping_id,
            form_id=form.id,
            field_key="first_name",
            surrogate_field="full_name",
            created_at=created_at,
        )
        appointment_type = AppointmentType(
            id=appointment_type_id,
            organization_id=test_org.id,
            user_id=test_user.id,
            name="Consultation",
            slug="consultation",
            description="Test appointment",
            duration_minutes=45,
            buffer_before_minutes=10,
            buffer_after_minutes=5,
            meeting_mode="zoom",
            reminder_hours_before=12,
            is_active=True,
            created_at=created_at,
            updated_at=created_at,
        )
        availability_rule = AvailabilityRule(
            id=availability_rule_id,
            organization_id=test_org.id,
            user_id=test_user.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
            timezone="America/Los_Angeles",
            created_at=created_at,
            updated_at=created_at,
        )
        availability_override = AvailabilityOverride(
            id=availability_override_id,
            organization_id=test_org.id,
            user_id=test_user.id,
            override_date=date(2025, 2, 1),
            is_unavailable=False,
            start_time=time(10, 0),
            end_time=time(12, 0),
            reason="Vacation",
            created_at=created_at,
        )
        booking_link = BookingLink(
            id=booking_link_id,
            organization_id=test_org.id,
            user_id=test_user.id,
            public_slug="public-link",
            is_active=True,
            created_at=created_at,
            updated_at=created_at,
        )
        workflow_template = WorkflowTemplate(
            id=workflow_template_id,
            name="Template One",
            description="Workflow template",
            icon="template",
            category="general",
            trigger_type="status_changed",
            trigger_config={"from": ["new_unread"]},
            conditions=[],
            condition_logic="AND",
            actions=[{"type": "add_note", "content": "Hi"}],
            is_global=False,
            organization_id=test_org.id,
            usage_count=0,
            created_by_user_id=test_user.id,
            created_at=created_at,
            updated_at=created_at,
        )
        retention_policy = DataRetentionPolicy(
            id=retention_policy_id,
            organization_id=test_org.id,
            entity_type="tasks",
            retention_days=365,
            is_active=True,
            created_by_user_id=test_user.id,
            created_at=created_at,
            updated_at=created_at,
        )
        legal_hold = LegalHold(
            id=legal_hold_id,
            organization_id=test_org.id,
            entity_type="surrogate",
            entity_id=uuid.uuid4(),
            reason="Legal hold",
            created_by_user_id=test_user.id,
            created_at=created_at,
        )
        org_counter = OrgCounter(
            organization_id=test_org.id,
            counter_type="surrogate_number",
            current_value=123,
            updated_at=created_at,
        )

        db.add_all(
            [
                logo,
                mapping,
                appointment_type,
                availability_rule,
                availability_override,
                booking_link,
                workflow_template,
                retention_policy,
                legal_hold,
                org_counter,
            ]
        )
        db.commit()

        zip_bytes = admin_export_service.build_org_config_zip(db, test_org.id)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            names = set(archive.namelist())
            assert "forms.json" in names
            assert "form_logos.json" in names
            assert "form_field_mappings.json" in names
            assert "appointment_types.json" in names
            assert "availability_rules.json" in names
            assert "availability_overrides.json" in names
            assert "booking_links.json" in names
            assert "workflow_templates.json" in names
            assert "data_retention_policies.json" in names
            assert "legal_holds.json" in names
            assert "org_counters.json" in names

            org_payload = json.loads(archive.read("organization.json"))
            assert org_payload["portal_domain"] == "portal.example.com"
            assert org_payload["signature_template"] == "modern"

            users_payload = json.loads(archive.read("users.json"))
            exported_user = next(
                item for item in users_payload if item["id"] == str(test_user.id)
            )
            assert exported_user["signature_name"] == "Signature Name"
            assert exported_user["signature_phone"] == "+1 555 2222"

            forms_payload = json.loads(archive.read("forms.json"))
            assert forms_payload and forms_payload[0]["name"] == "Test Form"
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
