"""Tests for form builder submission flow."""

import json
import uuid
from datetime import date

import pytest

from app.core.encryption import hash_email, hash_phone
from app.db.models import AutomationWorkflow, EmailTemplate, FormIntakeLink, FormSubmission, Surrogate
from app.utils.normalization import normalize_email, normalize_name, normalize_phone, normalize_search_text


def _create_surrogate(
    db,
    org_id,
    user_id,
    stage,
    *,
    full_name: str = "Original Name",
    email: str | None = None,
    phone: str = "+1 (555) 100-2000",
    date_of_birth: str = "1990-01-01",
):
    email = email or f"form-test-{uuid.uuid4().hex[:8]}@example.com"
    normalized_name = normalize_name(full_name)
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name=normalized_name,
        full_name_normalized=normalize_search_text(normalized_name),
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        phone=normalized_phone,
        phone_hash=hash_phone(normalized_phone),
        date_of_birth=date.fromisoformat(date_of_birth),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


async def _create_published_form_and_shared_link(*, authed_client, name: str, schema: dict):
    create_res = await authed_client.post(
        "/forms",
        json={"name": name, "description": "Test form", "form_schema": schema},
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    links_res = await authed_client.get(f"/forms/{form_id}/intake-links")
    assert links_res.status_code == 200
    links = links_res.json()
    assert len(links) >= 1
    link = links[0]
    return form_id, link["id"], link["slug"]


async def _submit_shared_intake(*, authed_client, slug: str, answers: dict) -> str:
    submission_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={"answers": json.dumps(answers)},
    )
    assert submission_res.status_code == 200
    return submission_res.json()["id"]


def _create_auto_match_workflow(*, db, test_org, test_user, form_id: str):
    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Auto match {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[{"action_type": "auto_match_submission"}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()


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
                    {"key": "full_name", "label": "Full Name", "type": "text", "required": True},
                    {"key": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
                    {"key": "phone", "label": "Phone", "type": "text", "required": True},
                    {"key": "email", "label": "Email", "type": "email", "required": True},
                ],
            }
        ]
    }

    form_id, _link_id, slug = await _create_published_form_and_shared_link(
        authed_client=authed_client,
        name="Application Form",
        schema=schema,
    )

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

    submission_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Jane Doe",
                    "date_of_birth": "1990-01-01",
                    "phone": "+1 (555) 303-0000",
                    "email": "jane.doe@example.com",
                }
            )
        },
    )
    assert submission_res.status_code == 200
    submission_id = submission_res.json()["id"]

    resolve_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={
            "surrogate_id": str(surrogate.id),
            "create_intake_lead": False,
        },
    )
    assert resolve_res.status_code == 200

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
async def test_publish_form_auto_generates_default_shared_intake_link(
    authed_client, db, test_org
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
                    }
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Auto Share Form",
            "description": "Auto shared link test",
            "form_schema": schema,
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]
    form_uuid = uuid.UUID(form_id)

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    links = (
        db.query(FormIntakeLink)
        .filter(
            FormIntakeLink.organization_id == test_org.id,
            FormIntakeLink.form_id == form_uuid,
        )
        .all()
    )
    assert len(links) == 1
    assert links[0].is_active is True
    assert links[0].slug

    list_res = await authed_client.get(f"/forms/{form_id}/intake-links")
    assert list_res.status_code == 200
    payload = list_res.json()
    assert len(payload) == 1
    assert payload[0]["slug"] == links[0].slug
    assert payload[0]["intake_url"].endswith(f"/intake/{links[0].slug}")


@pytest.mark.asyncio
async def test_publish_form_auto_provisions_default_intake_routing_workflow(
    authed_client, db, test_org, test_user
):
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
        json={"name": "Routing Provision Form", "form_schema": schema},
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    workflow = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == test_org.id,
            AutomationWorkflow.system_key == f"shared_intake_routing:{form_id}",
        )
        .first()
    )
    assert workflow is not None
    assert workflow.is_enabled is True
    assert workflow.trigger_type == "form_submitted"
    assert workflow.trigger_config.get("form_id") == form_id

    action_types = [action.get("action_type") for action in (workflow.actions or [])]
    assert action_types == ["auto_match_submission", "create_intake_lead"]
    assert all(action.get("requires_approval") is True for action in (workflow.actions or []))


@pytest.mark.asyncio
async def test_publish_form_skips_default_routing_workflow_when_enabled_form_workflow_exists(
    authed_client, db, test_org, test_user
):
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
        json={"name": "Routing Skip Form", "form_schema": schema},
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    custom_workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Custom form submitted {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "auto_match_submission"}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(custom_workflow)
    db.commit()

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    auto_workflow = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == test_org.id,
            AutomationWorkflow.system_key == f"shared_intake_routing:{form_id}",
        )
        .first()
    )
    assert auto_workflow is None


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
async def test_auto_match_keeps_new_submission_ambiguous_when_surrogate_already_has_submission(
    authed_client, db, test_org, test_user, default_stage, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FORMS_SHARED_DUPLICATE_WINDOW_SECONDS", 0)

    surrogate = _create_surrogate(
        db,
        test_org.id,
        test_user.id,
        default_stage,
        full_name="Repeat Candidate",
        email="repeat-candidate@example.com",
        phone="+1 (555) 401-5000",
        date_of_birth="1991-03-04",
    )

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

    form_id, _link_id, slug = await _create_published_form_and_shared_link(
        authed_client=authed_client,
        name="Single Submit Form",
        schema=schema,
    )
    _create_auto_match_workflow(db=db, test_org=test_org, test_user=test_user, form_id=form_id)

    submission_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Repeat Candidate",
                    "date_of_birth": "1991-03-04",
                    "phone": "+1 (555) 401-5000",
                    "email": "repeat-candidate@example.com",
                }
            )
        },
    )
    assert submission_res.status_code == 200
    first_payload = submission_res.json()
    assert first_payload["outcome"] == "linked"
    assert first_payload["surrogate_id"] == str(surrogate.id)

    resubmission_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Repeat Candidate",
                    "date_of_birth": "1991-03-04",
                    "phone": "+1 (555) 401-5000",
                    "email": "repeat-candidate@example.com",
                }
            )
        },
    )
    assert resubmission_res.status_code == 200
    second_payload = resubmission_res.json()
    assert second_payload["outcome"] == "ambiguous_review"
    assert second_payload["surrogate_id"] is None

    second_submission = (
        db.query(FormSubmission).filter(FormSubmission.id == uuid.UUID(second_payload["id"])).first()
    )
    assert second_submission is not None
    assert second_submission.surrogate_id is None
    assert second_submission.match_status == "ambiguous_review"
    assert second_submission.match_reason == "existing_submission_for_surrogate"


@pytest.mark.asyncio
async def test_send_shared_intake_link_uses_template_and_returns_intake_url(
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

    form_id, link_id, slug = await _create_published_form_and_shared_link(
        authed_client=authed_client,
        name="Shared Send Form",
        schema=schema,
    )

    template = EmailTemplate(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name=f"Send Template {uuid.uuid4().hex[:6]}",
        subject="Complete your application",
        body="Click {{form_link}}",
        scope="org",
        is_active=True,
    )
    db.add(template)
    db.commit()

    send_link_res = await authed_client.post(
        f"/forms/{form_id}/intake-links/{link_id}/send",
        json={"surrogate_id": str(surrogate.id), "template_id": str(template.id)},
    )
    assert send_link_res.status_code == 200
    payload = send_link_res.json()
    assert payload["intake_link_id"] == link_id
    assert payload["template_id"] == str(template.id)
    assert payload["email_log_id"]
    assert payload["intake_url"].endswith(f"/intake/{slug}")


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
                        "required": True,
                    },
                    {"key": "phone", "label": "Phone", "type": "text", "required": True},
                    {"key": "email", "label": "Email", "type": "email", "required": True},
                ],
            }
        ]
    }

    form_id, _link_id, slug = await _create_published_form_and_shared_link(
        authed_client=authed_client,
        name="Application Form",
        schema=schema,
    )

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

    submission_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Jane Doe",
                    "date_of_birth": "1990-01-01",
                    "phone": "+1 (555) 800-1111",
                    "email": "update-test@example.com",
                }
            )
        },
    )
    assert submission_res.status_code == 200
    submission_id = submission_res.json()["id"]

    resolve_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={
            "surrogate_id": str(surrogate.id),
            "create_intake_lead": False,
        },
    )
    assert resolve_res.status_code == 200

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
                    {"key": "full_name", "label": "Full Name", "type": "text", "required": True},
                    {"key": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
                    {"key": "phone", "label": "Phone", "type": "text", "required": True},
                    {"key": "email", "label": "Email", "type": "email", "required": True},
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

    _form_id, _link_id, slug = await _create_published_form_and_shared_link(
        authed_client=authed_client,
        name="Docs Form",
        schema=schema,
    )

    submission_res = await client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": surrogate.full_name,
                    "date_of_birth": "1990-01-01",
                    "phone": surrogate.phone,
                    "email": surrogate.email,
                }
            )
        },
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
                    {"key": "full_name", "label": "Full Name", "type": "text", "required": True},
                    {"key": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
                    {"key": "phone", "label": "Phone", "type": "text", "required": True},
                    {"key": "email", "label": "Email", "type": "email", "required": True},
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

    form_id, _link_id, slug = await _create_published_form_and_shared_link(
        authed_client=authed_client,
        name="Insurance Form",
        schema=schema,
    )

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

    submission_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Insurance Candidate",
                    "date_of_birth": "1990-01-01",
                    "phone": "+1 (555) 907-0000",
                    "email": "insurance-candidate@example.com",
                    "insurance_company": "Northwest Mutual",
                }
            )
        },
    )
    assert submission_res.status_code == 200
    submission_id = submission_res.json()["id"]

    resolve_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={
            "surrogate_id": str(surrogate.id),
            "create_intake_lead": False,
        },
    )
    assert resolve_res.status_code == 200

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


@pytest.mark.asyncio
async def test_dedicated_token_creation_endpoint_returns_gone_after_retirement(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    schema = {
        "pages": [
            {"title": "Basics", "fields": [{"key": "full_name", "label": "Full Name", "type": "text"}]}
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Event Intake Form",
            "purpose": "event_intake",
            "form_schema": schema,
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    denied_res = await authed_client.post(
        f"/forms/{form_id}/tokens",
        json={"surrogate_id": str(surrogate.id), "expires_in_days": 7},
    )
    assert denied_res.status_code == 410
    assert "retired" in denied_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dedicated_token_send_endpoint_returns_gone_after_retirement(
    authed_client, db, test_org, test_user
):
    schema = {
        "pages": [
            {"title": "Basics", "fields": [{"key": "full_name", "label": "Full Name", "type": "text"}]}
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Event Send Form",
            "purpose": "event_intake",
            "form_schema": schema,
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    template = EmailTemplate(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name=f"Event Template {uuid.uuid4().hex[:6]}",
        subject="Complete your application",
        body="Click {{form_link}}",
        scope="org",
        is_active=True,
    )
    db.add(template)
    db.commit()

    send_denied_res = await authed_client.post(
        f"/forms/{form_id}/tokens/{uuid.uuid4()}/send",
        json={"template_id": str(template.id)},
    )
    assert send_denied_res.status_code == 410
    assert "retired" in send_denied_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_default_surrogate_application_form_reconciles_on_purpose_change(
    authed_client,
):
    schema = {
        "pages": [
            {"title": "Basics", "fields": [{"key": "full_name", "label": "Full Name", "type": "text"}]}
        ]
    }

    form_a_res = await authed_client.post(
        "/forms",
        json={"name": "Default A", "purpose": "surrogate_application", "form_schema": schema},
    )
    assert form_a_res.status_code == 200
    form_a_id = form_a_res.json()["id"]
    assert form_a_res.json()["is_default_surrogate_application"] is False

    form_b_res = await authed_client.post(
        "/forms",
        json={"name": "Default B", "purpose": "surrogate_application", "form_schema": schema},
    )
    assert form_b_res.status_code == 200
    form_b_id = form_b_res.json()["id"]

    publish_a = await authed_client.post(f"/forms/{form_a_id}/publish")
    assert publish_a.status_code == 200
    publish_b = await authed_client.post(f"/forms/{form_b_id}/publish")
    assert publish_b.status_code == 200

    list_res = await authed_client.get("/forms")
    assert list_res.status_code == 200
    by_id = {form["id"]: form for form in list_res.json()}
    assert by_id[form_a_id]["is_default_surrogate_application"] is True
    assert by_id[form_b_id]["is_default_surrogate_application"] is False

    set_default_res = await authed_client.post(
        f"/forms/{form_b_id}/set-default-surrogate-application"
    )
    assert set_default_res.status_code == 200
    assert set_default_res.json()["is_default_surrogate_application"] is True

    after_set_list_res = await authed_client.get("/forms")
    assert after_set_list_res.status_code == 200
    by_id = {form["id"]: form for form in after_set_list_res.json()}
    assert by_id[form_a_id]["is_default_surrogate_application"] is False
    assert by_id[form_b_id]["is_default_surrogate_application"] is True

    demote_res = await authed_client.patch(
        f"/forms/{form_b_id}",
        json={"purpose": "event_intake"},
    )
    assert demote_res.status_code == 200
    assert demote_res.json()["purpose"] == "event_intake"

    after_demote_list_res = await authed_client.get("/forms")
    assert after_demote_list_res.status_code == 200
    by_id = {form["id"]: form for form in after_demote_list_res.json()}
    assert by_id[form_a_id]["is_default_surrogate_application"] is True
    assert by_id[form_b_id]["is_default_surrogate_application"] is False
