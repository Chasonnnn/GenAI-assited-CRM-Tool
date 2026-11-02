"""Characterization of match after-commit effects and AI route access.

Split from test_match_lifecycle_characterization.py; the same pinning rules apply.
"""

import uuid
from collections import Counter

import pytest

from app.db.models import (
    AuditLog,
    AutomationWorkflow,
    Donor,
    Match,
    StatusChangeRequest,
    Surrogate,
    Task,
    UserPermissionOverride,
    WorkflowExecution,
)
from app.services import (
    dashboard_service,
    match_lifecycle,
    notification_service,
    workflow_triggers,
)
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _accept, _case, _donor
from tests.test_match_lifecycle_characterization import (
    _client_for,
    _committed_org,
    _committed_state,
    _foreign_accepted_match,
    _ip_stage_key,
    _match_row,
    _other_org,
    _request_cancel,
    _snapshot,
    _Spy,
    _spy_ordered_effects,
    _stage_slug,
)


@pytest.mark.asyncio
async def test_accept_dispatches_surrogate_stage_callbacks_before_later_effects(
    authed_client, db, test_auth, monkeypatch
):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)
    events: list[str] = []
    spies = _spy_ordered_effects(monkeypatch, events)

    await _accept(authed_client, created)

    assert events == [
        "dispatch_note_added",
        "handle_status_changed",
        "push_dashboard_stats",
        "trigger_match_accepted",
    ]
    stage = spies["handle_status_changed"].calls[0][1]
    assert stage["surrogate"].id == uuid.UUID(surrogate["id"])
    assert stage["new_stage"].slug == "matched"
    assert stage["old_slug"] == "ready_to_match"
    assert stage["user_id"] == test_auth.user.id
    assert stage["request_id"] is None
    assert stage["approved_by_user_id"] is None
    assert stage["is_undo"] is False
    assert stage["trigger_workflows"] is True
    note = spies["dispatch_note_added"].calls[0][1]
    assert note["org_id"] == test_auth.org.id
    from app.db.models import EntityNote

    note_row = db.get(EntityNote, note["note_id"])
    assert note_row.entity_id == uuid.UUID(surrogate["id"])
    assert "Match accepted" in note_row.content


@pytest.mark.asyncio
async def test_accept_donor_match_dispatches_donor_stage_callback_before_later_effects(
    authed_client, db, test_auth, monkeypatch
):
    created = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        donor=await _donor(authed_client),
    )
    events: list[str] = []
    _spy_ordered_effects(monkeypatch, events)
    stage_trigger = _Spy(events=events, name="trigger_donor_stage_changed")
    monkeypatch.setattr(workflow_triggers, "trigger_donor_stage_changed", stage_trigger)

    await _accept(authed_client, created)

    assert events == [
        "trigger_donor_stage_changed",
        "push_dashboard_stats",
        "trigger_match_accepted",
    ]
    assert stage_trigger.calls[0][1]["old_stage"].stage_key == "ready_to_match"
    assert stage_trigger.calls[0][1]["new_stage"].stage_key == "matched"


@pytest.mark.asyncio
async def test_failing_proposed_trigger_returns_created_after_match_is_committed(
    db_engine, monkeypatch
):
    async with _committed_org(db_engine, monkeypatch) as (org_id, _user_id, client):
        surrogate = await _create_surrogate(client)
        ip = await _create_intended_parent(client)
        monkeypatch.setattr(
            workflow_triggers, "trigger_match_proposed", _Spy(error=RuntimeError("workflow down"))
        )

        response = await client.post(
            "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
        )

        assert response.status_code == 201, response.text
        assert response.json()["status"] == "under_review"
        from sqlalchemy.orm import Session

        with Session(db_engine) as verify:
            statuses = [
                row.status
                for row in verify.query(Match).filter(
                    Match.organization_id == org_id,
                    Match.surrogate_id == uuid.UUID(surrogate["id"]),
                )
            ]
        assert statuses == ["under_review"]


@pytest.mark.asyncio
async def test_failing_accepted_trigger_returns_success_after_accept_is_committed(
    db_engine, monkeypatch
):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        surrogate = await _create_surrogate(client)
        ip = await _create_intended_parent(client)
        created = await _case(client, ip, surrogate=surrogate)
        monkeypatch.setattr(
            workflow_triggers, "trigger_match_accepted", _Spy(error=RuntimeError("workflow down"))
        )

        response = await client.put(f"/matches/{created['id']}/accept", json={})

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "accepted"
        assert _committed_state(db_engine, created["id"], surrogate["id"], ip["id"]) == {
            "match": "accepted",
            "requests": [],
            "surrogate_stage": "matched",
            "ip_stage": "matched",
        }


@pytest.mark.asyncio
async def test_failing_dashboard_push_after_accept_still_runs_trigger(db_engine, monkeypatch):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        surrogate = await _create_surrogate(client)
        created = await _case(client, await _create_intended_parent(client), surrogate=surrogate)
        events: list[str] = []
        spies = _spy_ordered_effects(monkeypatch, events, failing="push_dashboard_stats")

        response = await client.put(f"/matches/{created['id']}/accept", json={})

        assert response.status_code == 200, response.text
        assert events == [
            "dispatch_note_added",
            "handle_status_changed",
            "push_dashboard_stats",
            "trigger_match_accepted",
        ]
        assert len(spies["trigger_match_accepted"].calls) == 1
        assert _committed_state(db_engine, created["id"], surrogate["id"])["match"] == "accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize("failing", ["dispatch_note_added", "handle_status_changed"])
async def test_failing_accept_stage_callback_still_runs_later_effects(
    db_engine, monkeypatch, failing
):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        surrogate = await _create_surrogate(client)
        ip = await _create_intended_parent(client)
        created = await _case(client, ip, surrogate=surrogate)
        events: list[str] = []
        _spy_ordered_effects(monkeypatch, events, failing=failing)

        response = await client.put(f"/matches/{created['id']}/accept", json={})

        assert response.status_code == 200, response.text
        assert events == [
            "dispatch_note_added",
            "handle_status_changed",
            "push_dashboard_stats",
            "trigger_match_accepted",
        ]
        assert _committed_state(db_engine, created["id"], surrogate["id"], ip["id"]) == {
            "match": "accepted",
            "requests": [],
            "surrogate_stage": "matched",
            "ip_stage": "matched",
        }


@pytest.mark.asyncio
async def test_failing_rejected_trigger_returns_success_after_reject_is_committed(
    db_engine, monkeypatch
):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        created = await _case(
            client, await _create_intended_parent(client), surrogate=await _create_surrogate(client)
        )
        monkeypatch.setattr(
            workflow_triggers, "trigger_match_declined", _Spy(error=RuntimeError("workflow down"))
        )

        response = await client.put(f"/matches/{created['id']}/decline", json={"reason": "No"})

        assert response.status_code == 200, response.text
        assert _committed_state(db_engine, created["id"])["match"] == "declined"


@pytest.mark.asyncio
async def test_failing_cancel_request_notification_returns_success_after_request_is_committed(
    db_engine, monkeypatch
):
    async with _committed_org(db_engine, monkeypatch) as (_org_id, _user_id, client):
        created = await _accept(
            client,
            await _case(
                client,
                await _create_intended_parent(client),
                surrogate=await _create_surrogate(client),
            ),
        )
        monkeypatch.setattr(
            notification_service,
            "notify_match_cancel_request_pending",
            _Spy(error=RuntimeError("notify down")),
        )

        response = await client.post(
            f"/matches/{created['id']}/cancel-request", json={"reason": "Ended"}
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "cancellation_pending"
        state = _committed_state(db_engine, created["id"])
        assert state == {"match": "cancellation_pending", "requests": ["pending"]}


def _effect_failures(db, match_id) -> list[dict]:
    db.expire_all()
    return [
        row.details
        for row in db.query(AuditLog)
        .filter(
            AuditLog.event_type == "match_effect_failed",
            AuditLog.target_type == "match",
            AuditLog.target_id == uuid.UUID(str(match_id)),
        )
        .order_by(AuditLog.created_at)
    ]


@pytest.mark.asyncio
async def test_failing_effect_is_recorded_on_the_match_and_later_effects_run(
    authed_client, db, test_auth, monkeypatch
):
    created = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        surrogate=await _create_surrogate(authed_client),
    )
    events: list[str] = []
    spies = _spy_ordered_effects(monkeypatch, events, failing="push_dashboard_stats")

    response = await authed_client.put(f"/matches/{created['id']}/accept", json={})

    assert response.status_code == 200, response.text
    assert events[-2:] == ["push_dashboard_stats", "trigger_match_accepted"]
    assert len(spies["trigger_match_accepted"].calls) == 1
    assert _match_row(db, created["id"]).status == "accepted"
    assert _effect_failures(db, created["id"]) == [
        {
            "match_id": created["id"],
            "action": "accept",
            "effect": "dashboard_push",
            "error_class": "RuntimeError",
        }
    ]
    feed = await authed_client.get(f"/matches/{created['id']}/work")
    assert feed.status_code == 200, feed.text
    assert "Match Effect Failed" in {item["event_type"] for item in feed.json()["activity"]}


def test_non_match_dashboard_push_keeps_build_failures_best_effort(
    db, test_org, monkeypatch, caplog
):
    from app.services import surrogate_service

    monkeypatch.setattr(
        surrogate_service, "get_surrogate_stats", _Spy(error=RuntimeError("stats unavailable"))
    )

    dashboard_service.push_dashboard_stats(db, test_org.id)

    assert "Failed to build dashboard stats for websocket push" in caplog.text


@pytest.mark.asyncio
async def test_dashboard_build_failure_is_recorded_and_later_effect_runs(
    authed_client, db, monkeypatch
):
    from app.services import surrogate_service

    created = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        surrogate=await _create_surrogate(authed_client),
    )
    accepted_trigger = _Spy()
    monkeypatch.setattr(workflow_triggers, "trigger_match_accepted", accepted_trigger)
    monkeypatch.setattr(
        surrogate_service, "get_surrogate_stats", _Spy(error=RuntimeError("stats unavailable"))
    )

    response = await authed_client.put(f"/matches/{created['id']}/accept", json={})

    assert response.status_code == 200, response.text
    assert _match_row(db, created["id"]).status == "accepted"
    assert len(accepted_trigger.calls) == 1
    assert _effect_failures(db, created["id"]) == [
        {
            "match_id": created["id"],
            "action": "accept",
            "effect": "dashboard_push",
            "error_class": "RuntimeError",
        }
    ]


@pytest.mark.asyncio
async def test_each_failing_effect_is_recorded_separately(authed_client, db, monkeypatch):
    created = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        surrogate=await _create_surrogate(authed_client),
    )
    events: list[str] = []
    _spy_ordered_effects(monkeypatch, events)
    monkeypatch.setattr(
        workflow_triggers, "trigger_match_accepted", _Spy(error=ValueError("workflow down"))
    )
    monkeypatch.setattr(
        dashboard_service, "push_dashboard_stats_or_raise", _Spy(error=RuntimeError("socket down"))
    )

    response = await authed_client.put(f"/matches/{created['id']}/accept", json={})

    assert response.status_code == 200, response.text
    assert [(row["effect"], row["error_class"]) for row in _effect_failures(db, created["id"])] == [
        ("dashboard_push", "RuntimeError"),
        ("workflow_trigger_match_accepted", "ValueError"),
    ]


# =============================================================================
# AI routes enforce match access like the matches router
# =============================================================================


@pytest.mark.asyncio
async def test_ai_bulk_tasks_require_view_matches(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=surrogate)

    async with _client_for(db, test_auth.org.id, revoke=("view_matches",)) as (user, client):
        denied = await client.get(f"/matches/{created['id']}")
        response = await client.post(
            "/ai/create-bulk-tasks",
            json={
                "request_id": str(uuid.uuid4()),
                "match_id": created["id"],
                "tasks": [{"title": "Schedule consult"}],
            },
        )

    assert denied.status_code == 403
    assert response.status_code == 403
    assert response.json()["detail"] == denied.json()["detail"]
    assert db.query(Task).filter(Task.created_by_user_id == user.id).count() == 0


@pytest.mark.asyncio
async def test_ai_bulk_task_replay_requires_current_match_access(authed_client, db, test_auth):
    created = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        surrogate=await _create_surrogate(authed_client),
    )
    body = {
        "request_id": str(uuid.uuid4()),
        "match_id": created["id"],
        "tasks": [{"title": "Schedule consult"}],
    }
    async with _client_for(db, test_auth.org.id) as (user, client):
        initial = await client.post("/ai/create-bulk-tasks", json=body)
        assert initial.status_code == 200, initial.text
        count = db.query(Task).filter(Task.created_by_user_id == user.id).count()
        assert count == 1
        db.add(
            UserPermissionOverride(
                id=uuid.uuid4(),
                organization_id=test_auth.org.id,
                user_id=user.id,
                permission="view_matches",
                override_type="revoke",
            )
        )
        db.commit()

        replay = await client.post("/ai/create-bulk-tasks", json=body)
        fresh = await client.post(
            "/ai/create-bulk-tasks", json={**body, "request_id": str(uuid.uuid4())}
        )

    assert replay.status_code == fresh.status_code == 403
    assert replay.json()["detail"] == fresh.json()["detail"] == "Missing permission: view_matches"
    assert db.query(Task).filter(Task.created_by_user_id == user.id).count() == count


@pytest.mark.asyncio
async def test_ai_parse_schedule_requires_view_matches(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, test_auth.org.id, revoke=("view_matches",)) as (_user, client):
        response = await client.post(
            "/ai/parse-schedule", json={"text": "Consult tomorrow", "match_id": created["id"]}
        )
        missing = await client.post(
            "/ai/parse-schedule", json={"text": "Consult tomorrow", "match_id": str(uuid.uuid4())}
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: view_matches"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Match not found"


@pytest.mark.asyncio
async def test_ai_parse_schedule_stream_requires_view_matches(authed_client, db, test_auth):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))

    async with _client_for(db, test_auth.org.id, revoke=("view_matches",)) as (_user, client):
        response = await client.post(
            "/ai/parse-schedule/stream",
            json={"text": "Consult tomorrow", "match_id": created["id"]},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: view_matches"


@pytest.mark.asyncio
async def test_ai_parse_schedule_stream_returns_404_for_foreign_match(authed_client, db):
    match = await _foreign_accepted_match(db)

    response = await authed_client.post(
        "/ai/parse-schedule/stream", json={"text": "Consult tomorrow", "match_id": match["id"]}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Match not found"


@pytest.mark.asyncio
@pytest.mark.parametrize("revoked", ["view_intended_parents", "view_surrogates"])
async def test_ai_routes_require_record_scope_on_both_parties(
    authed_client, db, test_auth, revoked
):
    ip = await _create_intended_parent(authed_client)
    created = await _case(authed_client, ip, surrogate=await _create_surrogate(authed_client))
    count = db.query(Task).filter_by(organization_id=test_auth.org.id).count()

    async with _client_for(db, test_auth.org.id, revoke=(revoked,)) as (_user, client):
        detail = await client.get(f"/matches/{created['id']}")
        bulk = await client.post(
            "/ai/create-bulk-tasks",
            json={
                "request_id": str(uuid.uuid4()),
                "match_id": created["id"],
                "tasks": [{"title": "Scoped task"}],
            },
        )
        parsed = await client.post(
            "/ai/parse-schedule", json={"text": "Consult tomorrow", "match_id": created["id"]}
        )

    assert detail.status_code in (403, 404)
    for response in (bulk, parsed):
        assert (response.status_code, response.json()["detail"]) == (
            detail.status_code,
            detail.json()["detail"],
        )
    assert db.query(Task).filter_by(organization_id=test_auth.org.id).count() == count


def _transition_history(db, org_id):
    history = _snapshot(db, org_id)
    # Denied HTTP mutations can emit a request audit without changing match history.
    history["audit"] = Counter(
        {key: count for key, count in history["audit"].items() if key[1] == "match"}
    )
    return history


@pytest.mark.asyncio
@pytest.mark.parametrize("donor", [False, True])
@pytest.mark.parametrize("revoke_view", [False, True])
async def test_proposer_can_decline_own_match_without_propose_permission(
    authed_client, db, test_auth, donor, revoke_view
):
    async with _client_for(db, test_auth.org.id) as (proposer, client):
        match = await _case(
            client,
            await _create_intended_parent(authed_client),
            **(
                {"donor": await _donor(authed_client)}
                if donor
                else {"surrogate": await _create_surrogate(authed_client)}
            ),
        )
        for permission in ["propose_matches", *(["view_matches"] if revoke_view else [])]:
            db.add(
                UserPermissionOverride(
                    organization_id=test_auth.org.id,
                    user_id=proposer.id,
                    permission=permission,
                    override_type="revoke",
                )
            )
        db.commit()
        before = _transition_history(db, test_auth.org.id)
        response = await client.put(
            f"/matches/{match['id']}/decline", json={"reason": "  Withdrawing  "}
        )
        if revoke_view:
            assert response.status_code == 403
            assert _match_row(db, match["id"]).status == "under_review"
            assert _transition_history(db, test_auth.org.id) == before
        else:
            assert response.status_code == 200, response.text
            assert response.json()["decline_reason"] == "Withdrawing"
            history = (
                db.query(AuditLog)
                .filter(
                    AuditLog.target_id == uuid.UUID(match["id"]),
                    AuditLog.event_type == "match_declined",
                )
                .one()
            )
            assert history.actor_user_id == proposer.id
            assert _match_row(db, match["id"]).closed_by_user_id == proposer.id


@pytest.mark.asyncio
@pytest.mark.parametrize("donor", [False, True])
@pytest.mark.parametrize("action", ["proposed", "accepted", "declined", "cancelled"])
async def test_lifecycle_workflow_callbacks_include_both_match_kinds(
    authed_client, db, test_auth, monkeypatch, donor, action
):
    trigger = _Spy()
    monkeypatch.setattr(workflow_triggers.engine, "trigger", trigger)
    party = await _donor(authed_client) if donor else await _create_surrogate(authed_client)
    match = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        **({"donor": party} if donor else {"surrogate": party}),
    )
    if action in {"accepted", "cancelled"}:
        await _accept(authed_client, match)
    if action == "declined":
        response = await authed_client.put(
            f"/matches/{match['id']}/decline", json={"reason": "Ended"}
        )
        assert response.status_code == 200
    if action == "cancelled":
        await _request_cancel(authed_client, match)
        request = (
            db.query(StatusChangeRequest)
            .filter(StatusChangeRequest.entity_id == uuid.UUID(match["id"]))
            .one()
        )
        response = await authed_client.post(f"/status-change-requests/{request.id}/approve")
        assert response.status_code == 200
    calls = [
        kwargs for _, kwargs in trigger.calls if kwargs["trigger_type"].value == f"match_{action}"
    ]
    assert len(calls) == 1
    call = calls[0]
    assert call["org_id"] == test_auth.org.id
    assert call["subject_type"] == "match"
    assert call["subject_id"] == uuid.UUID(match["id"])
    assert call["event_data"]["donor_id" if donor else "surrogate_id"] == party["id"]
    assert call["event_data"]["surrogate_id" if donor else "donor_id"] is None
    assert not _effect_failures(db, match["id"])


@pytest.mark.asyncio
@pytest.mark.parametrize("donor", [False, True])
@pytest.mark.parametrize("foreign_org", [False, True])
async def test_decline_enforces_org_and_permission_for_both_match_kinds(
    authed_client, db, test_auth, donor, foreign_org
):
    party = await _donor(authed_client) if donor else await _create_surrogate(authed_client)
    match = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        **({"donor": party} if donor else {"surrogate": party}),
    )
    before = _transition_history(db, test_auth.org.id)
    org_id = _other_org(db).id if foreign_org else test_auth.org.id
    async with _client_for(db, org_id, revoke=() if foreign_org else ("propose_matches",)) as (
        _,
        client,
    ):
        response = await client.put(f"/matches/{match['id']}/decline", json={"reason": "Ended"})
    assert response.status_code == (404 if foreign_org else 403)
    assert _match_row(db, match["id"]).status == match["status"]
    assert _transition_history(db, test_auth.org.id) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("donor", [False, True])
async def test_missing_workflow_party_records_effect_failure(
    authed_client, db, test_auth, monkeypatch, caplog, donor
):
    from sqlalchemy.orm import Session

    from app.services import match_queries

    party = await _donor(authed_client) if donor else await _create_surrogate(authed_client)
    match = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        **({"donor": party} if donor else {"surrogate": party}),
    )
    monkeypatch.setattr(
        match_queries, "get_donor" if donor else "get_surrogate_with_stage", lambda *args: None
    )
    # Keep effect rollback inside a savepoint in the outer test transaction.
    with Session(bind=db.connection(), join_transaction_mode="create_savepoint") as effects_db:
        result = match_lifecycle.transition(
            effects_db,
            effects_db.get(Match, uuid.UUID(match["id"])),
            "decline",
            actor_user_id=test_auth.user.id,
            reason="Ended",
        )
        assert result.status == "declined"
        failures = _effect_failures(effects_db, match["id"])
        assert len(failures) == 1
        assert failures[0]["effect"] == "workflow_trigger_match_declined"
        assert failures[0]["error_class"] == "ValueError"
    assert any(
        record.levelname == "WARNING" and record.message == "match_workflow_party_missing"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_surrogate_stage_workflow_on_donor_match_fails_without_changes(
    authed_client, db, test_auth
):
    surrogate = await _create_surrogate(authed_client)
    donor = await _donor(authed_client)
    match = await _accept(
        authed_client,
        await _case(authed_client, await _create_intended_parent(authed_client), donor=donor),
    )
    workflow = AutomationWorkflow(
        organization_id=test_auth.org.id,
        name="Legacy surrogate stage action",
        subject_type="match",
        trigger_type="match_accepted",
        trigger_config={},
        conditions=[],
        actions=[
            {
                "action_type": "update_field",
                "field": "stage_id",
                "value": str(db.get(Surrogate, uuid.UUID(surrogate["id"])).stage_id),
            }
        ],
        created_by_user_id=test_auth.user.id,
        is_enabled=True,
    )
    db.add(workflow)
    db.commit()
    before = _snapshot(db, test_auth.org.id)
    stages = (
        _stage_slug(db, Donor, donor["id"]),
        _stage_slug(db, Surrogate, surrogate["id"]),
        _ip_stage_key(db, match["intended_parent_id"]),
    )
    workflow_triggers.trigger_match_accepted(db, _match_row(db, match["id"]))
    execution = (
        db.query(WorkflowExecution).filter(WorkflowExecution.workflow_id == workflow.id).one()
    )
    assert execution.status == "partial"
    assert len(execution.actions_executed) == 1
    assert execution.actions_executed[0]["success"] is False
    assert execution.actions_executed[0]["error"] == (
        "Action 'update_field' only supports Surrogate entities, got 'match'"
    )
    assert _snapshot(db, test_auth.org.id) == before
    assert stages == (
        _stage_slug(db, Donor, donor["id"]),
        _stage_slug(db, Surrogate, surrogate["id"]),
        _ip_stage_key(db, match["intended_parent_id"]),
    )
    assert _match_row(db, match["id"]).status == "accepted"
