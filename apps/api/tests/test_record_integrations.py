"""Record integrations preserve explicit context and deny unrelated organizations."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.csrf import CSRF_HEADER
from app.db.enums import LinkConfidence, TicketLinkStatus, TicketPriority, TicketStatus
from app.db.models import Appointment, EmailLog, Organization, RecordTicketLink, Ticket
from app.services import appointment_service


async def create_donor(client):
    response = await client.post(
        "/donors",
        json={
            "donor_type": "egg",
            "full_name": "Record QA Donor",
            "email": f"qa-{uuid4().hex}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def ticket(db, org_id, code, email):
    item = Ticket(
        organization_id=org_id,
        ticket_code=code,
        subject="Record conversation",
        requester_email=email,
        status=TicketStatus.OPEN,
        priority=TicketPriority.NORMAL,
        surrogate_link_status=TicketLinkStatus.UNLINKED,
        stitch_confidence=LinkConfidence.LOW,
    )
    db.add(item)
    db.flush()
    return item


@pytest.mark.asyncio
async def test_donor_appointment_create_retry_reschedule_cancel(
    authed_client, db, test_org, monkeypatch
):
    from app.services import appointment_email_service, appointment_integrations

    for name in ("send_cancelled", "send_rescheduled"):
        monkeypatch.setattr(appointment_email_service, name, lambda *args, **kwargs: None)
    for name in (
        "backfill_confirmed_appointments_to_google",
        "sync_manual_google_events_for_appointments",
    ):
        monkeypatch.setattr(appointment_integrations, name, lambda *args, **kwargs: None)
    start = (datetime.now(UTC) + timedelta(days=3)).replace(
        hour=14, minute=0, second=0, microsecond=0
    )
    monkeypatch.setattr(
        appointment_service,
        "get_available_slots",
        lambda *args, **kwargs: [
            appointment_service.TimeSlot(start, start + timedelta(minutes=30)),
            appointment_service.TimeSlot(
                start + timedelta(hours=2), start + timedelta(hours=2, minutes=30)
            ),
        ],
    )
    donor = await create_donor(authed_client)
    response = await authed_client.post(
        "/appointments/types",
        json={
            "name": "QA consultation",
            "duration_minutes": 30,
            "meeting_mode": "phone",
            "auto_approve": False,
        },
    )
    assert response.status_code == 201, response.text
    payload = {
        "appointment_type_id": response.json()["id"],
        "client_name": donor["full_name"],
        "client_email": donor["email"],
        "client_phone": "6075550100",
        "client_timezone": "UTC",
        "scheduled_start": start.isoformat(),
        "donor_id": donor["id"],
        "idempotency_key": str(uuid4()),
    }
    created = await authed_client.post("/appointments", json=payload)
    assert created.status_code == 201, created.text
    appt_id = created.json()["id"]
    assert created.json()["donor_id"] == donor["id"]
    retry = await authed_client.post("/appointments", json=payload)
    assert retry.status_code == 201 and retry.json()["id"] == appt_id
    another = await create_donor(authed_client)
    wrong_retry = await authed_client.post(
        "/appointments", json={**payload, "donor_id": another["id"]}
    )
    assert wrong_retry.status_code == 400
    listed = await authed_client.get("/appointments", params={"donor_id": donor["id"]})
    assert listed.status_code == 200 and [a["id"] for a in listed.json()["items"]] == [appt_id]
    assert (await authed_client.get("/appointments", params={"donor_id": another["id"]})).json()[
        "items"
    ] == []
    moved = await authed_client.post(
        f"/appointments/{appt_id}/reschedule",
        json={"scheduled_start": (start + timedelta(hours=2)).isoformat()},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["donor_id"] == donor["id"]
    cancelled = await authed_client.post(
        f"/appointments/{appt_id}/cancel", json={"reason": "QA change"}
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert db.query(Appointment).filter(Appointment.organization_id == test_org.id).count() == 1


@pytest.mark.asyncio
async def test_appointment_context_denies_unknown_records_and_attempt_without_case(authed_client):
    for field in ("donor_id", "intended_parent_id", "match_id"):
        response = await authed_client.get("/appointments", params={field: str(uuid4())})
        assert response.status_code == 404, response.text
    assert (
        await authed_client.get("/appointments", params={"attempt_id": str(uuid4())})
    ).status_code == 400


@pytest.mark.asyncio
async def test_correspondence_requires_durable_link_and_survives_email_change(
    authed_client, db, test_org
):
    donor = await create_donor(authed_client)
    linked = ticket(db, test_org.id, "T-LINKED", donor["email"])
    ticket(db, test_org.id, "T-SAME-EMAIL", donor["email"])
    path = f"/records/donor/{donor['id']}/correspondence"
    assert (await authed_client.get(path)).json()["total"] == 0
    response = await authed_client.put(f"{path}/{linked.id}")
    assert response.status_code == 204, response.text
    assert (await authed_client.put(f"{path}/{linked.id}")).status_code == 204
    assert (
        db.query(RecordTicketLink).filter(RecordTicketLink.organization_id == test_org.id).count()
        == 1
    )
    changed = await authed_client.patch(
        f"/donors/{donor['id']}", json={"email": f"changed-{uuid4().hex}@example.com"}
    )
    assert changed.status_code == 200, changed.text
    history = (await authed_client.get(path)).json()
    assert history["total"] == 1
    assert history["items"][0]["id"] == str(linked.id)
    assert (await authed_client.delete(f"{path}/{linked.id}")).status_code == 204
    assert (await authed_client.get(path)).json()["total"] == 0


@pytest.mark.asyncio
async def test_correspondence_includes_explicit_outbound_logs(authed_client, db, test_org):
    donor = await create_donor(authed_client)
    for source_id in (UUID(donor["id"]), uuid4()):
        db.add(
            EmailLog(
                organization_id=test_org.id,
                recipient_email=donor["email"],
                subject="History",
                body="Synthetic QA",
                source_type="donor",
                source_id=source_id,
                status="sent",
            )
        )
    db.flush()
    result = await authed_client.get(f"/records/donor/{donor['id']}/correspondence")
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 1
    assert result.json()["items"][0]["kind"] == "email"
    assert "body" not in result.json()["items"][0]


@pytest.mark.asyncio
async def test_correspondence_cross_org_and_csrf_denied(authed_client, db, test_org):
    donor = await create_donor(authed_client)
    other_org = Organization(id=uuid4(), name="Other", slug=f"other-{uuid4().hex}")
    db.add(other_org)
    db.flush()
    foreign = ticket(db, other_org.id, "T-FOREIGN", donor["email"])
    path = f"/records/donor/{donor['id']}/correspondence"
    assert (await authed_client.put(f"{path}/{foreign.id}")).status_code == 404
    local = ticket(db, test_org.id, "T-LOCAL", donor["email"])
    headers = dict(authed_client.headers)
    authed_client.headers.pop(CSRF_HEADER, None)
    try:
        assert (await authed_client.put(f"{path}/{local.id}")).status_code == 403
    finally:
        authed_client.headers.update(headers)
    assert (await authed_client.get(f"/records/donor/{uuid4()}/correspondence")).status_code == 404
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            RecordTicketLink(
                organization_id=test_org.id, donor_id=UUID(donor["id"]), ticket_id=foreign.id
            )
        )
        db.flush()


@pytest.mark.asyncio
async def test_appointment_case_attempt_scope_and_database_guards(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.db.models import Match, MatchAttempt
    from app.services import appointment_integrations

    for name in (
        "backfill_confirmed_appointments_to_google",
        "sync_manual_google_events_for_appointments",
    ):
        monkeypatch.setattr(appointment_integrations, name, lambda *args, **kwargs: None)
    donor = await create_donor(authed_client)
    ip_response = await authed_client.post(
        "/intended-parents",
        json={"full_name": "QA Parent", "email": f"ip-{uuid4().hex}@example.com"},
    )
    assert ip_response.status_code == 201, ip_response.text
    ip_id = UUID(ip_response.json()["id"])
    cases = []
    for index in (1, 2):
        case = Match(
            organization_id=test_org.id,
            donor_id=UUID(donor["id"]),
            intended_parent_id=ip_id,
            match_kind="donor",
            match_number=f"M{10000 + index}",
            status="cancelled",
        )
        db.add(case)
        db.flush()
        attempt = MatchAttempt(
            organization_id=test_org.id,
            match_id=case.id,
            sequence=1,
            attempt_type="retrieval",
            status="planned",
        )
        db.add(attempt)
        db.flush()
        cases.append((case, attempt))
    start = datetime.now(UTC) + timedelta(days=4)
    appointments = []
    for case, attempt in cases:
        item = Appointment(
            organization_id=test_org.id,
            user_id=test_user.id,
            donor_id=UUID(donor["id"]),
            intended_parent_id=ip_id,
            match_id=case.id,
            attempt_id=attempt.id,
            client_name="QA",
            client_email="qa@example.com",
            client_phone="6075550100",
            client_timezone="UTC",
            scheduled_start=start,
            scheduled_end=start + timedelta(minutes=30),
            duration_minutes=30,
            meeting_mode="phone",
            status="cancelled",
        )
        db.add(item)
        db.flush()
        appointments.append(item)
    result = await authed_client.get(
        "/appointments", params={"match_id": str(cases[0][0].id), "attempt_id": str(cases[0][1].id)}
    )
    assert result.status_code == 200, result.text
    assert [item["id"] for item in result.json()["items"]] == [str(appointments[0].id)]
    assert (
        await authed_client.get(
            "/appointments",
            params={"match_id": str(cases[0][0].id), "attempt_id": str(cases[1][1].id)},
        )
    ).status_code == 404
    with pytest.raises(IntegrityError), db.begin_nested():
        appointments[0].attempt_id = cases[1][1].id
        db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        appointments[0].match_id = None
        db.flush()
    foreign = Organization(id=uuid4(), name="Foreign", slug=f"foreign-{uuid4().hex}")
    db.add(foreign)
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        appointments[0].organization_id = foreign.id
        db.flush()


@pytest.mark.asyncio
async def test_record_integrations_honor_permission_and_ticket_beta_gate(
    authed_client, db, test_org, test_user
):
    from app.core.deps import get_current_session
    from app.db.enums import Role
    from app.db.models import Membership, UserPermissionOverride
    from app.main import app
    from app.schemas.auth import UserSession

    donor = await create_donor(authed_client)
    membership = (
        db.query(Membership)
        .filter(Membership.organization_id == test_org.id, Membership.user_id == test_user.id)
        .one()
    )
    membership.role = Role.ADMIN.value
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=test_user.id,
            permission="manage_appointments",
            override_type="revoke",
        )
    )
    db.flush()
    app.dependency_overrides[get_current_session] = lambda: UserSession(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.ADMIN,
        email=test_user.email,
        display_name=test_user.display_name,
    )
    try:
        assert (
            await authed_client.get("/appointments", params={"donor_id": donor["id"]})
        ).status_code == 403
        assert (
            await authed_client.get(f"/records/donor/{donor['id']}/correspondence")
        ).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_session, None)
