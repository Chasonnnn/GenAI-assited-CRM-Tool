"""Task chat uses the current task owner and linked record scope."""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from test_workflow_personal_defaults_v2 import client_for
from test_workflow_personal_defaults_v2 import staff as staff_fixture

from app.db.models import (
    Organization,
    OrganizationPermissionPolicy,
    Surrogate,
    Task,
    UserPermissionOverride,
)

staff = staff_fixture


@pytest.fixture
def task_context(db, staff, test_user, default_stage, monkeypatch):
    from app.services import ai_chat_service, oauth_service

    org, actor, _ = staff
    from app.db.models import RoleRecordScope

    db.add(
        RoleRecordScope(
            organization_id=org.id,
            role="intake_specialist",
            module="surrogates",
            assignment="assigned",
            phase="all",
        )
    )
    record = Surrogate(
        organization_id=org.id,
        surrogate_number="S10001",
        full_name="Synthetic task subject",
        email="task-subject@example.com",
        email_hash=uuid4().hex,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=actor.id,
        created_by_user_id=test_user.id,
    )
    db.add(record)
    db.flush()
    task = Task(
        organization_id=org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=actor.id,
        title="Synthetic task",
        surrogate_id=record.id,
    )
    db.add(task)
    db.flush()
    provider = Mock(
        return_value={
            "content": "Synthetic task response",
            "proposed_actions": [],
            "tokens_used": {"total": 0},
        }
    )
    monkeypatch.setattr(ai_chat_service, "chat", provider)
    monkeypatch.setattr(oauth_service, "get_user_integrations", lambda *args: [])
    return org, actor, task, record, test_user, provider


async def task_chat(client, task):
    return await client.post(
        "/ai/chat",
        json={"entity_type": "task", "entity_id": str(task.id), "message": "Summarize this task"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_task_owner_can_chat_when_another_user_created_task(db, task_context, version):
    org, actor, task, _, _, provider = task_context
    db.query(OrganizationPermissionPolicy).filter_by(organization_id=org.id).one().version = version
    if version == 1:
        db.add(
            UserPermissionOverride(
                organization_id=org.id,
                user_id=actor.id,
                permission="use_ai_assistant",
                override_type="grant",
            )
        )
    db.flush()
    async with client_for(db, org, actor) as client:
        response = await task_chat(client, task)
    assert response.status_code == 200, response.text
    assert response.json()["content"] == "Synthetic task response"
    assert provider.call_args.args[3:5] == ("task", task.id)


@pytest.mark.asyncio
async def test_unrelated_task_is_denied_before_ai_provider(db, task_context):
    org, actor, task, _, creator, provider = task_context
    task.owner_id = creator.id
    db.flush()
    async with client_for(db, org, actor) as client:
        response = await task_chat(client, task)
    assert response.status_code == 403
    provider.assert_not_called()


@pytest.mark.asyncio
async def test_queue_owner_id_does_not_grant_user_access(db, task_context):
    org, actor, task, _, _, provider = task_context
    task.owner_type = "queue"
    task.owner_id = actor.id
    db.flush()
    async with client_for(db, org, actor) as client:
        response = await task_chat(client, task)
    assert response.status_code == 403
    provider.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("owns_task", [True, False])
async def test_task_owner_or_author_cannot_bypass_linked_record_scope(db, task_context, owns_task):
    org, actor, task, record, creator, provider = task_context
    record.owner_id = creator.id
    if not owns_task:
        task.owner_id = creator.id
        task.created_by_user_id = actor.id
    db.flush()
    async with client_for(db, org, actor) as client:
        response = await task_chat(client, task)
    assert response.status_code == 403
    provider.assert_not_called()


@pytest.mark.asyncio
async def test_task_chat_rejects_another_organization_task(db, task_context):
    org, actor, task, _, _, provider = task_context
    other = Organization(id=uuid4(), name="Other tenant", slug=f"other-{uuid4()}")
    db.add(other)
    db.flush()
    task.organization_id = other.id
    task.surrogate_id = None
    db.flush()
    async with client_for(db, org, actor) as client:
        response = await task_chat(client, task)
    assert response.status_code == 404
    provider.assert_not_called()


@pytest.mark.asyncio
async def test_task_chat_rejects_foreign_linked_record(db, task_context):
    org, actor, task, record, _, provider = task_context
    other = Organization(id=uuid4(), name="Other tenant", slug=f"other-{uuid4()}")
    db.add(other)
    db.flush()
    record.organization_id = other.id
    db.flush()
    async with client_for(db, org, actor) as client:
        response = await task_chat(client, task)
    assert response.status_code == 404
    provider.assert_not_called()


@pytest.mark.asyncio
async def test_task_chat_requires_current_task_view_permission(db, task_context):
    from app.db.models import RolePermission

    org, actor, task, _, _, provider = task_context
    db.add(
        RolePermission(
            organization_id=org.id,
            role="intake_specialist",
            permission="view_tasks",
            is_granted=False,
        )
    )
    db.flush()
    async with client_for(db, org, actor) as client:
        response = await task_chat(client, task)
    assert response.status_code == 403
    provider.assert_not_called()
