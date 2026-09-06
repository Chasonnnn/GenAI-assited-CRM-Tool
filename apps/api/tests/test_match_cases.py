"""Independent case lifecycle and tenant boundaries."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.enums import Role
from app.db.models import AuditLog, IntendedParent, Match, MatchAttempt, StatusChangeRequest
from app.services import match_service
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate


async def _donor(client):
    response = await client.post(
        "/donors",
        json={
            "donor_type": "egg",
            "full_name": "Case Donor",
            "email": f"donor-{uuid.uuid4().hex}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _case(client, ip, *, donor=None, surrogate=None):
    data = {"intended_parent_id": ip["id"]}
    data["donor_id" if donor else "surrogate_id"] = (donor or surrogate)["id"]
    response = await client.post("/matches/", json=data)
    assert response.status_code == 201, response.text
    return response.json()


async def _accept(client, case):
    response = await client.put(f"/matches/{case['id']}/accept", json={})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_donor_concurrent_cases_repeat_and_attempt_history(authed_client, db):
    donor = await _donor(authed_client)
    first_ip = await _create_intended_parent(authed_client)
    second_ip = await _create_intended_parent(authed_client)
    first = await _accept(authed_client, await _case(authed_client, first_ip, donor=donor))
    second = await _accept(authed_client, await _case(authed_client, second_ip, donor=donor))
    assert first["match_kind"] == "donor" and first["surrogate_id"] is None
    assert second["status"] == "accepted"
    duplicate = await authed_client.post(
        "/matches/", json={"donor_id": donor["id"], "intended_parent_id": first_ip["id"]}
    )
    assert duplicate.status_code == 409
    a = await authed_client.post(
        f"/matches/{first['id']}/attempts",
        json={"attempt_type": "retrieval", "started_at": "2026-09-01"},
    )
    assert a.status_code == 201, a.text
    assert a.json()["sequence"] == 1
    blocked = await authed_client.put(
        f"/matches/{first['id']}/complete", json={"outcome": "Relationship completed"}
    )
    assert blocked.status_code == 400
    update = await authed_client.patch(
        f"/matches/{first['id']}/attempts/{a.json()['id']}",
        json={"status": "completed", "ended_at": "2026-09-03", "outcome": "Completed"},
    )
    assert update.status_code == 200, update.text
    finished = await authed_client.put(
        f"/matches/{first['id']}/complete", json={"outcome": "Relationship completed"}
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["closed_at"]
    later = await _case(authed_client, first_ip, donor=donor)
    assert later["id"] != first["id"]
    assert (await authed_client.get(f"/matches/{later['id']}/attempts")).json() == []
    assert (await authed_client.get(f"/matches/{first['id']}/attempts")).json()[0][
        "outcome"
    ] == "Completed"
    read_only = await authed_client.patch(
        f"/matches/{first['id']}/attempts/{a.json()['id']}", json={"status": "planned"}
    )
    assert read_only.status_code == 400
    listed = await authed_client.get(
        "/matches/", params={"match_kind": "donor", "donor_id": donor["id"], "q": "Case Donor"}
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 3
    assert {m["donor_name"] for m in listed.json()["items"]} == {"Case Donor"}
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.target_id == uuid.UUID(first["id"]), AuditLog.event_type == "match_completed"
        )
        .one()
    )
    assert audit.target_type == "match"


@pytest.mark.asyncio
async def test_cancel_one_case_preserves_overlapping_ip_stage(authed_client, db):
    ip = await _create_intended_parent(authed_client)
    s1 = await _create_surrogate(authed_client)
    s2 = await _create_surrogate(authed_client)
    first = await _accept(authed_client, await _case(authed_client, ip, surrogate=s1))
    second = await _accept(authed_client, await _case(authed_client, ip, surrogate=s2))
    request = await authed_client.post(
        f"/matches/{first['id']}/cancel-request", json={"reason": "Case ended"}
    )
    assert request.status_code == 200, request.text
    pending = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_id == uuid.UUID(first["id"]),
            StatusChangeRequest.status == "pending",
        )
        .one()
    )
    approved = await authed_client.post(f"/status-change-requests/{pending.id}/approve")
    assert approved.status_code == 200, approved.text
    assert db.get(IntendedParent, uuid.UUID(ip["id"])).status == "matched"
    assert db.get(Match, uuid.UUID(second["id"])).status == "accepted"
    assert db.get(Match, uuid.UUID(first["id"])).closed_at is not None


@pytest.mark.asyncio
async def test_pending_cancellation_reserves_surrogate_in_database(authed_client, db, test_auth):
    s = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    case = await _accept(authed_client, await _case(authed_client, ip, surrogate=s))
    result = await authed_client.post(f"/matches/{case['id']}/cancel-request", json={})
    assert result.status_code == 200
    ip2 = await _create_intended_parent(authed_client)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            Match(
                organization_id=test_auth.org.id,
                match_number="M99998",
                surrogate_id=uuid.UUID(s["id"]),
                intended_parent_id=uuid.UUID(ip2["id"]),
                status="accepted",
                proposed_by_user_id=test_auth.user.id,
            )
        )
        db.flush()
    assert match_service.get_accepted_match_for_surrogate(
        db, test_auth.org.id, uuid.UUID(s["id"])
    ).id == uuid.UUID(case["id"])


@pytest.mark.asyncio
async def test_case_exact_participants_and_attempt_parent_constraints(authed_client, db, test_auth):
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    surrogate = await _create_surrogate(authed_client)
    for data in (
        {"intended_parent_id": ip["id"]},
        {"intended_parent_id": ip["id"], "surrogate_id": surrogate["id"], "donor_id": donor["id"]},
    ):
        assert (await authed_client.post("/matches/", json=data)).status_code == 422
    case = await _accept(authed_client, await _case(authed_client, ip, donor=donor))
    other_org = uuid.uuid4()
    db.execute(
        text("INSERT INTO organizations (id,name,slug) VALUES (:id,'Other case org',:slug)"),
        {"id": other_org, "slug": f"other-{other_org}"},
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            MatchAttempt(
                organization_id=other_org,
                match_id=uuid.UUID(case["id"]),
                sequence=1,
                attempt_type="retrieval",
                status="planned",
            )
        )
        db.flush()
    result = await authed_client.post(
        f"/matches/{case['id']}/attempts", json={"attempt_type": "embryo_transfer"}
    )
    assert result.status_code == 400
    result = await authed_client.post(
        f"/matches/{case['id']}/attempts",
        json={"attempt_type": "retrieval", "started_at": "2026-09-03", "ended_at": "2026-09-01"},
    )
    assert result.status_code == 400


@pytest.mark.asyncio
async def test_attempt_route_org_and_permission_denials(authed_client, db, test_auth):
    from fastapi import HTTPException

    from app.schemas.auth import UserSession

    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    case = await _accept(authed_client, await _case(authed_client, ip, donor=donor))
    session = UserSession(
        user_id=test_auth.user.id,
        org_id=uuid.uuid4(),
        role=Role.ADMIN,
        email=test_auth.user.email,
        display_name=test_auth.user.display_name,
    )
    with pytest.raises(HTTPException) as denied:
        match_service.get_match_with_access(db, session, uuid.UUID(case["id"]))
    assert denied.value.status_code == 404
    missing = await authed_client.get(f"/matches/{uuid.uuid4()}/attempts")
    assert missing.status_code == 404
    session.org_id = test_auth.org.id
    session.role = Role.INTAKE_SPECIALIST
    with pytest.raises(HTTPException) as denied:
        match_service.get_match_with_access(db, session, uuid.UUID(case["id"]), write=True)
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_acceptance_audit_failure_does_not_commit_stage(authed_client, db, monkeypatch):
    from app.db.models import Surrogate
    from app.services import audit_service

    surrogate = await _create_surrogate(authed_client)
    ip = await _create_intended_parent(authed_client)
    case = await _case(authed_client, ip, surrogate=surrogate)
    match = db.get(Match, uuid.UUID(case["id"]))
    subject = db.get(Surrogate, uuid.UUID(surrogate["id"]))
    old_stage = subject.stage_id
    commits = []
    monkeypatch.setattr(db, "commit", lambda: commits.append("commit"))

    def fail_audit(**kwargs):
        raise RuntimeError("audit storage failed")

    monkeypatch.setattr(audit_service, "log_event", fail_audit)
    with pytest.raises(RuntimeError, match="audit storage failed"), db.begin_nested():
        match_service.accept_match(
            db,
            match,
            actor_user_id=match.proposed_by_user_id,
            actor_role=Role.DEVELOPER,
            org_id=match.organization_id,
        )
    assert commits == []
    db.refresh(subject)
    db.refresh(match)
    assert subject.stage_id == old_stage
    assert match.status == "proposed"


def test_concurrent_acceptances_reserve_one_surrogate(db_engine, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.orm import Session

    from app.db.models import Organization, User
    from app.services import audit_service, pipeline_service
    from tests.test_match_events import _create_case
    from tests.test_match_events import _create_intended_parent as create_ip

    # This connection-concurrency test uses committed fixtures. Atomic audit
    # persistence is covered separately; avoid immutable audit cleanup here.
    monkeypatch.setattr(audit_service, "log_event", lambda **kwargs: None)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    # A separate committed synthetic organization is required for two connections.
    with Session(db_engine) as setup:
        setup.add(
            Organization(id=org_id, name="Concurrent matching QA", slug=f"concurrent-{org_id}")
        )
        setup.add(
            User(
                id=user_id,
                email=f"concurrent-{user_id}@example.com",
                display_name="Concurrent QA",
                is_active=True,
                token_version=1,
            )
        )
        setup.commit()
        pipeline = pipeline_service.get_or_create_default_pipeline(setup, org_id)
        stage = pipeline_service.get_stage_by_system_role(setup, pipeline.id, "matched")
        surrogate = _create_case(setup, org_id, user_id, stage)
        ids = []
        for number in ("M10001", "M10002"):
            ip = create_ip(setup, org_id)
            case = Match(
                organization_id=org_id,
                surrogate_id=surrogate.id,
                intended_parent_id=ip.id,
                match_number=number,
                proposed_by_user_id=user_id,
            )
            setup.add(case)
            setup.flush()
            ids.append(case.id)
        setup.commit()

    barrier = Barrier(2)

    def accept(case_id):
        with Session(db_engine) as session:
            case = match_service.get_match(session, case_id, org_id)
            barrier.wait(timeout=10)
            try:
                match_service.accept_match(
                    session, case, actor_user_id=user_id, actor_role=Role.DEVELOPER, org_id=org_id
                )
                return "accepted"
            except ValueError:
                session.rollback()
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, ids))
        assert sorted(results) == ["accepted", "conflict"]
        with Session(db_engine) as verify:
            assert (
                verify.query(Match)
                .filter(Match.organization_id == org_id, Match.status == "accepted")
                .count()
                == 1
            )
    finally:
        with db_engine.begin() as cleanup:
            cleanup.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
            cleanup.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


@pytest.mark.asyncio
async def test_donor_cancellation_approval_and_attempt_closure(authed_client, db):
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    case = await _accept(authed_client, await _case(authed_client, ip, donor=donor))
    attempt = await authed_client.post(
        f"/matches/{case['id']}/attempts", json={"attempt_type": "retrieval"}
    )
    assert attempt.status_code == 201
    requested = await authed_client.post(
        f"/matches/{case['id']}/cancel-request", json={"reason": "Case ended"}
    )
    assert requested.status_code == 200, requested.text
    pending = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_id == uuid.UUID(case["id"]),
            StatusChangeRequest.status == "pending",
        )
        .one()
    )
    approved = await authed_client.post(f"/status-change-requests/{pending.id}/approve")
    assert approved.status_code == 200, approved.text
    assert db.get(Match, uuid.UUID(case["id"])).status == "cancelled"
    assert db.get(MatchAttempt, uuid.UUID(attempt.json()["id"])).status == "cancelled"
    repeat = await _case(authed_client, ip, donor=donor)
    assert repeat["id"] != case["id"]


@pytest.mark.asyncio
async def test_donor_case_permission_filters_lists_stats_approvals_and_notifications(
    authed_client, db, monkeypatch
):
    from app.services import permission_service

    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    case = await _accept(authed_client, await _case(authed_client, ip, donor=donor))
    requested = await authed_client.post(f"/matches/{case['id']}/cancel-request", json={})
    assert requested.status_code == 200, requested.text
    pending = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.entity_id == uuid.UUID(case["id"]),
            StatusChangeRequest.status == "pending",
        )
        .one()
    )
    original = permission_service.check_permission

    def check(db, org, user, role, permission):
        return False if permission == "view_donors" else original(db, org, user, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", check)
    assert (await authed_client.get(f"/matches/{case['id']}")).status_code == 403
    assert (await authed_client.get("/matches/")).json()["total"] == 0
    assert (await authed_client.get("/matches/stats")).json()["total"] == 0
    assert (await authed_client.get(f"/status-change-requests/{pending.id}")).status_code == 403
    assert (await authed_client.get("/status-change-requests")).json()["total"] == 0
    notifications = (await authed_client.get("/me/notifications")).json()
    assert not any(item.get("entity_id") == case["id"] for item in notifications["items"])
