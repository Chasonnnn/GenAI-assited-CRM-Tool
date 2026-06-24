from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Form, Membership, Organization, User, WorkflowTemplate
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


def create_published_form(db, org_id, user_id, name: str) -> Form:
    form = Form(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=name,
        status="published",
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(form)
    db.flush()
    return form


def create_template(
    db,
    org_id,
    user_id,
    *,
    trigger_type: str = "form_submitted",
    trigger_config: dict | None = None,
) -> WorkflowTemplate:
    template = WorkflowTemplate(
        id=uuid.uuid4(),
        name=f"Template {uuid.uuid4().hex[:8]}",
        description="Form-scoped intake workflow",
        icon="template",
        category="intake",
        trigger_type=trigger_type,
        trigger_config=trigger_config or {},
        conditions=[],
        condition_logic="AND",
        actions=[
            {"action_type": "auto_match_submission", "requires_approval": True},
            {"action_type": "create_intake_lead", "requires_approval": True},
        ]
        if trigger_type in {"form_started", "form_submitted", "intake_lead_created"}
        else [{"action_type": "add_note", "content": "Hello"}],
        is_global=False,
        organization_id=org_id,
        created_by_user_id=user_id,
    )
    db.add(template)
    db.flush()
    return template


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
async def test_use_template_creates_personal_workflow(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)

    template = WorkflowTemplate(
        id=uuid.uuid4(),
        name="Template One",
        description="Template description",
        icon="template",
        category="general",
        trigger_type="surrogate_created",
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "add_note", "content": "Hello"}],
        is_global=False,
        organization_id=test_org.id,
        created_by_user_id=admin.id,
    )
    db.add(template)
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            f"/templates/{template.id}/use",
            json={
                "name": "Personal Workflow",
                "description": "From template",
                "is_enabled": False,
                "scope": "personal",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["scope"] == "personal"
        assert data["owner_user_id"] == str(admin.id)


@pytest.mark.asyncio
async def test_use_template_resolves_form_name_trigger_config(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)

    published_form = create_published_form(
        db, test_org.id, admin.id, "Surrogate Full Application Form"
    )
    template = create_template(
        db,
        test_org.id,
        admin.id,
        trigger_config={"form_name": "Surrogate Full Application Form"},
    )
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            f"/templates/{template.id}/use",
            json={
                "name": "Org Intake Workflow",
                "description": "From template",
                "is_enabled": False,
                "scope": "org",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["scope"] == "org"
        assert data["trigger_type"] == "form_submitted"
        assert data["trigger_config"]["form_id"] == str(published_form.id)
        assert "form_name" not in data["trigger_config"]


@pytest.mark.asyncio
async def test_use_template_accepts_selected_published_form_when_form_name_is_stale(
    db, test_org
):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)
    ewi_form = create_published_form(db, test_org.id, admin.id, "EWI pre-questionnaire")
    template = create_template(
        db,
        test_org.id,
        admin.id,
        trigger_config={"form_name": "Surrogate Pre-Screening Questionnaire"},
    )
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            f"/templates/{template.id}/use",
            json={
                "name": "EWI Intake Workflow",
                "description": "From template",
                "is_enabled": False,
                "scope": "org",
                "trigger_form_id": str(ewi_form.id),
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["trigger_config"]["form_id"] == str(ewi_form.id)
        assert "form_name" not in data["trigger_config"]


@pytest.mark.asyncio
async def test_use_template_rejects_unpublished_selected_form(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)
    draft_form = Form(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Draft Intake",
        status="draft",
        schema_json={"pages": []},
        published_schema_json=None,
        created_by_user_id=admin.id,
        updated_by_user_id=admin.id,
    )
    db.add(draft_form)
    template = create_template(
        db,
        test_org.id,
        admin.id,
        trigger_config={"form_name": "Surrogate Pre-Screening Questionnaire"},
    )
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            f"/templates/{template.id}/use",
            json={
                "name": "Draft Form Workflow",
                "scope": "org",
                "trigger_form_id": str(draft_form.id),
            },
        )
        assert res.status_code == 400
        assert res.json()["detail"] == "Selected published form not found in this organization"


@pytest.mark.asyncio
async def test_use_template_rejects_cross_org_selected_form(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Org",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    other_user = create_user_with_role(db, other_org.id, Role.ADMIN)
    other_form = create_published_form(db, other_org.id, other_user.id, "Other Intake")
    template = create_template(
        db,
        test_org.id,
        admin.id,
        trigger_config={"form_name": "Surrogate Pre-Screening Questionnaire"},
    )
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            f"/templates/{template.id}/use",
            json={
                "name": "Cross Org Workflow",
                "scope": "org",
                "trigger_form_id": str(other_form.id),
            },
        )
        assert res.status_code == 400
        assert res.json()["detail"] == "Selected published form not found in this organization"


@pytest.mark.asyncio
async def test_use_template_rejects_selected_form_for_non_form_template(db, test_org):
    admin = create_user_with_role(db, test_org.id, Role.ADMIN)
    published_form = create_published_form(db, test_org.id, admin.id, "Published Intake")
    template = create_template(
        db,
        test_org.id,
        admin.id,
        trigger_type="surrogate_created",
    )
    db.commit()

    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        res = await client.post(
            f"/templates/{template.id}/use",
            json={
                "name": "Non Form Workflow",
                "scope": "org",
                "trigger_form_id": str(published_form.id),
            },
        )
        assert res.status_code == 400
        assert res.json()["detail"] == "trigger_form_id is only valid for form-trigger workflow templates"
