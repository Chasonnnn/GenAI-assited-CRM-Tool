"""Draft dry runs from the workflow editor: POST /workflows/test-draft."""

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import Role, WorkflowTriggerType
from app.db.models import Membership, Organization, Surrogate, User
from app.main import app
from app.schemas.workflow import WorkflowCreate
from app.services import session_service, workflow_service
from app.utils.normalization import normalize_email

NOTIFY = {"action_type": "send_notification", "title": "Follow up", "recipients": "owner"}


@asynccontextmanager
async def _authed_client_for_user(db, org_id, user, role: Role, *, csrf: bool = True):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=user.id, org_id=org_id, token=token, request=None)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token} if csrf else {},
    ) as client:
        yield client
    app.dependency_overrides.clear()


def _user(db, org_id, role: Role) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Draft Tester",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(Membership(id=uuid.uuid4(), user_id=user.id, organization_id=org_id, role=role))
    db.flush()
    return user


def _surrogate(db, org_id, owner_id, stage, *, state: str = "CA") -> Surrogate:
    email = normalize_email(f"draft-{uuid.uuid4().hex[:8]}@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=owner_id,
        created_by_user_id=owner_id,
        full_name="Draft Record",
        email=email,
        email_hash=hash_email(email),
        state=state,
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _draft(**overrides) -> dict:
    body = {
        "name": "Draft",
        "scope": "org",
        "subject_type": "surrogate",
        "trigger_type": "surrogate_created",
        "trigger_config": {},
        "conditions": [{"field": "state", "operator": "equals", "value": "CA"}],
        "condition_logic": "AND",
        "actions": [NOTIFY, {**NOTIFY, "title": "Approve me", "requires_approval": True}],
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_draft_dry_run_evaluates_unsaved_filters_and_actions(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)
    db.commit()

    response = await authed_client.post(
        "/workflows/test-draft",
        json={"workflow": _draft(), "entity_id": str(surrogate.id)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conditions_matched"] is True
    assert body["conditions_evaluated"] == [
        {"field": "state", "operator": "equals", "expected": "CA", "actual": "CA", "result": True}
    ]
    assert [item["requires_approval"] for item in body["actions_preview"]] == [False, True]
    assert all(item["action_type"] == "send_notification" for item in body["actions_preview"])


@pytest.mark.asyncio
async def test_draft_dry_run_reports_unmatched_filters(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage, state="TX")
    db.commit()

    response = await authed_client.post(
        "/workflows/test-draft",
        json={"workflow": _draft(), "entity_id": str(surrogate.id)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conditions_matched"] is False
    assert body["conditions_evaluated"][0]["actual"] == "TX"


@pytest.mark.asyncio
async def test_draft_dry_run_rejects_an_invalid_definition(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)
    db.commit()

    response = await authed_client.post(
        "/workflows/test-draft",
        json={
            "workflow": _draft(actions=[{"action_type": "send_email"}]),
            "entity_id": str(surrogate.id),
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_draft_dry_run_requires_csrf(db, test_org, test_user, default_stage):
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)
    db.commit()

    async with _authed_client_for_user(
        db, test_org.id, test_user, Role.DEVELOPER, csrf=False
    ) as client:
        response = await client.post(
            "/workflows/test-draft",
            json={"workflow": _draft(), "entity_id": str(surrogate.id)},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_draft_dry_run_cannot_read_another_orgs_record(
    authed_client, db, test_org, test_user, default_stage
):
    other_org = Organization(
        id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    other_owner = _user(db, other_org.id, Role.ADMIN)
    foreign = _surrogate(db, other_org.id, other_owner.id, default_stage)
    db.commit()

    response = await authed_client.post(
        "/workflows/test-draft",
        json={"workflow": _draft(), "entity_id": str(foreign.id)},
    )

    assert response.status_code == 404
    assert "CA" not in response.text


@pytest.mark.asyncio
async def test_draft_dry_run_cannot_target_another_orgs_workflow(
    authed_client, db, test_org, test_user, default_stage
):
    other_org = Organization(
        id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    other_owner = _user(db, other_org.id, Role.ADMIN)
    foreign_workflow = workflow_service.create_workflow(
        db,
        other_org.id,
        other_owner.id,
        WorkflowCreate(
            name="Foreign",
            trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
            actions=[NOTIFY],
        ),
    )
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)
    db.commit()

    response = await authed_client.post(
        "/workflows/test-draft",
        json={
            "workflow": _draft(),
            "entity_id": str(surrogate.id),
            "workflow_id": str(foreign_workflow.id),
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_draft_dry_run_enforces_record_scope(db, test_org, test_user, default_stage):
    intake_user = _user(db, test_org.id, Role.INTAKE_SPECIALIST)
    # Owned by someone else, so outside an intake specialist's record scope.
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)
    db.commit()

    async with _authed_client_for_user(
        db, test_org.id, intake_user, Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.post(
            "/workflows/test-draft",
            json={"workflow": _draft(scope="personal"), "entity_id": str(surrogate.id)},
        )

    assert response.status_code == 403
    assert "CA" not in response.text


@pytest.mark.asyncio
async def test_saved_workflow_dry_run_enforces_record_scope(
    db, test_org, test_user, default_stage
):
    intake_user = _user(db, test_org.id, Role.INTAKE_SPECIALIST)
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        intake_user.id,
        WorkflowCreate(
            name="Personal",
            scope="personal",
            trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
            conditions=[{"field": "state", "operator": "equals", "value": "CA"}],
            actions=[NOTIFY],
        ),
    )
    surrogate = _surrogate(db, test_org.id, test_user.id, default_stage)
    db.commit()

    async with _authed_client_for_user(
        db, test_org.id, intake_user, Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.post(
            f"/workflows/{workflow.id}/test",
            json={"entity_id": str(surrogate.id)},
        )

    assert response.status_code == 403
    assert "CA" not in response.text
