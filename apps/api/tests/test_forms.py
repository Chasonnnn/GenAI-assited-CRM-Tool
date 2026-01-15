"""Tests for form builder submission flow."""

import json
import uuid

import pytest

from app.core.encryption import hash_email
from app.db.models import Surrogate
from app.utils.normalization import normalize_email


def _create_surrogate(db, org_id, user_id, stage):
    email = f"form-test-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Original Name",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


@pytest.mark.asyncio
async def test_form_submission_approval_updates_surrogate(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)

    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [
                    {
                        "key": "full_name",
                        "label": "Full Name",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "date_of_birth",
                        "label": "Date of Birth",
                        "type": "date",
                        "required": False,
                    },
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Application Form",
            "description": "Test form",
            "form_schema": schema,
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    mapping_res = await authed_client.put(
        f"/forms/{form_id}/mappings",
        json={
            "mappings": [
                {"field_key": "full_name", "surrogate_field": "full_name"},
                {"field_key": "date_of_birth", "surrogate_field": "date_of_birth"},
            ]
        },
    )
    assert mapping_res.status_code == 200

    token_res = await authed_client.post(
        f"/forms/{form_id}/tokens",
        json={"surrogate_id": str(surrogate.id), "expires_in_days": 7},
    )
    assert token_res.status_code == 200
    token = token_res.json()["token"]

    submission_res = await authed_client.post(
        f"/forms/public/{token}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Jane Doe",
                    "date_of_birth": "1990-01-01",
                }
            )
        },
    )
    assert submission_res.status_code == 200
    submission_id = submission_res.json()["id"]

    surrogate_submission = await authed_client.get(
        f"/forms/{form_id}/surrogates/{surrogate.id}/submission"
    )
    assert surrogate_submission.status_code == 200
    assert surrogate_submission.json()["status"] == "pending_review"

    approve_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/approve",
        json={"review_notes": "Looks good"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    db.refresh(surrogate)
    assert surrogate.full_name == "Jane Doe"
    assert str(surrogate.date_of_birth) == "1990-01-01"


@pytest.mark.asyncio
async def test_form_submission_single_per_surrogate(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)

    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [
                    {
                        "key": "full_name",
                        "label": "Full Name",
                        "type": "text",
                        "required": True,
                    }
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={"name": "Single Submit Form", "form_schema": schema},
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    token_res = await authed_client.post(
        f"/forms/{form_id}/tokens",
        json={"surrogate_id": str(surrogate.id), "expires_in_days": 7},
    )
    assert token_res.status_code == 200
    token = token_res.json()["token"]

    submission_res = await authed_client.post(
        f"/forms/public/{token}/submit",
        data={"answers": json.dumps({"full_name": "Jane Doe"})},
    )
    assert submission_res.status_code == 200

    second_token_res = await authed_client.post(
        f"/forms/{form_id}/tokens",
        json={"surrogate_id": str(surrogate.id), "expires_in_days": 7},
    )
    assert second_token_res.status_code == 409


@pytest.mark.asyncio
async def test_update_submission_answers_syncs_surrogate_fields(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)

    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [
                    {
                        "key": "full_name",
                        "label": "Full Name",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "date_of_birth",
                        "label": "Date of Birth",
                        "type": "date",
                        "required": False,
                    },
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Application Form",
            "description": "Test form",
            "form_schema": schema,
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    mapping_res = await authed_client.put(
        f"/forms/{form_id}/mappings",
        json={
            "mappings": [
                {"field_key": "full_name", "surrogate_field": "full_name"},
                {"field_key": "date_of_birth", "surrogate_field": "date_of_birth"},
            ]
        },
    )
    assert mapping_res.status_code == 200

    token_res = await authed_client.post(
        f"/forms/{form_id}/tokens",
        json={"surrogate_id": str(surrogate.id), "expires_in_days": 7},
    )
    assert token_res.status_code == 200
    token = token_res.json()["token"]

    submission_res = await authed_client.post(
        f"/forms/public/{token}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Jane Doe",
                    "date_of_birth": "1990-01-01",
                }
            )
        },
    )
    assert submission_res.status_code == 200
    submission_id = submission_res.json()["id"]

    update_res = await authed_client.patch(
        f"/forms/submissions/{submission_id}/answers",
        json={
            "updates": [
                {"field_key": "full_name", "value": "Jane Smith"},
                {"field_key": "date_of_birth", "value": "1991-02-03"},
            ]
        },
    )
    assert update_res.status_code == 200
    assert "full_name" in update_res.json()["surrogate_updates"]

    db.refresh(surrogate)
    assert surrogate.full_name == "Jane Smith"
    assert str(surrogate.date_of_birth) == "1991-02-03"
