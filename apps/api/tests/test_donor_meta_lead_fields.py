"""Donor Meta forms map donor profile fields, and donor detail shows the source lead."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.constants import SYSTEM_USER_ID
from app.db.models import Donor, MetaForm, MetaFormVersion, MetaLead, Organization
from app.schemas.donor import DonorCreate
from app.services import donor_service, meta_lead_service
from tests.test_meta_donor_form_permissions import _admin_with_revokes, _client_for


def _rule(column: str, field: str | None, action: str = "map", custom_field_key=None) -> dict:
    return {
        "csv_column": column,
        "surrogate_field": field,
        "transformation": None,
        "action": action,
        "custom_field_key": custom_field_key,
    }


REQUIRED_RULES = [_rule("full_name", "full_name"), _rule("email", "email")]


def _form(db, org_id, *, suffix: str, lead_kind: str = "egg_donor") -> MetaForm:
    form = MetaForm(
        organization_id=org_id,
        page_id=f"page-{suffix}",
        form_external_id=f"form-{suffix}",
        form_name=f"Donor form {suffix}",
        lead_kind=lead_kind,
        mapping_status="unmapped",
    )
    db.add(form)
    db.flush()
    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=[
            {"key": "full_name", "type": "FULL_NAME", "label": "Full name"},
            {"key": "email", "type": "EMAIL", "label": "Email"},
            {"key": "dob", "type": "DATE", "label": "Date of birth"},
            {"key": "height", "type": "TEXT", "label": "How tall are you?"},
            {"key": "favorite_color", "type": "TEXT", "label": "Favorite color"},
        ],
        schema_hash=f"hash-{suffix}",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id
    db.commit()
    return form


@pytest.mark.asyncio
@pytest.mark.parametrize("lead_kind", ["egg_donor", "sperm_donor"])
async def test_donor_mapping_accepts_donor_profile_fields(authed_client, db, test_org, lead_kind):
    form = _form(db, test_org.id, suffix=f"profile-{lead_kind}", lead_kind=lead_kind)

    preview = await authed_client.get(f"/integrations/meta/forms/{form.id}/mapping")
    assert preview.status_code == 200, preview.text
    fields = preview.json()["available_fields"]
    assert {"date_of_birth", "race", "height_ft", "weight_lb"} <= set(fields)
    by_kind = preview.json()["available_fields_by_lead_kind"]
    assert by_kind["egg_donor"] == by_kind["sperm_donor"] == fields
    assert "journey_timing_preference" in by_kind["surrogate"]
    system_actions = {
        item["csv_column"]: item["default_action"]
        for item in preview.json()["column_suggestions"]
        if item["csv_column"].startswith("meta_")
    }
    assert system_actions and set(system_actions.values()) == {"ignore"}

    saved = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json={
            "lead_kind": lead_kind,
            "column_mappings": [
                *REQUIRED_RULES,
                _rule("dob", "date_of_birth"),
                _rule("height", "height_ft"),
                _rule("favorite_color", None, action="ignore"),
            ],
            "unknown_column_behavior": "ignore",
        },
    )
    assert saved.status_code == 200, saved.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule",
    [
        _rule("favorite_color", None, action="metadata"),
        _rule("favorite_color", None, action="custom", custom_field_key="favorite_color"),
    ],
)
async def test_donor_mapping_rejects_custom_and_metadata_actions(authed_client, db, test_org, rule):
    form = _form(db, test_org.id, suffix=f"reject-{rule['action']}")

    saved = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json={
            "lead_kind": "egg_donor",
            "column_mappings": [*REQUIRED_RULES, rule],
            "unknown_column_behavior": "ignore",
        },
    )

    assert saved.status_code == 400
    assert saved.json()["detail"] == (
        "Donor forms cannot store custom fields or metadata. Map these columns to a donor "
        "field or ignore them: favorite_color"
    )
    db.refresh(form)
    assert form.mapping_status == "unmapped"


@pytest.mark.asyncio
async def test_surrogate_mapping_still_accepts_metadata_actions(authed_client, db, test_org):
    form = _form(db, test_org.id, suffix="surrogate-metadata", lead_kind="surrogate")

    saved = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json={
            "lead_kind": "surrogate",
            "column_mappings": [*REQUIRED_RULES, _rule("favorite_color", None, action="metadata")],
            "unknown_column_behavior": "metadata",
        },
    )

    assert saved.status_code == 200, saved.text


def _converted_donor_lead(db, org_id, *, suffix: str) -> tuple[Donor, MetaLead]:
    form = _form(db, org_id, suffix=suffix)
    donor = donor_service.create_donor(
        db,
        org_id,
        SYSTEM_USER_ID,
        DonorCreate(
            donor_type="egg",
            full_name="Meta Card Donor",
            email=f"meta-card-{suffix}@example.com",
            source="meta",
        ),
    )
    lead = MetaLead(
        organization_id=org_id,
        meta_lead_id=f"lead-{suffix}",
        meta_form_id=form.form_external_id,
        lead_kind="egg_donor",
        field_data={"full_name": "Meta Card Donor"},
        field_data_raw={
            "full_name": "Meta Card Donor",
            "height": "5'6\"",
            "favorite_color": ["Blue", "Green"],
            "empty_answer": "",
            "lead_id": f"lead-{suffix}",
            "zapier_lead_id": f"lead-{suffix}",
            "meta_ad_id": "ad-1",
        },
        unmapped_fields={"dropped_invalid_fields": ["state"]},
        meta_created_time=datetime(2026, 9, 20, 15, 30, tzinfo=UTC),
        is_converted=True,
        converted_donor_id=donor.id,
        converted_at=datetime.now(UTC),
        status="converted",
    )
    db.add(lead)
    db.commit()
    return donor, lead


@pytest.mark.asyncio
async def test_donor_meta_lead_returns_source_answers(authed_client, db, test_org):
    donor, lead = _converted_donor_lead(db, test_org.id, suffix="card")

    response = await authed_client.get(f"/donors/{donor.id}/meta-lead")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(lead.id)
    assert body["form_name"] == "Donor form card"
    assert body["meta_created_time"].startswith("2026-09-20T15:30:00")
    assert body["answers"] == [
        {"key": "full_name", "label": "Full name", "value": "Meta Card Donor"},
        {"key": "height", "label": "How tall are you?", "value": "5'6\""},
        {"key": "favorite_color", "label": "Favorite color", "value": "Blue, Green"},
    ]
    assert body["dropped_fields"] == ["state"]


@pytest.mark.asyncio
async def test_donor_meta_lead_is_null_for_donor_without_meta_lead(authed_client, db, test_org):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        SYSTEM_USER_ID,
        DonorCreate(donor_type="sperm", full_name="Manual Donor", email="manual-card@example.com"),
    )

    response = await authed_client.get(f"/donors/{donor.id}/meta-lead")

    assert response.status_code == 200, response.text
    assert response.json() is None


@pytest.mark.asyncio
async def test_donor_meta_lead_requires_donor_view_permission(db, test_org):
    donor, _ = _converted_donor_lead(db, test_org.id, suffix="denied")
    user = _admin_with_revokes(db, test_org.id, "view_donors")

    async with _client_for(db, test_org.id, user) as client:
        response = await client.get(f"/donors/{donor.id}/meta-lead")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_donor_meta_lead_hides_other_org_donor(authed_client, db):
    other_org = Organization(id=uuid4(), name="Other Org", slug=f"other-{uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    donor, _ = _converted_donor_lead(db, other_org.id, suffix="cross-org")

    response = await authed_client.get(f"/donors/{donor.id}/meta-lead")

    assert response.status_code == 404
    assert meta_lead_service.get_donor_meta_lead_summary(db, other_org.id, donor.id)


def test_synthetic_meta_lead_ids_are_recognizable():
    generated = meta_lead_service.generate_synthetic_meta_lead_id()

    assert generated.startswith("zapier-generated-")
    assert meta_lead_service.is_synthetic_meta_lead_id(generated)
    assert meta_lead_service.is_synthetic_meta_lead_id(f"zapier-{uuid4()}")
    assert meta_lead_service.is_synthetic_meta_lead_id(f"zapier-test-{uuid4()}")
    assert not meta_lead_service.is_synthetic_meta_lead_id("1234567890123456")
    assert not meta_lead_service.is_synthetic_meta_lead_id(None)
