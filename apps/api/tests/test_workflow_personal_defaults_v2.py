"""Personal authoring never grants organization workflow authority."""

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.models import (
    AutomationWorkflow,
    Membership,
    Organization,
    OrganizationPermissionPolicy,
    User,
)
from app.main import app
from app.schemas.workflow import WorkflowCreate
from app.services import session_service, workflow_access, workflow_service
from app.services.workflow_execution_authority import active_session


@pytest.fixture
def staff(db, test_org):
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", display_name="Staff", is_active=True)
    db.add(user)
    db.flush()
    membership = Membership(
        organization_id=test_org.id, user_id=user.id, role="intake_specialist", is_active=True
    )
    db.add_all([membership, OrganizationPermissionPolicy(organization_id=test_org.id, version=2)])
    db.flush()
    return test_org, user, membership


@asynccontextmanager
async def client_for(db, org, user):
    token = create_session_token(
        user_id=user.id,
        org_id=org.id,
        role="intake_specialist",
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=user.id, org_id=org.id, token=token, request=None)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    csrf = generate_csrf_token()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf},
            headers={CSRF_HEADER: csrf},
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def definition(scope):
    return WorkflowCreate(
        name="Personal authoring",
        scope=scope,
        trigger_type="surrogate_created",
        actions=[{"action_type": "add_note", "content": "Synthetic note"}],
        is_enabled=False,
    )


def test_personal_default_does_not_grant_org_execution_dashboard(db, staff):
    org, user, _ = staff
    actor = active_session(db, org.id, user.id)
    assert workflow_access.can_create(db, actor, "personal")
    assert not workflow_access.can_create(db, actor, "org")
    assert not workflow_access.has_manage_permission(db, actor)


def test_service_rejects_disabled_org_creation_without_authority(db, staff):
    org, user, _ = staff
    with pytest.raises(ValueError, match="creation is not permitted"):
        workflow_service.create_workflow(db, org.id, user.id, definition("org"))
    assert db.query(AutomationWorkflow).filter_by(organization_id=org.id).count() == 0


def test_service_allows_personal_draft_without_extra_authoring_grant(db, staff):
    org, user, _ = staff
    item = workflow_service.create_workflow(db, org.id, user.id, definition("personal"))
    assert item.owner_user_id == user.id
    assert item.scope == "personal"
    assert not item.is_enabled


def test_service_personal_default_requires_active_same_org_membership(db, staff):
    org, user, membership = staff
    membership.is_active = False
    db.flush()
    with pytest.raises(ValueError, match="creation is not permitted"):
        workflow_service.create_workflow(db, org.id, user.id, definition("personal"))
    other = Organization(id=uuid4(), name="Other tenant", slug=f"other-{uuid4()}")
    db.add(other)
    db.flush()
    db.add(OrganizationPermissionPolicy(organization_id=other.id, version=2))
    db.flush()
    with pytest.raises(ValueError, match="creation is not permitted"):
        workflow_service.create_workflow(db, other.id, user.id, definition("personal"))


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["generate", "generate/stream", "validate", "save"])
async def test_ai_workflow_paths_reject_org_scope_before_provider_or_save(
    db, staff, monkeypatch, path
):
    from app.services import ai_workflow_service

    org, user, _ = staff
    monkeypatch.setattr(
        ai_workflow_service,
        "generate_workflow",
        lambda **kwargs: pytest.fail("Unauthorized provider access"),
    )
    monkeypatch.setattr(
        ai_workflow_service,
        "save_workflow",
        lambda **kwargs: pytest.fail("Unauthorized workflow save"),
    )
    body = {
        "scope": "org",
        "description": "Create a follow up note",
        "workflow": {
            "name": "Synthetic",
            "trigger_type": "surrogate_created",
            "actions": [{"action_type": "add_note", "content": "Synthetic note"}],
        },
    }
    async with client_for(db, org, user) as client:
        response = await client.post(f"/ai/workflows/{path}", json=body)
    assert response.status_code == 403, response.text
    assert db.query(AutomationWorkflow).filter_by(organization_id=org.id).count() == 0


@pytest.mark.asyncio
async def test_ai_workflow_personal_save_is_included_and_keeps_csrf(db, staff):
    org, user, _ = staff
    body = {
        "scope": "personal",
        "workflow": {
            "name": "Synthetic",
            "trigger_type": "surrogate_created",
            "actions": [{"action_type": "add_note", "content": "Synthetic note"}],
        },
    }
    async with client_for(db, org, user) as client:
        response = await client.post("/ai/workflows/save", json=body)
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
        client.headers.pop(CSRF_HEADER)
        denied = await client.post("/ai/workflows/save", json=body)
        assert denied.status_code == 403
    item = db.query(AutomationWorkflow).filter_by(organization_id=org.id).one()
    assert item.scope == "personal" and item.owner_user_id == user.id and not item.is_enabled
