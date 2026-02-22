"""Integration tests for shared/public intake submission flows."""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

from app.core.encryption import hash_email, hash_phone
from app.db.enums import FormSubmissionMatchStatus
from app.db.models import FormSubmission, IntakeLead, Surrogate
from app.utils.normalization import normalize_email, normalize_name, normalize_phone, normalize_search_text


def _create_surrogate(
    db,
    *,
    org_id,
    user_id,
    stage,
    full_name: str,
    email: str,
    phone: str,
    date_of_birth: str,
):
    normalized_full_name = normalize_name(full_name)
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)

    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name=normalized_full_name,
        full_name_normalized=normalize_search_text(normalized_full_name),
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        phone=normalized_phone,
        phone_hash=hash_phone(normalized_phone),
        date_of_birth=date.fromisoformat(date_of_birth),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


async def _create_published_form_and_shared_link(authed_client):
    schema = {
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

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Shared Intake Form",
            "description": "Campaign intake",
            "form_schema": schema,
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    link_res = await authed_client.post(
        f"/forms/{form_id}/intake-links",
        json={
            "campaign_name": "Spring Event",
            "event_name": "Austin Expo",
            "utm_defaults": {"utm_source": "expo"},
        },
    )
    assert link_res.status_code == 200
    link_payload = link_res.json()
    return form_id, link_payload["id"], link_payload["slug"]


@pytest.mark.asyncio
async def test_shared_draft_lifecycle(authed_client):
    _form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)
    draft_session_id = "draft-shared-1"

    missing_res = await authed_client.get(f"/forms/public/intake/{slug}/draft/{draft_session_id}")
    assert missing_res.status_code == 404

    upsert_res = await authed_client.put(
        f"/forms/public/intake/{slug}/draft/{draft_session_id}",
        json={"answers": {"full_name": "Draft Person", "email": "draft@example.com"}},
    )
    assert upsert_res.status_code == 200

    get_res = await authed_client.get(f"/forms/public/intake/{slug}/draft/{draft_session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["answers"]["full_name"] == "Draft Person"

    delete_res = await authed_client.delete(f"/forms/public/intake/{slug}/draft/{draft_session_id}")
    assert delete_res.status_code == 204

    after_delete_res = await authed_client.get(f"/forms/public/intake/{slug}/draft/{draft_session_id}")
    assert after_delete_res.status_code == 404


@pytest.mark.asyncio
async def test_shared_submit_no_match_creates_intake_lead(authed_client, db, test_org, test_user, default_stage):
    _form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    payload = {
        "full_name": "No Match Candidate",
        "date_of_birth": "1993-04-12",
        "phone": "+1 (555) 100-1000",
        "email": "nomatch@example.com",
    }
    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={"answers": json.dumps(payload)},
    )
    assert submit_res.status_code == 200
    body = submit_res.json()
    assert body["outcome"] == "lead_created"
    assert body["surrogate_id"] is None
    assert body["intake_lead_id"] is not None

    submission = db.query(FormSubmission).filter(FormSubmission.id == body["id"]).first()
    assert submission is not None
    assert submission.source_mode == "shared"
    assert submission.match_status == FormSubmissionMatchStatus.LEAD_CREATED.value
    assert submission.intake_lead_id is not None

    lead = db.query(IntakeLead).filter(IntakeLead.id == submission.intake_lead_id).first()
    assert lead is not None
    assert lead.full_name == "No Match Candidate"


@pytest.mark.asyncio
async def test_shared_submit_exact_match_links_surrogate(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    _form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    surrogate = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Exact Match",
        email="exact@example.com",
        phone="+1 (555) 222-3333",
        date_of_birth="1991-07-10",
    )

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Exact Match",
                    "date_of_birth": "1991-07-10",
                    "phone": "+1 (555) 222-3333",
                    "email": "exact@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200

    body = submit_res.json()
    assert body["outcome"] == "linked"
    assert body["surrogate_id"] == str(surrogate.id)
    assert body["intake_lead_id"] is None


@pytest.mark.asyncio
async def test_shared_submit_ambiguous_then_manual_resolve(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    surrogate_a = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Ambiguous Person",
        email="ambiguous-a@example.com",
        phone="+1 (555) 444-5555",
        date_of_birth="1990-01-01",
    )
    surrogate_b = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Ambiguous Person",
        email="ambiguous-b@example.com",
        phone="+1 (555) 444-5555",
        date_of_birth="1990-01-01",
    )

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Ambiguous Person",
                    "date_of_birth": "1990-01-01",
                    "phone": "+1 (555) 444-5555",
                    "email": "unknown@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert payload["outcome"] == "ambiguous_review"

    submission_id = payload["id"]
    queue_res = await authed_client.get(
        f"/forms/{form_id}/submissions",
        params={"match_status": "ambiguous_review", "source_mode": "shared"},
    )
    assert queue_res.status_code == 200
    assert any(row["id"] == submission_id for row in queue_res.json())

    candidates_res = await authed_client.get(f"/forms/submissions/{submission_id}/match-candidates")
    assert candidates_res.status_code == 200
    candidate_ids = {candidate["surrogate_id"] for candidate in candidates_res.json()}
    assert candidate_ids == {str(surrogate_a.id), str(surrogate_b.id)}

    resolve_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={
            "surrogate_id": str(surrogate_a.id),
            "create_intake_lead": False,
            "review_notes": "Confirmed by intake specialist",
        },
    )
    assert resolve_res.status_code == 200
    resolved = resolve_res.json()
    assert resolved["outcome"] == "linked"
    assert resolved["candidate_count"] == 0
    assert resolved["submission"]["surrogate_id"] == str(surrogate_a.id)
    assert resolved["submission"]["review_notes"] == "Confirmed by intake specialist"

    surrogate_submission_res = await authed_client.get(
        f"/forms/{form_id}/surrogates/{surrogate_a.id}/submission"
    )
    assert surrogate_submission_res.status_code == 200


@pytest.mark.asyncio
async def test_promote_intake_lead_links_pending_submission(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    _form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Lead Candidate",
                    "date_of_birth": "1994-06-06",
                    "phone": "+1 (555) 999-0000",
                    "email": "lead-candidate@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert payload["outcome"] == "lead_created"

    lead_id = payload["intake_lead_id"]
    promote_res = await authed_client.post(
        f"/forms/intake-leads/{lead_id}/promote",
        json={"source": "manual", "is_priority": True},
    )
    assert promote_res.status_code == 200
    promote_payload = promote_res.json()
    assert promote_payload["intake_lead_id"] == lead_id
    assert promote_payload["linked_submission_count"] == 1
    assert promote_payload["surrogate_id"]

    submission = db.query(FormSubmission).filter(FormSubmission.id == payload["id"]).first()
    assert submission is not None
    assert submission.surrogate_id is not None
    assert submission.match_status == FormSubmissionMatchStatus.LINKED.value
