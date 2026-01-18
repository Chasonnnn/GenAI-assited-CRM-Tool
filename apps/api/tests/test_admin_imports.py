import csv
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
from app.db.enums import Role
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
    MetaLead,
    Organization,
    OrgCounter,
    Surrogate,
    User,
    WorkflowTemplate,
)
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
        counter_updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        config_payload = {
            "organization.json": {
                "id": str(test_org.id),
                "name": "Imported Org",
                "slug": test_org.slug,
                "timezone": "America/Los_Angeles",
                "ai_enabled": True,
                "current_version": 1,
                "portal_domain": "portal.example.com",
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
            "pipelines.json": [],
            "email_templates.json": [],
            "workflows.json": [],
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
        assert refreshed_org.portal_domain == "portal.example.com"
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

        availability_rule = (
            db.query(AvailabilityRule)
            .filter(AvailabilityRule.id == availability_rule_id)
            .first()
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
            db.query(WorkflowTemplate)
            .filter(WorkflowTemplate.id == workflow_template_id)
            .first()
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
