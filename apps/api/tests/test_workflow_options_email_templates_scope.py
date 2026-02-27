from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import EmailTemplate, Membership, User
from app.main import app
from app.services import session_service


def create_user_with_role(db, org_id, role: Role) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.com",
        display_name=f"{role.value} user",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org_id,
        role=role,
    )
    db.add(membership)
    db.flush()
    return user


@asynccontextmanager
async def authed_client_for_user(db, org_id, user: User, role: Role):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_workflow_options_filters_email_templates_by_scope(db, test_org):
    user = create_user_with_role(db, test_org.id, Role.CASE_MANAGER)
    other = create_user_with_role(db, test_org.id, Role.CASE_MANAGER)

    org_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=user.id,
        name="Org Template",
        subject="Subject",
        body="<p>Body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    personal_template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=user.id,
        name="My Personal",
        subject="Subject",
        body="<p>Body</p>",
        scope="personal",
        owner_user_id=user.id,
        is_active=True,
    )
    other_personal = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=other.id,
        name="Other Personal",
        subject="Subject",
        body="<p>Body</p>",
        scope="personal",
        owner_user_id=other.id,
        is_active=True,
    )
    legacy_platform_invite = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=user.id,
        name="Organization Invite",
        subject="Invitation to join {{org_name}} as {{role_title}}",
        body="<p>Invite</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
        is_system_template=True,
        system_key="org_invite",
    )
    db.add_all([org_template, personal_template, other_personal, legacy_platform_invite])
    db.commit()

    async with authed_client_for_user(db, test_org.id, user, Role.CASE_MANAGER) as client:
        res = await client.get("/workflows/options?workflow_scope=org")
        assert res.status_code == 200
        org_payload = res.json()
        names = {item["name"] for item in org_payload["email_templates"]}
        assert "Org Template" in names
        assert "My Personal" not in names
        assert "Other Personal" not in names
        assert "Organization Invite" not in names
        assert "intake_lead_created" in {item["value"] for item in org_payload["trigger_types"]}
        assert "promote_intake_lead" in {item["value"] for item in org_payload["action_types"]}
        assert "send_zapier_conversion_event" in {
            item["value"] for item in org_payload["action_types"]
        }
        assert org_payload["action_types_by_trigger"]["intake_lead_created"] == [
            "send_notification",
            "promote_intake_lead",
        ]
        assert "send_zapier_conversion_event" in org_payload["action_types_by_trigger"][
            "status_changed"
        ]
        assert org_payload["trigger_entity_types"]["form_submitted"] == "form_submission"
        assert org_payload["action_types_by_trigger"]["form_submitted"][:2] == [
            "auto_match_submission",
            "create_intake_lead",
        ]

        res = await client.get("/workflows/options?workflow_scope=personal")
        assert res.status_code == 200
        names = {item["name"] for item in res.json()["email_templates"]}
        assert "Org Template" in names
        assert "My Personal" in names
        assert "Other Personal" not in names
        assert "Organization Invite" not in names
