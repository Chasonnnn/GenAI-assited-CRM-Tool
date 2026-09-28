"""Donor source uses the canonical lowercase surrogate source values."""

import uuid

import pytest
from pydantic import ValidationError

from app.db.enums import SurrogateSource
from app.schemas.donor import DonorCreate, DonorUpdate


def _create(source):
    return DonorCreate(
        donor_type="egg",
        full_name="Source Donor",
        email="source-donor@example.com",
        **({} if source is ... else {"source": source}),
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (..., "manual"),
        (None, "manual"),
        ("  ", "manual"),
        ("Meta", "meta"),
        (" META ", "meta"),
        (SurrogateSource.TIKTOK, "tiktok"),
        ("Website", "website"),
        ("shared_intake", "website"),
        ("form_embed", "website"),
        ("manual_review_resolution", "website"),
        ("manual_retry_resolution", "website"),
    ],
)
def test_donor_create_normalizes_source_variants(source, expected):
    assert _create(source).source == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [(None, None), ("Referral", "referral"), ("form_embed", "website")],
)
def test_donor_update_normalizes_source_variants(source, expected):
    assert DonorUpdate(source=source).source == expected


@pytest.mark.parametrize("source", ["Spring Fair 2026", "hosted_form", 7])
def test_donor_source_rejects_unknown_values(source):
    with pytest.raises(ValidationError):
        _create(source)
    with pytest.raises(ValidationError):
        DonorUpdate(source=source)


@pytest.mark.asyncio
async def test_create_donor_api_stores_canonical_source_and_rejects_unknown(authed_client):
    email = f"source-{uuid.uuid4().hex[:8]}@example.com"
    created = await authed_client.post(
        "/donors",
        json={"donor_type": "egg", "full_name": "Source Donor", "email": email, "source": "Meta"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["source"] == "meta"

    default = await authed_client.post(
        "/donors",
        json={
            "donor_type": "sperm",
            "full_name": "Default Source Donor",
            "email": f"default-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert default.status_code == 201, default.text
    assert default.json()["source"] == "manual"

    rejected = await authed_client.post(
        "/donors",
        json={
            "donor_type": "egg",
            "full_name": "Unknown Source Donor",
            "email": f"unknown-{uuid.uuid4().hex[:8]}@example.com",
            "source": "Spring Fair",
        },
    )
    assert rejected.status_code == 422

    updated = await authed_client.patch(
        f"/donors/{created.json()['id']}",
        json={"source": "Referral"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["source"] == "referral"
