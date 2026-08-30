import csv
import io
import json
import uuid
import zipfile
from datetime import UTC, date, datetime, time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import OwnerType, Role, SurrogateSource
from app.db.models import (
    AppointmentType,
    AutomationWorkflow,
    AvailabilityOverride,
    AvailabilityRule,
    BookingLink,
    DataRetentionPolicy,
    DonorStatusHistory,
    Form,
    FormFieldMapping,
    FormLogo,
    LegalHold,
    Membership,
    MessagingContact,
    MessagingConversation,
    MessagingMessage,
    OrgCounter,
    Pipeline,
    PipelineStage,
    Surrogate,
    TwilioRoute,
    TwilioSettings,
    User,
    WorkflowTemplate,
)
from app.main import app
from app.schemas.donor import DonorCreate
from app.services import admin_export_service, donor_service, job_service
from app.utils.normalization import normalize_email
from app.worker import process_admin_export


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
    async def test_admin_can_export_org_scoped_messaging_archive(
        self,
        non_dev_client,
        db,
        test_org,
    ):
        twilio_settings = TwilioSettings(organization_id=test_org.id)
        db.add(twilio_settings)
        db.flush()
        route = TwilioRoute(
            settings_id=twilio_settings.id,
            organization_id=test_org.id,
            purpose="operational",
        )
        contact = MessagingContact(
            organization_id=test_org.id,
            phone_e164="+14155550100",
            phone_hash="a" * 64,
            phone_last4="0100",
        )
        db.add_all([route, contact])
        db.flush()
        conversation = MessagingConversation(
            organization_id=test_org.id,
            contact_id=contact.id,
            route_id=route.id,
        )
        db.add(conversation)
        db.flush()
        message = MessagingMessage(
            organization_id=test_org.id,
            conversation_id=conversation.id,
            contact_id=contact.id,
            route_id=route.id,
            purpose="operational",
            direction="inbound",
            body="Please call tomorrow",
            from_phone_hash="a" * 64,
            from_phone_last4="0100",
            to_phone_hash="b" * 64,
            to_phone_last4="0200",
        )
        db.add(message)
        db.commit()

        response = await non_dev_client.post("/messaging/exports")
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        job = job_service.get_job(db, uuid.UUID(job_id), test_org.id)
        assert job is not None
        await process_admin_export(db, job)
        job_service.mark_job_completed(db, job)

        download = await non_dev_client.get(f"/messaging/exports/{job_id}/file")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("application/zip")
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            assert "contacts.json" in archive.namelist()
            assert "messages.json" in archive.namelist()
            contacts = json.loads(archive.read("contacts.json"))
            messages = json.loads(archive.read("messages.json"))
            routes = json.loads(archive.read("routes.json"))
            manifest = json.loads(archive.read("manifest.json"))

        assert contacts[0]["phone_e164"] == "+14155550100"
        assert messages[0]["body"] == "Please call tomorrow"
        assert "messaging_service_sid_encrypted" not in routes[0]
        assert "sender_phone_encrypted" not in routes[0]
        assert manifest["organization_id"] == str(test_org.id)
        assert manifest["credential_fields_included"] is False

    def test_resolve_admin_export_path_rejects_traversal(self, monkeypatch, tmp_path):
        original_local_dir = settings.EXPORT_LOCAL_DIR
        settings.EXPORT_LOCAL_DIR = str(tmp_path)

        try:
            with pytest.raises(ValueError, match="outside export directory"):
                admin_export_service.resolve_admin_export_path("../escape.csv")
        finally:
            settings.EXPORT_LOCAL_DIR = original_local_dir

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
    async def test_donors_export_csv(self, authed_client, db, test_org, test_user):
        donor = donor_service.create_donor(
            db,
            test_org.id,
            test_user.id,
            DonorCreate(
                donor_type="egg",
                full_name="Export Egg Donor",
                email="export-egg@example.com",
                education="Bachelor's degree",
            ),
        )
        initial_history = (
            db.query(DonorStatusHistory)
            .filter(DonorStatusHistory.donor_id == donor.id)
            .one()
        )
        initial_at = datetime(2026, 8, 27, 10, 15, tzinfo=UTC)
        initial_history.effective_at = initial_at
        initial_history.recorded_at = initial_at
        contacted_stage = (
            db.query(PipelineStage)
            .join(Pipeline, Pipeline.id == PipelineStage.pipeline_id)
            .filter(
                Pipeline.organization_id == test_org.id,
                Pipeline.entity_type == "egg_donor",
                PipelineStage.stage_key == "contacted",
            )
            .one()
        )
        transition_id = uuid.uuid4()
        transition_at = datetime(2026, 8, 28, 14, 30, tzinfo=UTC)
        db.add(
            DonorStatusHistory(
                id=transition_id,
                donor_id=donor.id,
                organization_id=test_org.id,
                changed_by_user_id=test_user.id,
                old_stage_id=donor.stage_id,
                new_stage_id=contacted_stage.id,
                old_status="new",
                new_status="contacted",
                old_label_snapshot="New",
                new_label_snapshot="Contacted",
                reason="Client approved outreach",
                effective_at=transition_at,
                recorded_at=transition_at,
            )
        )
        donor.stage_id = contacted_stage.id
        db.commit()

        response = await authed_client.post("/admin/exports/donors")
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        job = job_service.get_job(db, uuid.UUID(job_id), test_org.id)
        assert job is not None
        await process_admin_export(db, job)
        job_service.mark_job_completed(db, job)

        download = await authed_client.get(f"/admin/exports/jobs/{job_id}/file")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("text/csv")
        row = next(csv.DictReader(io.StringIO(download.text)))
        assert row["donor_number"] == donor.donor_number
        assert row["full_name"] == "Export Egg Donor"
        assert row["education"] == "Bachelor's degree"
        history_payload = json.loads(row["status_history_json"])
        assert history_payload["version"] == 1
        assert [event["id"] for event in history_payload["events"]] == [
            str(initial_history.id),
            str(transition_id),
        ]
        transition = history_payload["events"][1]
        assert transition["changed_by_email"] == test_user.email
        assert transition["old_stage_key"] == "new"
        assert transition["new_stage_key"] == "contacted"
        assert transition["old_label_snapshot"] == "New"
        assert transition["new_label_snapshot"] == "Contacted"
        assert transition["reason"] == "Client approved outreach"
        assert transition["effective_at"] == transition_at.isoformat()
        assert transition["recorded_at"] == transition_at.isoformat()

    @pytest.mark.asyncio
    async def test_donor_export_rechecks_donor_view_for_request_and_download(
        self,
        authed_client,
        db,
        test_org,
        test_user,
        monkeypatch,
    ):
        created = await authed_client.post("/admin/exports/donors")
        assert created.status_code == 202, created.text
        job_id = uuid.UUID(created.json()["job_id"])
        job = job_service.get_job(db, job_id, test_org.id)
        assert job is not None
        await process_admin_export(db, job)
        job_service.mark_job_completed(db, job)

        from app.services import permission_service

        original_check_permission = permission_service.check_permission

        def deny_donor_view(db, org_id, user_id, role, permission):
            if permission == "view_donors":
                return False
            return original_check_permission(db, org_id, user_id, role, permission)

        monkeypatch.setattr(permission_service, "check_permission", deny_donor_view)

        requested_after_revoke = await authed_client.post("/admin/exports/donors")
        job_status = await authed_client.get(f"/admin/exports/jobs/{job_id}")
        download = await authed_client.get(f"/admin/exports/jobs/{job_id}/download")
        file_download = await authed_client.get(f"/admin/exports/jobs/{job_id}/file")
        surrogate_export = await authed_client.post("/admin/exports/surrogates")

        assert requested_after_revoke.status_code == 403
        assert job_status.status_code == 403
        assert download.status_code == 403
        assert file_download.status_code == 403
        assert surrogate_export.status_code == 202, surrogate_export.text

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

        created_at = datetime(2025, 1, 1, tzinfo=UTC)
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
        donor_pipeline_id = uuid.uuid4()
        donor_stage_id = uuid.uuid4()
        donor_workflow_id = uuid.uuid4()

        form = Form(
            id=form_id,
            organization_id=test_org.id,
            name="Test Form",
            description="Intake form",
            status="draft",
            purpose="other",
            lead_kind="egg_donor",
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

        donor_pipeline = Pipeline(
            id=donor_pipeline_id,
            organization_id=test_org.id,
            entity_type="egg_donor",
            name="Egg Donors",
            is_default=True,
            feature_config={"requires_profile_photo": True},
        )
        donor_stage = PipelineStage(
            id=donor_stage_id,
            pipeline_id=donor_pipeline_id,
            stage_key="egg_donor.new",
            slug="new",
            label="New",
            color="#2563EB",
            order=1,
            stage_type="active",
            semantics={"analytics_bucket": "egg_new"},
            is_intake_stage=True,
            allowed_next_slugs=["contacted"],
        )
        donor_workflow = AutomationWorkflow(
            id=donor_workflow_id,
            organization_id=test_org.id,
            name="Egg donor welcome",
            trigger_type="donor_created",
            subject_type="egg_donor",
            actions=[],
        )

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
            meeting_modes=["zoom", "google_meet"],
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
                donor_pipeline,
                donor_stage,
                donor_workflow,
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
            assert "portal_domain" not in org_payload
            assert org_payload["signature_template"] == "modern"

            users_payload = json.loads(archive.read("users.json"))
            exported_user = next(item for item in users_payload if item["id"] == str(test_user.id))
            assert exported_user["signature_name"] == "Signature Name"
            assert exported_user["signature_phone"] == "+1 555 2222"

            forms_payload = json.loads(archive.read("forms.json"))
            assert forms_payload and forms_payload[0]["name"] == "Test Form"
            assert forms_payload[0]["purpose"] == "other"
            assert forms_payload[0]["lead_kind"] == "egg_donor"
            assert "default_application_email_template_id" in forms_payload[0]

            pipelines_payload = json.loads(archive.read("pipelines.json"))
            exported_pipeline = next(
                item for item in pipelines_payload if item["id"] == str(donor_pipeline_id)
            )
            assert exported_pipeline["entity_type"] == "egg_donor"
            assert exported_pipeline["feature_config"] == {"requires_profile_photo": True}
            assert exported_pipeline["stages"][0]["stage_key"] == "egg_donor.new"
            assert exported_pipeline["stages"][0]["semantics"] == {
                "analytics_bucket": "egg_new"
            }
            assert exported_pipeline["stages"][0]["is_intake_stage"] is True
            assert exported_pipeline["stages"][0]["allowed_next_slugs"] == ["contacted"]

            workflows_payload = json.loads(archive.read("workflows.json"))
            exported_workflow = next(
                item for item in workflows_payload if item["id"] == str(donor_workflow_id)
            )
            assert exported_workflow["subject_type"] == "egg_donor"

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

    @pytest.mark.asyncio
    async def test_admin_export_download_rejects_traversal_path(self, authed_client, db, test_org):
        original_storage_backend = settings.EXPORT_STORAGE_BACKEND
        settings.EXPORT_STORAGE_BACKEND = "local"

        try:
            response = await authed_client.post("/admin/exports/surrogates")
            assert response.status_code == 202
            job_id = response.json()["job_id"]

            job = job_service.get_job(db, uuid.UUID(job_id), test_org.id)
            assert job is not None
            job.status = "completed"
            job.payload = {
                "file_path": "../escape.csv",
                "filename": "surrogates.csv",
                "export_type": "surrogates_csv",
            }
            db.commit()

            download = await authed_client.get(f"/admin/exports/jobs/{job_id}/file")
            assert download.status_code == 404
        finally:
            settings.EXPORT_STORAGE_BACKEND = original_storage_backend
