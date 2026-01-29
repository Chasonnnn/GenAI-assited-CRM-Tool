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
