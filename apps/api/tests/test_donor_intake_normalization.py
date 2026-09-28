"""Incoming donor records drop invalid optional values instead of failing."""

import json
import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.db.models import Donor, IntakeLead, MetaForm, MetaFormVersion, MetaLead
from app.services import donor_input_normalization_service, zapier_settings_service
from tests.test_hosted_donor_forms import _create_and_promote_lead, _png_bytes

INTERNATIONAL_PHONE = "+44 20 7946 0958"


def _mapping(column: str, field: str) -> dict:
    return {
        "csv_column": column,
        "surrogate_field": field,
        "transformation": None,
        "action": "map",
        "custom_field_key": None,
    }


def _mapped_donor_meta_form(db, org_id, *, external_id: str, lead_kind: str) -> MetaForm:
    columns = {
        "full_name": "full_name",
        "email": "email",
        "phone_number": "phone",
        "state": "state",
        "date_of_birth": "date_of_birth",
        "race": "race",
        "height": "height_ft",
        "weight": "weight_lb",
    }
    form = MetaForm(
        organization_id=org_id,
        page_id=f"page-{external_id}",
        form_external_id=external_id,
        form_name=f"Form {external_id}",
        mapping_status="mapped",
        lead_kind=lead_kind,
    )
    db.add(form)
    db.flush()
    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=[{"key": key, "type": "TEXT", "label": key} for key in columns],
        schema_hash=f"hash-{external_id}",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id
    form.mapping_version_id = version.id
    form.mapping_rules = [_mapping(column, field) for column, field in columns.items()]
    db.commit()
    return form


def test_builder_drops_invalid_optional_fields_and_keeps_valid_values():
    result = donor_input_normalization_service.build_donor_create_from_payload(
        {
            "full_name": "  Taylor   Donor ",
            "email": "Taylor@Example.com",
            "phone": INTERNATIONAL_PHONE,
            "state": "Ontario",
            "education": "Master's degree",
            "date_of_birth": "03/04/1995",
            "race": "Asian",
            "height_ft": "5'6\"",
            "weight_lb": "not a weight",
            "source": "Spring Fair",
        },
        donor_type="egg",
        fallback_source="website",
    )

    assert result.create.full_name == "Taylor Donor"
    assert result.create.email == "taylor@example.com"
    assert result.create.phone is None
    assert result.create.state is None
    assert result.create.education == "Master's degree"
    assert result.create.source == "website"
    assert result.profile == {
        "date_of_birth": date(1995, 3, 4),
        "race": "Asian",
        "height_ft": Decimal("5.5"),
    }
    assert result.dropped_fields == ["phone", "state", "weight_lb"]


@pytest.mark.parametrize(
    "payload",
    [
        {"full_name": "Taylor Donor", "email": "not-an-email"},
        {"full_name": "", "email": "taylor@example.com"},
        {"email": "taylor@example.com"},
    ],
)
def test_builder_keeps_identity_fields_required(payload):
    with pytest.raises((ValidationError, ValueError)):
        donor_input_normalization_service.build_donor_create_from_payload(
            payload,
            donor_type="sperm",
            fallback_source="website",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lead_kind", "donor_type"), [("egg_donor", "egg"), ("sperm_donor", "sperm")]
)
async def test_zapier_donor_lead_with_international_phone_and_province_converts(
    client, db, test_org, lead_kind, donor_type
):
    form = _mapped_donor_meta_form(
        db, test_org.id, external_id=f"intl-{donor_type}", lead_kind=lead_kind
    )
    settings_row = zapier_settings_service.get_or_create_settings(db, test_org.id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings_row.webhook_secret_encrypted)
    email = f"intl-{donor_type}-{uuid.uuid4().hex[:8]}@example.com"

    response = await client.post(
        f"/webhooks/zapier/{settings_row.webhook_id}",
        json={
            "lead_id": f"intl-{donor_type}-lead",
            "form_id": form.form_external_id,
            "field_data": [
                {"name": "full_name", "values": ["Canada Donor"]},
                {"name": "email", "values": [email]},
                {"name": "phone_number", "values": [INTERNATIONAL_PHONE]},
                {"name": "state", "values": ["Ontario"]},
                {"name": "date_of_birth", "values": ["1996-05-17"]},
                {"name": "race", "values": ["White"]},
                {"name": "height", "values": ["5'8\""]},
                {"name": "weight", "values": ["140"]},
            ],
        },
        headers={"X-Webhook-Token": secret},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "converted"
    donor = db.get(Donor, response.json()["donor_id"])
    assert donor is not None
    assert donor.donor_type == donor_type
    assert donor.email == email
    assert donor.phone is None
    assert donor.state is None
    assert donor.source == "meta"
    assert donor.date_of_birth == date(1996, 5, 17)
    assert donor.race == "White"
    assert donor.height_ft == Decimal("5.67")
    assert donor.weight_lb == 140
    lead = (
        db.query(MetaLead)
        .filter(MetaLead.organization_id == test_org.id, MetaLead.converted_donor_id == donor.id)
        .one()
    )
    assert lead.unmapped_fields["dropped_invalid_fields"] == ["phone", "state"]


# The shared hosted-form helper uses a phone-type field, which rejects international
# numbers at submit; this copy uses a text field so the value reaches promotion.
async def _create_text_contact_donor_form(client, *, lead_kind: str) -> str:
    fields = [
        ("applicant_name", "Full Name", "text", True, "full_name"),
        ("email_address", "Email", "email", True, "email"),
        ("mobile", "Phone", "text", False, "phone"),
        ("home_state", "State", "text", False, "state"),
        ("headshot", "Profile Photo", "file", True, "profile_photo"),
    ]
    create = await client.post(
        "/forms",
        json={
            "name": f"{lead_kind} text contact application",
            "purpose": "other",
            "lead_kind": lead_kind,
            "form_schema": {
                "pages": [
                    {
                        "title": "Donor",
                        "fields": [
                            {"key": key, "label": label, "type": kind, "required": required}
                            for key, label, kind, required, _ in fields
                        ],
                    }
                ]
            },
            "allowed_mime_types": ["image/png", "image/jpeg"],
        },
    )
    assert create.status_code == 200, create.text
    form_id = create.json()["id"]
    mappings = await client.put(
        f"/forms/{form_id}/mappings",
        json={
            "mappings": [
                {"field_key": key, "surrogate_field": target} for key, *_, target in fields
            ]
        },
    )
    assert mappings.status_code == 200, mappings.text
    publish = await client.post(f"/forms/{form_id}/publish")
    assert publish.status_code == 200, publish.text
    links = await client.get(f"/forms/{form_id}/intake-links")
    assert links.status_code == 200, links.text
    return links.json()[0]["slug"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lead_kind", "donor_type"), [("egg_donor", "egg"), ("sperm_donor", "sperm")]
)
async def test_hosted_donor_promotion_accepts_international_phone_and_province(
    authed_client, db, test_org, monkeypatch, lead_kind, donor_type
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    slug = await _create_text_contact_donor_form(authed_client, lead_kind=lead_kind)
    public_form = await authed_client.get(f"/forms/public/intake/{slug}")
    assert public_form.status_code == 200, public_form.text
    email = f"hosted-intl-{donor_type}-{uuid.uuid4().hex[:8]}@example.com"
    submit = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "applicant_name": "Ontario Donor",
                    "email_address": email,
                    "mobile": INTERNATIONAL_PHONE,
                    # State-mapped fields accept two characters; ON is Ontario.
                    "home_state": "ON",
                }
            ),
            "file_field_keys": json.dumps(["headshot"]),
            "published_version_id": public_form.json()["published_version_id"],
        },
        files=[("files", ("profile.png", _png_bytes(), "image/png"))],
    )
    assert submit.status_code == 200, submit.text

    lead_id, promote = await _create_and_promote_lead(authed_client, submit.json()["id"])

    assert promote.status_code == 200, promote.text
    donor = db.get(Donor, uuid.UUID(promote.json()["donor_id"]))
    assert donor is not None
    assert donor.donor_type == donor_type
    assert donor.email == email
    assert donor.phone is None
    assert donor.state is None
    assert donor.source == "website"
    lead = db.get(IntakeLead, uuid.UUID(lead_id))
    assert lead.source_metadata["dropped_invalid_submission_fields"] == ["state"]
