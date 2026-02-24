from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.permissions import PermissionKey as P
from app.core.security import create_session_token
from app.db.enums import AuditEventType, Role, TaskStatus, TaskType
from app.db.models import (
    AuditLog,
    AutomationWorkflow,
    Membership,
    Task,
    User,
    UserPermissionOverride,
    WorkflowExecution,
)
from app.main import app
from app.services import session_service


def _latest_event(
    db,
    org_id,
    event_type: AuditEventType,
    *,
    target_id=None,
    actor_user_id=None,
) -> AuditLog | None:
    query = db.query(AuditLog).filter(
        AuditLog.organization_id == org_id,
        AuditLog.event_type == event_type.value,
    )
    if target_id is not None:
        query = query.filter(AuditLog.target_id == target_id)
    if actor_user_id is not None:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)
    return query.order_by(AuditLog.created_at.desc()).first()


def _event_count(db, org_id, event_type: AuditEventType) -> int:
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == org_id,
            AuditLog.event_type == event_type.value,
        )
        .count()
    )


def _create_user_with_membership(db, org_id, role: Role = Role.ADMIN) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"audit-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Audit User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org_id,
        role=role.value,
        is_active=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(user)
    return user


def _create_override(
    db,
    *,
    org_id,
    user_id,
    permission: P,
    override_type: str = "revoke",
) -> None:
    override = UserPermissionOverride(
        id=uuid.uuid4(),
        organization_id=org_id,
        user_id=user_id,
        permission=permission.value,
        override_type=override_type,
    )
    db.add(override)
    db.commit()


async def _authed_client_for_user(db, *, user_id, org_id, role: Role, raise_app_exceptions=True):
    token = create_session_token(
        user_id=user_id,
        org_id=org_id,
        role=role.value,
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

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    )


def _fallback_events_for_actor(db, org_id, actor_user_id) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == org_id,
            AuditLog.event_type == AuditEventType.API_MUTATION_FALLBACK.value,
            AuditLog.actor_user_id == actor_user_id,
        )
        .order_by(AuditLog.created_at.desc())
        .all()
    )


async def _create_surrogate(authed_client: AsyncClient, *, index: int, assign_to_user: bool = True):
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": f"Surrogate {index}",
            "email": f"surrogate-{index}@test.com",
            "assign_to_user": assign_to_user,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_intended_parent(authed_client: AsyncClient, *, index: int):
    response = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": f"Intended Parent {index}",
            "email": f"ip-{index}@test.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_audit_list_is_org_wide_and_actor_filter_still_works(authed_client, db, test_auth):
    from app.services import audit_service

    other_user = _create_user_with_membership(db, test_auth.org.id, Role.ADMIN)

    audit_service.log_event(
        db=db,
        org_id=test_auth.org.id,
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
        actor_user_id=test_auth.user.id,
        target_type="user",
        target_id=test_auth.user.id,
    )
    audit_service.log_event(
        db=db,
        org_id=test_auth.org.id,
        event_type=AuditEventType.AUTH_LOGOUT,
        actor_user_id=other_user.id,
        target_type="user",
        target_id=other_user.id,
    )
    db.commit()

    response = await authed_client.get("/audit/")
    assert response.status_code == 200, response.text
    payload = response.json()
    actor_ids = {item["actor_user_id"] for item in payload["items"] if item["actor_user_id"]}
    assert str(test_auth.user.id) in actor_ids
    assert str(other_user.id) in actor_ids

    filtered = await authed_client.get("/audit/", params={"actor_user_id": str(other_user.id)})
    assert filtered.status_code == 200, filtered.text
    filtered_payload = filtered.json()
    assert filtered_payload["total"] >= 1
    assert all(item["actor_user_id"] == str(other_user.id) for item in filtered_payload["items"])


@pytest.mark.asyncio
async def test_uninstrumented_mutation_logs_fallback_on_success(authed_client, db, test_auth):
    response = await authed_client.post(
        "/queues",
        json={"name": f"Queue {uuid.uuid4().hex[:6]}"},
    )
    assert response.status_code == 201, response.text

    events = _fallback_events_for_actor(db, test_auth.org.id, test_auth.user.id)
    assert events
    details = events[0].details or {}
    assert details.get("method") == "POST"
    assert details.get("path") == "/queues"
    assert details.get("status_code") == 201
    assert details.get("outcome_class") == "success"


@pytest.mark.asyncio
async def test_authenticated_denied_mutation_logs_fallback_4xx(db, test_org):
    user = _create_user_with_membership(db, test_org.id, Role.ADMIN)
    _create_override(db, org_id=test_org.id, user_id=user.id, permission=P.QUEUES_MANAGE)

    client = await _authed_client_for_user(
        db,
        user_id=user.id,
        org_id=test_org.id,
        role=Role.ADMIN,
    )
    try:
        async with client:
            response = await client.post(
                "/queues",
                json={"name": f"Denied Queue {uuid.uuid4().hex[:6]}"},
            )
            assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.clear()

    events = _fallback_events_for_actor(db, test_org.id, user.id)
    assert events
    details = events[0].details or {}
    assert details.get("status_code") == 403
    assert details.get("outcome_class") == "client_error"


@pytest.mark.asyncio
async def test_authenticated_mutation_5xx_logs_fallback(db, test_auth, monkeypatch):
    from app.services import queue_service

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(queue_service, "create_queue", _boom)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    client = AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="https://test",
        cookies={COOKIE_NAME: test_auth.token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    )
    try:
        async with client:
            response = await client.post(
                "/queues",
                json={"name": f"Boom Queue {uuid.uuid4().hex[:6]}"},
            )
        assert response.status_code == 500, response.text
    finally:
        app.dependency_overrides.clear()

    events = _fallback_events_for_actor(db, test_auth.org.id, test_auth.user.id)
    assert events
    details = events[0].details or {}
    assert details.get("status_code") == 500
    assert details.get("outcome_class") == "server_error"


@pytest.mark.asyncio
async def test_instrumented_mutation_does_not_emit_fallback(authed_client, db, test_auth):
    response = await authed_client.post(
        "/intended-parents",
        json={"full_name": "No Fallback IP", "email": "no-fallback-ip@test.com"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()

    created_event = _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.INTENDED_PARENT_CREATED,
        target_id=uuid.UUID(payload["id"]),
        actor_user_id=test_auth.user.id,
    )
    assert created_event is not None

    fallback_count = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_auth.org.id,
            AuditLog.event_type == AuditEventType.API_MUTATION_FALLBACK.value,
            AuditLog.details["route_template"].astext == "/intended-parents",
        )
        .count()
    )
    assert fallback_count == 0


@pytest.mark.asyncio
async def test_surrogate_write_routes_emit_semantic_audit_events(authed_client, db, test_auth):
    # create
    surrogate_1 = await _create_surrogate(authed_client, index=1, assign_to_user=True)
    surrogate_1_id = uuid.UUID(surrogate_1["id"])
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.SURROGATE_CREATED,
        target_id=surrogate_1_id,
        actor_user_id=test_auth.user.id,
    )

    # update
    update_response = await authed_client.patch(
        f"/surrogates/{surrogate_1_id}",
        json={"full_name": "Surrogate One Updated"},
    )
    assert update_response.status_code == 200, update_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.SURROGATE_UPDATED,
        target_id=surrogate_1_id,
        actor_user_id=test_auth.user.id,
    )

    # claim
    surrogate_2 = await _create_surrogate(authed_client, index=2, assign_to_user=False)
    surrogate_2_id = uuid.UUID(surrogate_2["id"])
    claim_response = await authed_client.post(f"/surrogates/{surrogate_2_id}/claim")
    assert claim_response.status_code == 200, claim_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.SURROGATE_CLAIMED,
        target_id=surrogate_2_id,
        actor_user_id=test_auth.user.id,
    )

    # assign + bulk assign
    other_user = _create_user_with_membership(db, test_auth.org.id, Role.CASE_MANAGER)
    assign_response = await authed_client.patch(
        f"/surrogates/{surrogate_2_id}/assign",
        json={"owner_type": "user", "owner_id": str(other_user.id)},
    )
    assert assign_response.status_code == 200, assign_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.SURROGATE_ASSIGNED,
        target_id=surrogate_2_id,
        actor_user_id=test_auth.user.id,
    )

    surrogate_3 = await _create_surrogate(authed_client, index=3, assign_to_user=False)
    surrogate_4 = await _create_surrogate(authed_client, index=4, assign_to_user=False)
    bulk_assign_response = await authed_client.post(
        "/surrogates/bulk-assign",
        json={
            "owner_type": "user",
            "owner_id": str(test_auth.user.id),
            "surrogate_ids": [surrogate_3["id"], surrogate_4["id"]],
        },
    )
    assert bulk_assign_response.status_code == 200, bulk_assign_response.text
    assert _event_count(db, test_auth.org.id, AuditEventType.SURROGATE_BULK_ASSIGNED) >= 1

    # archive -> restore -> delete
    archive_response = await authed_client.post(f"/surrogates/{surrogate_1_id}/archive")
    assert archive_response.status_code == 200, archive_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.SURROGATE_ARCHIVED,
        target_id=surrogate_1_id,
        actor_user_id=test_auth.user.id,
    )

    restore_response = await authed_client.post(f"/surrogates/{surrogate_1_id}/restore")
    assert restore_response.status_code == 200, restore_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.SURROGATE_RESTORED,
        target_id=surrogate_1_id,
        actor_user_id=test_auth.user.id,
    )

    rearchive_response = await authed_client.post(f"/surrogates/{surrogate_1_id}/archive")
    assert rearchive_response.status_code == 200, rearchive_response.text
    delete_response = await authed_client.delete(f"/surrogates/{surrogate_1_id}")
    assert delete_response.status_code == 204, delete_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.SURROGATE_DELETED,
        target_id=surrogate_1_id,
        actor_user_id=test_auth.user.id,
    )


@pytest.mark.asyncio
async def test_intended_parent_write_routes_emit_semantic_audit_events(authed_client, db, test_auth):
    create_response = await authed_client.post(
        "/intended-parents",
        json={"full_name": "IP One", "email": "ip-one@test.com"},
    )
    assert create_response.status_code == 201, create_response.text
    ip_id = uuid.UUID(create_response.json()["id"])
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.INTENDED_PARENT_CREATED,
        target_id=ip_id,
        actor_user_id=test_auth.user.id,
    )

    update_response = await authed_client.patch(
        f"/intended-parents/{ip_id}",
        json={"full_name": "IP One Updated"},
    )
    assert update_response.status_code == 200, update_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.INTENDED_PARENT_UPDATED,
        target_id=ip_id,
        actor_user_id=test_auth.user.id,
    )

    status_response = await authed_client.patch(
        f"/intended-parents/{ip_id}/status",
        json={"status": "ready_to_match", "reason": "ready"},
    )
    assert status_response.status_code == 200, status_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.INTENDED_PARENT_STATUS_CHANGED,
        target_id=ip_id,
        actor_user_id=test_auth.user.id,
    )

    archive_response = await authed_client.post(f"/intended-parents/{ip_id}/archive")
    assert archive_response.status_code == 200, archive_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.INTENDED_PARENT_ARCHIVED,
        target_id=ip_id,
        actor_user_id=test_auth.user.id,
    )

    restore_response = await authed_client.post(f"/intended-parents/{ip_id}/restore")
    assert restore_response.status_code == 200, restore_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.INTENDED_PARENT_RESTORED,
        target_id=ip_id,
        actor_user_id=test_auth.user.id,
    )

    rearchive_response = await authed_client.post(f"/intended-parents/{ip_id}/archive")
    assert rearchive_response.status_code == 200, rearchive_response.text
    delete_response = await authed_client.delete(f"/intended-parents/{ip_id}")
    assert delete_response.status_code == 204, delete_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.INTENDED_PARENT_DELETED,
        target_id=ip_id,
        actor_user_id=test_auth.user.id,
    )


@pytest.mark.asyncio
async def test_task_write_routes_emit_semantic_audit_events(authed_client, db, test_auth):
    create_task = await authed_client.post("/tasks", json={"title": "Task One"})
    assert create_task.status_code == 201, create_task.text
    task_id = uuid.UUID(create_task.json()["id"])
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.TASK_CREATED,
        target_id=task_id,
        actor_user_id=test_auth.user.id,
    )

    update_task = await authed_client.patch(f"/tasks/{task_id}", json={"title": "Task One Updated"})
    assert update_task.status_code == 200, update_task.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.TASK_UPDATED,
        target_id=task_id,
        actor_user_id=test_auth.user.id,
    )

    complete_task = await authed_client.post(f"/tasks/{task_id}/complete")
    assert complete_task.status_code == 200, complete_task.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.TASK_COMPLETED,
        target_id=task_id,
        actor_user_id=test_auth.user.id,
    )

    uncomplete_task = await authed_client.post(f"/tasks/{task_id}/uncomplete")
    assert uncomplete_task.status_code == 200, uncomplete_task.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.TASK_UNCOMPLETED,
        target_id=task_id,
        actor_user_id=test_auth.user.id,
    )

    task_two = await authed_client.post("/tasks", json={"title": "Task Two"})
    task_three = await authed_client.post("/tasks", json={"title": "Task Three"})
    assert task_two.status_code == 201, task_two.text
    assert task_three.status_code == 201, task_three.text
    task_two_id = task_two.json()["id"]
    task_three_id = task_three.json()["id"]

    bulk_complete = await authed_client.post(
        "/tasks/bulk-complete",
        json={"task_ids": [task_two_id, task_three_id]},
    )
    assert bulk_complete.status_code == 200, bulk_complete.text
    assert _event_count(db, test_auth.org.id, AuditEventType.TASK_BULK_COMPLETED) >= 1

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_auth.org.id,
        name=f"Approval Flow {uuid.uuid4().hex[:6]}",
        trigger_type="surrogate_created",
        trigger_config={},
        actions=[],
        scope="org",
    )
    db.add(workflow)
    db.flush()

    execution = WorkflowExecution(
        id=uuid.uuid4(),
        organization_id=test_auth.org.id,
        workflow_id=workflow.id,
        event_id=uuid.uuid4(),
        depth=0,
        event_source="manual",
        entity_type="surrogate",
        entity_id=uuid.uuid4(),
        trigger_event={},
        matched_conditions=True,
        actions_executed=[],
        status="paused",
        paused_at_action_index=0,
    )
    db.add(execution)
    db.flush()

    approval_task = Task(
        id=uuid.uuid4(),
        organization_id=test_auth.org.id,
        created_by_user_id=test_auth.user.id,
        owner_type="user",
        owner_id=test_auth.user.id,
        title="Approve task",
        task_type=TaskType.WORKFLOW_APPROVAL.value,
        workflow_execution_id=execution.id,
        workflow_action_index=0,
        workflow_action_type="add_note",
        status=TaskStatus.PENDING.value,
    )
    db.add(approval_task)
    db.flush()

    execution.paused_task_id = approval_task.id
    db.commit()

    resolve_response = await authed_client.post(
        f"/tasks/{approval_task.id}/resolve",
        json={"decision": "approve"},
    )
    assert resolve_response.status_code == 200, resolve_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.TASK_RESOLVED,
        target_id=approval_task.id,
        actor_user_id=test_auth.user.id,
    )

    delete_response = await authed_client.delete(f"/tasks/{task_id}")
    assert delete_response.status_code == 204, delete_response.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.TASK_DELETED,
        target_id=task_id,
        actor_user_id=test_auth.user.id,
    )


@pytest.mark.asyncio
async def test_match_write_routes_emit_semantic_audit_events(authed_client, db, test_auth):
    surrogate_1 = await _create_surrogate(authed_client, index=101)
    ip_1 = await _create_intended_parent(authed_client, index=101)
    proposed_1 = await authed_client.post(
        "/matches/",
        json={
            "surrogate_id": surrogate_1["id"],
            "intended_parent_id": ip_1["id"],
            "notes": "proposal one",
        },
    )
    assert proposed_1.status_code == 201, proposed_1.text
    match_1_id = uuid.UUID(proposed_1.json()["id"])
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.MATCH_PROPOSED,
        target_id=match_1_id,
        actor_user_id=test_auth.user.id,
    )

    accept_1 = await authed_client.put(f"/matches/{match_1_id}/accept", json={"notes": "accept"})
    assert accept_1.status_code == 200, accept_1.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.MATCH_ACCEPTED,
        target_id=match_1_id,
        actor_user_id=test_auth.user.id,
    )

    surrogate_2 = await _create_surrogate(authed_client, index=102)
    ip_2 = await _create_intended_parent(authed_client, index=102)
    proposed_2 = await authed_client.post(
        "/matches/",
        json={"surrogate_id": surrogate_2["id"], "intended_parent_id": ip_2["id"]},
    )
    assert proposed_2.status_code == 201, proposed_2.text
    match_2_id = uuid.UUID(proposed_2.json()["id"])

    reject_2 = await authed_client.put(
        f"/matches/{match_2_id}/reject",
        json={"rejection_reason": "not a fit"},
    )
    assert reject_2.status_code == 200, reject_2.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.MATCH_REJECTED,
        target_id=match_2_id,
        actor_user_id=test_auth.user.id,
    )

    surrogate_3 = await _create_surrogate(authed_client, index=103)
    ip_3 = await _create_intended_parent(authed_client, index=103)
    proposed_3 = await authed_client.post(
        "/matches/",
        json={"surrogate_id": surrogate_3["id"], "intended_parent_id": ip_3["id"]},
    )
    assert proposed_3.status_code == 201, proposed_3.text
    match_3_id = uuid.UUID(proposed_3.json()["id"])

    cancel_3 = await authed_client.delete(f"/matches/{match_3_id}")
    assert cancel_3.status_code == 204, cancel_3.text
    assert _latest_event(
        db,
        test_auth.org.id,
        AuditEventType.MATCH_CANCELLED,
        target_id=match_3_id,
        actor_user_id=test_auth.user.id,
    )
