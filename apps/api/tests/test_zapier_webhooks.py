"""Tests for Zapier webhook integration."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


def _create_mapped_meta_form(db, org_id, user_id: str | None, *, form_external_id: str = "form_1"):
    from app.db.models import MetaForm, MetaFormVersion

    form = MetaForm(
        organization_id=org_id,
        page_id="page_123",
        form_external_id=form_external_id,
        form_name="Lead Form",
    )
    db.add(form)
    db.flush()

    questions = [
        {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
        {"key": "email", "type": "EMAIL", "label": "Email"},
        {"key": "phone_number", "type": "PHONE", "label": "Phone"},
        {"key": "state", "type": "STATE", "label": "State"},
        {"key": "created_time", "type": "DATETIME", "label": "Submitted At"},
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
        {
            "csv_column": "phone_number",
            "surrogate_field": "phone",
            "transformation": "phone_normalize",
            "action": "map",
            "custom_field_key": None,
        },
        {
            "csv_column": "state",
            "surrogate_field": "state",
            "transformation": "state_normalize",
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
    form.mapping_status = "mapped"
    form.mapping_version_id = version.id
    form.mapping_updated_at = datetime.now(timezone.utc)
    form.mapping_updated_by_user_id = user_id
    db.commit()
    return form


class TestZapierSettings:
    def test_get_or_create_settings(self, db, test_org):
        from app.services import zapier_settings_service

        settings = zapier_settings_service.get_settings(db, test_org.id)
        assert settings is None

        settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
        assert settings is not None
        assert settings.organization_id == test_org.id
        assert settings.webhook_id
        assert settings.webhook_secret_encrypted

    def test_rotate_secret(self, db, test_org):
        from app.services import zapier_settings_service

        settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
        original = settings.webhook_secret_encrypted

        updated, secret = zapier_settings_service.rotate_webhook_secret(db, test_org.id)
        assert updated.webhook_secret_encrypted != original
        assert secret


@pytest.mark.asyncio
async def test_zapier_settings_endpoint_returns_webhook_url(
    authed_client, db, test_org, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.test", raising=False)

    res = await authed_client.get("/integrations/zapier/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["webhook_url"].startswith("https://api.test/webhooks/zapier/")
    assert data["inbound_webhooks"]


@pytest.mark.asyncio
async def test_zapier_allows_multiple_inbound_webhooks(
    authed_client, client, db, test_org, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.test", raising=False)

    res = await authed_client.get("/integrations/zapier/settings")
    assert res.status_code == 200
    data = res.json()
    assert len(data["inbound_webhooks"]) == 1

    created = await authed_client.post(
        "/integrations/zapier/webhooks",
        json={"label": "Secondary Intake"},
    )
    assert created.status_code == 200
    created_data = created.json()
    assert created_data["webhook_secret"]
    assert created_data["webhook_url"].startswith("https://api.test/webhooks/zapier/")

    res2 = await authed_client.get("/integrations/zapier/settings")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["inbound_webhooks"]) == 2

    webhook_id = created_data["webhook_id"]
    secret = created_data["webhook_secret"]
    payload = {
        "lead_id": "lead_multi_1",
        "form_id": f"zapier-{webhook_id}",
        "field_data": [
            {"name": "full_name", "values": ["Zapier Multi"]},
            {"name": "email", "values": ["multi@example.com"]},
        ],
    }
    inbound_res = await client.post(
        f"/webhooks/zapier/{webhook_id}",
        json=payload,
        headers={"X-Webhook-Token": secret},
    )
    assert inbound_res.status_code == 200


@pytest.mark.asyncio
async def test_zapier_webhook_rejects_missing_secret(client, db, test_org):
    from app.services import zapier_settings_service

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)

    res = await client.post(f"/webhooks/zapier/{settings.webhook_id}", json={"foo": "bar"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_zapier_webhook_creates_surrogate(client, db, test_org):
    from app.db.models import Surrogate
    from app.services import zapier_settings_service

    _create_mapped_meta_form(db, test_org.id, user_id=None, form_external_id="form_1")

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)

    payload = {
        "lead_id": "lead_123",
        "created_time": "2026-01-15T10:30:00-08:00",
        "ad_id": "ad_1",
        "ad_name": "Test Ad",
        "campaign_id": "camp_1",
        "campaign_name": "Campaign 1",
        "form_id": "form_1",
        "form_name": "Form 1",
        "field_data": [
            {"name": "full_name", "values": ["Jane Doe"]},
            {"name": "email", "values": ["jane@example.com"]},
            {"name": "phone_number", "values": ["(555) 123-4567"]},
            {"name": "state", "values": ["CA"]},
        ],
    }

    res = await client.post(
        f"/webhooks/zapier/{settings.webhook_id}",
        json=payload,
        headers={"X-Webhook-Token": secret},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "converted"
    assert body["duplicate"] is False

    surrogate = (
        db.query(Surrogate)
        .filter(Surrogate.organization_id == test_org.id)
        .order_by(Surrogate.created_at.desc())
        .first()
    )
    assert surrogate is not None
    assert surrogate.full_name == "Jane Doe"
    assert surrogate.email_hash
    assert surrogate.meta_ad_external_id == "ad_1"
    assert surrogate.meta_form_id == "form_1"
    assert surrogate.import_metadata.get("zapier_lead_id") == "lead_123"

    expected = datetime(2026, 1, 15, 18, 30, tzinfo=timezone.utc)
    assert surrogate.created_at.replace(tzinfo=timezone.utc) == expected


@pytest.mark.asyncio
async def test_zapier_webhook_accepts_form_encoded_payload(client, db, test_org):
    from app.db.models import Surrogate
    from app.services import zapier_settings_service

    _create_mapped_meta_form(db, test_org.id, user_id=None, form_external_id="form_form")

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)

    payload = {
        "lead_id": "lead_form",
        "form_id": "form_form",
        "full_name": "Form Lead",
        "email": "form@example.com",
        "phone_number": "(555) 123-4567",
        "state": "CA",
        "created_time": "2026-01-16T10:30:00Z",
    }

    res = await client.post(
        f"/webhooks/zapier/{settings.webhook_id}",
        data=payload,
        headers={"X-Webhook-Token": secret},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "converted"

    surrogate = (
        db.query(Surrogate)
        .filter(Surrogate.organization_id == test_org.id)
        .order_by(Surrogate.created_at.desc())
        .first()
    )
    assert surrogate is not None
    assert surrogate.full_name == "Form Lead"


@pytest.mark.asyncio
async def test_zapier_webhook_rejects_payload_too_large(client, db, test_org):
    from app.services import zapier_settings_service
    from app.services.webhooks import zapier as zapier_webhook_service

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)

    oversized = b"x" * (zapier_webhook_service.MAX_PAYLOAD_BYTES + 1)

    res = await client.post(
        f"/webhooks/zapier/{settings.webhook_id}",
        content=oversized,
        headers={
            "X-Webhook-Token": secret,
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 413


@pytest.mark.asyncio
async def test_zapier_webhook_dedupes_by_lead_id(client, db, test_org):
    from app.db.models import MetaLead, Surrogate
    from app.services import zapier_settings_service

    _create_mapped_meta_form(db, test_org.id, user_id=None, form_external_id="form_dup")

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)

    payload = {
        "lead_id": "lead_dup",
        "form_id": "form_dup",
        "field_data": [
            {"name": "full_name", "values": ["Test Lead"]},
            {"name": "email", "values": ["lead@example.com"]},
        ],
    }

    res1 = await client.post(
        f"/webhooks/zapier/{settings.webhook_id}",
        json=payload,
        headers={"X-Webhook-Token": secret},
    )
    assert res1.status_code == 200

    res2 = await client.post(
        f"/webhooks/zapier/{settings.webhook_id}",
        json=payload,
        headers={"X-Webhook-Token": secret},
    )
    assert res2.status_code == 200
    assert res2.json()["duplicate"] is True

    lead_count = db.query(MetaLead).filter(MetaLead.organization_id == test_org.id).count()
    assert lead_count == 1

    count = db.query(Surrogate).filter(Surrogate.organization_id == test_org.id).count()
    assert count == 1


@pytest.mark.asyncio
async def test_zapier_test_endpoint_creates_test_lead(authed_client, db, test_org, test_user):
    from app.db.models import MetaLead, Surrogate

    _create_mapped_meta_form(db, test_org.id, test_user.id, form_external_id="form_test")

    res = await authed_client.post(
        "/integrations/zapier/test-lead",
        json={"form_id": "form_test"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "converted"
    assert body["meta_lead_id"]

    lead = (
        db.query(MetaLead)
        .filter(MetaLead.organization_id == test_org.id)
        .order_by(MetaLead.received_at.desc())
        .first()
    )
    assert lead is not None
    assert lead.field_data_raw.get("zapier_test") is True

    surrogate = db.get(Surrogate, body["surrogate_id"])
    assert surrogate is not None
    assert surrogate.import_metadata.get("zapier_test") is True


@pytest.mark.asyncio
async def test_zapier_webhook_stores_raw_payload_and_creates_form(client, db, test_org):
    from app.db.models import MetaForm, MetaFormVersion, MetaLead, Task
    from app.services import zapier_settings_service

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)

    payload = [
        {
            "lead_id": "lead_zapier_1",
            "form_id": "zap_form_1",
            "form_name": "Zapier Intake",
            "field_data": [
                {"name": "full_name", "values": ["Zapier User"]},
                {"name": "email", "values": ["zapier@example.com"]},
                {"name": "state", "values": ["CA"]},
                {"name": "created_time", "values": ["2026-01-20T12:00:00Z"]},
            ],
        }
    ]

    res = await client.post(
        f"/webhooks/zapier/{settings.webhook_id}",
        json=payload,
        headers={"X-Webhook-Token": secret},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "awaiting_mapping"
    assert body["surrogate_id"] is None

    lead = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == test_org.id,
            MetaLead.meta_lead_id == "lead_zapier_1",
        )
        .first()
    )
    assert lead is not None
    assert lead.raw_payload == payload[0]
    assert lead.meta_form_id == "zap_form_1"

    form = (
        db.query(MetaForm)
        .filter(
            MetaForm.organization_id == test_org.id,
            MetaForm.form_external_id == "zap_form_1",
        )
        .first()
    )
    assert form is not None
    assert form.form_name == "Zapier Intake"
    assert form.current_version_id is not None

    version = db.get(MetaFormVersion, form.current_version_id)
    assert version is not None
    schema_keys = {item.get("key") for item in version.field_schema}
    assert {"full_name", "email", "state", "created_time"}.issubset(schema_keys)

    task = (
        db.query(Task)
        .filter(
            Task.organization_id == test_org.id,
            Task.title == f"Review Meta form mapping: {form.form_name}",
        )
        .first()
    )
    assert task is not None


@pytest.mark.asyncio
async def test_zapier_webhook_handles_dict_field_data(client, db, test_org):
    from app.db.models import MetaForm, MetaFormVersion, MetaLead
    from app.services import zapier_settings_service

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)

    payload = {
        "lead_id": "lead_dict_1",
        "form_id": "zap_form_dict",
        "form_name": "Zapier Dict Intake",
        "field_data": {
            "Full Name": "Dict User",
            "Email": "dict@example.com",
            "Phone Number": "(555) 123-4567",
            "State": "CA",
            "Created Time": "2026-01-20T12:00:00Z",
        },
    }

    res = await client.post(
        f"/webhooks/zapier/{settings.webhook_id}",
        json=payload,
        headers={"X-Webhook-Token": secret},
    )
    assert res.status_code == 200

    lead = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == test_org.id,
            MetaLead.meta_lead_id == "lead_dict_1",
        )
        .first()
    )
    assert lead is not None
    assert lead.field_data_raw.get("full_name") == "Dict User"
    assert lead.field_data_raw.get("email") == "dict@example.com"

    form = (
        db.query(MetaForm)
        .filter(
            MetaForm.organization_id == test_org.id,
            MetaForm.form_external_id == "zap_form_dict",
        )
        .first()
    )
    assert form is not None

    version = db.get(MetaFormVersion, form.current_version_id)
    assert version is not None
    schema_keys = {item.get("key") for item in version.field_schema}
    assert {"full_name", "email", "phone_number", "state", "created_time"}.issubset(schema_keys)


@pytest.mark.asyncio
async def test_zapier_webhook_creates_form_when_missing_form_id(client, db, test_org):
    from app.db.models import MetaForm, MetaLead
    from app.services import zapier_settings_service

    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)

    payload = {
        "lead_id": "lead_no_form",
        "field_data": [
            {"name": "full_name", "values": ["No Form"]},
            {"name": "email", "values": ["noform@example.com"]},
        ],
    }

    res = await client.post(
        f"/webhooks/zapier/{settings.webhook_id}",
        json=payload,
        headers={"X-Webhook-Token": secret},
    )
    assert res.status_code == 200

    expected_form_id = f"zapier-{settings.webhook_id}"

    lead = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == test_org.id,
            MetaLead.meta_lead_id == "lead_no_form",
        )
        .first()
    )
    assert lead is not None
    assert lead.meta_form_id == expected_form_id

    form = (
        db.query(MetaForm)
        .filter(
            MetaForm.organization_id == test_org.id,
            MetaForm.form_external_id == expected_form_id,
        )
        .first()
    )
    assert form is not None
    assert form.form_name.startswith("Zapier Lead Intake")
