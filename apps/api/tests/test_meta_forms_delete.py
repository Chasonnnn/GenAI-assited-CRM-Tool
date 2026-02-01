"""Tests for deleting Meta lead forms."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_delete_meta_form(authed_client, db, test_org):
    from app.services import meta_form_mapping_service

    form = meta_form_mapping_service.upsert_form_from_payload(
        db,
        test_org.id,
        form_external_id="form_delete_1",
        form_name="Delete Me",
        field_keys=["full_name", "email"],
        page_id="page_1",
    )
    assert form is not None
    db.commit()

    res = await authed_client.delete(f"/integrations/meta/forms/{form.id}")
    assert res.status_code == 204

    list_res = await authed_client.get("/integrations/meta/forms")
    assert list_res.status_code == 200
    assert list_res.json() == []
