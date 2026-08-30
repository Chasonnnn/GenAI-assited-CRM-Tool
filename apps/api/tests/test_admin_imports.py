import base64
import csv
import hashlib
import io
import json
import os
import uuid
import zipfile
from datetime import UTC, date, datetime, time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import (
    AppointmentType,
    Attachment,
    AutomationWorkflow,
    AvailabilityOverride,
    AvailabilityRule,
    BookingLink,
    DataRetentionPolicy,
    Donor,
    DonorStatusHistory,
    Form,
    FormFieldMapping,
    FormLogo,
    LegalHold,
    Membership,
    MetaLead,
    Organization,
    OrgCounter,
    Pipeline,
    PipelineStage,
    Surrogate,
    User,
    UserNotificationSettings,
    WorkflowTemplate,
)
from app.main import app
from app.schemas.donor import DonorCreate
from app.services import (
    admin_export_service,
    attachment_service,
    donor_service,
    pipeline_service,
)
from app.services.admin_import_service import _ensure_empty_org
from app.services.donor_service import generate_donor_number


@pytest.fixture(autouse=True)
def admin_import_rate_limiter_reset():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


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


def _build_config_zip(payload: dict[str, object]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            archive.writestr(name, json.dumps(data, default=str))
    buffer.seek(0)
    return buffer.read()


def _build_surrogates_csv(rows: list[dict]) -> bytes:
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


def _png_bytes() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (6, 6), color=(32, 96, 192)).save(buffer, format="PNG")
    return buffer.getvalue()


def _large_png_bytes() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.frombytes("RGB", (320, 320), os.urandom(320 * 320 * 3)).save(
        buffer,
        format="PNG",
    )
    return buffer.getvalue()


class TestAdminImports:
    def test_ensure_empty_org_counts_notification_settings_without_id(
        self,
        db,
        test_org,
        test_user,
    ):
        db.add(
            UserNotificationSettings(
                user_id=test_user.id,
                organization_id=test_org.id,
            )
        )
        db.commit()

        with pytest.raises(ValueError, match="notification_settings"):
            _ensure_empty_org(db, test_org.id)

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
        counter_updated_at = datetime(2025, 1, 1, tzinfo=UTC)
        config_payload = {
            "organization.json": {
                "id": str(test_org.id),
                "name": "Imported Org",
                "slug": test_org.slug,
                "timezone": "America/Los_Angeles",
                "ai_enabled": True,
                "current_version": 1,
                "signature_template": "modern",
                "signature_logo_url": "logos/org.png",
                "signature_primary_color": "#112233",
                "signature_company_name": "Acme Surrogacy",
                "signature_address": "123 Test St",
                "signature_phone": "+1 555 0100",
                "signature_website": "https://example.com",
                "signature_social_links": [
                    {"platform": "linkedin", "url": "https://linkedin.com/company/acme"}
                ],
                "signature_disclaimer": "Confidential",
            },
            "users.json": [
                {
                    "id": str(export_user_id),
                    "email": test_user.email,
                    "display_name": "Imported User",
                    "is_active": True,
                    "phone": "+1 555 1111",
                    "title": "Case Manager",
                    "signature_name": "Signature Name",
                    "signature_title": "Signature Title",
                    "signature_phone": "+1 555 2222",
                    "signature_photo_url": "users/photos/signature.png",
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
            "pipelines.json": [
                {
                    "id": str(donor_pipeline_id),
                    "organization_id": str(test_org.id),
                    "entity_type": "sperm_donor",
                    "name": "Sperm Donors",
                    "is_default": True,
                    "current_version": 1,
                    "feature_config": {"screening": "semen_analysis"},
                    "stages": [
                        {
                            "id": str(donor_stage_id),
                            "stage_key": "sperm_donor.semen_analysis",
                            "slug": "semen_analysis",
                            "label": "Semen Analysis",
                            "color": "#2563EB",
                            "order": 1,
                            "stage_type": "active",
                            "semantics": {"analytics_bucket": "sperm_screening"},
                            "is_active": True,
                            "is_intake_stage": True,
                            "allowed_next_slugs": ["available"],
                        }
                    ],
                }
            ],
            "email_templates.json": [],
            "workflows.json": [
                {
                    "id": str(donor_workflow_id),
                    "organization_id": str(test_org.id),
                    "name": "Sperm donor welcome",
                    "trigger_type": "donor_created",
                    "subject_type": "sperm_donor",
                    "trigger_config": {},
                    "conditions": [],
                    "condition_logic": "AND",
                    "actions": [],
                }
            ],
            "notification_settings.json": [],
            "meta_pages.json": [],
            "ai_settings.json": None,
            "forms.json": [
                {
                    "id": str(form_id),
                    "organization_id": str(test_org.id),
                    "name": "Test Form",
                    "description": "Intake form",
                    "status": "draft",
                    "purpose": "other",
                    "lead_kind": "sperm_donor",
                    "schema_json": {"title": "Draft"},
                    "published_schema_json": {"title": "Published"},
                    "max_file_size_bytes": 1048576,
                    "max_file_count": 3,
                    "allowed_mime_types": ["image/png"],
                    "created_by_user_id": str(export_user_id),
                    "updated_by_user_id": str(export_user_id),
                    "created_at": "2025-01-01T00:00:00+00:00",
                    "updated_at": "2025-01-02T00:00:00+00:00",
                }
            ],
            "form_logos.json": [
                {
                    "id": str(logo_id),
                    "organization_id": str(test_org.id),
                    "storage_key": "org/form-logos/logo.png",
                    "filename": "logo.png",
                    "content_type": "image/png",
                    "file_size": 1234,
                    "created_by_user_id": str(export_user_id),
                    "created_at": "2025-01-03T00:00:00+00:00",
                }
            ],
            "form_field_mappings.json": [
                {
                    "id": str(mapping_id),
                    "form_id": str(form_id),
                    "field_key": "first_name",
                    "surrogate_field": "full_name",
                    "created_at": "2025-01-04T00:00:00+00:00",
                }
            ],
            "appointment_types.json": [
                {
                    "id": str(appointment_type_id),
                    "organization_id": str(test_org.id),
                    "user_id": str(export_user_id),
                    "name": "Consultation",
                    "slug": "consultation",
                    "description": "Test appointment",
                    "duration_minutes": 45,
                    "buffer_before_minutes": 10,
                    "buffer_after_minutes": 5,
                    "meeting_mode": "zoom",
                    "meeting_modes": ["zoom", "google_meet"],
                    "reminder_hours_before": 12,
                    "is_active": True,
                    "created_at": "2025-01-05T00:00:00+00:00",
                    "updated_at": "2025-01-06T00:00:00+00:00",
                }
            ],
            "availability_rules.json": [
                {
                    "id": str(availability_rule_id),
                    "organization_id": str(test_org.id),
                    "user_id": str(export_user_id),
                    "day_of_week": 1,
                    "start_time": "09:00:00",
                    "end_time": "17:00:00",
                    "timezone": "America/Los_Angeles",
                    "created_at": "2025-01-07T00:00:00+00:00",
                    "updated_at": "2025-01-08T00:00:00+00:00",
                }
            ],
            "availability_overrides.json": [
                {
                    "id": str(availability_override_id),
                    "organization_id": str(test_org.id),
                    "user_id": str(export_user_id),
                    "override_date": "2025-02-01",
                    "is_unavailable": False,
                    "start_time": "10:00:00",
                    "end_time": "12:00:00",
                    "reason": "Vacation",
                    "created_at": "2025-01-09T00:00:00+00:00",
                }
            ],
            "booking_links.json": [
                {
                    "id": str(booking_link_id),
                    "organization_id": str(test_org.id),
                    "user_id": str(export_user_id),
                    "public_slug": "public-link",
                    "is_active": True,
                    "created_at": "2025-01-10T00:00:00+00:00",
                    "updated_at": "2025-01-11T00:00:00+00:00",
                }
            ],
            "workflow_templates.json": [
                {
                    "id": str(workflow_template_id),
                    "name": "Template One",
                    "description": "Workflow template",
                    "icon": "template",
                    "category": "general",
                    "trigger_type": "status_changed",
                    "trigger_config": {"from": ["new_unread"]},
                    "conditions": [],
                    "condition_logic": "AND",
                    "actions": [{"type": "add_note", "content": "Hi"}],
                    "is_global": False,
                    "organization_id": str(test_org.id),
                    "usage_count": 0,
                    "created_by_user_id": str(export_user_id),
                    "created_at": "2025-01-12T00:00:00+00:00",
                    "updated_at": "2025-01-13T00:00:00+00:00",
                }
            ],
            "data_retention_policies.json": [
                {
                    "id": str(retention_policy_id),
                    "organization_id": str(test_org.id),
                    "entity_type": "tasks",
                    "retention_days": 365,
                    "is_active": True,
                    "created_by_user_id": str(export_user_id),
                    "created_at": "2025-01-14T00:00:00+00:00",
                    "updated_at": "2025-01-15T00:00:00+00:00",
                }
            ],
            "legal_holds.json": [
                {
                    "id": str(legal_hold_id),
                    "organization_id": str(test_org.id),
                    "entity_type": "surrogate",
                    "entity_id": str(uuid.uuid4()),
                    "reason": "Legal hold",
                    "created_by_user_id": str(export_user_id),
                    "released_by_user_id": None,
                    "created_at": "2025-01-16T00:00:00+00:00",
                    "released_at": None,
                }
            ],
            "org_counters.json": [
                {
                    "organization_id": str(test_org.id),
                    "counter_type": "surrogate_number",
                    "current_value": 123,
                    "updated_at": counter_updated_at.isoformat(),
                }
            ],
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

        refreshed_org = db.query(Organization).filter(Organization.id == test_org.id).first()
        assert refreshed_org is not None
        assert refreshed_org.signature_template == "modern"
        assert refreshed_org.signature_logo_url == "logos/org.png"
        assert refreshed_org.signature_primary_color == "#112233"
        assert refreshed_org.signature_company_name == "Acme Surrogacy"
        assert refreshed_org.signature_address == "123 Test St"
        assert refreshed_org.signature_phone == "+1 555 0100"
        assert refreshed_org.signature_website == "https://example.com"
        assert refreshed_org.signature_social_links == [
            {"platform": "linkedin", "url": "https://linkedin.com/company/acme"}
        ]
        assert refreshed_org.signature_disclaimer == "Confidential"

        refreshed_user = db.query(User).filter(User.email == test_user.email).first()
        assert refreshed_user is not None
        assert refreshed_user.phone == "+1 555 1111"
        assert refreshed_user.title == "Case Manager"
        assert refreshed_user.signature_name == "Signature Name"
        assert refreshed_user.signature_title == "Signature Title"
        assert refreshed_user.signature_phone == "+1 555 2222"
        assert refreshed_user.signature_photo_url == "users/photos/signature.png"

        form = db.query(Form).filter(Form.id == form_id).first()
        assert form is not None
        assert form.name == "Test Form"
        assert form.schema_json == {"title": "Draft"}
        assert form.published_schema_json == {"title": "Published"}
        assert form.created_by_user_id == test_user.id
        assert form.updated_by_user_id == test_user.id
        assert form.purpose == "other"
        assert form.lead_kind == "sperm_donor"

        pipeline = db.query(Pipeline).filter(Pipeline.id == donor_pipeline_id).one()
        assert pipeline.entity_type == "sperm_donor"
        assert pipeline.feature_config == {"screening": "semen_analysis"}
        stage = db.query(PipelineStage).filter(PipelineStage.id == donor_stage_id).one()
        assert stage.stage_key == "sperm_donor.semen_analysis"
        assert stage.semantics == {"analytics_bucket": "sperm_screening"}
        assert stage.is_intake_stage is True
        assert stage.allowed_next_slugs == ["available"]

        workflow = (
            db.query(AutomationWorkflow)
            .filter(AutomationWorkflow.id == donor_workflow_id)
            .one()
        )
        assert workflow.subject_type == "sperm_donor"

        logo = db.query(FormLogo).filter(FormLogo.id == logo_id).first()
        assert logo is not None
        assert logo.storage_key == "org/form-logos/logo.png"
        assert logo.created_by_user_id == test_user.id

        mapping = db.query(FormFieldMapping).filter(FormFieldMapping.id == mapping_id).first()
        assert mapping is not None
        assert mapping.form_id == form_id
        assert mapping.field_key == "first_name"

        appointment_type = (
            db.query(AppointmentType).filter(AppointmentType.id == appointment_type_id).first()
        )
        assert appointment_type is not None
        assert appointment_type.user_id == test_user.id
        assert appointment_type.duration_minutes == 45
        assert appointment_type.meeting_mode == "zoom"
        assert appointment_type.meeting_modes == ["zoom", "google_meet"]

        availability_rule = (
            db.query(AvailabilityRule).filter(AvailabilityRule.id == availability_rule_id).first()
        )
        assert availability_rule is not None
        assert availability_rule.user_id == test_user.id
        assert availability_rule.start_time == time(9, 0)
        assert availability_rule.end_time == time(17, 0)

        availability_override = (
            db.query(AvailabilityOverride)
            .filter(AvailabilityOverride.id == availability_override_id)
            .first()
        )
        assert availability_override is not None
        assert availability_override.user_id == test_user.id
        assert availability_override.override_date == date(2025, 2, 1)
        assert availability_override.start_time == time(10, 0)
        assert availability_override.end_time == time(12, 0)

        booking_link = db.query(BookingLink).filter(BookingLink.id == booking_link_id).first()
        assert booking_link is not None
        assert booking_link.user_id == test_user.id
        assert booking_link.public_slug == "public-link"

        workflow_template = (
            db.query(WorkflowTemplate).filter(WorkflowTemplate.id == workflow_template_id).first()
        )
        assert workflow_template is not None
        assert workflow_template.organization_id == test_org.id
        assert workflow_template.created_by_user_id == test_user.id
        assert workflow_template.trigger_type == "status_changed"

        retention_policy = (
            db.query(DataRetentionPolicy)
            .filter(DataRetentionPolicy.id == retention_policy_id)
            .first()
        )
        assert retention_policy is not None
        assert retention_policy.organization_id == test_org.id
        assert retention_policy.retention_days == 365
        assert retention_policy.created_by_user_id == test_user.id

        legal_hold = db.query(LegalHold).filter(LegalHold.id == legal_hold_id).first()
        assert legal_hold is not None
        assert legal_hold.organization_id == test_org.id
        assert legal_hold.created_by_user_id == test_user.id

        counter = (
            db.query(OrgCounter)
            .filter(
                OrgCounter.organization_id == test_org.id,
                OrgCounter.counter_type == "surrogate_number",
            )
            .first()
        )
        assert counter is not None
        assert counter.current_value == 123
        assert counter.updated_at == counter_updated_at

    @pytest.mark.asyncio
    async def test_import_cases_maps_user_by_email_and_imports_meta_payload(
        self, authed_client, db, test_org, test_user, default_stage
    ):
        meta_lead_id = uuid.uuid4()
        surrogate_id = uuid.uuid4()
        export_user_id = uuid.uuid4()
        surrogates_csv = _build_surrogates_csv(
            [
                {
                    "id": str(surrogate_id),
                    "surrogate_number": "S10001",
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
                    "meta_lead_raw_payload": json.dumps({"payload": {"id": "lead_123"}}),
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/surrogates",
            files={"surrogates_csv": ("cases.csv", surrogates_csv, "text/csv")},
        )
        assert response.status_code == 200

        imported_case = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
        assert imported_case is not None
        assert imported_case.owner_id == test_user.id

        imported_lead = db.query(MetaLead).filter(MetaLead.id == meta_lead_id).first()
        assert imported_lead is not None
        assert imported_lead.meta_lead_id == "lead_123"
        assert imported_lead.field_data == {"first_name": "Jane"}
        assert imported_lead.raw_payload == {"payload": {"id": "lead_123"}}

    @pytest.mark.asyncio
    async def test_import_donors_restores_exact_subtype_stage_and_owner(
        self,
        authed_client,
        db,
        test_org,
        test_user,
        monkeypatch,
    ):
        egg_pipeline = pipeline_service.get_or_create_default_pipeline(
            db,
            test_org.id,
            entity_type="egg_donor",
        )
        sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
            db,
            test_org.id,
            entity_type="sperm_donor",
        )
        egg_stage = pipeline_service.get_stage_by_key(db, egg_pipeline.id, "new")
        sperm_stage = pipeline_service.get_stage_by_key(db, sperm_pipeline.id, "semen_analysis")
        assert egg_stage is not None
        assert sperm_stage is not None
        exported_owner_id = uuid.uuid4()
        egg_id = uuid.uuid4()
        sperm_id = uuid.uuid4()
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(egg_id),
                    "donor_number": "D10001",
                    "donor_type": "egg",
                    "stage_id": str(egg_stage.id),
                    "source": "import",
                    "owner_type": "user",
                    "owner_id": str(exported_owner_id),
                    "owner_email": test_user.email,
                    "full_name": "Imported Egg Donor",
                    "email": "egg-import@example.com",
                    "phone": "+1 (607) 555-0101",
                    "state": "NY",
                    "education": "Bachelor's degree",
                    "is_archived": "false",
                    "created_at": "2026-08-20T12:00:00+00:00",
                    "updated_at": "2026-08-21T12:00:00+00:00",
                },
                {
                    "id": str(sperm_id),
                    "donor_number": "D10002",
                    "donor_type": "sperm",
                    "stage_id": str(sperm_stage.id),
                    "full_name": "Imported Sperm Donor",
                    "email": "sperm-import@example.com",
                    "is_archived": "true",
                    "archived_at": "2026-08-22T12:00:00+00:00",
                },
            ]
        )

        original_commit = db.commit
        commit_calls = 0

        def tracked_commit() -> None:
            nonlocal commit_calls
            commit_calls += 1
            original_commit()

        monkeypatch.setattr(db, "commit", tracked_commit)
        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 200, response.text
        assert commit_calls == 2
        assert response.json()["donors_imported"] == 2
        imported_egg = db.get(Donor, egg_id)
        imported_sperm = db.get(Donor, sperm_id)
        assert imported_egg is not None
        assert imported_egg.owner_id == test_user.id
        assert imported_egg.stage_id == egg_stage.id
        assert imported_egg.phone == "+16075550101"
        assert imported_sperm is not None
        assert imported_sperm.stage_id == sperm_stage.id
        assert imported_sperm.is_archived is True
        egg_history = (
            db.query(DonorStatusHistory)
            .filter(DonorStatusHistory.donor_id == egg_id)
            .one()
        )
        assert egg_history.organization_id == test_org.id
        assert egg_history.changed_by_user_id == test_user.id
        assert egg_history.old_stage_id is None
        assert egg_history.new_stage_id == egg_stage.id
        assert egg_history.new_status == egg_stage.stage_key
        assert egg_history.new_label_snapshot == egg_stage.label
        assert egg_history.reason == "Imported current stage"
        assert generate_donor_number(db, test_org.id) == "D10003"

    @pytest.mark.asyncio
    async def test_import_donors_rejects_cross_subtype_stage(
        self,
        authed_client,
        db,
        test_org,
    ):
        sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
            db,
            test_org.id,
            entity_type="sperm_donor",
        )
        sperm_stage = pipeline_service.get_stage_by_key(db, sperm_pipeline.id, "new")
        assert sperm_stage is not None
        donor_id = uuid.uuid4()
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": "D10003",
                    "donor_type": "egg",
                    "stage_id": str(sperm_stage.id),
                    "full_name": "Wrong Pipeline Donor",
                    "email": "wrong-pipeline@example.com",
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 400
        assert "not in the egg_donor pipeline" in response.json()["detail"]
        assert db.get(Donor, donor_id) is None

    @pytest.mark.asyncio
    async def test_import_donors_restores_full_status_history_with_safe_actor_remap(
        self,
        authed_client,
        db,
        test_org,
        test_user,
    ):
        egg_pipeline = pipeline_service.get_or_create_default_pipeline(
            db,
            test_org.id,
            entity_type="egg_donor",
        )
        new_stage = pipeline_service.get_stage_by_key(db, egg_pipeline.id, "new")
        contacted_stage = pipeline_service.get_stage_by_key(db, egg_pipeline.id, "contacted")
        assert new_stage is not None
        assert contacted_stage is not None
        donor_id = uuid.uuid4()
        initial_history_id = uuid.uuid4()
        transition_history_id = uuid.uuid4()
        initial_at = "2026-08-20T12:00:00+00:00"
        transition_at = "2026-08-21T13:30:00+00:00"
        status_history = {
            "version": 1,
            "events": [
                {
                    "id": str(initial_history_id),
                    "changed_by_user_id": str(uuid.uuid4()),
                    "changed_by_email": test_user.email,
                    "old_stage_id": None,
                    "old_pipeline_id": None,
                    "old_pipeline_name": None,
                    "old_stage_key": None,
                    "new_stage_id": str(uuid.uuid4()),
                    "new_pipeline_id": str(uuid.uuid4()),
                    "new_pipeline_name": egg_pipeline.name,
                    "new_stage_key": "new",
                    "old_status": None,
                    "new_status": "new",
                    "old_label_snapshot": None,
                    "new_label_snapshot": "Original New Label",
                    "reason": "Initial creation",
                    "effective_at": initial_at,
                    "recorded_at": initial_at,
                },
                {
                    "id": str(transition_history_id),
                    "changed_by_user_id": str(uuid.uuid4()),
                    "changed_by_email": "missing-actor@example.com",
                    "old_stage_id": str(new_stage.id),
                    "old_pipeline_id": str(egg_pipeline.id),
                    "old_pipeline_name": egg_pipeline.name,
                    "old_stage_key": "new",
                    "new_stage_id": str(contacted_stage.id),
                    "new_pipeline_id": str(egg_pipeline.id),
                    "new_pipeline_name": egg_pipeline.name,
                    "new_stage_key": "contacted",
                    "old_status": "new",
                    "new_status": "contacted",
                    "old_label_snapshot": "Original New Label",
                    "new_label_snapshot": "Original Contacted Label",
                    "reason": "Reached by phone",
                    "effective_at": transition_at,
                    "recorded_at": transition_at,
                },
            ],
        }
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": "D10004",
                    "donor_type": "egg",
                    "stage_id": str(contacted_stage.id),
                    "full_name": "History Donor",
                    "email": "history-donor@example.com",
                    "status_history_json": json.dumps(status_history),
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 200, response.text
        histories = (
            db.query(DonorStatusHistory)
            .filter(DonorStatusHistory.donor_id == donor_id)
            .order_by(DonorStatusHistory.recorded_at.asc())
            .all()
        )
        assert [history.id for history in histories] == [
            initial_history_id,
            transition_history_id,
        ]
        assert histories[0].changed_by_user_id == test_user.id
        assert histories[0].new_stage_id == new_stage.id
        assert histories[0].new_label_snapshot == "Original New Label"
        assert histories[0].effective_at == datetime.fromisoformat(initial_at)
        assert histories[1].changed_by_user_id is None
        assert histories[1].old_stage_id == new_stage.id
        assert histories[1].new_stage_id == contacted_stage.id
        assert histories[1].reason == "Reached by phone"
        assert histories[1].recorded_at == datetime.fromisoformat(transition_at)

    @pytest.mark.asyncio
    async def test_import_donors_rejects_history_stage_from_other_subtype(
        self,
        authed_client,
        db,
        test_org,
    ):
        egg_pipeline = pipeline_service.get_or_create_default_pipeline(
            db, test_org.id, entity_type="egg_donor"
        )
        sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
            db, test_org.id, entity_type="sperm_donor"
        )
        egg_stage = pipeline_service.get_stage_by_key(db, egg_pipeline.id, "new")
        sperm_stage = pipeline_service.get_stage_by_key(db, sperm_pipeline.id, "new")
        assert egg_stage is not None
        assert sperm_stage is not None
        donor_id = uuid.uuid4()
        history_payload = {
            "version": 1,
            "events": [
                {
                    "id": str(uuid.uuid4()),
                    "new_stage_id": str(sperm_stage.id),
                    "new_stage_key": "new",
                    "new_status": "new",
                    "new_label_snapshot": "New",
                    "effective_at": "2026-08-20T12:00:00+00:00",
                    "recorded_at": "2026-08-20T12:00:00+00:00",
                }
            ],
        }
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": "D10005",
                    "donor_type": "egg",
                    "stage_id": str(egg_stage.id),
                    "full_name": "Wrong History Donor",
                    "email": "wrong-history@example.com",
                    "status_history_json": json.dumps(history_payload),
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 400
        assert "not in the egg_donor pipeline" in response.json()["detail"]
        assert db.get(Donor, donor_id) is None

    @pytest.mark.asyncio
    async def test_import_donors_rejects_colliding_status_history_id(
        self,
        authed_client,
        db,
        test_org,
        test_user,
        monkeypatch,
    ):
        foreign_org = Organization(
            id=uuid.uuid4(),
            name="History Collision Source",
            slug=f"history-collision-{uuid.uuid4().hex[:8]}",
            ai_enabled=True,
        )
        db.add(foreign_org)
        db.flush()
        foreign_donor = donor_service.create_donor(
            db,
            foreign_org.id,
            test_user.id,
            DonorCreate(
                donor_type="egg",
                full_name="Foreign History Donor",
                email="foreign-history@example.com",
            ),
        )
        foreign_history = (
            db.query(DonorStatusHistory)
            .filter(DonorStatusHistory.donor_id == foreign_donor.id)
            .one()
        )
        foreign_history_id = foreign_history.id
        egg_pipeline = pipeline_service.get_or_create_default_pipeline(
            db, test_org.id, entity_type="egg_donor"
        )
        egg_stage = pipeline_service.get_stage_by_key(db, egg_pipeline.id, "new")
        assert egg_stage is not None
        donor_id = uuid.uuid4()
        history_payload = {
            "version": 1,
            "events": [
                {
                    "id": str(foreign_history_id),
                    "new_stage_id": str(egg_stage.id),
                    "new_stage_key": "new",
                    "new_status": "new",
                    "new_label_snapshot": "New",
                    "effective_at": "2026-08-20T12:00:00+00:00",
                    "recorded_at": "2026-08-20T12:00:00+00:00",
                }
            ],
        }
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": "D10006",
                    "donor_type": "egg",
                    "stage_id": str(egg_stage.id),
                    "full_name": "Collision Target",
                    "email": "collision-target@example.com",
                    "status_history_json": json.dumps(history_payload),
                }
            ]
        )
        db.commit()
        failure_savepoint = db.begin_nested()

        def rollback_failure_savepoint() -> None:
            if failure_savepoint.is_active:
                failure_savepoint.rollback()

        monkeypatch.setattr(db, "rollback", rollback_failure_savepoint)

        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 400
        assert "Status history id" in response.json()["detail"]
        assert "is unavailable" in response.json()["detail"]
        assert db.get(Donor, donor_id) is None
        assert db.get(DonorStatusHistory, foreign_history_id) is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("donor_number", ["D00001", "D10000"])
    async def test_import_donors_rejects_number_below_reserved_floor(
        self,
        authed_client,
        db,
        test_org,
        donor_number,
    ):
        pipeline = pipeline_service.get_or_create_default_pipeline(
            db, test_org.id, entity_type="egg_donor"
        )
        stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
        assert stage is not None
        donor_id = uuid.uuid4()
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": donor_number,
                    "donor_type": "egg",
                    "stage_id": str(stage.id),
                    "full_name": "Invalid Number Donor",
                    "email": f"invalid-number-{donor_number}@example.com",
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 400
        assert f"Invalid donor_number {donor_number}" in response.json()["detail"]
        assert db.get(Donor, donor_id) is None

    @pytest.mark.asyncio
    async def test_import_donors_rejects_oversized_status_history_json(
        self,
        authed_client,
        db,
        test_org,
    ):
        pipeline = pipeline_service.get_or_create_default_pipeline(
            db, test_org.id, entity_type="egg_donor"
        )
        stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
        assert stage is not None
        donor_id = uuid.uuid4()
        oversized_history = json.dumps(
            {
                "version": 1,
                "events": [],
                "padding": "x" * 1_048_576,
            }
        )
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": "D10007",
                    "donor_type": "egg",
                    "stage_id": str(stage.id),
                    "full_name": "Oversized History Donor",
                    "email": "oversized-history@example.com",
                    "status_history_json": oversized_history,
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 400
        assert "Status history payload exceeds the limit" in response.json()["detail"]
        assert db.get(Donor, donor_id) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("scan_status", "quarantined"),
        [
            ("infected", "false"),
            ("error", "false"),
            ("pending", "false"),
            ("clean", "true"),
        ],
    )
    async def test_import_donor_photo_rejects_non_clean_or_quarantined_content(
        self,
        authed_client,
        db,
        test_org,
        tmp_path,
        monkeypatch,
        scan_status,
        quarantined,
    ):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
        pipeline = pipeline_service.get_or_create_default_pipeline(
            db, test_org.id, entity_type="egg_donor"
        )
        stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
        assert stage is not None
        payload = _png_bytes()
        donor_id = uuid.uuid4()
        attachment_id = uuid.uuid4()
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": "D10008",
                    "donor_type": "egg",
                    "stage_id": str(stage.id),
                    "full_name": "Unsafe Photo Donor",
                    "email": f"unsafe-{scan_status}-{quarantined}@example.com",
                    "profile_photo_attachment_id": str(attachment_id),
                    "profile_photo_filename": "profile.png",
                    "profile_photo_content_type": "image/png",
                    "profile_photo_file_size": str(len(payload)),
                    "profile_photo_checksum_sha256": hashlib.sha256(payload).hexdigest(),
                    "profile_photo_scan_status": scan_status,
                    "profile_photo_quarantined": quarantined,
                    "profile_photo_bytes_base64": base64.b64encode(payload).decode("ascii"),
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 400
        assert "must be clean and not quarantined" in response.json()["detail"]
        assert db.get(Donor, donor_id) is None
        assert db.get(Attachment, attachment_id) is None
        assert not any(path.is_file() for path in tmp_path.rglob("*"))

    @pytest.mark.asyncio
    async def test_import_donor_photo_accepts_export_sized_csv_fields(
        self,
        authed_client,
        db,
        test_org,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)
        pipeline = pipeline_service.get_or_create_default_pipeline(
            db,
            test_org.id,
            entity_type="egg_donor",
        )
        stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
        assert stage is not None
        payload = _large_png_bytes()
        encoded_payload = base64.b64encode(payload).decode("ascii")
        assert len(encoded_payload) > 131_072
        donor_id = uuid.uuid4()
        attachment_id = uuid.uuid4()
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": "D10009",
                    "donor_type": "egg",
                    "stage_id": str(stage.id),
                    "full_name": "Large Photo Donor",
                    "email": "large-photo@example.com",
                    "profile_photo_attachment_id": str(attachment_id),
                    "profile_photo_filename": "profile.png",
                    "profile_photo_content_type": "image/png",
                    "profile_photo_file_size": str(len(payload)),
                    "profile_photo_checksum_sha256": hashlib.sha256(payload).hexdigest(),
                    "profile_photo_scan_status": "clean",
                    "profile_photo_quarantined": "false",
                    "profile_photo_bytes_base64": encoded_payload,
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 200, response.text
        donor = db.get(Donor, donor_id)
        attachment = db.get(Attachment, attachment_id)
        assert donor is not None
        assert donor.profile_photo_attachment_id == attachment_id
        assert attachment is not None
        assert attachment.organization_id == test_org.id
        assert attachment.donor_id == donor_id

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("tamper", "expected_error"),
        [
            ("size", "Profile photo size mismatch"),
            ("checksum", "Profile photo checksum mismatch"),
            ("content", "Invalid image file"),
        ],
    )
    async def test_import_donor_photo_validates_size_checksum_and_content(
        self,
        authed_client,
        db,
        test_org,
        tmp_path,
        monkeypatch,
        tamper,
        expected_error,
    ):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
        pipeline = pipeline_service.get_or_create_default_pipeline(
            db,
            test_org.id,
            entity_type="egg_donor",
        )
        stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
        assert stage is not None
        payload = b"not an image" if tamper == "content" else _png_bytes()
        expected_size = len(payload) + 1 if tamper == "size" else len(payload)
        expected_checksum = (
            "0" * 64 if tamper == "checksum" else hashlib.sha256(payload).hexdigest()
        )
        donor_id = uuid.uuid4()
        attachment_id = uuid.uuid4()
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": "D10009",
                    "donor_type": "egg",
                    "stage_id": str(stage.id),
                    "full_name": "Invalid Photo Donor",
                    "email": f"invalid-photo-{tamper}@example.com",
                    "profile_photo_attachment_id": str(attachment_id),
                    "profile_photo_filename": "profile.png",
                    "profile_photo_content_type": "image/png",
                    "profile_photo_file_size": str(expected_size),
                    "profile_photo_checksum_sha256": expected_checksum,
                    "profile_photo_scan_status": "clean",
                    "profile_photo_quarantined": "false",
                    "profile_photo_bytes_base64": base64.b64encode(payload).decode("ascii"),
                }
            ]
        )

        response = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", donors_csv, "text/csv")},
        )

        assert response.status_code == 400
        assert expected_error in response.json()["detail"]
        assert db.get(Donor, donor_id) is None
        assert db.get(Attachment, attachment_id) is None
        assert not any(path.is_file() for path in tmp_path.rglob("*"))

    @pytest.mark.asyncio
    async def test_import_all_round_trips_donor_profile_photo_into_tenant_storage(
        self,
        authed_client,
        db,
        test_org,
        test_user,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)

        source_org = Organization(
            id=uuid.uuid4(),
            name="Donor Photo Source",
            slug=f"donor-photo-source-{uuid.uuid4().hex[:8]}",
            ai_enabled=True,
        )
        db.add(source_org)
        db.flush()
        source_user = User(
            id=uuid.uuid4(),
            email=f"photo-source-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Photo Source User",
            token_version=1,
            is_active=True,
        )
        db.add(source_user)
        db.flush()
        source_membership = Membership(
            id=uuid.uuid4(),
            user_id=source_user.id,
            organization_id=source_org.id,
            role=Role.DEVELOPER.value,
        )
        db.add(source_membership)
        db.flush()

        donor = donor_service.create_donor(
            db,
            source_org.id,
            source_user.id,
            DonorCreate(
                donor_type="egg",
                full_name="Portable Photo Donor",
                email="portable-photo@example.com",
                education="Bachelor's degree",
            ),
        )
        raw_photo = _png_bytes()
        attachment = attachment_service.upload_attachment(
            db=db,
            org_id=source_org.id,
            user_id=source_user.id,
            donor_id=donor.id,
            filename="profile.png",
            content_type="image/png",
            file=io.BytesIO(raw_photo),
            file_size=len(raw_photo),
            allowed_extensions={"png", "jpg", "jpeg"},
            allowed_mime_types={"image/png", "image/jpeg"},
        )
        attachment_service.set_donor_profile_photo(
            db,
            donor=donor,
            attachment=attachment,
            user_id=source_user.id,
        )
        db.commit()
        source_history = (
            db.query(DonorStatusHistory)
            .filter(DonorStatusHistory.donor_id == donor.id)
            .one()
        )
        source_history_id = source_history.id
        source_history_effective_at = source_history.effective_at
        source_history_recorded_at = source_history.recorded_at

        source_storage_key = attachment.storage_key
        exported_photo = attachment_service.load_file_bytes(source_storage_key)
        config_zip = admin_export_service.build_org_config_zip(db, source_org.id)
        with zipfile.ZipFile(io.BytesIO(config_zip)) as archive:
            config_payload = {
                name: json.loads(archive.read(name).decode("utf-8"))
                for name in archive.namelist()
            }
        config_payload["organization.json"]["slug"] = test_org.slug
        config_zip = _build_config_zip(config_payload)
        donors_csv = "".join(
            admin_export_service.stream_donors_csv(db, source_org.id)
        ).encode("utf-8")
        exported_row = next(csv.DictReader(io.StringIO(donors_csv.decode("utf-8"))))
        assert exported_row["profile_photo_filename"] == "profile.png"
        assert base64.b64decode(exported_row["profile_photo_bytes_base64"], validate=True) == (
            exported_photo
        )
        exported_history = json.loads(exported_row["status_history_json"])
        assert [event["id"] for event in exported_history["events"]] == [
            str(source_history_id)
        ]

        donor_id = donor.id
        attachment_id = attachment.id
        attachment_service.delete_file(source_storage_key)
        donor.profile_photo_attachment_id = None
        db.flush()
        db.delete(attachment)
        db.delete(donor)
        db.delete(source_membership)
        for source_pipeline in (
            db.query(Pipeline).filter(Pipeline.organization_id == source_org.id).all()
        ):
            db.delete(source_pipeline)
        db.commit()

        response = await authed_client.post(
            "/admin/imports/all",
            files={
                "config_zip": ("config.zip", config_zip, "application/zip"),
                "surrogates_csv": ("surrogates.csv", b"id\n", "text/csv"),
                "donors_csv": ("donors.csv", donors_csv, "text/csv"),
            },
        )

        assert response.status_code == 200, response.text
        imported_donor = db.get(Donor, donor_id)
        imported_attachment = db.get(Attachment, attachment_id)
        assert imported_donor is not None
        assert imported_donor.organization_id == test_org.id
        assert imported_donor.profile_photo_attachment_id == attachment_id
        assert imported_attachment is not None
        assert imported_attachment.organization_id == test_org.id
        assert imported_attachment.donor_id == donor_id
        assert imported_attachment.storage_key.startswith(
            f"{test_org.id}/donors/{donor_id}/profile/"
        )
        assert ".." not in imported_attachment.storage_key
        restored_photo = attachment_service.load_file_bytes(imported_attachment.storage_key)
        assert imported_attachment.file_size == len(restored_photo)
        assert imported_attachment.checksum_sha256 == hashlib.sha256(restored_photo).hexdigest()
        from PIL import Image

        restored_image = Image.open(io.BytesIO(restored_photo))
        assert restored_image.size == (6, 6)
        assert restored_image.getpixel((0, 0)) == (32, 96, 192)
        history = (
            db.query(DonorStatusHistory)
            .filter(DonorStatusHistory.donor_id == donor_id)
            .one()
        )
        assert history.id == source_history_id
        assert history.organization_id == test_org.id
        assert history.changed_by_user_id == source_user.id
        assert history.new_stage_id == imported_donor.stage_id
        assert history.effective_at == source_history_effective_at
        assert history.recorded_at == source_history_recorded_at
        assert history.reason == "Initial creation"

    @pytest.mark.asyncio
    async def test_import_donor_photo_ignores_untrusted_path_and_rejects_cross_org_id(
        self,
        authed_client,
        db,
        test_org,
        test_user,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)
        pipeline = pipeline_service.get_or_create_default_pipeline(
            db,
            test_org.id,
            entity_type="egg_donor",
        )
        stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
        assert stage is not None
        payload = _png_bytes()
        checksum = hashlib.sha256(payload).hexdigest()
        donor_id = uuid.uuid4()
        attachment_id = uuid.uuid4()
        safe_csv = _build_surrogates_csv(
            [
                {
                    "id": str(donor_id),
                    "donor_number": "D10010",
                    "donor_type": "egg",
                    "stage_id": str(stage.id),
                    "full_name": "Path Safe Donor",
                    "email": "path-safe@example.com",
                    "profile_photo_attachment_id": str(attachment_id),
                    "profile_photo_filename": "../../outside.png",
                    "profile_photo_storage_key": "../../outside.png",
                    "profile_photo_content_type": "image/png",
                    "profile_photo_file_size": str(len(payload)),
                    "profile_photo_checksum_sha256": checksum,
                    "profile_photo_scan_status": "clean",
                    "profile_photo_quarantined": "false",
                    "profile_photo_bytes_base64": base64.b64encode(payload).decode("ascii"),
                }
            ]
        )

        imported = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", safe_csv, "text/csv")},
        )

        assert imported.status_code == 200, imported.text
        attachment = db.get(Attachment, attachment_id)
        assert attachment is not None
        assert attachment.organization_id == test_org.id
        assert attachment.donor_id == donor_id
        assert attachment.storage_key.startswith(
            f"{test_org.id}/donors/{donor_id}/profile/"
        )
        assert not (tmp_path / "outside.png").exists()
        attachment_service.delete_file(attachment.storage_key)
        db.delete(db.get(Donor, donor_id))
        db.commit()

        foreign_org = Organization(
            id=uuid.uuid4(),
            name="Foreign Attachment Owner",
            slug=f"foreign-attachment-owner-{uuid.uuid4().hex[:8]}",
            ai_enabled=True,
        )
        db.add(foreign_org)
        db.flush()
        foreign_attachment_id = uuid.uuid4()
        foreign_key = f"{foreign_org.id}/foreign/{foreign_attachment_id}.png"
        attachment_service.store_file(foreign_key, io.BytesIO(payload), "image/png")
        foreign_attachment = Attachment(
            id=foreign_attachment_id,
            organization_id=foreign_org.id,
            filename="foreign.png",
            storage_key=foreign_key,
            content_type="image/png",
            file_size=len(payload),
            checksum_sha256=checksum,
            scan_status="clean",
            quarantined=False,
        )
        db.add(foreign_attachment)
        db.commit()

        second_donor_id = uuid.uuid4()
        collision_csv = _build_surrogates_csv(
            [
                {
                    "id": str(second_donor_id),
                    "donor_number": "D10011",
                    "donor_type": "egg",
                    "stage_id": str(stage.id),
                    "full_name": "Cross Org Collision Donor",
                    "email": "cross-org-photo@example.com",
                    "profile_photo_attachment_id": str(foreign_attachment_id),
                    "profile_photo_filename": "profile.png",
                    "profile_photo_content_type": "image/png",
                    "profile_photo_file_size": str(len(payload)),
                    "profile_photo_checksum_sha256": checksum,
                    "profile_photo_scan_status": "clean",
                    "profile_photo_quarantined": "false",
                    "profile_photo_bytes_base64": base64.b64encode(payload).decode("ascii"),
                }
            ]
        )
        failure_savepoint = db.begin_nested()

        def rollback_failure_savepoint() -> None:
            if failure_savepoint.is_active:
                failure_savepoint.rollback()

        monkeypatch.setattr(db, "rollback", rollback_failure_savepoint)
        collision = await authed_client.post(
            "/admin/imports/donors",
            files={"donors_csv": ("donors.csv", collision_csv, "text/csv")},
        )

        assert collision.status_code == 400
        assert "Profile photo attachment id is unavailable" in collision.json()["detail"]
        assert db.get(Donor, second_donor_id) is None
        assert db.get(Attachment, foreign_attachment_id).organization_id == foreign_org.id
        assert attachment_service.load_file_bytes(foreign_key) == payload

    @pytest.mark.asyncio
    async def test_import_all_rolls_back_config_records_and_photo_storage_on_donor_error(
        self,
        authed_client,
        db,
        test_org,
        test_user,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)
        test_org_id = test_org.id
        original_org_name = test_org.name
        surrogate_pipeline_id = uuid.uuid4()
        surrogate_stage_id = uuid.uuid4()
        donor_pipeline_id = uuid.uuid4()
        donor_stage_id = uuid.uuid4()
        config_zip = _build_config_zip(
            {
                "organization.json": {
                    "name": "Must Roll Back",
                    "slug": test_org.slug,
                },
                "users.json": [],
                "memberships.json": [],
                "queues.json": [],
                "queue_members.json": [],
                "role_permissions.json": [],
                "user_permission_overrides.json": [],
                "pipelines.json": [
                    {
                        "id": str(surrogate_pipeline_id),
                        "name": "Surrogates",
                        "entity_type": "surrogate",
                        "is_default": True,
                        "current_version": 1,
                        "feature_config": {},
                        "stages": [
                            {
                                "id": str(surrogate_stage_id),
                                "stage_key": "new",
                                "slug": "new",
                                "label": "New",
                                "color": "#2563EB",
                                "order": 1,
                                "stage_type": "intake",
                                "semantics": {},
                                "is_active": True,
                                "is_intake_stage": True,
                            }
                        ],
                    },
                    {
                        "id": str(donor_pipeline_id),
                        "name": "Egg Donors",
                        "entity_type": "egg_donor",
                        "is_default": True,
                        "current_version": 1,
                        "feature_config": {},
                        "stages": [
                            {
                                "id": str(donor_stage_id),
                                "stage_key": "new",
                                "slug": "new",
                                "label": "New",
                                "color": "#2563EB",
                                "order": 1,
                                "stage_type": "intake",
                                "semantics": {},
                                "is_active": True,
                                "is_intake_stage": True,
                            }
                        ],
                    },
                ],
            }
        )
        surrogate_id = uuid.uuid4()
        surrogates_csv = _build_surrogates_csv(
            [
                {
                    "id": str(surrogate_id),
                    "surrogate_number": "S10001",
                    "status_label": "New",
                    "stage_id": str(surrogate_stage_id),
                    "source": "import",
                    "owner_type": "user",
                    "owner_id": str(test_user.id),
                    "full_name": "Atomic Surrogate",
                    "email": "atomic-surrogate@example.com",
                }
            ]
        )
        photo = _png_bytes()
        attachment_id = uuid.uuid4()
        valid_donor_id = uuid.uuid4()
        invalid_donor_id = uuid.uuid4()
        status_history_id = uuid.uuid4()
        status_history_json = json.dumps(
            {
                "version": 1,
                "events": [
                    {
                        "id": str(status_history_id),
                        "new_stage_id": str(donor_stage_id),
                        "new_stage_key": "new",
                        "new_status": "new",
                        "new_label_snapshot": "New",
                        "reason": "Must roll back",
                        "effective_at": "2026-08-20T12:00:00+00:00",
                        "recorded_at": "2026-08-20T12:00:00+00:00",
                    }
                ],
            }
        )
        donors_csv = _build_surrogates_csv(
            [
                {
                    "id": str(valid_donor_id),
                    "donor_number": "D10020",
                    "donor_type": "egg",
                    "stage_id": str(donor_stage_id),
                    "full_name": "Atomic Photo Donor",
                    "email": "atomic-photo@example.com",
                    "profile_photo_attachment_id": str(attachment_id),
                    "profile_photo_filename": "profile.png",
                    "profile_photo_content_type": "image/png",
                    "profile_photo_file_size": str(len(photo)),
                    "profile_photo_checksum_sha256": hashlib.sha256(photo).hexdigest(),
                    "profile_photo_scan_status": "clean",
                    "profile_photo_quarantined": "false",
                    "profile_photo_bytes_base64": base64.b64encode(photo).decode("ascii"),
                    "status_history_json": status_history_json,
                },
                {
                    "id": str(invalid_donor_id),
                    "donor_number": "D10021",
                    "donor_type": "egg",
                    "stage_id": str(donor_stage_id),
                    "full_name": "Invalid Donor",
                    "email": "",
                },
            ]
        )
        expected_storage_key = (
            f"{test_org_id}/donors/{valid_donor_id}/profile/{attachment_id}.png"
        )
        failure_savepoint = db.begin_nested()

        def rollback_failure_savepoint() -> None:
            if failure_savepoint.is_active:
                failure_savepoint.rollback()

        monkeypatch.setattr(db, "rollback", rollback_failure_savepoint)

        response = await authed_client.post(
            "/admin/imports/all",
            files={
                "config_zip": ("config.zip", config_zip, "application/zip"),
                "surrogates_csv": ("surrogates.csv", surrogates_csv, "text/csv"),
                "donors_csv": ("donors.csv", donors_csv, "text/csv"),
            },
        )

        assert response.status_code == 400
        assert "Missing email" in response.json()["detail"]
        db.expire_all()
        assert db.get(Organization, test_org_id).name == original_org_name
        assert db.get(Pipeline, surrogate_pipeline_id) is None
        assert db.get(Pipeline, donor_pipeline_id) is None
        assert db.get(Surrogate, surrogate_id) is None
        assert db.get(Donor, valid_donor_id) is None
        assert db.get(Donor, invalid_donor_id) is None
        assert db.get(DonorStatusHistory, status_history_id) is None
        assert db.get(Attachment, attachment_id) is None
        assert db.scalar(
            db.query(OrgCounter)
            .filter(
                OrgCounter.organization_id == test_org_id,
                OrgCounter.counter_type == "donor_number",
            )
            .exists()
            .select()
        ) is False
        assert not os.path.exists(attachment_service.resolve_local_storage_path(expected_storage_key))
