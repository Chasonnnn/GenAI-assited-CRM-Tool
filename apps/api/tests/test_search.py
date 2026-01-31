import uuid

import pytest

from app.core.encryption import hash_email
from app.db.models import Surrogate
from app.utils.normalization import normalize_email, normalize_identifier, normalize_search_text


@pytest.mark.asyncio
async def test_search_default_types_includes_surrogates(
    authed_client, db, test_org, test_user, default_stage
):
    """
    /search defaults types=case,note,attachment,intended_parent.

    "case" is a legacy alias for "surrogate"; ensure default search includes surrogates.
    """
    email = "searchable-surrogate@test.com"
    normalized = normalize_email(email)

    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        stage_id=default_stage.id,
        full_name="Searchable Surrogate",
        status_label=default_stage.label,
        email=normalized,
        email_hash=hash_email(normalized),
        source="website",
        surrogate_number="S99999",
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
    )
    db.add(surrogate)
    db.flush()

    res = await authed_client.get(f"/search?q={email}&limit=10")
    assert res.status_code == 200

    payload = res.json()
    assert payload["total"] >= 1
    assert any(
        r["entity_type"] == "surrogate" and r["entity_id"] == str(surrogate.id)
        for r in payload["results"]
    )


@pytest.mark.asyncio
async def test_search_by_name_returns_surrogate(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        stage_id=default_stage.id,
        full_name="Guadalupe Delgado",
        full_name_normalized=normalize_search_text("Guadalupe Delgado"),
        status_label=default_stage.label,
        email=normalize_email("guadalupe@test.com"),
        email_hash=hash_email("guadalupe@test.com"),
        source="website",
        surrogate_number="S10690",
        surrogate_number_normalized=normalize_identifier("S10690"),
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
    )
    db.add(surrogate)
    db.flush()

    res = await authed_client.get("/search?q=Guadalupe&limit=10")
    assert res.status_code == 200

    payload = res.json()
    assert any(
        r["entity_type"] == "surrogate" and r["entity_id"] == str(surrogate.id)
        for r in payload["results"]
    )
