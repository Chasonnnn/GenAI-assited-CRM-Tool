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
