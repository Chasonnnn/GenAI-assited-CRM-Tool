"""Integration tests for embeddable public lead-capture intake."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db.enums import JobType
from app.db.models import (
    AutomationWorkflow,
    ConsentRecord,
    EmbedSession,
    Form,
    FormIntakeDraft,
    FormIntakeLink,
    FormSubmission,
    IntakeLead,
    Job,
    LeadAttribution,
    MessagingConsentEvidence,
    MessagingConsentState,
    MessagingContact,
    MetaCrmDatasetEvent,
    Organization,
    PublishedIntakeVersion,
    Surrogate,
    TrackingEventLog,
    WorkflowExecution,
)
from app.db.models.messaging import TwilioSettings
from app.services import form_intake_service


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
    return await _create_published_lead_capture_form_with_schema(
        authed_client,
        form_schema=_lead_capture_schema(),
    )


async def _create_published_lead_capture_form_with_schema(
    authed_client,
    *,
    form_schema: dict[str, object],
    mappings: list[dict[str, str]] | None = None,
) -> tuple[str, str, str]:
    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Lead Capture",
            "description": "Public lead form",
            "purpose": "lead_capture",
            "form_schema": form_schema,
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    if mappings is not None:
        mapping_res = await authed_client.put(
            f"/forms/{form_id}/mappings", json={"mappings": mappings}
        )
        assert mapping_res.status_code == 200

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    links_res = await authed_client.get(f"/forms/{form_id}/intake-links")
    assert links_res.status_code == 200
    links = links_res.json()
    assert len(links) >= 1
    return form_id, links[0]["id"], links[0]["slug"]


@pytest.mark.asyncio
async def test_embed_public_form_uses_latest_logo_branding_without_republish(
    authed_client, db, test_org
):
    form_id, link_id, slug = await _create_published_lead_capture_form(authed_client)
    allowed_origin = "https://www.ewisurrogacy.com"
    logo_url = f"/forms/public/{test_org.id}/signature-logo"
    updated_schema = _lead_capture_schema()
    updated_schema["public_title"] = "Unpublished Lead Capture Title"
    updated_schema["logo_url"] = logo_url

    test_org.signature_logo_url = "logos/ewi-signature.png"
    db.add(test_org)
    db.commit()

    update_res = await authed_client.patch(
        f"/forms/{form_id}",
        json={"form_schema": updated_schema},
    )
    assert update_res.status_code == 200

    link_res = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={
            "embed_enabled": True,
            "allowed_embed_origins": [allowed_origin],
            "tracking_mode": "privacy_safe_lead",
        },
    )
    assert link_res.status_code == 200

    public_res = await authed_client.get(
        f"/forms/public/embed/{slug}",
        headers={"origin": allowed_origin},
    )
    assert public_res.status_code == 200
    public_schema = public_res.json()["form_schema"]
    assert public_schema["logo_url"] == logo_url
    assert public_schema["public_title"] == "Become a Surrogate"
    # Agency branding is a hosted-intake field; the embed payload stays unchanged.
    assert "agency_name" not in public_res.json()
    assert "agency_logo_url" not in public_res.json()


@pytest.fixture
def messaging_consent_settings(db, test_org):
    settings = TwilioSettings(
        organization_id=test_org.id,
        enabled=False,
        legal_messaging_brand="EWI Surrogacy",
        operational_disclosure=(
            "I agree to receive application and appointment texts from EWI Surrogacy. "
            "Message frequency varies. Msg & data rates may apply. Reply STOP to opt out "
            "or HELP for help."
        ),
        promotional_disclosure=(
            "I agree to receive promotional texts from EWI Surrogacy about surrogacy "
            "opportunities. Message frequency varies. Msg & data rates may apply. "
            "Reply STOP to opt out or HELP for help."
        ),
        sms_terms_url="https://agency.example/sms-terms",
        privacy_policy_url="https://agency.example/privacy",
        support_contact="support@agency.example",
        expected_frequency="Message frequency varies",
        counsel_approved_at=datetime.now(UTC),
    )
    db.add(settings)
    db.commit()
    return settings


@pytest.mark.asyncio
async def test_embed_sms_choices_are_optional_separate_and_snapshotted(
    authed_client, db, test_org, messaging_consent_settings
):
    _form_id, link_id, slug = await _create_published_lead_capture_form(authed_client)
    allowed_origin = "https://www.ewisurrogacy.com"
    link_res = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={
            "embed_enabled": True,
            "allowed_embed_origins": [allowed_origin],
            "tracking_mode": "privacy_safe_lead",
        },
    )
    assert link_res.status_code == 200

    public_res = await authed_client.get(
        f"/forms/public/embed/{slug}",
        headers={"origin": allowed_origin},
    )
    assert public_res.status_code == 200
    public_payload = public_res.json()
    assert public_payload["messaging_consent"]["phone_field_key"] == "phone"
    assert public_payload["messaging_consent"]["operational"]["disclosure"].startswith(
        "I agree to receive application"
    )
    assert public_payload["messaging_consent"]["promotional"]["disclosure"].startswith(
        "I agree to receive promotional"
    )

    session_res = await authed_client.post(
        f"/forms/public/embed/{slug}/session",
        json={"parent_origin": allowed_origin, "attribution": {}},
    )
    assert session_res.status_code == 200
    submit_res = await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": session_res.json()["session_token"],
            "idempotency_key": "sms-choice-1",
            "published_version_id": public_payload["published_version_id"],
            "answers": {
                "full_name": "Consent Choice",
                "email": "consent-choice@example.com",
                "phone": "+1 555 481 0901",
            },
            "sms_operational": True,
            "sms_promotional": False,
            "sms_phone_field_key": public_payload["messaging_consent"]["phone_field_key"],
        },
    )
    assert submit_res.status_code == 200

    consent_rows = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.form_submission_id == uuid.UUID(submit_res.json()["id"]))
        .order_by(ConsentRecord.consent_type.asc())
        .all()
    )
    consent_by_type = {row.consent_type: row for row in consent_rows}
    assert consent_by_type["contact"].accepted is False
    assert consent_by_type["sms_operational"].accepted is True
    assert consent_by_type["sms_promotional"].accepted is False
    assert consent_by_type["sms_operational"].consent_text_hash
    assert consent_by_type["sms_operational"].privacy_policy_url_snapshot == (
        "https://agency.example/privacy"
    )
    messaging_contact = (
        db.query(MessagingContact).filter(MessagingContact.organization_id == test_org.id).one()
    )
    state_by_purpose = {
        state.purpose: state.status
        for state in db.query(MessagingConsentState)
        .filter(MessagingConsentState.contact_id == messaging_contact.id)
        .all()
    }
    assert state_by_purpose == {
        "operational": "opted_in",
        "promotional": "unknown",
    }


async def _create_sms_phone_form(authed_client, variant):
    schema = _lead_capture_schema(
        extra_fields=[
            {
                "key": "date_of_birth",
                "label": "DOB",
                "type": "date",
                "required": False,
                "sensitivity": "identity",
            }
        ]
    )
    fields = schema["pages"][0]["fields"]
    phone_field = next(field for field in fields if field["key"] == "phone")
    mappings = None
    if variant == "mapped":
        phone_field["key"] = "mobile"
        fields.insert(0, {**phone_field, "key": "phone", "label": "Other Phone"})
        mappings = [{"field_key": "mobile", "surrogate_field": "phone"}]
    elif variant == "none":
        fields.remove(phone_field)
    elif variant == "unmapped":
        phone_field["key"] = "backup_phone"
    elif variant == "hidden":
        phone_field["show_if"] = {"field_key": "state", "operator": "equals", "value": "CA"}
    form_id, link_id, slug = await _create_published_lead_capture_form_with_schema(
        authed_client, form_schema=schema, mappings=mappings
    )
    origin = "https://agency.example"
    enabled = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={
            "embed_enabled": True,
            "allowed_embed_origins": [origin],
            "tracking_mode": "internal_only",
        },
    )
    assert enabled.status_code == 200
    if variant == "draft_mapped":
        fields.append({**phone_field, "key": "mobile", "label": "Draft Mobile"})
        updated = await authed_client.patch(f"/forms/{form_id}", json={"form_schema": schema})
        assert updated.status_code == 200
        mapped = await authed_client.put(
            f"/forms/{form_id}/mappings",
            json={"mappings": [{"field_key": "mobile", "surrogate_field": "phone"}]},
        )
        assert mapped.status_code == 200
    return slug, origin


async def _submit_sms_phone_form(
    authed_client,
    *,
    surface,
    slug,
    origin,
    payload,
    answers,
    purpose,
    accepted=True,
    organization_id=None,
):
    phone_key = payload["messaging_consent"]["phone_field_key"]
    scope = {"organization_id": str(organization_id)} if organization_id else {}
    if surface == "intake":
        return await authed_client.post(
            f"/forms/public/intake/{slug}/submit",
            params=scope,
            data={
                "answers": json.dumps(answers),
                "published_version_id": payload["published_version_id"],
                f"sms_{purpose}": str(accepted).lower(),
                **({"sms_phone_field_key": phone_key} if phone_key is not None else {}),
                **scope,
            },
        )
    session = await authed_client.post(
        f"/forms/public/embed/{slug}/session",
        json={"parent_origin": origin, "attribution": {}},
    )
    assert session.status_code == 200
    return await authed_client.post(
        f"/forms/public/embed/{slug}/submit",
        params=scope,
        json={
            "embed_session_token": session.json()["session_token"],
            "idempotency_key": f"phone-consent-{uuid.uuid4().hex}",
            "published_version_id": payload["published_version_id"],
            "answers": answers,
            f"sms_{purpose}": accepted,
            "sms_phone_field_key": phone_key,
            **scope,
        },
    )


@pytest.mark.parametrize("surface", ["intake", "embed"])
@pytest.mark.parametrize(
    "variant,expected",
    [
        ("mapped", "mobile"),
        ("plain", "phone"),
        ("none", None),
        ("unmapped", None),
        ("draft_mapped", "phone"),
    ],
)
async def test_public_sms_options_resolve_published_phone_field(
    authed_client, messaging_consent_settings, surface, variant, expected
):
    slug, origin = await _create_sms_phone_form(authed_client, variant)
    response = await authed_client.get(
        f"/forms/public/{surface}/{slug}", headers={"origin": origin}
    )
    assert response.status_code == 200
    options = response.json()["messaging_consent"]
    assert options["phone_field_key"] == expected
    for purpose in ("operational", "promotional"):
        assert (options[purpose] is not None) is (expected is not None)


@pytest.mark.parametrize("surface", ["intake", "embed"])
@pytest.mark.parametrize("purpose", ["operational", "promotional"])
@pytest.mark.parametrize(
    "variant,answer",
    [
        ("none", "+14155550199"),
        ("plain", None),
        ("plain", ""),
        ("plain", "invalid-secret-phone"),
        ("plain", ["invalid-secret-phone"]),
        ("mapped", None),
        ("mapped", "invalid-secret-phone"),
    ],
)
async def test_public_sms_consent_rejects_missing_or_invalid_phone_atomically(
    authed_client, db, test_org, messaging_consent_settings, surface, purpose, variant, answer
):
    slug, origin = await _create_sms_phone_form(authed_client, variant)
    payload = (await authed_client.get(f"/forms/public/{surface}/{slug}")).json()
    answers = {
        "full_name": "SMS Applicant",
        "email": "sms-applicant@example.com",
        "date_of_birth": "1993-04-12",
        "phone": "+14155550198",
    }
    key = "mobile" if variant == "mapped" else "phone"
    if answer is None:
        answers.pop(key, None)
    else:
        answers[key] = answer
    response = await _submit_sms_phone_form(
        authed_client,
        surface=surface,
        slug=slug,
        origin=origin,
        payload=payload,
        answers=answers,
        purpose=purpose,
    )
    assert response.status_code == (409 if variant == "none" else 400)
    assert response.json()["detail"] == (
        "This form changed. Reload the page and try again."
        if variant == "none"
        else "A valid phone number is required to enroll in SMS"
    )
    _assert_no_sms_submission(db, test_org.id)


def _assert_no_sms_submission(db, org_id):
    for model in (
        FormSubmission,
        ConsentRecord,
        MessagingContact,
        MessagingConsentEvidence,
        MessagingConsentState,
    ):
        assert db.query(model).filter(model.organization_id == org_id).count() == 0


@pytest.mark.parametrize("surface", ["intake", "embed"])
@pytest.mark.parametrize(
    "variant,expected_phone",
    [
        ("mapped", "+14155550199"),
        ("draft_mapped", "+14155550198"),
    ],
)
async def test_public_sms_read_and_submit_use_same_phone_field(
    authed_client,
    db,
    test_org,
    messaging_consent_settings,
    monkeypatch,
    surface,
    variant,
    expected_phone,
):
    monkeypatch.setattr(
        form_intake_service, "_attempt_form_submission_workflow_job", lambda *a, **k: None
    )
    slug, origin = await _create_sms_phone_form(authed_client, variant)
    payload = (await authed_client.get(f"/forms/public/{surface}/{slug}")).json()
    answers = {
        "full_name": "SMS Applicant",
        "email": "sms-applicant@example.com",
        "date_of_birth": "1993-04-12",
        "phone": "+14155550198",
        "mobile": "+14155550199",
    }
    assert answers[payload["messaging_consent"]["phone_field_key"]] == expected_phone
    response = await _submit_sms_phone_form(
        authed_client,
        surface=surface,
        slug=slug,
        origin=origin,
        payload=payload,
        answers=answers,
        purpose="operational",
    )
    assert response.status_code == 200
    contact = db.query(MessagingContact).filter_by(organization_id=test_org.id).one()
    assert contact.phone_e164 == expected_phone
    evidence = db.query(MessagingConsentEvidence).filter_by(organization_id=test_org.id).one()
    assert evidence.contact_id == contact.id
    # Workflow execution can follow a later mapping edit; it must use the saved snapshots.
    remap = await authed_client.put(
        f"/forms/{payload['form_id']}/mappings",
        json={"mappings": [{"field_key": "phone", "surrogate_field": "phone"}]},
    )
    assert remap.status_code == 200
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    form_intake_service.auto_match_submission(db, submission=submission)
    _, lead = form_intake_service.create_intake_lead_for_submission(
        db, submission=submission, user_id=None, allow_ambiguous=True
    )
    surrogate = db.get(Surrogate, lead.promoted_surrogate_id)
    assert lead.phone == surrogate.phone == contact.phone_e164 == expected_phone


@pytest.mark.parametrize("surface", ["intake", "embed"])
@pytest.mark.parametrize("variant", ["mapped", "draft_mapped"])
async def test_public_sms_auto_match_uses_submission_snapshots(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
    messaging_consent_settings,
    monkeypatch,
    surface,
    variant,
):
    from tests.test_forms_public_shared_intake import _create_surrogate

    monkeypatch.setattr(
        form_intake_service, "_attempt_form_submission_workflow_job", lambda *a, **k: None
    )
    slug, origin = await _create_sms_phone_form(authed_client, variant)
    payload = (await authed_client.get(f"/forms/public/{surface}/{slug}")).json()
    response = await _submit_sms_phone_form(
        authed_client,
        surface=surface,
        slug=slug,
        origin=origin,
        payload=payload,
        answers={
            "full_name": "SMS Applicant",
            "email": "sms@example.com",
            "date_of_birth": "1993-04-12",
            "phone": "+14155550198",
            "mobile": "+14155550199",
        },
        purpose="operational",
    )
    assert response.status_code == 200, response.text
    contact = db.query(MessagingContact).filter_by(organization_id=test_org.id).one()
    candidate = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="SMS Applicant",
        email="different-email@example.com",
        phone=contact.phone_e164,
        date_of_birth="1993-04-12",
    )
    remap = await authed_client.put(
        f"/forms/{payload['form_id']}/mappings",
        json={
            "mappings": [
                {
                    "field_key": "phone" if variant == "mapped" else "mobile",
                    "surrogate_field": "phone",
                }
            ]
        },
    )
    assert remap.status_code == 200
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    _, outcome = form_intake_service.auto_match_submission(db, submission=submission)
    assert outcome == "linked"
    assert submission.surrogate_id == candidate.id
    assert submission.match_reason == "phone_dob_name_exact"


async def test_shared_draft_phone_ignores_unpublished_answer_keys(authed_client, db, test_org):
    from app.core.encryption import hash_phone

    slug, _origin = await _create_sms_phone_form(authed_client, "draft_mapped")
    answers = {
        "full_name": "Draft Applicant",
        "date_of_birth": "1993-04-12",
        "phone": "+14155550198",
    }
    response = await authed_client.put(
        f"/forms/public/intake/{slug}/draft/saved-draft", json={"answers": answers}
    )
    assert response.status_code == 200
    draft = db.query(FormIntakeDraft).filter_by(organization_id=test_org.id).one()
    draft.answers_json = {**answers, "mobile": "+14155550199"}
    db.commit()
    response = await authed_client.put(
        f"/forms/public/intake/{slug}/draft/saved-draft", json={"answers": {}}
    )
    assert response.status_code == 200
    db.refresh(draft)
    assert draft.phone_hash == hash_phone(answers["phone"])
    lookup = await authed_client.post(
        f"/forms/public/intake/{slug}/draft/lookup",
        json={"answers": draft.answers_json, "current_draft_session_id": "new-draft"},
    )
    assert lookup.status_code == 200
    assert lookup.json()["status"] == "match_found"


@pytest.mark.parametrize("surface", ["intake", "embed"])
@pytest.mark.parametrize("phone_key", [None, "phone", "mobile"])
@pytest.mark.parametrize("purpose", ["operational", "promotional"])
async def test_public_sms_consent_requires_matching_phone_field_key(
    authed_client, db, test_org, messaging_consent_settings, surface, phone_key, purpose
):
    slug, origin = await _create_sms_phone_form(authed_client, "mapped")
    payload = (await authed_client.get(f"/forms/public/{surface}/{slug}")).json()
    payload["messaging_consent"]["phone_field_key"] = phone_key
    response = await _submit_sms_phone_form(
        authed_client,
        surface=surface,
        slug=slug,
        origin=origin,
        payload=payload,
        answers={
            "full_name": "SMS Applicant",
            "email": "sms@example.com",
            "date_of_birth": "1993-04-12",
            "phone": "+14155550198",
            "mobile": "+14155550199",
        },
        purpose=purpose,
    )
    if phone_key == "mobile":
        assert response.status_code == 200, response.text
        assert (
            db.query(MessagingContact).filter_by(organization_id=test_org.id).one().phone_e164
            == "+14155550199"
        )
    else:
        assert response.status_code == 409
        assert response.json()["detail"] == "This form changed. Reload the page and try again."
        _assert_no_sms_submission(db, test_org.id)


@pytest.mark.parametrize("surface", ["intake", "embed"])
async def test_public_sms_remap_between_read_and_submit_is_rejected(
    authed_client, db, test_org, messaging_consent_settings, surface
):
    slug, origin = await _create_sms_phone_form(authed_client, "mapped")
    payload = (await authed_client.get(f"/forms/public/{surface}/{slug}")).json()
    assert payload["messaging_consent"]["phone_field_key"] == "mobile"
    remap = await authed_client.put(
        f"/forms/{payload['form_id']}/mappings",
        json={"mappings": [{"field_key": "phone", "surrogate_field": "phone"}]},
    )
    assert remap.status_code == 200
    current = (await authed_client.get(f"/forms/public/{surface}/{slug}")).json()
    assert current["published_version_id"] == payload["published_version_id"]
    assert current["messaging_consent"]["phone_field_key"] == "phone"
    response = await _submit_sms_phone_form(
        authed_client,
        surface=surface,
        slug=slug,
        origin=origin,
        payload=payload,
        answers={
            "full_name": "SMS Applicant",
            "email": "sms@example.com",
            "date_of_birth": "1993-04-12",
            "phone": "+14155550198",
            "mobile": "+14155550199",
        },
        purpose="operational",
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "This form changed. Reload the page and try again."
    _assert_no_sms_submission(db, test_org.id)


@pytest.mark.parametrize("surface", ["intake", "embed"])
@pytest.mark.parametrize("phone_key", [None, "outdated"])
async def test_public_sms_phone_key_is_ignored_without_consent(
    authed_client, db, test_org, messaging_consent_settings, surface, phone_key
):
    slug, origin = await _create_sms_phone_form(authed_client, "plain")
    payload = (await authed_client.get(f"/forms/public/{surface}/{slug}")).json()
    payload["messaging_consent"]["phone_field_key"] = phone_key
    response = await _submit_sms_phone_form(
        authed_client,
        surface=surface,
        slug=slug,
        origin=origin,
        payload=payload,
        answers={
            "full_name": "SMS Applicant",
            "email": "sms@example.com",
            "date_of_birth": "1993-04-12",
            "phone": "+14155550198",
        },
        purpose="operational",
        accepted=False,
    )
    assert response.status_code == 200, response.text
    assert db.query(MessagingConsentEvidence).filter_by(organization_id=test_org.id).count() == 0


@pytest.mark.parametrize("surface", ["intake", "embed"])
@pytest.mark.parametrize("state", ["NY", "CA"])
async def test_public_sms_requires_visible_phone_field(
    authed_client, db, test_org, messaging_consent_settings, surface, state
):
    slug, origin = await _create_sms_phone_form(authed_client, "hidden")
    payload = (await authed_client.get(f"/forms/public/{surface}/{slug}")).json()
    response = await _submit_sms_phone_form(
        authed_client,
        surface=surface,
        slug=slug,
        origin=origin,
        payload=payload,
        answers={
            "full_name": "SMS Applicant",
            "email": "sms@example.com",
            "date_of_birth": "1993-04-12",
            "phone": "+14155550198",
            "state": state,
        },
        purpose="operational",
    )
    if state == "CA":
        assert response.status_code == 200, response.text
    else:
        assert response.status_code == 400
        assert response.json()["detail"] == "A valid phone number is required to enroll in SMS"
        _assert_no_sms_submission(db, test_org.id)


@pytest.mark.parametrize("surface", ["intake", "embed"])
async def test_public_sms_submit_uses_link_organization_for_ledger(
    authed_client, db, test_org, messaging_consent_settings, surface
):
    slug, origin = await _create_sms_phone_form(authed_client, "plain")
    payload = (await authed_client.get(f"/forms/public/{surface}/{slug}")).json()
    other_org = Organization(id=uuid.uuid4(), name="Other Agency", slug=f"other-{uuid.uuid4().hex}")
    db.add(other_org)
    db.commit()
    response = await _submit_sms_phone_form(
        authed_client,
        surface=surface,
        slug=slug,
        origin=origin,
        payload=payload,
        answers={
            "full_name": "SMS Applicant",
            "email": "sms@example.com",
            "date_of_birth": "1993-04-12",
            "phone": "+14155550198",
        },
        purpose="operational",
        organization_id=other_org.id,
    )
    assert response.status_code == 200, response.text
    for model in (MessagingContact, MessagingConsentEvidence):
        assert db.query(model).filter_by(organization_id=test_org.id).count() == 1
        assert db.query(model).filter_by(organization_id=other_org.id).count() == 0
    # Consent state is projected per purpose; only the operational one was opted in.
    states = db.query(MessagingConsentState).filter_by(organization_id=test_org.id).all()
    assert {state.purpose for state in states if state.status == "opted_in"} == {"operational"}
    assert db.query(MessagingConsentState).filter_by(organization_id=other_org.id).count() == 0


@pytest.mark.parametrize("include_email", [True, False])
async def test_embed_submit_validates_published_version_schema(
    authed_client, db, test_org, messaging_consent_settings, include_email
):
    slug, origin = await _create_sms_phone_form(authed_client, "plain")
    payload = (await authed_client.get(f"/forms/public/embed/{slug}")).json()
    form = db.get(Form, uuid.UUID(payload["form_id"]))
    version = db.get(PublishedIntakeVersion, uuid.UUID(payload["published_version_id"]))
    replacement = deepcopy(form.published_schema_json)
    fields = replacement["pages"][0]["fields"]
    next(field for field in fields if field["key"] == "email")["required"] = False
    fields.append({"key": "later_field", "label": "Later Field", "type": "text", "required": True})
    form.published_schema_json = replacement
    db.commit()
    answers = {"full_name": "SMS Applicant", "date_of_birth": "1993-04-12", "phone": "+14155550198"}
    if include_email:
        answers["email"] = "sms@example.com"
    else:
        answers["later_field"] = "Only required by the replacement schema"
    response = await _submit_sms_phone_form(
        authed_client,
        surface="embed",
        slug=slug,
        origin=origin,
        payload=payload,
        answers=answers,
        purpose="operational",
    )
    if include_email:
        assert response.status_code == 200, response.text
        submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
        assert submission.schema_snapshot == version.form_schema_snapshot_json
    else:
        assert response.status_code == 400
        assert response.json()["detail"] == "Missing required field: Email"
        _assert_no_sms_submission(db, test_org.id)


async def test_donor_sms_uses_published_mapping_snapshot(
    authed_client, db, test_org, messaging_consent_settings, monkeypatch, tmp_path
):
    from app.core.config import settings
    from tests.test_hosted_donor_forms import _create_donor_form, _png_bytes

    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    form_id, slug = await _create_donor_form(authed_client, lead_kind="egg_donor")
    payload = (await authed_client.get(f"/forms/public/intake/{slug}")).json()
    assert payload["messaging_consent"]["phone_field_key"] == "mobile"
    remap = await authed_client.put(f"/forms/{form_id}/mappings", json={"mappings": []})
    assert remap.status_code == 200
    current = (await authed_client.get(f"/forms/public/intake/{slug}")).json()
    assert current["messaging_consent"]["phone_field_key"] == "mobile"
    response = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "applicant_name": "SMS Donor",
                    "email_address": "donor@example.com",
                    "mobile": "+14155550199",
                    "phone": "+14155550198",
                }
            ),
            "published_version_id": payload["published_version_id"],
            "file_field_keys": json.dumps(["headshot"]),
            "sms_operational": "true",
            "sms_phone_field_key": "mobile",
        },
        files=[("files", ("profile.png", _png_bytes(), "image/png"))],
    )
    assert response.status_code == 200, response.text
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    version = db.get(PublishedIntakeVersion, uuid.UUID(payload["published_version_id"]))
    assert submission.mapping_snapshot == version.mapping_snapshot_json
    form_intake_service.auto_match_submission(db, submission=submission)
    _, lead = form_intake_service.create_intake_lead_for_submission(
        db, submission=submission, user_id=None, allow_ambiguous=True
    )
    contact = db.query(MessagingContact).filter_by(organization_id=test_org.id).one()
    assert lead.phone == contact.phone_e164 == "+14155550199"


@pytest.mark.parametrize("surface", ["intake", "embed"])
async def test_public_sms_options_ignore_client_organization_id(
    authed_client, db, messaging_consent_settings, surface
):
    slug, origin = await _create_sms_phone_form(authed_client, "plain")
    other_org = Organization(id=uuid.uuid4(), name="Other Agency", slug=f"other-{uuid.uuid4().hex}")
    db.add(other_org)
    db.flush()
    approved = messaging_consent_settings
    db.add(
        TwilioSettings(
            organization_id=other_org.id,
            **{
                field: getattr(approved, field)
                for field in (
                    "legal_messaging_brand",
                    "operational_disclosure",
                    "promotional_disclosure",
                    "sms_terms_url",
                    "privacy_policy_url",
                    "support_contact",
                    "expected_frequency",
                    "counsel_approved_at",
                )
            },
        )
    )
    approved.counsel_approved_at = None
    db.commit()

    response = await authed_client.get(
        f"/forms/public/{surface}/{slug}",
        params={"organization_id": str(other_org.id)},
        headers={"origin": origin},
    )

    assert response.status_code == 200
    assert response.json()["messaging_consent"] == {
        "phone_field_key": "phone",
        "operational": None,
        "promotional": None,
    }


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
    assert db.get(FormSubmission, uuid.UUID(payload["id"])).match_status == "workflow_pending"

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
    assert duplicate_res.json() == payload

    submission_id = uuid.UUID(payload["id"])
    link_uuid = uuid.UUID(link_id)
    submission = db.query(FormSubmission).filter(FormSubmission.id == submission_id).first()
    assert submission is not None
    workflow_job = (
        db.query(Job)
        .filter(
            Job.organization_id == submission.organization_id,
            Job.job_type == JobType.FORM_SUBMISSION_WORKFLOW.value,
            Job.payload["submission_id"].astext == str(submission_id),
        )
        .one()
    )
    assert workflow_job.status == "completed"
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
        db.query(IntakeLead).filter(IntakeLead.form_submission_id == submission_id).first() is None
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
    # Omitted contact consent is never manufactured by the server.
    assert consent.accepted is False
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
    form_id, link_id, slug = await _create_published_lead_capture_form_with_schema(
        authed_client,
        form_schema=_lead_capture_schema(
            extra_fields=[
                {
                    "key": "height_ft",
                    "label": "Height",
                    "type": "height",
                    "required": True,
                    "sensitivity": "sensitive_health",
                },
                {
                    "key": "weight_lb",
                    "label": "Weight (lb)",
                    "type": "number",
                    "required": True,
                    "sensitivity": "sensitive_health",
                    "validation": {"min_value": 1, "max_value": 1000},
                },
            ]
        ),
    )
    allowed_origin = "https://www.ewisurrogacy.com"

    mappings_res = await authed_client.put(
        f"/forms/{form_id}/mappings",
        json={
            "mappings": [
                {"field_key": "full_name", "surrogate_field": "full_name"},
                {"field_key": "email", "surrogate_field": "email"},
                {"field_key": "phone", "surrogate_field": "phone"},
                {"field_key": "state", "surrogate_field": "state"},
                {"field_key": "height_ft", "surrogate_field": "height_ft"},
                {"field_key": "weight_lb", "surrogate_field": "weight_lb"},
            ]
        },
    )
    assert mappings_res.status_code == 200

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Create embed lead {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[{"action_type": "create_intake_lead"}],
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
                "state": "ca",
                "height_ft": "5.58",
                "weight_lb": "146",
            },
            "consent": {"accepted": True},
            "attribution": {},
        },
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert db.get(FormSubmission, uuid.UUID(payload["id"])).match_status == "lead_created"

    submission_id = uuid.UUID(payload["id"])
    intake_lead = (
        db.query(IntakeLead)
        .filter(IntakeLead.organization_id == test_org.id)
        .filter(IntakeLead.form_submission_id == submission_id)
        .one()
    )
    assert intake_lead.source == "website"
    assert intake_lead.source_metadata["source"] == "website"

    visible_leads_res = await authed_client.get(
        "/surrogates",
        params={"source": "website", "q": "workflow-embed@example.com"},
    )
    assert visible_leads_res.status_code == 200
    visible_leads = visible_leads_res.json()
    assert visible_leads["total"] == 1
    assert visible_leads["items"][0]["full_name"] == "Workflow Embed Lead"
    assert visible_leads["items"][0]["source"] == "website"
    surrogate = (
        db.query(Surrogate).filter(Surrogate.id == uuid.UUID(visible_leads["items"][0]["id"])).one()
    )
    assert surrogate.state == "CA"
    assert surrogate.height_ft == Decimal("5.58")
    assert surrogate.weight_lb == 146

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
    visible_leads_after_retry = await authed_client.get(
        "/surrogates",
        params={"source": "website", "q": "workflow-embed@example.com"},
    )
    assert visible_leads_after_retry.status_code == 200
    assert visible_leads_after_retry.json()["total"] == 1
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
    assert (
        db.get(FormSubmission, uuid.UUID(submit_res.json()["id"])).match_status
        == "workflow_pending"
    )

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


@pytest.mark.asyncio
async def test_embed_health_blocks_privacy_safe_file_fields(authed_client, db):
    form_id, link_id, _slug = await _create_published_lead_capture_form(authed_client)
    file_schema = _lead_capture_schema(
        extra_fields=[
            {
                "key": "supporting_docs",
                "label": "Supporting Documents",
                "type": "file",
                "required": False,
                "sensitivity": "sensitive_health",
            }
        ]
    )
    update_form_res = await authed_client.patch(
        f"/forms/{form_id}",
        json={"form_schema": file_schema},
    )
    assert update_form_res.status_code == 200

    link = db.query(FormIntakeLink).filter(FormIntakeLink.id == uuid.UUID(link_id)).one()
    link.embed_enabled = True
    link.allowed_embed_origins = ["https://www.ewisurrogacy.com"]
    link.tracking_mode = "privacy_safe_lead"
    link.consent_text = "I agree to be contacted about my inquiry."
    db.commit()

    health_res = await authed_client.get(f"/forms/intake-links/{link_id}/embed-health")
    assert health_res.status_code == 200
    payload = health_res.json()
    assert payload["status"] == "blocked"
    checks = {check["key"]: check for check in payload["checks"]}
    assert checks["tracking_policy"]["status"] == "block"
    assert "supporting documents" in checks["tracking_policy"]["message"].lower()
    assert "file" in checks["tracking_policy"]["message"].lower()


@pytest.mark.parametrize(
    ("schema_snapshot", "message"),
    [
        (None, "Submission has no schema snapshot"),
        ({"pages": "not-a-list"}, "Submission schema snapshot is invalid"),
    ],
)
def test_submission_identity_rejects_missing_or_invalid_schema_snapshot(schema_snapshot, message):
    submission = FormSubmission(
        schema_snapshot=schema_snapshot,
        answers_json={"phone": "+14155550198"},
        mapping_snapshot=[],
    )
    with pytest.raises(ValueError, match=f"^{message}$"):
        form_intake_service.extract_submission_identity(submission)
