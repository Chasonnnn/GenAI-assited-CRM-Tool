"""Tests for form builder submission flow."""

import json
import uuid

import pytest

from app.db.models import Case


def _create_case(db, org_id, user_id, stage):
    case = Case(
        id=uuid.uuid4(),
        organization_id=org_id,
        case_number=f"C{uuid.uuid4().hex[:9]}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Original Name",
        email=f"form-test-{uuid.uuid4().hex[:8]}@example.com",
    )
    db.add(case)
    db.flush()
    return case


@pytest.mark.asyncio
async def test_form_submission_approval_updates_case(
    authed_client, db, test_org, test_user, default_stage
):
    case = _create_case(db, test_org.id, test_user.id, default_stage)

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
                {"field_key": "full_name", "case_field": "full_name"},
                {"field_key": "date_of_birth", "case_field": "date_of_birth"},
            ]
        },
    )
    assert mapping_res.status_code == 200

    token_res = await authed_client.post(
        f"/forms/{form_id}/tokens",
        json={"case_id": str(case.id), "expires_in_days": 7},
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

    case_submission = await authed_client.get(
        f"/forms/{form_id}/cases/{case.id}/submission"
    )
    assert case_submission.status_code == 200
    assert case_submission.json()["status"] == "pending_review"

    approve_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/approve",
        json={"review_notes": "Looks good"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    db.refresh(case)
    assert case.full_name == "Jane Doe"
    assert str(case.date_of_birth) == "1990-01-01"


@pytest.mark.asyncio
async def test_form_submission_single_per_case(
    authed_client, db, test_org, test_user, default_stage
):
    case = _create_case(db, test_org.id, test_user.id, default_stage)

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
        json={"case_id": str(case.id), "expires_in_days": 7},
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
        json={"case_id": str(case.id), "expires_in_days": 7},
    )
    assert second_token_res.status_code == 409
