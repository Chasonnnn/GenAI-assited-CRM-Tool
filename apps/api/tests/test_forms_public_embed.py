"""Integration tests for embeddable public lead-capture intake."""

from __future__ import annotations

import uuid

import pytest

from app.db.enums import JobType
from app.db.models import (
    AutomationWorkflow,
    ConsentRecord,
    EmbedSession,
    FormSubmission,
    IntakeLead,
    Job,
    LeadAttribution,
    MetaCrmDatasetEvent,
    TrackingEventLog,
    WorkflowExecution,
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter_between_tests():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


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
async def test_embed_session_submit_stores_submission_attribution_consent_and_tracking_without_workflow(
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
    assert payload["outcome"] == "workflow_pending"
    assert payload["intake_lead_id"] is None

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
    assert duplicate_res.json()["outcome"] == "workflow_pending"

    submission_id = uuid.UUID(payload["id"])
    link_uuid = uuid.UUID(link_id)
    submission = db.query(FormSubmission).filter(FormSubmission.id == submission_id).first()
    assert submission is not None
    assert submission.published_version_id is not None
    assert submission.idempotency_key == "idem-embed-1"
    assert submission.form_schema_hash
    assert submission.consent_text_hash
    assert submission.tracking_policy_hash
    assert submission.match_status == "workflow_pending"
    assert submission.full_name_normalized == "embed lead"
    assert submission.email_hash
    assert submission.phone_hash

    assert (
        db.query(IntakeLead)
        .filter(IntakeLead.form_submission_id == submission_id)
        .first()
        is None
    )

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
async def test_embed_submit_enabled_workflow_creates_one_lead(
    authed_client,
    db,
    test_org,
    test_user,
):
    form_id, link_id, slug = await _create_published_lead_capture_form(authed_client)
    allowed_origin = "https://www.ewisurrogacy.com"

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Create embed lead {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[{"action_type": "create_intake_lead", "source": "form_embed"}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    link_res = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={
            "embed_enabled": True,
            "allowed_embed_origins": [allowed_origin],
            "tracking_mode": "internal_only",
            "consent_text": "I agree to be contacted about my inquiry.",
        },
    )
    assert link_res.status_code == 200

    public_res = await authed_client.get(
        f"/forms/public/embed/{slug}",
        headers={"origin": allowed_origin},
    )
    assert public_res.status_code == 200
    session_res = await authed_client.post(
        f"/forms/public/embed/{slug}/session",
        json={"parent_origin": allowed_origin, "attribution": {}},
    )
    assert session_res.status_code == 200

    submit_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": session_res.json()["session_token"],
            "idempotency_key": "idem-embed-workflow",
            "published_version_id": public_res.json()["published_version_id"],
            "answers": {
                "full_name": "Workflow Embed Lead",
                "email": "workflow-embed@example.com",
                "phone": "+1 (555) 481-0902",
                "state": "CA",
            },
            "consent": {"accepted": True},
            "attribution": {},
        },
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert payload["outcome"] == "lead_created"
    assert payload["intake_lead_id"] is not None

    submission_id = uuid.UUID(payload["id"])
    lead_count = (
        db.query(IntakeLead)
        .filter(IntakeLead.organization_id == test_org.id)
        .filter(IntakeLead.form_submission_id == submission_id)
        .count()
    )
    assert lead_count == 1

    from app.services import workflow_triggers

    submission = db.query(FormSubmission).filter(FormSubmission.id == submission_id).one()
    workflow_triggers.trigger_form_submitted(
        db=db,
        org_id=test_org.id,
        form_id=uuid.UUID(form_id),
        submission_id=submission.id,
        submitted_at=submission.submitted_at,
        surrogate_id=submission.surrogate_id,
        source_mode=submission.source_mode,
        entity_owner_id=None,
    )
    assert (
        db.query(IntakeLead)
        .filter(IntakeLead.organization_id == test_org.id)
        .filter(IntakeLead.full_name == "Workflow Embed Lead")
        .count()
        == 1
    )
    assert (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == test_org.id,
            WorkflowExecution.workflow_id == workflow.id,
            WorkflowExecution.entity_id == submission_id,
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_embed_submit_duplicate_applicant_returns_conflict(
    authed_client,
):
    _form_id, link_id, slug = await _create_published_lead_capture_form(authed_client)
    allowed_origin = "https://www.ewisurrogacy.com"

    link_res = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={
            "embed_enabled": True,
            "allowed_embed_origins": [allowed_origin],
            "tracking_mode": "enhanced_match_lead",
            "consent_text": "I agree to be contacted.",
        },
    )
    assert link_res.status_code == 200
    public_res = await authed_client.get(
        f"/forms/public/embed/{slug}",
        headers={"origin": allowed_origin},
    )
    assert public_res.status_code == 200

    first_session = await authed_client.post(
        f"/forms/public/embed/{slug}/session",
        json={"parent_origin": allowed_origin, "attribution": {}},
    )
    assert first_session.status_code == 200
    first_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": first_session.json()["session_token"],
            "idempotency_key": "idem-duplicate-original",
            "published_version_id": public_res.json()["published_version_id"],
            "answers": {
                "full_name": "Duplicate Embed",
                "email": "duplicate-embed@example.com",
                "phone": "+1 (555) 222-7788",
            },
            "consent": {"accepted": True},
            "attribution": {},
        },
    )
    assert first_res.status_code == 200

    second_session = await authed_client.post(
        f"/forms/public/embed/{slug}/session",
        json={"parent_origin": allowed_origin, "attribution": {}},
    )
    assert second_session.status_code == 200
    duplicate_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": second_session.json()["session_token"],
            "idempotency_key": "idem-duplicate-new",
            "published_version_id": public_res.json()["published_version_id"],
            "answers": {
                "full_name": "Duplicate Embed",
                "email": "duplicate-embed@example.com",
                "phone": "+1 (555) 222-7788",
            },
            "consent": {"accepted": True},
            "attribution": {},
        },
    )
    assert duplicate_res.status_code == 409
    detail = duplicate_res.json()["detail"]
    assert "already pending review" in detail.lower()
    assert "duplicate-embed@example.com" not in detail
    assert "Duplicate Embed" not in detail


@pytest.mark.asyncio
async def test_embed_submit_blocks_unresolved_duplicate_applicant(
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
            "consent_text": "I agree to be contacted about my inquiry.",
        },
    )
    assert link_res.status_code == 200
    public_res = await authed_client.get(
        f"/forms/public/embed/{slug}",
        headers={"origin": allowed_origin},
    )
    assert public_res.status_code == 200

    async def start_session() -> str:
        session_res = await authed_client.post(
            f"/forms/public/embed/{slug}/session",
            json={"parent_origin": allowed_origin, "attribution": {}},
        )
        assert session_res.status_code == 200
        return session_res.json()["session_token"]

    answers = {
        "full_name": "Duplicate Embed Lead",
        "email": "duplicate-embed@example.com",
        "phone": "+1 (555) 481-0999",
        "state": "CA",
    }
    first_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": await start_session(),
            "idempotency_key": "idem-embed-duplicate-1",
            "published_version_id": public_res.json()["published_version_id"],
            "answers": answers,
            "consent": {"accepted": True},
            "attribution": {},
        },
    )
    assert first_res.status_code == 200

    duplicate_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": await start_session(),
            "idempotency_key": "idem-embed-duplicate-2",
            "published_version_id": public_res.json()["published_version_id"],
            "answers": answers,
            "consent": {"accepted": True},
            "attribution": {},
        },
    )
    assert duplicate_res.status_code == 409
    detail = duplicate_res.json()["detail"]
    assert "already pending review" in detail.lower()
    assert "duplicate-embed@example.com" not in detail
    assert "Duplicate Embed Lead" not in detail


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
async def test_internal_only_embed_submit_queues_crm_dataset_lead_without_sensitive_answers(
    authed_client,
    db,
    test_org,
):
    from app.services import meta_crm_dataset_settings_service

    _form_id, link_id, slug = await _create_published_lead_capture_form(authed_client)
    allowed_origin = "https://ewi-surrogacy.com"

    settings = meta_crm_dataset_settings_service.get_or_create_settings(db, test_org.id)
    settings.dataset_id = "1428122951556949"
    settings.access_token_encrypted = meta_crm_dataset_settings_service.encrypt_access_token(
        "meta-token"
    )
    settings.enabled = True
    settings.send_hashed_pii = True
    db.commit()

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
    public_payload = public_res.json()

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
                "landing_url": "https://ewi-surrogacy.com",
                "medical_condition": "do not send",
            },
        },
    )
    assert session_res.status_code == 200

    submit_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": session_res.json()["session_token"],
            "idempotency_key": "idem-internal-crm-dataset",
            "published_version_id": public_payload["published_version_id"],
            "answers": {
                "full_name": "Internal Lead",
                "email": "internal-lead@example.com",
                "phone": "+1 (555) 222-3333",
                "state": "CA",
                "free_text_medical_notes": "private text",
            },
            "consent": {"accepted": True},
            "attribution": {},
        },
    )
    assert submit_res.status_code == 200
    submission_id = uuid.UUID(submit_res.json()["id"])
    assert submit_res.json()["outcome"] == "workflow_pending"
    assert submit_res.json()["intake_lead_id"] is None

    assert (
        db.query(TrackingEventLog)
        .filter(TrackingEventLog.form_submission_id == submission_id)
        .first()
        is None
    )

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_CRM_DATASET_EVENT.value,
        )
        .one()
    )
    event_data = job.payload["body"]["data"][0]
    assert event_data["event_name"] == "Lead"
    assert event_data["event_id"] == f"sf_lead_{submission_id}"
    assert event_data["action_source"] == "website"
    assert event_data["event_source_url"] == "https://ewi-surrogacy.com"
    assert event_data["custom_data"] == {
        "content_name": "lead_capture",
        "content_category": "intake",
        "event_source": "website",
        "source": "meta",
        "campaign": "spring-surrogate",
    }
    user_data = event_data["user_data"]
    assert user_data["fbc"] == "fb.1.1772942400.fb-test-click"
    assert user_data["fbp"] == "fb.1.1772942400.1234567890"
    assert user_data["em"]
    assert user_data["ph"]
    assert "fn" not in user_data
    assert "ln" not in user_data
    assert "answers" not in event_data
    assert "medical" not in str(event_data)
    assert "private text" not in str(event_data)
    assert "internal-lead@example.com" not in str(event_data)
    assert "+15552223333" not in str(event_data)

    monitor_event = (
        db.query(MetaCrmDatasetEvent)
        .filter(MetaCrmDatasetEvent.event_id == f"sf_lead_{submission_id}")
        .one()
    )
    assert monitor_event.status == "queued"
    assert monitor_event.event_name == "Lead"
    assert monitor_event.lead_id is None
    assert monitor_event.form_submission_id == submission_id
    assert monitor_event.intake_lead_id is None
    assert monitor_event.stage_key == "form_submitted"


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
