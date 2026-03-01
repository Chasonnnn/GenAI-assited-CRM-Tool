"""Tests for profile card endpoints."""

import json
import uuid
from datetime import date

import pytest

from app.core.encryption import hash_email, hash_phone
from app.db.models import Surrogate
from app.utils.normalization import normalize_email, normalize_name, normalize_phone, normalize_search_text


def _create_surrogate(db, org_id, user_id, stage):
    email = f"profile-test-{uuid.uuid4().hex[:8]}@example.com"
    phone = f"+1 (555) {uuid.uuid4().int % 900 + 100}-{uuid.uuid4().int % 9000 + 1000}"
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)
    full_name = "Original Name"
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name=full_name,
        full_name_normalized=normalize_search_text(normalize_name(full_name)),
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        phone=normalized_phone,
        phone_hash=hash_phone(normalized_phone),
        date_of_birth=date.fromisoformat("1990-01-01"),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


async def _create_form_and_submission(authed_client, surrogate: Surrogate, label, full_name):
    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [
                    {"key": "full_name", "label": "Full Name", "type": "text", "required": True},
                    {"key": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
                    {"key": "phone", "label": "Phone", "type": "text", "required": True},
                    {"key": "email", "label": "Email", "type": "email", "required": True},
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": f"Application {label}",
            "description": "Test form",
            "form_schema": schema,
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    links_res = await authed_client.get(f"/forms/{form_id}/intake-links")
    assert links_res.status_code == 200
    slug = links_res.json()[0]["slug"]

    submission_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": full_name,
                    "date_of_birth": str(surrogate.date_of_birth or "1990-01-01"),
                    "phone": surrogate.phone or "+1 (555) 111-1111",
                    "email": surrogate.email or f"{uuid.uuid4().hex[:8]}@example.com",
                }
            )
        },
    )
    assert submission_res.status_code == 200
    submission_id = submission_res.json()["id"]

    resolve_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={"surrogate_id": str(surrogate.id), "create_intake_lead": False},
    )
    assert resolve_res.status_code == 200
    return submission_id


@pytest.mark.asyncio
async def test_profile_defaults_to_latest_submission(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)

    first_submission_id = await _create_form_and_submission(
        authed_client, surrogate, "One", "First Name"
    )
    second_submission_id = await _create_form_and_submission(
        authed_client, surrogate, "Two", "Second Name"
    )

    profile_res = await authed_client.get(f"/surrogates/{surrogate.id}/profile")
    assert profile_res.status_code == 200
    data = profile_res.json()
    assert data["base_submission_id"] == second_submission_id
    assert data["base_submission_id"] != first_submission_id


@pytest.mark.asyncio
async def test_profile_sync_updates_base_submission(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)

    first_submission_id = await _create_form_and_submission(
        authed_client, surrogate, "One", "First Name"
    )
    second_submission_id = await _create_form_and_submission(
        authed_client, surrogate, "Two", "Second Name"
    )

    sync_res = await authed_client.post(f"/surrogates/{surrogate.id}/profile/sync")
    assert sync_res.status_code == 200
    assert sync_res.json()["latest_submission_id"] == second_submission_id

    save_res = await authed_client.put(
        f"/surrogates/{surrogate.id}/profile/overrides",
        json={"overrides": {}, "new_base_submission_id": second_submission_id},
    )
    assert save_res.status_code == 200

    profile_res = await authed_client.get(f"/surrogates/{surrogate.id}/profile")
    assert profile_res.status_code == 200
    assert profile_res.json()["base_submission_id"] == second_submission_id
    assert profile_res.json()["base_submission_id"] != first_submission_id


@pytest.mark.asyncio
async def test_profile_hidden_toggle(authed_client, db, test_org, test_user, default_stage):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)

    await _create_form_and_submission(authed_client, surrogate, "One", "Hidden Name")

    hide_res = await authed_client.post(
        f"/surrogates/{surrogate.id}/profile/hidden",
        json={"field_key": "full_name", "hidden": True},
    )
    assert hide_res.status_code == 200

    profile_res = await authed_client.get(f"/surrogates/{surrogate.id}/profile")
    assert profile_res.status_code == 200
    assert "full_name" in profile_res.json()["hidden_fields"]

    unhide_res = await authed_client.post(
        f"/surrogates/{surrogate.id}/profile/hidden",
        json={"field_key": "full_name", "hidden": False},
    )
    assert unhide_res.status_code == 200

    profile_res = await authed_client.get(f"/surrogates/{surrogate.id}/profile")
    assert profile_res.status_code == 200
    assert "full_name" not in profile_res.json()["hidden_fields"]


@pytest.mark.asyncio
async def test_profile_returns_custom_header_and_qas(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    await _create_form_and_submission(authed_client, surrogate, "One", "Base Name")

    save_res = await authed_client.put(
        f"/surrogates/{surrogate.id}/profile/overrides",
        json={
            "overrides": {
                "__profile_header_name": "Display Name",
                "__profile_header_note": "Custom note for this profile",
                "__profile_custom_qas": [
                    {
                        "id": "qa-1",
                        "section_key": "section_0",
                        "question": "Preferred schedule",
                        "answer": "Weekday mornings",
                        "order": 0,
                    }
                ],
            },
        },
    )
    assert save_res.status_code == 200

    profile_res = await authed_client.get(f"/surrogates/{surrogate.id}/profile")
    assert profile_res.status_code == 200
    data = profile_res.json()
    assert data["header_name_override"] == "Display Name"
    assert data["header_note"] == "Custom note for this profile"
    assert len(data["custom_qas"]) == 1
    assert data["custom_qas"][0]["question"] == "Preferred schedule"
    assert "__profile_header_name" not in data["merged_view"]
    assert "__profile_header_note" not in data["merged_view"]


@pytest.mark.asyncio
async def test_profile_sync_ignores_profile_meta_keys(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    await _create_form_and_submission(authed_client, surrogate, "One", "Base Name")

    save_res = await authed_client.put(
        f"/surrogates/{surrogate.id}/profile/overrides",
        json={
            "overrides": {
                "__profile_header_name": "Header Only Name",
                "__profile_header_note": "Header Note",
            },
        },
    )
    assert save_res.status_code == 200

    sync_res = await authed_client.post(f"/surrogates/{surrogate.id}/profile/sync")
    assert sync_res.status_code == 200
    staged = sync_res.json()["staged_changes"]
    field_keys = {item["field_key"] for item in staged}
    assert "__profile_header_name" not in field_keys
    assert "__profile_header_note" not in field_keys
