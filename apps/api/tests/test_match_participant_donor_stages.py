"""Donor stage changes across match accept, cancellation, and manual moves.

Split from test_match_participant_stages.py.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.db.models import (
    AuditLog,
    Donor,
    DonorStatusHistory,
    StatusChangeRequest,
)
from app.main import app
from app.services import (
    pipeline_service,
)
from tests.test_match_cancel_request import _create_intended_parent
from tests.test_match_cases import _accept, _case, _donor
from tests.test_match_lifecycle_characterization import (
    _client_for,
    _match_row,
    _other_org,
)
from tests.test_match_participant_stages import (
    _cancel,
    _stage,
)
from tests.test_match_permissions_v2_characterization import _activate_v2


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [1, 2])
async def test_donor_two_active_matches_keep_stage_until_last_cancellation(
    authed_client, db, test_auth, policy, subtests
):
    if policy == 2:
        _activate_v2(db, test_auth.org.id)
    for kind, handoff in [("egg", "ready_to_match"), ("sperm", "available")]:
        for first_status in ["accepted", "cancellation_pending"]:
            with subtests.test(
                kind=repr(kind), handoff=repr(handoff), first_status=repr(first_status)
            ):
                donor = await _donor(authed_client, donor_type=kind)
                first = await _accept(
                    authed_client,
                    await _case(
                        authed_client, await _create_intended_parent(authed_client), donor=donor
                    ),
                )
                if first_status == "cancellation_pending":
                    assert (
                        await authed_client.post(
                            f"/matches/{first['id']}/cancel-request", json={"reason": "Ended"}
                        )
                    ).status_code == 200
                second = await _case(
                    authed_client, await _create_intended_parent(authed_client), donor=donor
                )
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
async def test_donor_manual_matched_requires_active_match_and_protects_system_stages(
    authed_client, db, test_auth, subtests
):
    for kind, handoff in [("egg", "ready_to_match"), ("sperm", "available")]:
        with subtests.test(kind=repr(kind), handoff=repr(handoff)):
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
                await _case(
                    authed_client, await _create_intended_parent(authed_client), donor=donor
                ),
            )
            _stage(db, row, handoff)
            allowed = await authed_client.patch(
                f"/donors/{donor['id']}/status", json={"stage_id": stages["matched"]["id"]}
            )
            assert allowed.status_code == 200, allowed.text
            assert _match_row(db, match["id"]).status == "accepted"


@pytest.mark.asyncio
async def test_manual_donor_matched_guard_preserves_permission_and_org_scope(
    authed_client, db, test_auth, subtests
):
    for kind in ["egg", "sperm"]:
        for denied in ["permission", "cross_org"]:
            with subtests.test(kind=repr(kind), denied=repr(denied)):
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
async def test_cancellation_preserves_donor_stage_outside_matched(authed_client, db, subtests):
    for kind, stage in [
        ("egg", "cycle_in_progress"),
        ("egg", "retrieval_complete"),
        ("sperm", "collection_in_progress"),
        ("sperm", "donation_complete"),
    ]:
        with subtests.test(kind=repr(kind), stage=repr(stage)):
            donor = await _donor(authed_client, donor_type=kind)
            match = await _accept(
                authed_client,
                await _case(
                    authed_client, await _create_intended_parent(authed_client), donor=donor
                ),
            )
            row = db.get(Donor, uuid.UUID(donor["id"]))
            target = _stage(db, row, stage)
            before = db.query(DonorStatusHistory).filter_by(donor_id=row.id).count()

            await _cancel(authed_client, db, match)

            db.refresh(row)
            assert row.stage_id == target.id
            assert _match_row(db, match["id"]).status == "cancelled"
            assert db.query(DonorStatusHistory).filter_by(donor_id=row.id).count() == before
