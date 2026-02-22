"""Tests for form builder submission flow."""

import json
import uuid

import pytest

from app.core.encryption import hash_email
from app.db.models import EmailTemplate, FormSubmission, Surrogate
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
    token_payload = token_res.json()
    token = token_payload["token"]
    assert token_payload["application_url"].endswith(f"/apply/{token}")

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
async def test_delete_form_removes_it_from_list(authed_client):
    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Delete Me",
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    del_res = await authed_client.delete(f"/forms/{form_id}")
    assert del_res.status_code == 200

    get_res = await authed_client.get(f"/forms/{form_id}")
    assert get_res.status_code == 404

    list_res = await authed_client.get("/forms")
    assert list_res.status_code == 200
    assert form_id not in {f["id"] for f in list_res.json()}


@pytest.mark.asyncio
async def test_form_submission_can_be_resent_for_existing_surrogate(
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
    assert second_token_res.status_code == 200
    second_payload = second_token_res.json()
    second_token = second_payload["token"]
    assert second_payload["application_url"].endswith(f"/apply/{second_token}")
    assert second_token != token

    resubmission_res = await authed_client.post(
        f"/forms/public/{second_token}/submit",
        data={"answers": json.dumps({"full_name": "Jane Smith"})},
    )
    assert resubmission_res.status_code == 200

    latest_submission_res = await authed_client.get(
        f"/forms/{form_id}/surrogates/{surrogate.id}/submission"
    )
    assert latest_submission_res.status_code == 200
    assert latest_submission_res.json()["answers"]["full_name"] == "Jane Smith"

    submission_count = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == test_org.id,
            FormSubmission.form_id == form_id,
            FormSubmission.surrogate_id == surrogate.id,
        )
        .count()
    )
    assert submission_count == 1


@pytest.mark.asyncio
async def test_send_token_enforces_locked_recipient_email(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)

    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [
                    {"key": "full_name", "label": "Full Name", "type": "text", "required": True}
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={"name": "Lock Test Form", "form_schema": schema},
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    template = EmailTemplate(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name=f"Lock Template {uuid.uuid4().hex[:6]}",
        subject="Complete your application",
        body="Click {{form_link}}",
        scope="org",
        is_active=True,
    )
    db.add(template)
    db.flush()

    token_res = await authed_client.post(
        f"/forms/{form_id}/tokens",
        json={"surrogate_id": str(surrogate.id), "expires_in_days": 7},
    )
    assert token_res.status_code == 200
    token_payload = token_res.json()
    token = token_payload["token"]
    token_id = token_payload["token_id"]

    token_row = (
        db.query(FormSubmission)
        .filter(FormSubmission.form_id == uuid.UUID(form_id), FormSubmission.surrogate_id == surrogate.id)
        .first()
    )
    assert token_row is None  # No submission yet; lock applies to token record only

    from app.services import form_submission_service

    token_record = form_submission_service.get_token_row(db, token)
    assert token_record is not None
    token_record.locked_recipient_email = "different@example.com"
    db.commit()

    send_res = await authed_client.post(
        f"/forms/{form_id}/tokens/{token_id}/send",
        json={"template_id": str(template.id)},
    )
    assert send_res.status_code == 409
    assert "locked to a different recipient email" in send_res.json()["detail"]


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


@pytest.mark.asyncio
async def test_form_mappings_reject_duplicate_surrogate_fields(
    authed_client,
):
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
                        "key": "email",
                        "label": "Email",
                        "type": "email",
                        "required": True,
                    },
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Mapping Form",
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
                {"field_key": "full_name", "surrogate_field": "email"},
                {"field_key": "email", "surrogate_field": "email"},
            ]
        },
    )
    assert mapping_res.status_code == 400
    assert "Duplicate surrogate field" in mapping_res.text


@pytest.mark.asyncio
async def test_public_form_requires_file_fields(
    client, authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)

    schema = {
        "pages": [
            {
                "title": "Docs",
                "fields": [
                    {
                        "key": "supporting_docs",
                        "label": "Supporting Documents",
                        "type": "file",
                        "required": True,
                    }
                ],
            }
        ]
    }

    # Use authed client to create form and token
    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Docs Form",
            "description": "Test form",
            "form_schema": schema,
        },
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

    submission_res = await client.post(
        f"/forms/public/{token}/submit",
        data={"answers": json.dumps({})},
    )
    assert submission_res.status_code == 400


@pytest.mark.asyncio
async def test_form_mapping_allows_extended_surrogate_fields(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)

    schema = {
        "pages": [
            {
                "title": "Insurance",
                "fields": [
                    {
                        "key": "insurance_company",
                        "label": "Insurance Company",
                        "type": "text",
                        "required": False,
                    }
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Insurance Form",
            "description": "Extended mapping test form",
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
                {
                    "field_key": "insurance_company",
                    "surrogate_field": "insurance_company",
                }
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
        data={"answers": json.dumps({"insurance_company": "Northwest Mutual"})},
    )
    assert submission_res.status_code == 200
    submission_id = submission_res.json()["id"]

    approve_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/approve",
        json={"review_notes": "Apply insurance mapping"},
    )
    assert approve_res.status_code == 200

    db.refresh(surrogate)
    assert surrogate.insurance_company == "Northwest Mutual"


@pytest.mark.asyncio
async def test_form_mapping_options_include_extended_fields(authed_client):
    response = await authed_client.get("/forms/mapping-options")
    assert response.status_code == 200
    payload = response.json()

    values = {option["value"] for option in payload}
    assert "full_name" in values
    assert "email" in values
    assert "insurance_company" in values

    full_name_option = next((option for option in payload if option["value"] == "full_name"), None)
    email_option = next((option for option in payload if option["value"] == "email"), None)
    assert full_name_option is not None
    assert full_name_option["is_critical"] is True
    assert email_option is not None
    assert email_option["is_critical"] is True
