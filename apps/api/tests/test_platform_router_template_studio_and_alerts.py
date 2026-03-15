from __future__ import annotations

import uuid

import pytest


async def _create_platform_email_template(authed_client) -> str:
    response = await authed_client.post(
        "/platform/templates/email",
        json={
            "name": "Coverage Email Template",
            "subject": "Hello {{org_name}}",
            "body": "<p>Hello {{full_name}}</p>",
            "from_email": "Ops <ops@example.com>",
            "category": "ops",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_platform_form_template(authed_client) -> str:
    response = await authed_client.post(
        "/platform/templates/forms",
        json={
            "name": "Coverage Form Template",
            "description": "Coverage form",
            "schema_json": {
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
            },
            "settings_json": {"max_file_count": 3},
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_platform_workflow_template(authed_client) -> str:
    response = await authed_client.post(
        "/platform/templates/workflows",
        json={
            "name": "Coverage Workflow Template",
            "description": "Coverage workflow",
            "icon": "template",
            "category": "general",
            "trigger_type": "surrogate_created",
            "trigger_config": {},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_platform_alert_acknowledge_and_resolve_missing_alert_returns_404(
    authed_client, db, test_user
):
    test_user.is_platform_admin = True
    db.commit()

    missing_id = uuid.uuid4()

    acknowledge = await authed_client.post(f"/platform/alerts/{missing_id}/acknowledge")
    assert acknowledge.status_code == 404
    assert acknowledge.json()["detail"] == "Alert not found"

    resolve = await authed_client.post(f"/platform/alerts/{missing_id}/resolve")
    assert resolve.status_code == 404
    assert resolve.json()["detail"] == "Alert not found"


@pytest.mark.asyncio
async def test_platform_template_studio_missing_resources_return_404(
    authed_client, db, test_user, test_org
):
    test_user.is_platform_admin = True
    db.commit()

    missing_id = uuid.uuid4()
    cases = [
        ("get", f"/platform/templates/email/{missing_id}", None),
        ("patch", f"/platform/templates/email/{missing_id}", {"name": "x"}),
        ("post", f"/platform/templates/email/{missing_id}/publish", {"publish_all": True}),
        ("delete", f"/platform/templates/email/{missing_id}", None),
        (
            "post",
            f"/platform/templates/email/{missing_id}/test",
            {"to_email": "test@example.com", "org_id": str(test_org.id)},
        ),
        ("get", f"/platform/templates/forms/{missing_id}", None),
        ("patch", f"/platform/templates/forms/{missing_id}", {"name": "x"}),
        ("post", f"/platform/templates/forms/{missing_id}/publish", {"publish_all": True}),
        ("delete", f"/platform/templates/forms/{missing_id}", None),
        ("get", f"/platform/templates/workflows/{missing_id}", None),
        ("patch", f"/platform/templates/workflows/{missing_id}", {"name": "x"}),
        (
            "post",
            f"/platform/templates/workflows/{missing_id}/publish",
            {"publish_all": True},
        ),
        ("delete", f"/platform/templates/workflows/{missing_id}", None),
    ]

    for method, path, payload in cases:
        if payload is None:
            response = await getattr(authed_client, method)(path)
        else:
            response = await getattr(authed_client, method)(path, json=payload)

        assert response.status_code == 404, (
            f"{method.upper()} {path} returned {response.status_code}"
        )
        assert response.json()["detail"] == "Template not found"


@pytest.mark.asyncio
async def test_platform_template_updates_reject_version_mismatch(authed_client, db, test_user):
    test_user.is_platform_admin = True
    db.commit()

    email_template_id = await _create_platform_email_template(authed_client)
    form_template_id = await _create_platform_form_template(authed_client)
    workflow_template_id = await _create_platform_workflow_template(authed_client)

    email_update = await authed_client.patch(
        f"/platform/templates/email/{email_template_id}",
        json={"subject": "Updated", "expected_version": 999},
    )
    assert email_update.status_code == 409
    assert "version mismatch" in email_update.text.lower()

    form_update = await authed_client.patch(
        f"/platform/templates/forms/{form_template_id}",
        json={"description": "Updated", "expected_version": 999},
    )
    assert form_update.status_code == 409
    assert "version mismatch" in form_update.text.lower()

    workflow_update = await authed_client.patch(
        f"/platform/templates/workflows/{workflow_template_id}",
        json={"description": "Updated", "expected_version": 999},
    )
    assert workflow_update.status_code == 409
    assert "version mismatch" in workflow_update.text.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("template_kind", "create_fn"),
    [
        ("email", _create_platform_email_template),
        ("forms", _create_platform_form_template),
        ("workflows", _create_platform_workflow_template),
    ],
)
async def test_platform_template_publish_requires_target_orgs(
    authed_client, db, test_user, template_kind: str, create_fn
):
    test_user.is_platform_admin = True
    db.commit()

    template_id = await create_fn(authed_client)
    publish_response = await authed_client.post(
        f"/platform/templates/{template_kind}/{template_id}/publish",
        json={"publish_all": False},
    )

    assert publish_response.status_code == 422
    assert "org_ids" in publish_response.text
