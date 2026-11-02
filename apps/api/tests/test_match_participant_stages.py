"""Step 6 participant eligibility, conflict notifications and protected stage moves."""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.db.enums import Role
from app.db.models import (
    AuditLog,
    Donor,
    IntendedParent,
    Notification,
    StatusChangeRequest,
    Surrogate,
)
from app.main import app
from app.services import (
    match_effects,
    notification_service,
    pipeline_service,
)
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _accept, _case, _donor
from tests.test_match_lifecycle_characterization import (
    _client_for,
    _diff,
    _match_row,
    _other_org,
    _snapshot,
)
from tests.test_match_permissions_v2_characterization import _activate_v2, _set_role_permission


def _stage(db, record, key):
    stage = pipeline_service.get_stage_by_key(db, record.stage.pipeline_id, key)
    record.stage_id = stage.id
    record.stage = stage
    if isinstance(record, IntendedParent):
        record.status = stage.stage_key
    db.commit()
    return stage


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [1, 2])
async def test_surrogate_conflict_set_blocks_accept_allows_decline_and_clears(
    authed_client, db, test_auth, policy
):
    if policy == 2:
        _activate_v2(db, test_auth.org.id)
    surrogate = await _create_surrogate(authed_client)
    first = await _case(
        authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
    )
    others = [
        await _case(
            authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
        )
        for _ in range(2)
    ]
    await _accept(authed_client, first)
    for other in others:
        read = (await authed_client.get(f"/matches/{other['id']}")).json()
        assert read["status"] == "under_review"
        assert read["surrogate_has_accepted_match"] is True
        assert "accept" not in read["allowed_actions"]
        assert read["blocked_reasons"]["accept"] == "Surrogate has an accepted match"
        refused = await authed_client.put(f"/matches/{other['id']}/accept", json={})
        assert refused.status_code == 400
        assert refused.json()["detail"] == "Surrogate has an accepted match"
    event = match_effects.TransitionEvent(
        "accept",
        _match_row(db, first["id"]),
        test_auth.user.id,
        match_effects.surrogate_conflict_notifications(db, _match_row(db, first["id"])),
    )
    assert match_effects.dispatch(db, event) == []
    notifications = (
        db.query(Notification)
        .filter_by(organization_id=test_auth.org.id, type="match_conflict")
        .all()
    )
    assert {n.entity_id for n in notifications} == {uuid.UUID(m["id"]) for m in others}
    assert len(notifications) == 2
    assert all(n.user_id == test_auth.user.id for n in notifications)
    declined = await authed_client.put(
        f"/matches/{others[0]['id']}/decline", json={"reason": "Withdrawn"}
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"
    await _cancel(authed_client, db, first)
    read = (await authed_client.get(f"/matches/{others[1]['id']}")).json()
    assert read["surrogate_has_accepted_match"] is False
    assert read["accept_eligibility_warnings"] == []
    await _accept(authed_client, others[1])


async def _cancel(client, db, match):
    requested = await client.post(
        f"/matches/{match['id']}/cancel-request", json={"reason": "Ended"}
    )
    assert requested.status_code == 200, requested.text
    request = (
        db.query(StatusChangeRequest)
        .filter_by(entity_id=uuid.UUID(match["id"]), status="pending")
        .one()
    )
    approved = await client.post(f"/status-change-requests/{request.id}/approve")
    assert approved.status_code == 200, approved.text
    return request


@pytest.mark.asyncio
async def test_conflict_notification_failure_is_audited_and_later_recipient_still_notified(
    authed_client, db, test_auth, monkeypatch
):
    surrogate = await _create_surrogate(authed_client)
    matches = [
        await _case(
            authed_client, await _create_intended_parent(authed_client), surrogate=surrogate
        )
        for _ in range(3)
    ]
    failed_id = min(m["id"] for m in matches[1:])
    create = notification_service.create_notification

    def fail_one(*args, **kwargs):
        if kwargs.get("type") == "match_conflict" and str(kwargs["entity_id"]) == failed_id:
            raise RuntimeError("injected")
        return create(*args, **kwargs)

    monkeypatch.setattr(notification_service, "create_notification", fail_one)
    # The effect rollback must not roll back the fixture's outer transaction.
    with Session(bind=db.connection(), join_transaction_mode="create_savepoint") as request_db:
        original = app.dependency_overrides[get_db]
        app.dependency_overrides[get_db] = lambda: request_db
        try:
            response = await authed_client.put(f"/matches/{matches[0]['id']}/accept", json={})
        finally:
            app.dependency_overrides[get_db] = original
    assert response.status_code == 200, response.text
    assert _match_row(db, matches[0]["id"]).status == "accepted"
    failures = (
        db.query(AuditLog)
        .filter_by(organization_id=test_auth.org.id, event_type="match_effect_failed")
        .all()
    )
    assert len(failures) == 1
    assert failures[0].details["effect"] == f"surrogate_conflict_notification:{failed_id}"
    assert failures[0].details["error_class"] == "RuntimeError"
    assert failures[0].target_id == uuid.UUID(failed_id)
    assert failures[0].details["match_id"] == failed_id
    assert (
        db.query(Notification)
        .filter_by(organization_id=test_auth.org.id, type="match_conflict")
        .count()
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [1, 2])
@pytest.mark.parametrize("kind", ["surrogate", "egg", "sperm"])
@pytest.mark.parametrize("denied", ["permission", "cross_org"])
async def test_eligibility_fields_require_view_permission_and_org_scope(
    authed_client, db, test_auth, policy, kind, denied
):
    if policy == 2:
        _activate_v2(db, test_auth.org.id)
    donor = kind != "surrogate"
    party = (
        await _donor(authed_client, donor_type=kind)
        if donor
        else await _create_surrogate(authed_client)
    )
    match = await _case(
        authed_client,
        await _create_intended_parent(authed_client),
        **{"donor" if donor else "surrogate": party},
    )
    org = _other_org(db) if denied == "cross_org" else test_auth.org
    if policy == 2 and denied == "permission":
        _set_role_permission(db, org.id, Role.CASE_MANAGER, "view_matches", False)
    async with _client_for(
        db,
        org.id,
        role=Role.CASE_MANAGER if denied == "permission" else Role.ADMIN,
        revoke=("view_matches",) if denied == "permission" and policy == 1 else (),
    ) as (_, client):
        read = await client.get(f"/matches/{match['id']}")
        assert read.status_code == (404 if denied == "cross_org" else 403)
        assert "accept_eligibility_warnings" not in read.json()
        assert "surrogate_has_accepted_match" not in read.json()
    assert _match_row(db, match["id"]).status == "under_review"


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [1, 2])
async def test_accept_requires_ip_stage_permission_and_rolls_back_primary_move(
    authed_client, db, test_auth, policy, subtests
):
    if policy == 2:
        _activate_v2(db, test_auth.org.id)
        _set_role_permission(
            db, test_auth.org.id, Role.CASE_MANAGER, "change_intended_parent_status", False
        )
    for kind in ["surrogate", "egg", "sperm"]:
        with subtests.test(kind=repr(kind)):
            is_donor = kind != "surrogate"
            party = (
                await _donor(authed_client, donor_type=kind)
                if is_donor
                else await _create_surrogate(authed_client)
            )
            match = await _case(
                authed_client,
                await _create_intended_parent(authed_client),
                **{"donor" if is_donor else "surrogate": party},
            )
            model = Donor if is_donor else Surrogate
            before = db.get(model, uuid.UUID(party["id"])).stage_id
            async with _client_for(
                db,
                test_auth.org.id,
                role=Role.CASE_MANAGER if policy == 2 else Role.ADMIN,
                revoke=("change_intended_parent_status",) if policy == 1 else (),
            ) as (_, client):
                response = await client.put(f"/matches/{match['id']}/accept", json={})
            assert response.status_code == 400
            assert response.json()["detail"] == "Missing permission: change_intended_parent_status"
            assert _match_row(db, match["id"]).status == "under_review"
            assert db.get(model, uuid.UUID(party["id"])).stage_id == before
            assert (
                db.query(AuditLog)
                .filter_by(organization_id=test_auth.org.id, event_type="match_accepted")
                .count()
                == 0
            )


@pytest.mark.asyncio
async def test_missing_matched_stage_cannot_partially_accept(
    authed_client, db, monkeypatch, subtests
):
    for kind in ["surrogate", "egg", "sperm"]:
        with subtests.test(kind=repr(kind)), monkeypatch.context() as patch:
            is_donor = kind != "surrogate"
            party = (
                await _donor(authed_client, donor_type=kind)
                if is_donor
                else await _create_surrogate(authed_client)
            )
            ip = await _create_intended_parent(authed_client)
            match = await _case(authed_client, ip, **{"donor" if is_donor else "surrogate": party})
            original = pipeline_service.get_stage_by_system_role

            def missing(db, pipeline_id, role, *args, **kwargs):
                if role == "matched":
                    return None
                return original(db, pipeline_id, role, *args, **kwargs)

            patch.setattr(pipeline_service, "get_stage_by_system_role", missing)
            response = await authed_client.put(f"/matches/{match['id']}/accept", json={})
            assert response.status_code == 400
            assert "stage not found" in response.json()["detail"]
            assert _match_row(db, match["id"]).status == "under_review"
            assert db.get(IntendedParent, uuid.UUID(ip["id"])).stage.stage_key == "ready_to_match"


@pytest.mark.asyncio
async def test_accept_denied_by_pipeline_role_rule_changes_nothing(
    authed_client, db, test_auth, subtests
):
    for kind in ["surrogate", "egg", "sperm"]:
        with subtests.test(kind=repr(kind)):
            is_donor = kind != "surrogate"
            party = (
                await _donor(authed_client, donor_type=kind)
                if is_donor
                else await _create_surrogate(authed_client)
            )
            ip = await _create_intended_parent(authed_client)
            match = await _case(authed_client, ip, **{"donor" if is_donor else "surrogate": party})
            model = Donor if is_donor else Surrogate
            row = db.get(model, uuid.UUID(party["id"]))
            pipeline = row.stage.pipeline
            pipeline.feature_config = {
                **pipeline.feature_config,
                "role_mutation": {
                    Role.DEVELOPER.value: {
                        "stage_keys": [row.stage.stage_key],
                        "stage_types": [],
                        "capabilities": [],
                    }
                },
            }
            db.commit()
            before_stage = row.stage_id
            before_ip_stage = db.get(IntendedParent, uuid.UUID(ip["id"])).stage_id
            read = await authed_client.get(f"/matches/{match['id']}")
            assert "accept" not in read.json()["allowed_actions"]
            before_history = _snapshot(db, test_auth.org.id)

            response = await authed_client.put(f"/matches/{match['id']}/accept", json={})

            assert response.status_code == 400, response.text
            party_kind = "donor" if is_donor else "surrogate"
            assert (
                response.json()["detail"]
                == read.json()["blocked_reasons"]["accept"]
                == f"Role not permitted to change {party_kind} stage"
            )
            assert _match_row(db, match["id"]).status == "under_review"
            assert db.get(model, row.id).stage_id == before_stage
            assert db.get(IntendedParent, uuid.UUID(ip["id"])).stage_id == before_ip_stage
            # Keep the rejected HTTP request's fallback audit; no domain history changes.
            assert _diff(before_history, _snapshot(db, test_auth.org.id)) == {
                "audit": {("api_mutation_fallback", "api_route"): 1},
                "surrogate_activity": {},
                "entity_activity": {},
                "stage_history": {},
            }
