"""Step 6 participant eligibility, conflict notifications and protected stage moves."""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.db.enums import Role
from app.db.models import (
    AuditLog,
    Donor,
    DonorStatusHistory,
    IntendedParent,
    Notification,
    StatusChangeRequest,
    Surrogate,
)
from app.main import app
from app.services import (
    match_effects,
    match_lifecycle,
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
@pytest.mark.parametrize(
    "kind,blocked,stage",
    [
        ("surrogate", "party", "new_unread"),
        ("surrogate", "party", "approved"),
        ("surrogate", "party", "matched"),
        ("egg", "party", "new"),
        ("egg", "party", "approved"),
        ("egg", "party", "matched"),
        ("sperm", "party", "new"),
        ("sperm", "party", "approved"),
        ("sperm", "party", "matched"),
        ("surrogate", "ip", "new"),
        ("egg", "ip", "delivered"),
        ("sperm", "ip", "new"),
    ],
)
async def test_accept_eligibility_warning_names_ineligible_party_and_stage(
    authed_client, db, test_auth, kind, blocked, stage, policy
):
    if policy == 2:
        _activate_v2(db, test_auth.org.id)
    donor = kind != "surrogate"
    party = (
        await _donor(authed_client, donor_type=kind)
        if donor
        else await _create_surrogate(authed_client)
    )
    ip = await _create_intended_parent(authed_client)
    record = db.get(
        IntendedParent if blocked == "ip" else Donor if donor else Surrogate,
        uuid.UUID(ip["id"] if blocked == "ip" else party["id"]),
    )
    target = _stage(db, record, stage)
    match = await _case(authed_client, ip, **{"donor" if donor else "surrogate": party})
    label = "Intended parent" if blocked == "ip" else "Donor" if donor else "Surrogate"
    expected = f"{label} at {target.label} ({stage}) is not eligible to accept"
    assert match["status"] == "under_review"
    assert match["accept_eligibility_warnings"] == [expected]
    assert match["surrogate_has_accepted_match"] is False
    response = await authed_client.put(f"/matches/{match['id']}/accept", json={})
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == expected
    assert _match_row(db, match["id"]).status == "under_review"
    assert db.get(type(record), record.id).stage_id == target.id
    with pytest.raises(match_lifecycle.TransitionError, match="is not eligible to accept"):
        match_lifecycle.transition(
            db,
            _match_row(db, match["id"]),
            "accept",
            actor_user_id=test_auth.user.id,
            actor_role=Role.DEVELOPER,
        )


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
        refused = await authed_client.put(f"/matches/{other['id']}/accept", json={})
        assert refused.status_code == 400
        assert refused.json()["detail"] == "Surrogate already has an accepted match"
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
@pytest.mark.parametrize("kind,handoff", [("egg", "ready_to_match"), ("sperm", "available")])
@pytest.mark.parametrize("policy", [1, 2])
@pytest.mark.parametrize("first_status", ["accepted", "cancellation_pending"])
async def test_donor_two_active_matches_keep_stage_until_last_cancellation(
    authed_client, db, test_auth, kind, handoff, policy, first_status
):
    if policy == 2:
        _activate_v2(db, test_auth.org.id)
    donor = await _donor(authed_client, donor_type=kind)
    first = await _accept(
        authed_client,
        await _case(authed_client, await _create_intended_parent(authed_client), donor=donor),
    )
    if first_status == "cancellation_pending":
        assert (
            await authed_client.post(
                f"/matches/{first['id']}/cancel-request", json={"reason": "Ended"}
            )
        ).status_code == 200
    second = await _case(authed_client, await _create_intended_parent(authed_client), donor=donor)
    assert second["accept_eligibility_warnings"] == []
    await _accept(authed_client, second)
    row = db.get(Donor, uuid.UUID(donor["id"]))
    assert row.stage.stage_key == "matched"

    def histories():
        return db.query(DonorStatusHistory).filter_by(donor_id=row.id).count()

    before = histories()
    async with _client_for(db, test_auth.org.id) as (approver, client):
        if first_status == "accepted":
            await _cancel(client, db, first)
        else:
            request = (
                db.query(StatusChangeRequest)
                .filter_by(entity_id=uuid.UUID(first["id"]), status="pending")
                .one()
            )
            assert (
                await client.post(f"/status-change-requests/{request.id}/approve")
            ).status_code == 200
        db.refresh(row)
        assert row.stage.stage_key == "matched"
        assert histories() == before
        request = await _cancel(client, db, second)
        db.refresh(row)
        assert row.stage.stage_key == handoff
        history = db.query(DonorStatusHistory).filter_by(request_id=request.id).one()
        assert history.changed_by_user_id == approver.id
        assert history.approved_by_user_id == approver.id
        assert histories() == before + 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,handoff", [("egg", "ready_to_match"), ("sperm", "available")])
async def test_donor_manual_matched_requires_active_match_and_protects_system_stages(
    authed_client, db, test_auth, kind, handoff
):
    donor = await _donor(authed_client, donor_type=kind)
    pipeline = (
        await authed_client.get(
            "/settings/pipelines/default", params={"entity_type": f"{kind}_donor"}
        )
    ).json()
    stages = {s["stage_key"]: s for s in pipeline["stages"]}
    for key, role in [(handoff, "handoff"), ("matched", "matched")]:
        assert stages[key]["is_locked"] is True
        assert stages[key]["system_role"] == role
        assert {"delete", "duplicate", "semantics", "is_active"} <= set(
            stages[key]["locked_fields"]
        )
        with pytest.raises(ValueError, match="protected"):
            pipeline_service.delete_stage(
                db,
                pipeline_service.get_stage_by_id(db, uuid.UUID(stages[key]["id"])),
                test_auth.user.id,
            )
    refused = await authed_client.patch(
        f"/donors/{donor['id']}/status", json={"stage_id": stages["matched"]["id"]}
    )
    assert refused.status_code == 400, refused.text
    assert refused.json()["detail"] == "Cannot set to Matched without an accepted Match."
    row = db.get(Donor, uuid.UUID(donor["id"]))
    assert row.stage.stage_key == handoff
    match = await _accept(
        authed_client,
        await _case(authed_client, await _create_intended_parent(authed_client), donor=donor),
    )
    _stage(db, row, handoff)
    allowed = await authed_client.patch(
        f"/donors/{donor['id']}/status", json={"stage_id": stages["matched"]["id"]}
    )
    assert allowed.status_code == 200, allowed.text
    assert _match_row(db, match["id"]).status == "accepted"


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
@pytest.mark.parametrize("kind", ["surrogate", "egg", "sperm"])
async def test_accept_requires_ip_stage_permission_and_rolls_back_primary_move(
    authed_client, db, test_auth, policy, kind
):
    if policy == 2:
        _activate_v2(db, test_auth.org.id)
        _set_role_permission(
            db, test_auth.org.id, Role.CASE_MANAGER, "edit_intended_parents", False
        )
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
        revoke=("edit_intended_parents",) if policy == 1 else (),
    ) as (_, client):
        response = await client.put(f"/matches/{match['id']}/accept", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "Stage change permission required"
    assert _match_row(db, match["id"]).status == "under_review"
    assert db.get(model, uuid.UUID(party["id"])).stage_id == before
    assert (
        db.query(AuditLog)
        .filter_by(organization_id=test_auth.org.id, event_type="match_accepted")
        .count()
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["egg", "sperm"])
@pytest.mark.parametrize("denied", ["permission", "cross_org"])
async def test_manual_donor_matched_guard_preserves_permission_and_org_scope(
    authed_client, db, test_auth, kind, denied
):
    donor = await _donor(authed_client, donor_type=kind)
    row = db.get(Donor, uuid.UUID(donor["id"]))
    before = row.stage_id
    matched = pipeline_service.get_stage_by_key(db, row.stage.pipeline_id, "matched")
    org_id = _other_org(db).id if denied == "cross_org" else test_auth.org.id
    async with _client_for(
        db, org_id, revoke=("change_donor_status",) if denied == "permission" else ()
    ) as (_, client):
        response = await client.patch(
            f"/donors/{donor['id']}/status", json={"stage_id": str(matched.id)}
        )
    assert response.status_code == (403 if denied == "permission" else 404)
    db.refresh(row)
    assert row.stage_id == before


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["egg", "sperm"])
async def test_donor_complete_keeps_participant_stages(authed_client, db, kind):
    donor = await _donor(authed_client, donor_type=kind)
    ip = await _create_intended_parent(authed_client)
    match = await _accept(authed_client, await _case(authed_client, ip, donor=donor))
    before = db.query(DonorStatusHistory).filter_by(donor_id=uuid.UUID(donor["id"])).count()
    response = await authed_client.put(
        f"/matches/{match['id']}/complete", json={"outcome": "Completed"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert db.get(Donor, uuid.UUID(donor["id"])).stage.stage_key == "matched"
    assert db.get(IntendedParent, uuid.UUID(ip["id"])).stage.stage_key == "matched"
    assert db.query(DonorStatusHistory).filter_by(donor_id=uuid.UUID(donor["id"])).count() == before
    later = await _case(authed_client, await _create_intended_parent(authed_client), donor=donor)
    assert "Donor at Matched (matched)" in later["accept_eligibility_warnings"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["surrogate", "egg", "sperm"])
async def test_missing_matched_stage_cannot_partially_accept(authed_client, db, monkeypatch, kind):
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

    monkeypatch.setattr(pipeline_service, "get_stage_by_system_role", missing)
    response = await authed_client.put(f"/matches/{match['id']}/accept", json={})
    assert response.status_code == 400
    assert "stage not found" in response.json()["detail"]
    assert _match_row(db, match["id"]).status == "under_review"
    assert db.get(IntendedParent, uuid.UUID(ip["id"])).stage.stage_key == "ready_to_match"


@pytest.mark.asyncio
async def test_donor_stage_effect_failure_is_audited_and_match_trigger_still_runs(
    authed_client, db, test_auth, monkeypatch
):
    from app.services import workflow_triggers
    from tests.test_match_lifecycle_characterization import _Spy

    donor = await _donor(authed_client)
    match = await _case(authed_client, await _create_intended_parent(authed_client), donor=donor)
    monkeypatch.setattr(
        workflow_triggers, "trigger_donor_stage_changed", _Spy(error=RuntimeError("injected"))
    )
    accepted = _Spy()
    monkeypatch.setattr(workflow_triggers, "trigger_match_accepted", accepted)
    with Session(bind=db.connection(), join_transaction_mode="create_savepoint") as request_db:
        original = app.dependency_overrides[get_db]
        app.dependency_overrides[get_db] = lambda: request_db
        try:
            response = await authed_client.put(f"/matches/{match['id']}/accept", json={})
        finally:
            app.dependency_overrides[get_db] = original
    assert response.status_code == 200, response.text
    assert _match_row(db, match["id"]).status == "accepted"
    assert db.get(Donor, uuid.UUID(donor["id"])).stage.stage_key == "matched"
    assert len(accepted.calls) == 1
    failure = (
        db.query(AuditLog)
        .filter_by(organization_id=test_auth.org.id, event_type="match_effect_failed")
        .one()
    )
    assert failure.details["effect"] == "donor_stage_changed"
    assert failure.details["error_class"] == "RuntimeError"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,stage",
    [
        ("egg", "cycle_in_progress"),
        ("egg", "retrieval_complete"),
        ("sperm", "collection_in_progress"),
        ("sperm", "donation_complete"),
    ],
)
async def test_cancellation_preserves_donor_stage_outside_matched(authed_client, db, kind, stage):
    donor = await _donor(authed_client, donor_type=kind)
    match = await _accept(
        authed_client,
        await _case(authed_client, await _create_intended_parent(authed_client), donor=donor),
    )
    row = db.get(Donor, uuid.UUID(donor["id"]))
    target = _stage(db, row, stage)
    before = db.query(DonorStatusHistory).filter_by(donor_id=row.id).count()

    await _cancel(authed_client, db, match)

    db.refresh(row)
    assert row.stage_id == target.id
    assert _match_row(db, match["id"]).status == "cancelled"
    assert db.query(DonorStatusHistory).filter_by(donor_id=row.id).count() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["surrogate", "egg", "sperm"])
async def test_accept_denied_by_pipeline_role_rule_changes_nothing(
    authed_client, db, test_auth, kind
):
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
    before_history = _snapshot(db, test_auth.org.id)

    response = await authed_client.put(f"/matches/{match['id']}/accept", json={})

    assert response.status_code == 400, response.text
    party_kind = "donor" if is_donor else "surrogate"
    assert response.json()["detail"] == f"Role not permitted to change {party_kind} stage"
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
