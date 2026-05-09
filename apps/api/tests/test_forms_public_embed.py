"""Integration tests for embeddable public lead-capture intake."""

from __future__ import annotations

import uuid

import pytest

from app.db.models import (
    ConsentRecord,
    EmbedSession,
    FormSubmission,
    IntakeLead,
    LeadAttribution,
    TrackingEventLog,
)


def _lead_capture_schema(
    *, extra_fields: list[dict[str, object]] | None = None
) -> dict[str, object]:
    fields: list[dict[str, object]] = [
        {
            "key": "full_name",
            "label": "Full Name",
            "type": "text",
            "required": True,
            "sensitivity": "identity",
        },
        {
            "key": "email",
            "label": "Email",
            "type": "email",
            "required": True,
            "sensitivity": "contact",
        },
        {
            "key": "phone",
            "label": "Phone",
            "type": "phone",
            "required": False,
            "sensitivity": "contact",
        },
        {
            "key": "state",
            "label": "State",
            "type": "text",
            "required": False,
            "sensitivity": "campaign_safe",
        },
    ]
    if extra_fields:
        fields.extend(extra_fields)
    return {
        "public_title": "Become a Surrogate",
        "privacy_notice": "By submitting, you agree to be contacted by the intake team.",
        "pages": [{"title": "Contact", "fields": fields}],
    }


async def _create_published_lead_capture_form(authed_client) -> tuple[str, str, str]:
    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Lead Capture",
            "description": "Public lead form",
            "purpose": "lead_capture",
            "form_schema": _lead_capture_schema(),
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    links_res = await authed_client.get(f"/forms/{form_id}/intake-links")
    assert links_res.status_code == 200
    links = links_res.json()
    assert len(links) >= 1
    return form_id, links[0]["id"], links[0]["slug"]


@pytest.mark.asyncio
async def test_lead_capture_publish_requires_name_and_contact_but_not_date_of_birth(
    authed_client,
):
    form_id, link_id, _slug = await _create_published_lead_capture_form(authed_client)

    links_res = await authed_client.get(f"/forms/{form_id}/intake-links")
    assert links_res.status_code == 200
    link = next(item for item in links_res.json() if item["id"] == link_id)
    assert link["tracking_mode"] == "enhanced_match_lead"
    assert link["embed_enabled"] is False

    missing_contact_schema = _lead_capture_schema()
    missing_contact_schema["pages"][0]["fields"] = [
        field
        for field in missing_contact_schema["pages"][0]["fields"]
        if field["key"] not in {"email", "phone"}
    ]

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Lead Capture Missing Contact",
            "purpose": "lead_capture",
            "form_schema": missing_contact_schema,
        },
    )
    assert create_res.status_code == 200
    publish_res = await authed_client.post(f"/forms/{create_res.json()['id']}/publish")
    assert publish_res.status_code == 400
    assert "email or phone" in publish_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_enhanced_match_lead_publish_blocks_sensitive_and_unclassified_fields(
    authed_client,
):
    form_id, link_id, _slug = await _create_published_lead_capture_form(authed_client)

    risky_schema = _lead_capture_schema(
        extra_fields=[
            {
                "key": "medical_notes",
                "label": "Anything else we should know?",
                "type": "textarea",
                "required": False,
                "sensitivity": "free_text_unclassified",
            }
        ]
    )
    update_res = await authed_client.patch(
        f"/forms/{form_id}",
        json={"form_schema": risky_schema},
    )
    assert update_res.status_code == 200

    link_res = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={
            "embed_enabled": True,
            "allowed_embed_origins": ["https://www.ewisurrogacy.com/"],
            "tracking_mode": "enhanced_match_lead",
            "consent_text": "I agree to be contacted about my inquiry.",
        },
    )
    assert link_res.status_code == 400
    assert "privacy-safe" in link_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_embed_session_submit_creates_lead_attribution_consent_and_tracking(
    authed_client,
    db,
):
    _form_id, link_id, slug = await _create_published_lead_capture_form(authed_client)
    allowed_origin = "https://www.ewisurrogacy.com"

    link_res = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={
            "embed_enabled": True,
            "allowed_embed_origins": [f"{allowed_origin}/apply"],
            "tracking_mode": "enhanced_match_lead",
            "consent_text": "I agree to be contacted about my inquiry.",
            "thank_you_config": {"message": "Thank you."},
            "embed_theme_json": {"accent": "#2563eb"},
        },
    )
    assert link_res.status_code == 200
    assert link_res.json()["allowed_embed_origins"] == [allowed_origin]

    public_res = await authed_client.get(
        f"/forms/public/embed/{slug}",
        headers={"origin": allowed_origin},
    )
    assert public_res.status_code == 200
    public_payload = public_res.json()
    assert public_payload["tracking_mode"] == "enhanced_match_lead"
    assert public_payload["published_version_id"]
    assert public_payload["consent"]["text"] == "I agree to be contacted about my inquiry."
    assert "meta_pixel_id" not in public_payload
    assert public_res.headers["cache-control"] == "no-store"

    frame_policy_res = await authed_client.get(f"/forms/public/embed/{slug}/frame-policy")
    assert frame_policy_res.status_code == 200
    assert frame_policy_res.headers["cache-control"] == "no-store"
    assert frame_policy_res.json()["content_security_policy"] == (
        "frame-ancestors 'self' https://www.ewisurrogacy.com"
    )

    iframe_origin_res = await authed_client.get(
        f"/forms/public/embed/{slug}?parent_origin={allowed_origin}",
        headers={"origin": "https://app.surrogacyforce.com"},
    )
    assert iframe_origin_res.status_code == 200

    denied_session_res = await authed_client.post(
        f"/forms/public/embed/{slug}/session",
        json={"parent_origin": "https://www.ewisurrogacy.com.evil.com"},
    )
    assert denied_session_res.status_code == 403

    session_res = await authed_client.post(
        f"/forms/public/embed/{slug}/session",
        json={
            "parent_origin": allowed_origin,
            "attribution": {
                "utm_source": "meta",
                "utm_campaign": "spring-surrogate",
                "fbclid": "fb-test-click",
                "fbc": "fb.1.1772942400.fb-test-click",
                "fbp": "fb.1.1772942400.1234567890",
                "landing_url": "https://www.ewisurrogacy.com/apply?full_name=Leak#step",
                "referrer": "https://www.facebook.com/ad?click_id=secret",
                "medical_condition": "should-not-store-as-campaign-field",
            },
        },
        headers={"user-agent": "embed-test-agent"},
    )
    assert session_res.status_code == 200
    session_payload = session_res.json()
    assert session_payload["session_token"]

    submit_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": session_payload["session_token"],
            "idempotency_key": "idem-embed-1",
            "published_version_id": public_payload["published_version_id"],
            "answers": {
                "full_name": "Embed Lead",
                "email": "embed-lead@example.com",
                "phone": "+1 (555) 481-0901",
                "state": "CA",
            },
            "consent": {"accepted": True},
            "attribution": {
                "utm_source": "meta",
                "utm_campaign": "spring-surrogate",
                "fbclid": "fb-test-click",
                "landing_url": "https://www.ewisurrogacy.com/apply?email=leak@example.com",
                "referrer": "https://www.facebook.com/ad?click_id=secret",
                "free_text_medical_notes": "not allowed outbound",
            },
        },
        headers={"user-agent": "embed-test-agent"},
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert payload["outcome"] == "lead_created"
    assert payload["intake_lead_id"]

    duplicate_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": session_payload["session_token"],
            "idempotency_key": "idem-embed-1",
            "published_version_id": public_payload["published_version_id"],
            "answers": {
                "full_name": "Embed Lead",
                "email": "embed-lead@example.com",
                "phone": "+1 (555) 481-0901",
                "state": "CA",
            },
            "consent": {"accepted": True},
            "attribution": {"utm_source": "meta"},
        },
    )
    assert duplicate_res.status_code == 200
    assert duplicate_res.json()["id"] == payload["id"]

    submission_id = uuid.UUID(payload["id"])
    link_uuid = uuid.UUID(link_id)
    submission = db.query(FormSubmission).filter(FormSubmission.id == submission_id).first()
    assert submission is not None
    assert submission.published_version_id is not None
    assert submission.idempotency_key == "idem-embed-1"
    assert submission.form_schema_hash
    assert submission.consent_text_hash
    assert submission.tracking_policy_hash

    lead = (
        db.query(IntakeLead).filter(IntakeLead.id == uuid.UUID(payload["intake_lead_id"])).first()
    )
    assert lead is not None
    assert lead.form_submission_id == submission_id
    assert lead.source == "form_embed"
    assert lead.email_hash
    assert lead.phone_hash

    attribution = (
        db.query(LeadAttribution).filter(LeadAttribution.form_submission_id == submission_id).one()
    )
    assert attribution.intake_link_id == link_uuid
    assert attribution.parent_origin == allowed_origin
    assert attribution.source == "meta"
    assert attribution.campaign == "spring-surrogate"
    assert attribution.fbclid == "fb-test-click"
    assert attribution.landing_url == "https://www.ewisurrogacy.com/apply"
    assert attribution.referrer == "https://www.facebook.com/ad"
    assert "medical_condition" not in (attribution.first_touch_json or {})
    assert "leak@example.com" not in str(attribution.first_touch_json)

    consent = (
        db.query(ConsentRecord).filter(ConsentRecord.form_submission_id == submission_id).one()
    )
    assert consent.accepted is True
    assert consent.consent_text_snapshot == "I agree to be contacted about my inquiry."
    assert consent.parent_origin == allowed_origin

    tracking_event = (
        db.query(TrackingEventLog)
        .filter(TrackingEventLog.form_submission_id == submission_id)
        .one()
    )
    assert tracking_event.destination == "meta"
    assert tracking_event.event_name == "Lead"
    assert tracking_event.status == "queued"
    assert tracking_event.payload_json["event_name"] == "Lead"
    user_data = tracking_event.payload_json["user_data"]
    assert user_data["em"]
    assert user_data["ph"]
    assert user_data["fn"]
    assert user_data["ln"]
    assert user_data["fbc"] == "fb.1.1772942400.fb-test-click"
    assert user_data["fbp"] == "fb.1.1772942400.1234567890"
    assert "answers" not in tracking_event.payload_json
    assert "email" not in tracking_event.payload_json
    assert "phone" not in tracking_event.payload_json
    assert "embed-lead@example.com" not in str(tracking_event.payload_json)
    assert "+15554810901" not in str(tracking_event.payload_json)
    assert "Embed Lead" not in str(tracking_event.payload_json)
    assert "free_text_medical_notes" not in str(tracking_event.payload_json)

    embed_session = db.query(EmbedSession).filter(EmbedSession.intake_link_id == link_uuid).one()
    assert embed_session.consumed_at is not None


@pytest.mark.asyncio
async def test_embed_submit_requires_valid_session_and_published_version(
    authed_client,
):
    _form_id, link_id, slug = await _create_published_lead_capture_form(authed_client)
    allowed_origin = "https://www.ewisurrogacy.com"

    link_res = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={
            "embed_enabled": True,
            "allowed_embed_origins": [allowed_origin],
            "tracking_mode": "internal_only",
            "consent_text": "I agree to be contacted.",
        },
    )
    assert link_res.status_code == 200

    public_res = await authed_client.get(
        f"/forms/public/embed/{slug}",
        headers={"origin": allowed_origin},
    )
    assert public_res.status_code == 200

    submit_without_session = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": "not-a-real-token",
            "idempotency_key": "idem-missing-session",
            "published_version_id": public_res.json()["published_version_id"],
            "answers": {"full_name": "No Session", "email": "nosession@example.com"},
            "consent": {"accepted": True},
            "attribution": {},
        },
    )
    assert submit_without_session.status_code == 403

    session_res = await authed_client.post(
        f"/forms/public/embed/{slug}/session",
        json={"parent_origin": allowed_origin, "attribution": {}},
    )
    assert session_res.status_code == 200

    wrong_version_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": session_res.json()["session_token"],
            "idempotency_key": "idem-wrong-version",
            "published_version_id": str(uuid.uuid4()),
            "answers": {"full_name": "Wrong Version", "email": "wrong-version@example.com"},
            "consent": {"accepted": True},
            "attribution": {},
        },
    )
    assert wrong_version_res.status_code == 409


@pytest.mark.asyncio
async def test_embed_health_reports_blockers_and_ready_state(authed_client):
    _form_id, link_id, _slug = await _create_published_lead_capture_form(authed_client)

    blocked_res = await authed_client.get(f"/forms/intake-links/{link_id}/embed-health")
    assert blocked_res.status_code == 200
    blocked_payload = blocked_res.json()
    assert blocked_payload["status"] == "blocked"
    blocked_checks = {check["key"]: check for check in blocked_payload["checks"]}
    assert blocked_checks["embed_enabled"]["status"] == "block"
    assert blocked_checks["allowed_origins"]["status"] == "block"

    update_res = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={
            "embed_enabled": True,
            "allowed_embed_origins": ["https://www.ewisurrogacy.com/"],
            "tracking_mode": "privacy_safe_lead",
            "consent_text": "I agree to be contacted about my inquiry.",
        },
    )
    assert update_res.status_code == 200

    ready_res = await authed_client.get(f"/forms/intake-links/{link_id}/embed-health")
    assert ready_res.status_code == 200
    ready_payload = ready_res.json()
    assert ready_payload["status"] == "ready"
    ready_checks = {check["key"]: check for check in ready_payload["checks"]}
    assert ready_checks["embed_enabled"]["status"] == "pass"
    assert ready_checks["allowed_origins"]["status"] == "pass"
    assert ready_checks["tracking_policy"]["status"] == "pass"
    assert ready_checks["snippet"]["message"].endswith("is current")
