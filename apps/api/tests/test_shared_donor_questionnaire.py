import json
import uuid
from pathlib import Path

import pytest

from app.core.config import settings
from app.db.models import FormSubmission
from tests.test_hosted_donor_forms import _create_donor_form, _png_bytes, _submit_donor_form


@pytest.fixture(autouse=True)
def reset_shared_donor_rate_limits():
    from app.core.rate_limit import limiter

    limiter.reset()


@pytest.mark.asyncio
async def test_ops_shared_template_preserves_donor_routing_when_agency_uses_it(
    authed_client, db, test_user, test_org, monkeypatch
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    test_user.is_platform_admin = True
    db.commit()
    schema = json.loads(
        (
            Path(__file__).resolve().parents[3] / "scripts/fixtures/ewi-donor-pre-screening.json"
        ).read_text()
    )
    schema["public_eyebrow"] = None
    schema["privacy_notice"] = None
    created = await authed_client.post(
        "/platform/templates/forms",
        json={
            "name": "Shared donor pre-screening",
            "schema_json": schema,
            "settings_json": {
                "lead_kind": "egg_donor",
                "purpose": "other",
                "max_file_count": 1,
                "allowed_mime_types": ["image/png", "image/jpeg"],
                "mappings": [
                    {"field_key": key, "surrogate_field": key}
                    for key in (
                        "donor_type",
                        "full_name",
                        "email",
                        "phone",
                        "state",
                        "education",
                        "profile_photo",
                    )
                ],
            },
        },
    )
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]
    published = await authed_client.post(
        f"/platform/templates/forms/{template_id}/publish", json={"publish_all": True}
    )
    assert published.status_code == 200, published.text
    assert published.json()["is_published_globally"] is True
    copied = await authed_client.post(
        f"/forms/templates/{template_id}/use", json={"name": "Agency donor pre-screening"}
    )
    assert copied.status_code == 200, copied.text
    form_id = copied.json()["id"]
    published_form = await authed_client.post(f"/forms/{form_id}/publish")
    assert published_form.status_code == 200, published_form.text
    links = await authed_client.get(f"/forms/{form_id}/intake-links")
    slug = links.json()[0]["slug"]
    public = await authed_client.get(f"/forms/public/intake/{slug}")
    submitted = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "published_version_id": public.json()["published_version_id"],
            "file_field_keys": json.dumps(["profile_photo"]),
            "answers": json.dumps(
                {
                    "donor_type": "Sperm donor",
                    "full_name": "Shared Template Test",
                    "email": "shared-template@example.com",
                    "phone": "+12025550146",
                    "date_of_birth": "1990-06-15",
                    "city": "Chino Hills",
                    "state": "CA",
                    "country": "United States",
                    "education": "Bachelor’s degree",
                    "college": "Example College",
                    "race": "Asian",
                    "height": 5.67,
                    "weight": 140,
                    "nicotine": "No",
                    "cannabis": "No",
                    "infectious_disease": "No",
                    "previous_donation": "No",
                    "referral_source": "Facebook",
                }
            ),
        },
        files=[("files", ("profile.png", _png_bytes(), "image/png"))],
    )
    assert submitted.status_code == 200, submitted.text
    submission = db.get(FormSubmission, uuid.UUID(submitted.json()["id"]))
    assert submission.organization_id == test_org.id
    assert submission.lead_kind == "sperm_donor"


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", [None, "", "surrogate", "unknown"])
async def test_shared_donor_questionnaire_requires_valid_program(authed_client, db, answer):
    form_id, slug = await _create_donor_form(authed_client, shared_donor=True)
    response = await _submit_donor_form(
        authed_client, slug=slug, email="invalid-program@example.com", donor_type=answer
    )
    assert response.status_code == 400, response.text
    assert (
        db.query(FormSubmission).filter(FormSubmission.form_id == uuid.UUID(form_id)).count() == 0
    )


@pytest.mark.asyncio
async def test_shared_donor_routing_uses_published_mapping_and_is_idempotent(
    authed_client, db, monkeypatch
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    form_id, slug = await _create_donor_form(authed_client, shared_donor=True)
    mappings = await authed_client.get(f"/forms/{form_id}/mappings")
    assert mappings.status_code == 200, mappings.text
    # A draft mapping edit must not change routing for the already published link.
    changed = await authed_client.put(
        f"/forms/{form_id}/mappings",
        json={
            "mappings": [
                {"field_key": item["field_key"], "surrogate_field": item["surrogate_field"]}
                for item in mappings.json()
                if item["surrogate_field"] != "donor_type"
            ]
        },
    )
    assert changed.status_code == 200, changed.text
    key = str(uuid.uuid4())
    first = await _submit_donor_form(
        authed_client,
        slug=slug,
        email="shared-routing@example.com",
        donor_type="Sperm donor",
        idempotency_key=key,
    )
    assert first.status_code == 200, first.text
    retry = await _submit_donor_form(
        authed_client,
        slug=slug,
        email="shared-routing@example.com",
        donor_type="Egg donor",
        idempotency_key=key,
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == first.json()["id"]
    db.expire_all()
    submission = db.get(FormSubmission, uuid.UUID(first.json()["id"]))
    assert submission.lead_kind == "sperm_donor"
    assert submission.answers_json["donation_program"] == "Sperm donor"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["optional", "conditional", "wrong_options"])
async def test_shared_donor_questionnaire_rejects_unsafe_program_field(authed_client, invalid):
    form_id, _slug = await _create_donor_form(authed_client, shared_donor=True)
    form = await authed_client.get(f"/forms/{form_id}")
    schema = form.json()["form_schema"]
    field = schema["pages"][0]["fields"][0]
    if invalid == "optional":
        field["required"] = False
    elif invalid == "conditional":
        field["show_if"] = {"field_key": "applicant_name", "operator": "is_empty"}
    else:
        field["options"].append({"label": "Surrogate", "value": "surrogate"})
    changed = await authed_client.patch(f"/forms/{form_id}", json={"form_schema": schema})
    assert changed.status_code == 200, changed.text
    publish = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish.status_code == 400, publish.text
    assert "Donor Type" in publish.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid", ["optional", "conditional", "wrong_options", "missing_photo", "no_uploads"]
)
async def test_ops_rejects_invalid_donor_template_before_publication(
    authed_client, db, test_user, invalid
):
    test_user.is_platform_admin = True
    db.commit()
    schema = json.loads(
        (
            Path(__file__).resolve().parents[3] / "scripts/fixtures/ewi-donor-pre-screening.json"
        ).read_text()
    )
    field = schema["pages"][0]["fields"][0]
    if invalid == "optional":
        field["required"] = False
    elif invalid == "conditional":
        field["show_if"] = {"field_key": "full_name", "operator": "is_empty"}
    elif invalid == "wrong_options":
        field["options"][1]["value"] = "surrogate"
    mappings = [
        {"field_key": key, "surrogate_field": key}
        for key in ("donor_type", "full_name", "email", "profile_photo")
        if invalid != "missing_photo" or key != "profile_photo"
    ]
    created = await authed_client.post(
        "/platform/templates/forms",
        json={
            "name": "Invalid shared donor",
            "schema_json": schema,
            "settings_json": {
                "lead_kind": "egg_donor",
                "purpose": "other",
                "mappings": mappings,
                "max_file_count": 0 if invalid == "no_uploads" else 1,
            },
        },
    )
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]
    published = await authed_client.post(
        f"/platform/templates/forms/{template_id}/publish", json={"publish_all": True}
    )
    assert published.status_code == 400, published.text
    saved = await authed_client.get(f"/platform/templates/forms/{template_id}")
    assert saved.json()["status"] == "draft"
    assert saved.json()["published_version"] == 0
    assert saved.json()["is_published_globally"] is False
