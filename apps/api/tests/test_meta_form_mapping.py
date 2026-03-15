"""Tests for Meta lead form mapping workflow."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_meta_form_mapping_preview_generates_sample_rows(
    authed_client: AsyncClient, db, test_org
):
    from app.db.models import MetaForm, MetaFormVersion

    form = MetaForm(
        organization_id=test_org.id,
        page_id="page_123",
        form_external_id="form_ext_1",
        form_name="Lead Form",
    )
    db.add(form)
    db.flush()

    questions = [
        {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
        {"key": "email", "type": "EMAIL", "label": "Email"},
        {"key": "phone_number", "type": "PHONE", "label": "Phone"},
    ]

    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=questions,
        schema_hash="hash_1",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id
    db.commit()

    response = await authed_client.get(f"/integrations/meta/forms/{form.id}/mapping")
    assert response.status_code == 200

    data = response.json()
    assert data["form"]["id"] == str(form.id)
    assert data["sample_rows"]
    sample = data["sample_rows"][0]
    assert "full_name" in sample
    assert "email" in sample
    assert "created_time" in sample
    assert "meta_ad_id" in sample
    assert "meta_ad_name" in sample
    assert "meta_form_name" in sample
    assert "meta_platform" in sample
    assert data["has_live_leads"] is False
    assert any(s["csv_column"] == "full_name" for s in data["column_suggestions"])
    assert any(s["csv_column"] == "created_time" for s in data["column_suggestions"])


@pytest.mark.asyncio
async def test_meta_form_mapping_save_enqueues_reprocess_job(
    authed_client: AsyncClient, db, test_org, test_user
):
    from app.db.enums import JobType
    from app.db.models import MetaForm, MetaFormVersion, MetaLead, Job

    form = MetaForm(
        organization_id=test_org.id,
        page_id="page_456",
        form_external_id="form_ext_2",
        form_name="Lead Form 2",
    )
    db.add(form)
    db.flush()

    questions = [
        {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
        {"key": "email", "type": "EMAIL", "label": "Email"},
    ]
    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=questions,
        schema_hash="hash_2",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id

    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_123",
        meta_form_id="form_ext_2",
        meta_page_id="page_456",
        field_data={"full_name": "Test User", "email": "test@example.com"},
        field_data_raw={"full_name": "Test User", "email": "test@example.com"},
        meta_created_time=datetime.now(timezone.utc),
    )
    db.add(lead)
    db.commit()

    payload = {
        "column_mappings": [
            {
                "csv_column": "full_name",
                "surrogate_field": "full_name",
                "transformation": None,
                "action": "map",
                "custom_field_key": None,
            },
            {
                "csv_column": "email",
                "surrogate_field": "email",
                "transformation": None,
                "action": "map",
                "custom_field_key": None,
            },
        ],
        "unknown_column_behavior": "metadata",
    }

    response = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json=payload,
    )
    assert response.status_code == 200

    job = (
        db.query(Job)
        .filter(Job.job_type == JobType.META_LEAD_REPROCESS_FORM.value)
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    assert job.payload.get("form_id") == str(form.id)
    assert job.payload.get("lead_ids") == [str(lead.id)]


@pytest.mark.asyncio
async def test_meta_form_mapping_unconverted_leads_endpoint_returns_failure_details(
    authed_client: AsyncClient, db, test_org
):
    from app.db.models import MetaForm, MetaFormVersion, MetaLead
    from app.schemas.surrogate import SurrogateCreate
    from app.services import surrogate_service

    form = MetaForm(
        organization_id=test_org.id,
        page_id="page_failed",
        form_external_id="form_failed",
        form_name="Failed Lead Form",
    )
    db.add(form)
    db.flush()

    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=[
            {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
            {"key": "email", "type": "EMAIL", "label": "Email"},
        ],
        schema_hash="hash_failed",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id

    failed = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_failed",
        meta_form_id="form_failed",
        meta_page_id="page_failed",
        field_data={"full_name": "Failed Lead", "email": "failed@example.com"},
        field_data_raw={"full_name": "Failed Lead", "email": "failed@example.com"},
        meta_created_time=datetime(2026, 2, 1, 14, 30, tzinfo=timezone.utc),
        status="convert_failed",
        conversion_error="Missing required fields: phone_number",
    )
    duplicate = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_duplicate",
        meta_form_id="form_failed",
        meta_page_id="page_failed",
        field_data={"full_name": "Duplicate Lead", "email": "dupe@example.com"},
        field_data_raw={"full_name": "Duplicate Lead", "email": "dupe@example.com"},
        meta_created_time=datetime(2026, 2, 1, 14, 45, tzinfo=timezone.utc),
        status="convert_failed",
        conversion_error="duplicate key value violates unique constraint",
    )
    test_lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="4105684652985314",
        meta_form_id="form_failed",
        meta_page_id="page_failed",
        field_data={
            "full_name": "test lead: dummy data for full_name",
            "email": "test@fb.com",
        },
        field_data_raw={
            "full_name": "test lead: dummy data for full_name",
            "email": "test@fb.com",
        },
        meta_created_time=datetime(2026, 2, 1, 14, 50, tzinfo=timezone.utc),
        status="convert_failed",
        conversion_error="Validation failed",
    )
    converted = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_converted",
        meta_form_id="form_failed",
        meta_page_id="page_failed",
        field_data={"full_name": "Converted Lead", "email": "done@example.com"},
        field_data_raw={"full_name": "Converted Lead", "email": "done@example.com"},
        meta_created_time=datetime(2026, 2, 1, 15, 30, tzinfo=timezone.utc),
        status="converted",
        is_converted=True,
    )
    db.add_all([failed, duplicate, test_lead, converted])
    surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=None,
        data=SurrogateCreate(full_name="Existing Duplicate", email="dupe@example.com"),
    )
    db.commit()

    response = await authed_client.get(f"/integrations/meta/forms/{form.id}/unconverted-leads")
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 3
    assert body["eligible_count"] == 1
    assert body["blocked_count"] == 2
    items = {item["meta_lead_id"]: item for item in body["items"]}

    assert items["lead_failed"]["status"] == "convert_failed"
    assert items["lead_failed"]["conversion_error"] == "Missing required fields: phone_number"
    assert items["lead_failed"]["full_name"] == "Failed Lead"
    assert items["lead_failed"]["email"] == "failed@example.com"
    assert items["lead_failed"]["is_converted"] is False
    assert items["lead_failed"]["reprocess_eligible"] is True
    assert items["lead_failed"]["reprocess_block_reason"] is None

    assert items["lead_duplicate"]["reprocess_eligible"] is False
    assert items["lead_duplicate"]["reprocess_block_reason"] == "duplicate_email"

    assert items["4105684652985314"]["reprocess_eligible"] is False
    assert items["4105684652985314"]["reprocess_block_reason"] == "test_lead"


@pytest.mark.asyncio
async def test_meta_form_reconvert_endpoint_queues_only_eligible_leads(
    authed_client: AsyncClient, db, test_org
):
    from app.db.enums import JobType
    from app.db.models import Job, MetaForm, MetaFormVersion, MetaLead
    from app.schemas.surrogate import SurrogateCreate
    from app.services import surrogate_service

    form = MetaForm(
        organization_id=test_org.id,
        page_id="page_reconvert",
        form_external_id="form_reconvert",
        form_name="Reconvert Form",
        mapping_status="mapped",
    )
    db.add(form)
    db.flush()

    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=[
            {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
            {"key": "email", "type": "EMAIL", "label": "Email"},
        ],
        schema_hash="hash_reconvert",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id
    form.mapping_version_id = version.id
    form.mapping_rules = [
        {
            "csv_column": "full_name",
            "surrogate_field": "full_name",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "email",
            "surrogate_field": "email",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
    ]

    eligible = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_ok",
        meta_form_id="form_reconvert",
        meta_page_id="page_reconvert",
        field_data={"full_name": "Eligible", "email": "eligible@example.com"},
        field_data_raw={"full_name": "Eligible", "email": "eligible@example.com"},
        meta_created_time=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        status="convert_failed",
        conversion_error="old parser error",
    )
    duplicate = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_dup",
        meta_form_id="form_reconvert",
        meta_page_id="page_reconvert",
        field_data={"full_name": "Dup", "email": "dupe@example.com"},
        field_data_raw={"full_name": "Dup", "email": "dupe@example.com"},
        meta_created_time=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc),
        status="convert_failed",
        conversion_error="duplicate",
    )
    test_lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_test",
        meta_form_id="form_reconvert",
        meta_page_id="page_reconvert",
        field_data={"full_name": "test lead: dummy data for full_name", "email": "test@fb.com"},
        field_data_raw={"full_name": "test lead: dummy data for full_name", "email": "test@fb.com"},
        meta_created_time=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
        status="convert_failed",
        conversion_error="validation",
    )
    db.add_all([eligible, duplicate, test_lead])
    surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=None,
        data=SurrogateCreate(full_name="Existing Duplicate", email="dupe@example.com"),
    )
    db.commit()

    response = await authed_client.post(f"/integrations/meta/forms/{form.id}/reconvert", json={})
    assert response.status_code == 200

    body = response.json()
    assert body["queued_count"] == 1
    assert body["blocked_count"] == 2
    assert body["blocked_reasons"] == {"duplicate_email": 1, "test_lead": 1}

    job = (
        db.query(Job)
        .filter(Job.job_type == JobType.META_LEAD_REPROCESS_FORM.value)
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    assert job.payload["form_id"] == str(form.id)
    assert job.payload["lead_ids"] == [str(eligible.id)]


def test_meta_lead_mapping_creates_review_task_on_unmapped_fields(db, test_org, test_user):
    from app.db.enums import TaskType
    from app.db.models import MetaForm, MetaFormVersion, MetaLead, Task
    from app.services import meta_lead_service

    form = MetaForm(
        organization_id=test_org.id,
        page_id="page_789",
        form_external_id="form_ext_3",
        form_name="Lead Form 3",
        mapping_status="mapped",
    )
    db.add(form)
    db.flush()

    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=[
            {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
            {"key": "email", "type": "EMAIL", "label": "Email"},
            {"key": "extra_field", "type": "SHORT_ANSWER", "label": "Extra"},
        ],
        schema_hash="hash_3",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id

    created_time = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_789",
        meta_form_id="form_ext_3",
        meta_page_id="page_789",
        field_data={"full_name": "Test User", "email": "test@example.com"},
        field_data_raw={
            "full_name": "Test User",
            "email": "test@example.com",
            "extra_field": "Extra value",
        },
        meta_created_time=created_time,
    )
    db.add(lead)
    db.commit()

    mappings = [
        {
            "csv_column": "full_name",
            "surrogate_field": "full_name",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "email",
            "surrogate_field": "email",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "created_time",
            "surrogate_field": "created_at",
            "transformation": "datetime_flexible",
            "action": "map",
            "custom_field_key": None,
        },
    ]

    surrogate, error = meta_lead_service.convert_to_surrogate_with_mapping(
        db=db,
        meta_lead=lead,
        mapping_rules=mappings,
        unknown_column_behavior="metadata",
        user_id=test_user.id,
    )

    assert error is None
    assert surrogate is not None
    assert surrogate.created_at.replace(tzinfo=timezone.utc) == created_time

    review_task = (
        db.query(Task)
        .filter(
            Task.organization_id == test_org.id,
            Task.task_type == TaskType.REVIEW,
            Task.title == f"Review Meta form mapping: {form.form_name}",
        )
        .first()
    )
    assert review_task is not None


def test_meta_lead_mapping_persists_meta_tracking_metadata(db, test_org, test_user):
    from app.db.models import MetaForm, MetaFormVersion, MetaLead
    from app.services import meta_lead_service

    form = MetaForm(
        organization_id=test_org.id,
        page_id="page_meta",
        form_external_id="form_ext_meta",
        form_name="Meta Form",
        mapping_status="mapped",
    )
    db.add(form)
    db.flush()

    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=[
            {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
            {"key": "email", "type": "EMAIL", "label": "Email"},
        ],
        schema_hash="hash_meta",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id

    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_meta",
        meta_form_id=form.form_external_id,
        meta_page_id="page_meta",
        field_data={"full_name": "Test User", "email": "test@example.com"},
        field_data_raw={
            "full_name": "Test User",
            "email": "test@example.com",
            "meta_ad_id": "ad_123",
            "meta_ad_name": "Ad Name",
            "meta_platform": "facebook",
        },
    )
    db.add(lead)
    db.commit()

    mappings = [
        {
            "csv_column": "full_name",
            "surrogate_field": "full_name",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "email",
            "surrogate_field": "email",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
    ]

    surrogate, error = meta_lead_service.convert_to_surrogate_with_mapping(
        db=db,
        meta_lead=lead,
        mapping_rules=mappings,
        unknown_column_behavior="ignore",
        user_id=test_user.id,
    )

    assert error is None
    assert surrogate is not None
    assert surrogate.meta_ad_external_id == "ad_123"
    assert surrogate.import_metadata is not None
    assert surrogate.import_metadata.get("meta_ad_id") == "ad_123"
    assert surrogate.import_metadata.get("meta_ad_name") == "Ad Name"
    assert surrogate.import_metadata.get("meta_form_name") == "Meta Form"
    assert surrogate.import_metadata.get("meta_platform") == "facebook"


def test_meta_lead_mapping_applies_default_transformers_when_mapping_has_none(
    db, test_org, test_user
):
    from decimal import Decimal

    from app.db.models import MetaLead
    from app.services import meta_lead_service

    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_transform_defaults",
        meta_form_id="form_transform_defaults",
        meta_page_id="page_transform_defaults",
        field_data={
            "full_name": "Conversion Test",
            "email": "convert@example.com",
            "height": "5 feet 4 inches",
            "deliveries": "One",
            "num_csections": "No",
            "phone": "(555) 222-3333",
            "state": "California",
        },
        field_data_raw={
            "full_name": "Conversion Test",
            "email": "convert@example.com",
            "height": "5 feet 4 inches",
            "deliveries": "One",
            "num_csections": "No",
            "phone": "(555) 222-3333",
            "state": "California",
        },
        meta_created_time=datetime.now(timezone.utc),
    )
    db.add(lead)
    db.commit()

    mappings = [
        {
            "csv_column": "full_name",
            "surrogate_field": "full_name",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "email",
            "surrogate_field": "email",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "height",
            "surrogate_field": "height_ft",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "deliveries",
            "surrogate_field": "num_deliveries",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "num_csections",
            "surrogate_field": "num_csections",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "phone",
            "surrogate_field": "phone",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "state",
            "surrogate_field": "state",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
    ]

    surrogate, error = meta_lead_service.convert_to_surrogate_with_mapping(
        db=db,
        meta_lead=lead,
        mapping_rules=mappings,
        unknown_column_behavior="metadata",
        user_id=test_user.id,
    )

    assert error is None
    assert surrogate is not None
    assert surrogate.height_ft == Decimal("5.3")
    assert surrogate.num_deliveries == 1
    assert surrogate.num_csections == 0
    assert surrogate.phone == "+15552223333"
    assert surrogate.state == "CA"


def test_meta_lead_conversion_failure_records_system_alert(monkeypatch, db, test_org, test_user):
    from types import SimpleNamespace

    from app.db.models import MetaLead
    from app.schemas.surrogate import SurrogateCreate
    from app.services import meta_lead_service
    from app.services import surrogate_service

    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.services.meta_lead_service._record_conversion_failure_alert",
        lambda lead, exc: captured.append((lead.meta_lead_id, type(exc).__name__)),
    )

    surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=SurrogateCreate(full_name="Existing Alert Failure", email="alert@example.com"),
    )

    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="lead_alert_failure",
        meta_form_id="form_alert_failure",
        meta_page_id="page_alert_failure",
        field_data={
            "full_name": "Alert Failure",
            "email": "alert@example.com",
        },
        field_data_raw={
            "full_name": "Alert Failure",
            "email": "alert@example.com",
        },
        meta_created_time=datetime.now(timezone.utc),
    )
    db.add(lead)
    db.commit()
    persisted_lead_id = lead.id
    persisted_lead = SimpleNamespace(
        meta_lead_id="lead_alert_failure",
        conversion_error=None,
        unmapped_fields=None,
    )

    class _FakeFailureSession:
        def get(self, model, value):
            return persisted_lead if value == persisted_lead_id else None

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        "app.services.meta_lead_service.SessionLocal", lambda: _FakeFailureSession()
    )

    mappings = [
        {
            "csv_column": "full_name",
            "surrogate_field": "full_name",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "email",
            "surrogate_field": "email",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
    ]

    surrogate, error = meta_lead_service.convert_to_surrogate_with_mapping(
        db=db,
        meta_lead=lead,
        mapping_rules=mappings,
        unknown_column_behavior="metadata",
        user_id=test_user.id,
    )

    assert surrogate is None
    assert error is not None
    assert captured
    assert captured[0] == ("lead_alert_failure", "IntegrityError")


@pytest.mark.parametrize(
    ("meta_lead_id", "height_value", "expected_height", "num_csections_value"),
    [
        ("zapier-9c807da9-d5f9-423f-bacd-9732aa39ca5f", "4”ft 11", "4.9", None),
        ("zapier-71fef5b9-320d-4107-9d97-dcc49dd10a6c", "5’3inch", "5.3", "No"),
    ],
)
def test_meta_lead_mapping_handles_additional_height_formats(
    db, test_org, test_user, meta_lead_id, height_value, expected_height, num_csections_value
):
    from decimal import Decimal

    from app.db.models import MetaLead
    from app.services import meta_lead_service

    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id=meta_lead_id,
        meta_form_id="form_height_formats",
        meta_page_id="page_height_formats",
        field_data={
            "full_name": "Height Test",
            "email": f"{expected_height.replace('.', '')}@example.com",
            "height": height_value,
            "num_csections": num_csections_value,
        },
        field_data_raw={
            "full_name": "Height Test",
            "email": f"{expected_height.replace('.', '')}@example.com",
            "height": height_value,
            "num_csections": num_csections_value,
        },
        meta_created_time=datetime.now(timezone.utc),
    )
    db.add(lead)
    db.commit()

    mappings = [
        {
            "csv_column": "full_name",
            "surrogate_field": "full_name",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "email",
            "surrogate_field": "email",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "height",
            "surrogate_field": "height_ft",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "num_csections",
            "surrogate_field": "num_csections",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
    ]

    surrogate, error = meta_lead_service.convert_to_surrogate_with_mapping(
        db=db,
        meta_lead=lead,
        mapping_rules=mappings,
        unknown_column_behavior="metadata",
        user_id=test_user.id,
    )

    assert error is None
    assert surrogate is not None
    assert surrogate.height_ft == Decimal(expected_height)
    if num_csections_value is not None:
        assert surrogate.num_csections == 0


def test_meta_lead_mapping_converts_num_csections_word_none(db, test_org, test_user):
    from app.db.models import MetaLead
    from app.services import meta_lead_service

    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="zapier-013ae5a7-b71a-4a9f-a4b6-17c6eb502c02",
        meta_form_id="form_num_csections_words",
        meta_page_id="page_num_csections_words",
        field_data={
            "full_name": "LaChicanaCali",
            "email": "0569cali@gmail.com",
            "num_csections": "No",
        },
        field_data_raw={
            "full_name": "LaChicanaCali",
            "email": "0569cali@gmail.com",
            "num_csections": "No",
        },
        meta_created_time=datetime.now(timezone.utc),
    )
    db.add(lead)
    db.commit()

    mappings = [
        {
            "csv_column": "full_name",
            "surrogate_field": "full_name",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "email",
            "surrogate_field": "email",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "num_csections",
            "surrogate_field": "num_csections",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
    ]

    surrogate, error = meta_lead_service.convert_to_surrogate_with_mapping(
        db=db,
        meta_lead=lead,
        mapping_rules=mappings,
        unknown_column_behavior="metadata",
        user_id=test_user.id,
    )

    assert error is None
    assert surrogate is not None
    assert surrogate.num_csections == 0


def test_meta_lead_mapping_drops_invalid_optional_phone(db, test_org, test_user):
    from app.db.models import MetaLead
    from app.services import meta_lead_service

    lead = MetaLead(
        organization_id=test_org.id,
        meta_lead_id="zapier-ecc8aa50-fa90-4e5a-ba26-da9bb2e244f8",
        meta_form_id="form_bad_phone",
        meta_page_id="page_bad_phone",
        field_data={
            "full_name": "Regina Reg",
            "email": "ginas89@hotmail.com",
            "phone": "+659566490211",
        },
        field_data_raw={
            "full_name": "Regina Reg",
            "email": "ginas89@hotmail.com",
            "phone": "+659566490211",
        },
        meta_created_time=datetime.now(timezone.utc),
    )
    db.add(lead)
    db.commit()

    mappings = [
        {
            "csv_column": "full_name",
            "surrogate_field": "full_name",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "email",
            "surrogate_field": "email",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "phone",
            "surrogate_field": "phone",
            "transformation": None,
            "action": "map",
            "custom_field_key": None,
        },
    ]

    surrogate, error = meta_lead_service.convert_to_surrogate_with_mapping(
        db=db,
        meta_lead=lead,
        mapping_rules=mappings,
        unknown_column_behavior="metadata",
        user_id=test_user.id,
    )

    assert error is None
    assert surrogate is not None
    assert surrogate.phone is None
