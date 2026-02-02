import uuid
import pytest

from app.core.security import create_session_token
from app.core.csrf import generate_csrf_token, CSRF_COOKIE_NAME, CSRF_HEADER
from app.core.deps import COOKIE_NAME
from app.db.enums import Role
from app.services import session_service


async def _make_authed_client(db, user_id, org_id):
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.deps import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    token = create_session_token(
        user_id=user_id,
        org_id=org_id,
        role=Role.DEVELOPER.value,
        token_version=1,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user_id,
        org_id=org_id,
        token=token,
        request=None,
    )
    csrf_token = generate_csrf_token()
    client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    )
    return client


@pytest.mark.asyncio
async def test_platform_email_templates_publish_targets(authed_client, db, test_user, test_org):
    from app.db.models import Organization, User, Membership

    test_user.is_platform_admin = True
    db.commit()

    org2 = Organization(
        id=uuid.uuid4(),
        name="Second Org",
        slug=f"second-org-{uuid.uuid4().hex[:8]}",
    )
    db.add(org2)
    db.flush()

    user2 = User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Second User",
        token_version=1,
        is_active=True,
    )
    db.add(user2)
    db.flush()

    membership2 = Membership(
        id=uuid.uuid4(),
        user_id=user2.id,
        organization_id=org2.id,
        role=Role.DEVELOPER,
    )
    db.add(membership2)
    db.commit()

    client2 = await _make_authed_client(db, user2.id, org2.id)

    create_resp = await authed_client.post(
        "/platform/templates/email",
        json={
            "name": "Ops Invite",
            "subject": "Welcome to {{org_name}}",
            "body": "<p>Hello {{full_name}}</p>",
            "from_email": "Invites <invites@surrogacyforce.com>",
            "category": "invite",
        },
    )
    assert create_resp.status_code == 201
    template_id = create_resp.json()["id"]

    publish_resp = await authed_client.post(
        f"/platform/templates/email/{template_id}/publish",
        json={"org_ids": [str(test_org.id)]},
    )
    assert publish_resp.status_code == 200

    list_org1 = await authed_client.get("/email-templates/library")
    assert list_org1.status_code == 200
    org1_ids = {item["id"] for item in list_org1.json()}
    assert template_id in org1_ids

    list_org2 = await client2.get("/email-templates/library")
    assert list_org2.status_code == 200
    org2_ids = {item["id"] for item in list_org2.json()}
    assert template_id not in org2_ids

    await client2.aclose()


@pytest.mark.asyncio
async def test_platform_form_templates_publish_and_use(authed_client, db, test_user, test_org):
    test_user.is_platform_admin = True
    db.commit()

    create_resp = await authed_client.post(
        "/platform/templates/forms",
        json={
            "name": "Surrogate Intake",
            "description": "Default intake form",
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
            "settings_json": {
                "max_file_size_bytes": 10485760,
                "max_file_count": 5,
                "allowed_mime_types": ["application/pdf"],
            },
        },
    )
    assert create_resp.status_code == 201
    template_id = create_resp.json()["id"]

    publish_resp = await authed_client.post(
        f"/platform/templates/forms/{template_id}/publish",
        json={"org_ids": [str(test_org.id)]},
    )
    assert publish_resp.status_code == 200

    list_resp = await authed_client.get("/forms/templates")
    assert list_resp.status_code == 200
    ids = {item["id"] for item in list_resp.json()}
    assert template_id in ids

    use_resp = await authed_client.post(
        f"/forms/templates/{template_id}/use",
        json={"name": "My Intake Form"},
    )
    assert use_resp.status_code == 200
    form = use_resp.json()
    assert form["name"] == "My Intake Form"


@pytest.mark.asyncio
async def test_jotform_form_template_list_includes_schema(authed_client, db, test_user):
    test_user.is_platform_admin = True
    db.commit()

    from app.db.models import PlatformFormTemplate

    template = PlatformFormTemplate(
        id=uuid.uuid4(),
        name="Surrogate Application Form Template",
        description="Template based on the Jotform Surrogate Application Form.",
        schema_json={
            "pages": [
                {
                    "title": "Personal Info",
                    "fields": [
                        {"key": "first_name", "label": "First Name", "type": "text"},
                        {"key": "last_name", "label": "Last Name", "type": "text"},
                        {"key": "upload_photos", "label": "Upload photos", "type": "file"},
                    ],
                }
            ]
        },
        settings_json={"max_file_count": 12},
        status="draft",
        current_version=1,
        published_version=0,
        is_published_globally=False,
    )
    db.add(template)
    db.commit()

    list_resp = await authed_client.get("/platform/templates/forms")
    assert list_resp.status_code == 200
    templates = list_resp.json()

    template = next(
        (
            item
            for item in templates
            if item["draft"]["name"] == "Surrogate Application Form Template"
        ),
        None,
    )
    assert template is not None

    schema = template["draft"].get("schema_json")
    assert schema is not None
    field_keys = {
        field["key"] for page in schema.get("pages", []) for field in page.get("fields", [])
    }
    assert "first_name" in field_keys
    assert "last_name" in field_keys
    assert "upload_photos" in field_keys


@pytest.mark.asyncio
async def test_platform_workflow_templates_publish_targets(authed_client, db, test_user, test_org):
    test_user.is_platform_admin = True
    db.commit()

    create_resp = await authed_client.post(
        "/platform/templates/workflows",
        json={
            "name": "Welcome Workflow",
            "description": "Send welcome email",
            "category": "onboarding",
            "icon": "mail",
            "trigger_type": "surrogate_created",
            "trigger_config": {},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [
                {
                    "action_type": "send_email",
                    "template_id": str(uuid.uuid4()),
                }
            ],
        },
    )
    assert create_resp.status_code == 201
    template_id = create_resp.json()["id"]

    publish_resp = await authed_client.post(
        f"/platform/templates/workflows/{template_id}/publish",
        json={"org_ids": [str(test_org.id)]},
    )
    assert publish_resp.status_code == 200

    list_resp = await authed_client.get("/templates")
    assert list_resp.status_code == 200
    ids = {item["id"] for item in list_resp.json()}
    assert template_id in ids
