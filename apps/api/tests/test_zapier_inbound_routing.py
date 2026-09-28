"""Zapier inbound leads always reach a form, and test leads leave forms unchanged."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.models import MetaForm, MetaFormVersion, MetaLead, Task
from app.services import meta_form_mapping_service, meta_lead_service, zapier_settings_service
from tests.test_zapier_webhooks import (
    _client_for,
    _create_mapped_meta_form,
    _integration_user_with_donor_access,
)

FIELDS = [
    {"name": "full_name", "values": ["Routing Lead"]},
    {"name": "email", "values": ["routing-lead@example.com"]},
]


def _webhook(db, org_id) -> tuple[str, str]:
    settings = zapier_settings_service.get_or_create_settings(db, org_id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)
    return settings.webhook_id, secret


async def _post(client, db, org_id, payload) -> dict:
    webhook_id, secret = _webhook(db, org_id)
    response = await client.post(
        f"/webhooks/zapier/{webhook_id}",
        json=payload,
        headers={"X-Webhook-Token": secret},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _lead(db, org_id, meta_lead_id: str) -> MetaLead:
    return (
        db.query(MetaLead)
        .filter(MetaLead.organization_id == org_id, MetaLead.meta_lead_id == meta_lead_id)
        .one()
    )


def _donor_form_without_state(db, org_id, *, lead_kind: str) -> MetaForm:
    form = MetaForm(
        organization_id=org_id,
        page_id="page-no-state",
        form_external_id=f"form-no-state-{lead_kind}",
        form_name="Donor form without state",
        lead_kind=lead_kind,
    )
    db.add(form)
    db.flush()
    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=[
            {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
            {"key": "email", "type": "EMAIL", "label": "Email"},
            {"key": "phone_number", "type": "PHONE", "label": "Phone"},
        ],
        schema_hash=f"hash-no-state-{lead_kind}",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id
    form.mapping_version_id = version.id
    form.mapping_status = "mapped"
    form.mapping_updated_at = datetime.now(UTC)
    form.mapping_rules = [
        {"csv_column": key, "surrogate_field": field, "action": "map", "transformation": None}
        for key, field in (
            ("full_name", "full_name"),
            ("email", "email"),
            ("phone_number", "phone"),
        )
    ]
    db.commit()
    return form


@pytest.mark.asyncio
@pytest.mark.parametrize("lead_kind", ["egg_donor", "sperm_donor"])
async def test_test_lead_keeps_form_schema_versions_and_mapping(
    authed_client, db, test_org, lead_kind
):
    form = _donor_form_without_state(db, test_org.id, lead_kind=lead_kind)
    version_id = form.current_version_id

    response = await authed_client.post(
        "/integrations/zapier/test-lead",
        json={"form_id": form.form_external_id},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "converted"
    assert response.json()["donor_id"]
    db.refresh(form)
    assert form.current_version_id == version_id
    assert form.mapping_version_id == version_id
    assert form.mapping_status == "mapped"
    assert form.form_name == "Donor form without state"
    assert db.query(MetaFormVersion).filter(MetaFormVersion.form_id == form.id).count() == 1


@pytest.mark.asyncio
async def test_webhook_without_lead_id_marks_generated_id_and_warns(client, db, test_org):
    _create_mapped_meta_form(db, test_org.id, None, form_external_id="form-no-lead-id")

    body = await _post(
        client, db, test_org.id, {"form_id": "form-no-lead-id", "field_data": FIELDS}
    )

    assert body["warnings"] == [
        "The payload has no lead_id, so the CRM generated one. Map the Meta lead ID to "
        "lead_id so repeated deliveries are detected as duplicates."
    ]
    lead = db.get(MetaLead, body["meta_lead_id"])
    assert lead.meta_lead_id.startswith("zapier-generated-")
    assert meta_lead_service.is_synthetic_meta_lead_id(lead.meta_lead_id)
    assert "lead_id" not in lead.field_data_raw


@pytest.mark.asyncio
async def test_webhook_with_lead_id_has_no_warnings(client, db, test_org):
    _create_mapped_meta_form(db, test_org.id, None, form_external_id="form-with-lead-id")

    body = await _post(
        client,
        db,
        test_org.id,
        {"lead_id": "123456789", "form_id": "form-with-lead-id", "field_data": FIELDS},
    )

    assert body["warnings"] == []
    assert not meta_lead_service.is_synthetic_meta_lead_id(
        _lead(db, test_org.id, "123456789").meta_lead_id
    )


@pytest.mark.asyncio
async def test_webhook_accepts_camel_case_lead_and_form_ids(client, db, test_org):
    _create_mapped_meta_form(db, test_org.id, None, form_external_id="form-camel")

    body = await _post(
        client,
        db,
        test_org.id,
        {"leadId": "lead-camel", "formId": "form-camel", "field_data": FIELDS},
    )

    assert body["status"] == "converted"
    lead = _lead(db, test_org.id, "lead-camel")
    assert lead.meta_form_id == "form-camel"
    assert "formid" not in lead.field_data_raw
    assert "leadid" not in lead.field_data_raw


@pytest.mark.asyncio
async def test_webhook_accepts_nested_form_object(client, db, test_org):
    _create_mapped_meta_form(db, test_org.id, None, form_external_id="form-object")

    body = await _post(
        client,
        db,
        test_org.id,
        {
            "lead_id": "lead-form-object",
            "form": {"id": "form-object", "name": "Object Form"},
            "field_data": FIELDS,
        },
    )

    assert body["status"] == "converted"
    lead = _lead(db, test_org.id, "lead-form-object")
    assert lead.meta_form_id == "form-object"
    assert "form" not in lead.field_data_raw


@pytest.mark.asyncio
async def test_webhook_nested_lead_keeps_outer_form_id(client, db, test_org):
    _create_mapped_meta_form(db, test_org.id, None, form_external_id="form-outer")

    body = await _post(
        client,
        db,
        test_org.id,
        {
            "form_id": "form-outer",
            "lead": {
                "lead_id": "lead-nested",
                "full_name": "Nested Lead",
                "email": "nested-lead@example.com",
            },
        },
    )

    assert body["status"] == "converted"
    assert _lead(db, test_org.id, "lead-nested").meta_form_id == "form-outer"


@pytest.mark.asyncio
async def test_webhook_nested_lead_without_form_id_attaches_to_fallback_form(
    client, db, test_org, test_user
):
    webhook_id, _ = _webhook(db, test_org.id)

    body = await _post(
        client,
        db,
        test_org.id,
        {
            "data": {
                "lead_id": "lead-no-form",
                "full_name": "No Form Lead",
                "email": "no-form-lead@example.com",
            }
        },
    )

    assert body["status"] == "awaiting_mapping"
    lead = _lead(db, test_org.id, "lead-no-form")
    assert lead.meta_form_id == f"zapier-{webhook_id}"
    form = meta_form_mapping_service.get_form_by_external_id(db, test_org.id, lead.meta_form_id)
    assert form is not None
    assert (
        db.query(Task)
        .filter(
            Task.organization_id == test_org.id,
            Task.title == f"Review Meta form mapping: {form.form_name}",
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_field_paste_reads_form_id_from_sample_data(authed_client, db, test_org):
    response = await authed_client.post(
        "/integrations/zapier/field-paste",
        json={"paste": "form_id: 555000111\nfull_name: Pat\nemail: pat@example.com"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["form_id"] == "555000111"
    assert response.json()["field_keys"] == ["full_name", "email"]


def _donor_meta_form(db, org_id, form_external_id: str) -> MetaForm:
    return _create_mapped_meta_form(
        db, org_id, None, form_external_id=form_external_id, lead_kind="egg_donor"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("can_view", "can_edit", "expected"),
    [(False, False, 403), (True, False, 403), (False, True, 403), (True, True, 200)],
)
async def test_field_paste_on_donor_form_requires_donor_view_and_edit(
    db, test_org, can_view, can_edit, expected
):
    form = _donor_meta_form(db, test_org.id, f"form-donor-paste-{uuid4().hex[:6]}")
    user = _integration_user_with_donor_access(
        db, test_org.id, can_view_donors=can_view, can_edit_donors=can_edit
    )

    async with _client_for(db, test_org.id, user) as client:
        response = await client.post(
            "/integrations/zapier/field-paste",
            json={
                "paste": "full_name: Pat\nemail: pat@example.com",
                "form_id": form.form_external_id,
            },
        )

    assert response.status_code == expected, response.text


@pytest.mark.asyncio
async def test_field_paste_on_surrogate_form_needs_no_donor_permissions(db, test_org):
    user = _integration_user_with_donor_access(db, test_org.id)

    async with _client_for(db, test_org.id, user) as client:
        response = await client.post(
            "/integrations/zapier/field-paste",
            json={
                "paste": "full_name: Pat\nemail: pat@example.com",
                "form_id": "form-surrogate-paste",
            },
        )

    assert response.status_code == 200, response.text
