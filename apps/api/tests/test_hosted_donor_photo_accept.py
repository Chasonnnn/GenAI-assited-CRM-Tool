"""The hosted donor profile photo field offers only the image types the server accepts."""

from __future__ import annotations

import pytest

from tests.test_forms_public_shared_intake import _create_published_form_and_shared_link
from tests.test_hosted_donor_forms import _create_donor_form


@pytest.fixture(autouse=True)
def _reset_rate_limiter_between_tests():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.mark.asyncio
async def test_donor_profile_photo_field_is_limited_to_png_and_jpeg(authed_client, client):
    form_id, slug = await _create_donor_form(authed_client)
    update = await authed_client.patch(
        f"/forms/{form_id}",
        json={"allowed_mime_types": ["application/pdf", "image/png", "image/jpeg"]},
    )
    assert update.status_code == 200, update.text

    public_form = await client.get(f"/forms/public/intake/{slug}")

    assert public_form.status_code == 200, public_form.text
    payload = public_form.json()
    assert "application/pdf" in payload["allowed_mime_types"]
    assert payload["field_allowed_mime_types"] == {"headshot": ["image/jpeg", "image/png"]}


@pytest.mark.asyncio
async def test_donor_profile_photo_field_respects_a_narrower_form_list(authed_client, client):
    form_id, slug = await _create_donor_form(authed_client)
    update = await authed_client.patch(
        f"/forms/{form_id}", json={"allowed_mime_types": ["image/png"]}
    )
    assert update.status_code == 200, update.text

    public_form = await client.get(f"/forms/public/intake/{slug}")

    assert public_form.status_code == 200, public_form.text
    assert public_form.json()["field_allowed_mime_types"] == {"headshot": ["image/png"]}


@pytest.mark.asyncio
async def test_surrogate_forms_have_no_field_upload_restrictions(authed_client, client):
    _form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    public_form = await client.get(f"/forms/public/intake/{slug}")

    assert public_form.status_code == 200, public_form.text
    assert public_form.json()["field_allowed_mime_types"] == {}
