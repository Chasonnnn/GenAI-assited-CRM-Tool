"""Hosted /intake submissions persist website click attribution."""

from __future__ import annotations

import json
import uuid

import pytest

from app.core.config import settings
from app.db.enums import JobType, Role
from app.db.models import (
    Donor,
    FormSubmission,
    Job,
    LeadAttribution,
    PipelineStage,
)
from app.services import donor_service, zapier_settings_service
from app.services.form_intake_service import sanitize_embed_attribution
from tests.test_forms_public_shared_intake import _create_other_org_intake_link
from tests.test_hosted_donor_forms import _create_and_promote_lead, _create_donor_form, _png_bytes


@pytest.fixture(autouse=True)
def _reset_rate_limiter_between_tests(monkeypatch):
    from app.core import rate_limit
    from app.core.rate_limit import limiter

    client_key = f"hosted-attribution-test-{uuid.uuid4().hex}"
    monkeypatch.setattr(rate_limit, "get_client_ip", lambda request: client_key)
    limiter.reset()
    yield
    limiter.reset()


SHARED_SCHEMA = {
    "pages": [
        {
            "title": "Identity",
            "fields": [
                {"key": "full_name", "label": "Full Name", "type": "text", "required": True},
                {"key": "date_of_birth", "label": "DOB", "type": "date", "required": True},
                {"key": "phone", "label": "Phone", "type": "text", "required": True},
                {"key": "email", "label": "Email", "type": "email", "required": True},
            ],
        }
    ]
}


async def _create_shared_link(authed_client, *, utm_defaults: dict[str, str] | None = None) -> str:
    create_res = await authed_client.post(
        "/forms",
        json={"name": "Hosted Attribution Form", "form_schema": SHARED_SCHEMA},
    )
    assert create_res.status_code == 200, create_res.text
    form_id = create_res.json()["id"]
    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200, publish_res.text
    link_res = await authed_client.post(
        f"/forms/{form_id}/intake-links",
        json={"campaign_name": "Website", "utm_defaults": utm_defaults},
    )
    assert link_res.status_code == 200, link_res.text
    return link_res.json()["slug"]


def _answers(email: str) -> str:
    return json.dumps(
        {
            "full_name": "Website Applicant",
            "date_of_birth": "1994-02-03",
            "phone": "+1 (555) 222-0101",
            "email": email,
        }
    )


def _attribution_rows(db, submission_id: str) -> list[LeadAttribution]:
    return (
        db.query(LeadAttribution)
        .filter(LeadAttribution.form_submission_id == uuid.UUID(submission_id))
        .all()
    )


@pytest.mark.asyncio
async def test_hosted_submit_writes_one_sanitized_attribution_row(authed_client, client, db):
    slug = await _create_shared_link(
        authed_client, utm_defaults={"utm_source": "link-default", "utm_medium": "paid_social"}
    )
    attribution = {
        "utm_source": "facebook",
        "utm_campaign": "donor-fall",
        "utm_content": "carousel-a",
        "ad_id": "ad-1",
        "adset_id": "adset-1",
        "campaign_id": "campaign-1",
        "fbclid": "click-abc",
        "fbc": "fb.1.1790510400123.click-abc",
        "fbp": "fb.1.1790510400000.998877",
        "landing_url": f"https://app.surrogacyforce.com/intake/{slug}?utm_source=facebook#step",
        "referrer": "https://www.ewisurrogacy.com/egg-donors?email=leak@example.com",
        "medical_history": "not attribution",
    }
    data = {
        "answers": _answers("hosted-attribution@example.com"),
        "attribution": json.dumps(attribution),
        "idempotency_key": "hosted-attribution-1",
    }

    submit = await client.post(f"/forms/public/intake/{slug}/submit", data=data)
    retry = await client.post(f"/forms/public/intake/{slug}/submit", data=data)

    assert submit.status_code == 200, submit.text
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == submit.json()["id"]
    submission = db.get(FormSubmission, uuid.UUID(submit.json()["id"]))
    rows = _attribution_rows(db, submit.json()["id"])
    assert len(rows) == 1
    row = rows[0]
    assert row.organization_id == submission.organization_id
    assert row.intake_link_id == submission.intake_link_id
    assert row.source_surface == "hosted_intake"
    assert row.parent_origin is None
    assert row.source == "facebook"
    assert row.medium == "paid_social"
    assert row.campaign == "donor-fall"
    assert (row.ad_id, row.adset_id, row.campaign_id) == ("ad-1", "adset-1", "campaign-1")
    assert row.fbclid == "click-abc"
    assert row.fbc == "fb.1.1790510400123.click-abc"
    assert row.fbp == "fb.1.1790510400000.998877"
    assert row.landing_url == f"https://app.surrogacyforce.com/intake/{slug}"
    assert row.referrer == "https://www.ewisurrogacy.com/egg-donors"
    assert row.first_touch_json["utm_content"] == "carousel-a"
    assert "medical_history" not in row.first_touch_json
    assert "leak@example.com" not in str(row.first_touch_json)


@pytest.mark.asyncio
async def test_hosted_submit_drops_invalid_and_oversized_attribution_values(
    authed_client, client, db
):
    slug = await _create_shared_link(authed_client)
    attribution = {
        "utm_source": "s" * 256,
        "utm_campaign": "kept-campaign",
        "fbclid": "c" * 501,
        "fbc": {"nested": "value"},
        "fbp": ["fb.1.1.2"],
        "ad_id": True,
        "landing_url": "javascript:alert(1)",
        "referrer": "https://www.ewisurrogacy.com/" + "p" * 1000,
    }

    submit = await client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": _answers("hosted-invalid-attribution@example.com"),
            "attribution": json.dumps(attribution),
        },
    )

    assert submit.status_code == 200, submit.text
    rows = _attribution_rows(db, submit.json()["id"])
    assert len(rows) == 1
    row = rows[0]
    assert row.first_touch_json == {"utm_campaign": "kept-campaign"}
    assert row.source is None
    assert row.fbclid is None
    assert row.fbc is None
    assert row.fbp is None
    assert row.ad_id is None
    assert row.landing_url is None
    assert row.referrer is None


@pytest.mark.asyncio
@pytest.mark.parametrize("attribution_part", ["not-json", json.dumps(["utm_source"]), None])
async def test_hosted_submit_without_usable_attribution_writes_no_row(
    authed_client, client, db, attribution_part
):
    slug = await _create_shared_link(authed_client)
    data = {"answers": _answers(f"hosted-no-attribution-{uuid.uuid4().hex[:6]}@example.com")}
    if attribution_part is not None:
        data["attribution"] = attribution_part

    submit = await client.post(f"/forms/public/intake/{slug}/submit", data=data)

    assert submit.status_code == 200, submit.text
    assert _attribution_rows(db, submit.json()["id"]) == []


@pytest.mark.asyncio
async def test_hosted_submit_keeps_link_utm_defaults_without_client_attribution(
    authed_client, client, db
):
    slug = await _create_shared_link(authed_client, utm_defaults={"utm_source": "expo"})

    submit = await client.post(
        f"/forms/public/intake/{slug}/submit?utm_campaign=api-query",
        data={"answers": _answers("hosted-defaults@example.com")},
    )

    assert submit.status_code == 200, submit.text
    rows = _attribution_rows(db, submit.json()["id"])
    assert len(rows) == 1
    assert rows[0].source == "expo"
    assert rows[0].campaign == "api-query"


@pytest.mark.asyncio
async def test_hosted_attribution_is_scoped_to_the_link_organization(
    authed_client, client, db, test_org
):
    other_org, other_link = _create_other_org_intake_link(db, event_name="Other Website")
    db.commit()

    submit = await client.post(
        f"/forms/public/intake/{other_link.slug}/submit",
        data={
            "answers": _answers("other-org-attribution@example.com"),
            "attribution": json.dumps(
                {
                    "utm_source": "facebook",
                    "fbclid": "other-click",
                    "organization_id": str(test_org.id),
                    "intake_link_id": str(uuid.uuid4()),
                }
            ),
        },
    )

    assert submit.status_code == 200, submit.text
    row = (
        db.query(LeadAttribution)
        .filter(LeadAttribution.form_submission_id == uuid.UUID(submit.json()["id"]))
        .one()
    )
    assert row.organization_id == other_org.id
    assert row.intake_link_id == other_link.id
    assert "organization_id" not in row.first_touch_json
    assert (
        db.query(LeadAttribution).filter(LeadAttribution.organization_id == test_org.id).count()
        == 0
    )


@pytest.mark.asyncio
async def test_hosted_donor_attribution_reaches_donor_zapier_outbound(
    authed_client, client, db, test_org, test_user, monkeypatch
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    _form_id, slug = await _create_donor_form(authed_client)
    public_form = await client.get(f"/forms/public/intake/{slug}")
    assert public_form.status_code == 200, public_form.text
    submit = await client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "applicant_name": "Website Donor",
                    "email_address": f"website-donor-{uuid.uuid4().hex[:8]}@example.com",
                    "mobile": "+1 (607) 555-0144",
                    "home_state": "NY",
                    "education_background": "Bachelor's degree",
                }
            ),
            "file_field_keys": json.dumps(["headshot"]),
            "published_version_id": public_form.json()["published_version_id"],
            "attribution": json.dumps(
                {
                    "utm_source": "facebook",
                    "campaign_id": "donor-campaign-1",
                    "fbclid": "donor-click",
                    "fbc": "fb.1.1790510400123.donor-click",
                    "fbp": "fb.1.1790510400000.445566",
                }
            ),
        },
        files=[("files", ("profile.png", _png_bytes(), "image/png"))],
    )
    assert submit.status_code == 200, submit.text
    _lead_id, promote = await _create_and_promote_lead(authed_client, submit.json()["id"])
    assert promote.status_code == 200, promote.text
    donor = db.get(Donor, uuid.UUID(promote.json()["donor_id"]))
    contacted = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == donor.stage.pipeline_id,
            PipelineStage.stage_key == "contacted",
        )
        .one()
    )
    zapier_settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    zapier_settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/123/donor"
    zapier_settings.donor_outbound_enabled = True
    zapier_settings.outbound_send_hashed_pii = True
    zapier_settings.donor_outbound_event_mapping = [
        {
            "donor_type": "egg",
            "pipeline_id": str(contacted.pipeline_id),
            "stage_id": str(contacted.id),
            "event_name": "Qualified",
            "enabled": True,
        }
    ]
    db.commit()

    donor_service.change_status(
        db,
        donor,
        contacted.id,
        test_user.id,
        user_role=Role.DEVELOPER,
        emit_workflow_events=False,
    )

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ZAPIER_STAGE_EVENT.value,
        )
        .one()
    )
    payload = job.payload["data"]
    assert payload["attribution_source"] == "website"
    assert payload["first_party_submission_id"] == submit.json()["id"]
    assert payload["fbc"] == "fb.1.1790510400123.donor-click"
    assert payload["fbp"] == "fb.1.1790510400000.445566"
    assert payload["campaign_id"] == "donor-campaign-1"


def test_attribution_sanitizer_drops_values_longer_than_their_column():
    assert sanitize_embed_attribution(
        {"utm_source": "s" * 256, "utm_medium": "m" * 255, "fbc": "f" * 500, "fbp": "p" * 501}
    ) == {"utm_medium": "m" * 255, "fbc": "f" * 500}
