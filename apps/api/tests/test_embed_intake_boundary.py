"""Embedded intake cannot collect file uploads, so donor and required-upload forms stay hosted."""

from __future__ import annotations

import uuid

import pytest

from app.db.models import FormIntakeLink
from tests.test_forms_public_embed import (
    _create_published_lead_capture_form_with_schema,
    _lead_capture_schema,
)
from tests.test_hosted_donor_forms import _create_donor_form

EMBED_SETTINGS = {
    "embed_enabled": True,
    "allowed_embed_origins": ["https://www.ewisurrogacy.com"],
    "tracking_mode": "internal_only",
    "consent_text": "I agree to be contacted about my inquiry.",
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter_between_tests():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


async def _first_link_id(authed_client, form_id: str) -> str:
    links = await authed_client.get(f"/forms/{form_id}/intake-links")
    assert links.status_code == 200, links.text
    return links.json()[0]["id"]


def _enable_embed_directly(db, link_id: str) -> None:
    link = db.get(FormIntakeLink, uuid.UUID(link_id))
    link.embed_enabled = True
    link.allowed_embed_origins = EMBED_SETTINGS["allowed_embed_origins"]
    link.tracking_mode = EMBED_SETTINGS["tracking_mode"]
    link.consent_text = EMBED_SETTINGS["consent_text"]
    db.commit()


async def _health_checks(authed_client, link_id: str) -> tuple[str, dict[str, dict]]:
    health = await authed_client.get(f"/forms/intake-links/{link_id}/embed-health")
    assert health.status_code == 200, health.text
    payload = health.json()
    return payload["status"], {check["key"]: check for check in payload["checks"]}


async def _create_lead_capture_form_with_file(authed_client, *, required: bool) -> str:
    form_id, link_id, _slug = await _create_published_lead_capture_form_with_schema(
        authed_client,
        form_schema=_lead_capture_schema(
            extra_fields=[
                {
                    "key": "supporting_docs",
                    "label": "Supporting Documents",
                    "type": "file",
                    "required": required,
                    "sensitivity": "file",
                }
            ]
        ),
    )
    assert form_id
    return link_id


@pytest.mark.asyncio
async def test_enabling_embed_on_a_donor_link_is_rejected(authed_client):
    form_id, _slug = await _create_donor_form(authed_client)
    link_id = await _first_link_id(authed_client, form_id)

    enable = await authed_client.patch(f"/forms/intake-links/{link_id}", json=EMBED_SETTINGS)

    assert enable.status_code == 400
    assert enable.json()["detail"] == (
        "Donor forms need a profile photo upload and cannot be embedded. "
        "Share the hosted link instead."
    )


@pytest.mark.asyncio
async def test_embed_health_blocks_donor_forms_and_embed_can_be_turned_off(authed_client, db):
    form_id, _slug = await _create_donor_form(authed_client)
    link_id = await _first_link_id(authed_client, form_id)
    _enable_embed_directly(db, link_id)

    status, checks = await _health_checks(authed_client, link_id)

    assert status == "blocked"
    assert checks["file_uploads"]["status"] == "block"
    assert "hosted link" in checks["file_uploads"]["message"]

    disable = await authed_client.patch(
        f"/forms/intake-links/{link_id}", json={"embed_enabled": False}
    )
    assert disable.status_code == 200, disable.text
    assert disable.json()["embed_enabled"] is False


@pytest.mark.asyncio
async def test_embed_is_rejected_for_a_required_file_field(authed_client, db):
    link_id = await _create_lead_capture_form_with_file(authed_client, required=True)
    _enable_embed_directly(db, link_id)
    status, checks = await _health_checks(authed_client, link_id)
    assert status == "blocked"
    assert checks["file_uploads"]["status"] == "block"

    # The failed update rolls back the request session, so it runs last.
    enable = await authed_client.patch(f"/forms/intake-links/{link_id}", json=EMBED_SETTINGS)

    assert enable.status_code == 400
    assert enable.json()["detail"] == (
        "Embedded forms cannot collect file uploads: Supporting Documents. "
        "Share the hosted link instead."
    )


@pytest.mark.asyncio
async def test_embed_allows_an_optional_file_field(authed_client):
    link_id = await _create_lead_capture_form_with_file(authed_client, required=False)

    enable = await authed_client.patch(f"/forms/intake-links/{link_id}", json=EMBED_SETTINGS)

    assert enable.status_code == 200, enable.text
    _status, checks = await _health_checks(authed_client, link_id)
    assert checks["file_uploads"]["status"] == "pass"


DONOR_EMBED_BLOCK = (
    "Donor forms need a profile photo upload and cannot be embedded. Share the hosted link instead."
)
FILE_EMBED_BLOCK = (
    "Embedded forms cannot collect file uploads: Supporting Documents. "
    "Share the hosted link instead."
)
FILE_FIELD = {
    "key": "supporting_docs",
    "label": "Supporting Documents",
    "type": "file",
    "required": True,
    "sensitivity": "file",
}


def _link_slug(db, link_id: str) -> str:
    return db.get(FormIntakeLink, uuid.UUID(link_id)).slug


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["donor", "required_file"])
async def test_embed_link_enabled_before_the_upload_rule_is_not_served(
    authed_client, client, db, kind
):
    if kind == "donor":
        form_id, _slug = await _create_donor_form(authed_client)
        link_id = await _first_link_id(authed_client, form_id)
        expected = DONOR_EMBED_BLOCK
    else:
        link_id = await _create_lead_capture_form_with_file(authed_client, required=True)
        expected = FILE_EMBED_BLOCK
    _enable_embed_directly(db, link_id)
    slug = _link_slug(db, link_id)
    origin = EMBED_SETTINGS["allowed_embed_origins"][0]

    read = await client.get(f"/forms/public/embed/{slug}", headers={"origin": origin})
    session = await client.post(
        f"/forms/public/embed/{slug}/session",
        json={"parent_origin": origin, "attribution": {}},
    )
    submit = await client.post(
        f"/forms/public/embed/{slug}/submit",
        json={
            "embed_session_token": "unused-session-token",
            "idempotency_key": "blocked-embed-1",
            "published_version_id": str(uuid.uuid4()),
            "answers": {"full_name": "Blocked Applicant", "email": "blocked@example.com"},
            "attribution": {},
        },
    )

    for response in (read, session, submit):
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == expected


@pytest.mark.asyncio
async def test_embed_rule_reads_the_published_form_not_an_unpublished_draft(authed_client, db):
    blocked_link_id = await _create_lead_capture_form_with_file(authed_client, required=True)
    blocked_form_id = str(db.get(FormIntakeLink, uuid.UUID(blocked_link_id)).form_id)
    draft = await authed_client.patch(
        f"/forms/{blocked_form_id}", json={"form_schema": _lead_capture_schema()}
    )
    assert draft.status_code == 200, draft.text
    _status, checks = await _health_checks(authed_client, blocked_link_id)
    assert checks["file_uploads"]["status"] == "block"

    live_form_id, live_link_id, _slug = await _create_published_lead_capture_form_with_schema(
        authed_client, form_schema=_lead_capture_schema()
    )
    enabled = await authed_client.patch(f"/forms/intake-links/{live_link_id}", json=EMBED_SETTINGS)
    assert enabled.status_code == 200, enabled.text
    draft = await authed_client.patch(
        f"/forms/{live_form_id}",
        json={"form_schema": _lead_capture_schema(extra_fields=[FILE_FIELD])},
    )
    assert draft.status_code == 200, draft.text
    _status, checks = await _health_checks(authed_client, live_link_id)
    assert checks["file_uploads"]["status"] == "pass"
    edited = await authed_client.patch(
        f"/forms/intake-links/{live_link_id}", json={"consent_text": "Updated consent."}
    )
    assert edited.status_code == 200, edited.text

    # The failed update rolls back the request session, so it runs last.
    enable = await authed_client.patch(
        f"/forms/intake-links/{blocked_link_id}", json=EMBED_SETTINGS
    )
    assert enable.status_code == 400
    assert enable.json()["detail"] == FILE_EMBED_BLOCK
