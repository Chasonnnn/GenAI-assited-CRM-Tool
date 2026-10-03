"""Public submit responses must not reveal whether an applicant matched an existing record."""

from __future__ import annotations

import json
import uuid

import pytest

from app.core.config import settings
from app.db.models import Form, FormSubmission
from app.schemas.donor import DonorCreate
from app.services import donor_service
from tests.test_forms_public_embed import _create_published_lead_capture_form
from tests.test_forms_public_shared_intake import (
    _create_published_form_and_shared_link,
    _create_surrogate,
)
from tests.test_hosted_donor_forms import _create_donor_form, _submit_donor_form

PUBLIC_SUBMIT_RESPONSE_KEYS = {"id", "outcome"}


@pytest.fixture(autouse=True)
def _reset_rate_limiter_between_tests():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


def _public_result(response) -> dict:
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == PUBLIC_SUBMIT_RESPONSE_KEYS
    return {key: value for key, value in body.items() if key != "id"}


def _automatic_matching(db, *, org_id, user_id, form_id: str) -> None:
    form = db.query(Form).filter_by(id=uuid.UUID(form_id), organization_id=org_id).one()
    form.routing_exact_match = "auto"
    form.routing_no_match = "off"
    db.commit()


@pytest.mark.asyncio
async def test_hosted_submit_hides_the_matched_surrogate(
    authed_client, client, db, test_org, test_user, default_stage
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)
    surrogate = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Returning Applicant",
        email="returning@example.com",
        phone="+1 (555) 222-4444",
        date_of_birth="1990-05-06",
    )
    _automatic_matching(db, org_id=test_org.id, user_id=test_user.id, form_id=form_id)

    submit = await client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Returning Applicant",
                    "date_of_birth": "1990-05-06",
                    "phone": "+1 (555) 222-4444",
                    "email": "returning@example.com",
                }
            )
        },
    )

    stranger = await client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "New Applicant",
                    "date_of_birth": "1992-07-08",
                    "phone": "+1 (555) 333-7777",
                    "email": "new-applicant@example.com",
                }
            )
        },
    )

    assert _public_result(submit) == _public_result(stranger) == {"outcome": "received"}
    assert str(surrogate.id) not in submit.text
    submission = db.get(FormSubmission, uuid.UUID(submit.json()["id"]))
    assert submission.surrogate_id == surrogate.id
    assert submission.match_status == "linked"
    unmatched = db.get(FormSubmission, uuid.UUID(stranger.json()["id"]))
    assert unmatched.match_status != "linked"


@pytest.mark.asyncio
async def test_hosted_submit_hides_the_matched_donor(
    authed_client, client, db, test_org, test_user, monkeypatch
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Taylor Donor",
            email="returning-donor@example.com",
            phone="+16075550199",
        ),
    )
    form_id, slug = await _create_donor_form(authed_client)
    _automatic_matching(db, org_id=test_org.id, user_id=test_user.id, form_id=form_id)
    _other_form_id, other_slug = await _create_donor_form(authed_client)

    submit = await _submit_donor_form(client, slug=slug, email="returning-donor@example.com")
    stranger = await _submit_donor_form(
        client, slug=other_slug, email="new-donor@example.com", idempotency_key="stranger-1"
    )
    replay = await _submit_donor_form(
        client, slug=other_slug, email="new-donor@example.com", idempotency_key="stranger-1"
    )

    assert _public_result(submit) == _public_result(stranger) == {"outcome": "received"}
    assert replay.json() == stranger.json()
    assert str(donor.id) not in submit.text
    submission = db.get(FormSubmission, uuid.UUID(submit.json()["id"]))
    assert submission.donor_id == donor.id
    assert submission.match_status == "linked"
    unmatched = db.get(FormSubmission, uuid.UUID(stranger.json()["id"]))
    assert unmatched.donor_id is None


@pytest.mark.asyncio
async def test_embed_submit_returns_only_the_submission_reference(authed_client, client, db):
    _form_id, link_id, slug = await _create_published_lead_capture_form(authed_client)
    origin = "https://www.ewisurrogacy.com"
    update = await authed_client.patch(
        f"/forms/intake-links/{link_id}",
        json={"embed_enabled": True, "allowed_embed_origins": [origin]},
    )
    assert update.status_code == 200, update.text
    public_form = await client.get(f"/forms/public/embed/{slug}", headers={"origin": origin})
    assert public_form.status_code == 200, public_form.text
    session = await client.post(
        f"/forms/public/embed/{slug}/session",
        json={"parent_origin": origin, "attribution": {}},
    )
    assert session.status_code == 200, session.text

    submit = await client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": session.json()["session_token"],
            "idempotency_key": "embed-privacy-1",
            "published_version_id": public_form.json()["published_version_id"],
            "answers": {"full_name": "Embed Applicant", "email": "embed-privacy@example.com"},
            "attribution": {},
        },
    )

    assert _public_result(submit) == {"outcome": "received"}
