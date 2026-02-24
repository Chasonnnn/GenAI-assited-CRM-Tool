from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.db.enums import AppointmentStatus, MeetingMode
from app.db.models import Appointment, Organization, Surrogate, SurrogateActivityLog


async def _create_surrogate(authed_client, name: str, email: str) -> dict:
    res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": name,
            "email": email,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _create_linked_appointment(
    db,
    *,
    org_id: UUID,
    user_id: UUID,
    surrogate_id: UUID,
    client_name: str = "Interview Candidate",
    client_email: str = "candidate@example.com",
) -> Appointment:
    start = datetime.now(timezone.utc) + timedelta(days=2)
    appointment = Appointment(
        id=uuid4(),
        organization_id=org_id,
        user_id=user_id,
        appointment_type_id=None,
        surrogate_id=surrogate_id,
        client_name=client_name,
        client_email=client_email,
        client_phone="+15555550123",
        client_timezone="America/Los_Angeles",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        meeting_mode=MeetingMode.PHONE.value,
        status=AppointmentStatus.CONFIRMED.value,
    )
    db.add(appointment)
    db.flush()
    return appointment


@pytest.mark.asyncio
async def test_log_interview_outcome_with_appointment_context(authed_client, db, test_auth):
    surrogate_payload = await _create_surrogate(
        authed_client,
        name="Outcome Linked",
        email="outcome-linked@example.com",
    )
    surrogate_id = UUID(surrogate_payload["id"])

    surrogate_before = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate_before is not None
    stage_before = surrogate_before.stage_id

    appointment = _create_linked_appointment(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        surrogate_id=surrogate_id,
    )
    db.commit()

    response = await authed_client.post(
        f"/surrogates/{surrogate_id}/interview-outcomes",
        json={
            "outcome": "completed",
            "notes": "Interview completed successfully.",
            "appointment_id": str(appointment.id),
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["activity_type"] == "interview_outcome_logged"

    activity = (
        db.query(SurrogateActivityLog)
        .filter(
            SurrogateActivityLog.surrogate_id == surrogate_id,
            SurrogateActivityLog.activity_type == "interview_outcome_logged",
        )
        .order_by(SurrogateActivityLog.created_at.desc())
        .first()
    )
    assert activity is not None
    details = activity.details or {}
    assert details.get("outcome") == "completed"
    assert details.get("appointment_id") == str(appointment.id)
    assert details.get("logged_from") == "appointment_detail"
    assert details.get("scheduled_start") == appointment.scheduled_start.isoformat()
    assert details.get("scheduled_end") == appointment.scheduled_end.isoformat()

    db.refresh(appointment)
    assert appointment.status == AppointmentStatus.CONFIRMED.value

    surrogate_after = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate_after is not None
    assert surrogate_after.stage_id == stage_before


@pytest.mark.asyncio
async def test_log_interview_outcome_supports_backdated_occurred_at(authed_client, db):
    surrogate_payload = await _create_surrogate(
        authed_client,
        name="Outcome Backdated",
        email="outcome-backdated@example.com",
    )
    surrogate_id = surrogate_payload["id"]

    occurred_at = datetime.now(timezone.utc) - timedelta(days=1, hours=2)
    response = await authed_client.post(
        f"/surrogates/{surrogate_id}/interview-outcomes",
        json={
            "outcome": "no_show",
            "notes": "Did not join the call.",
            "occurred_at": occurred_at.isoformat(),
        },
    )
    assert response.status_code == 201, response.text

    payload = response.json()
    assert payload["activity_type"] == "interview_outcome_logged"

    activity = (
        db.query(SurrogateActivityLog)
        .filter(
            SurrogateActivityLog.surrogate_id == UUID(surrogate_id),
            SurrogateActivityLog.activity_type == "interview_outcome_logged",
        )
        .order_by(SurrogateActivityLog.created_at.desc())
        .first()
    )
    assert activity is not None
    details = activity.details or {}
    assert details.get("outcome") == "no_show"
    assert details.get("occurred_at") == occurred_at.isoformat()
    assert details.get("logged_from") == "surrogate_detail"


@pytest.mark.asyncio
async def test_log_interview_outcome_rejects_future_occurred_at(authed_client):
    surrogate_payload = await _create_surrogate(
        authed_client,
        name="Outcome Future",
        email="outcome-future@example.com",
    )
    surrogate_id = surrogate_payload["id"]

    future_at = datetime.now(timezone.utc) + timedelta(hours=4)
    response = await authed_client.post(
        f"/surrogates/{surrogate_id}/interview-outcomes",
        json={
            "outcome": "rescheduled",
            "occurred_at": future_at.isoformat(),
        },
    )
    assert response.status_code == 400
    assert "future" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_log_interview_outcome_rejects_cross_org_appointment(authed_client, db, test_auth):
    surrogate_payload = await _create_surrogate(
        authed_client,
        name="Outcome Cross Org",
        email="outcome-cross-org@example.com",
    )
    surrogate_id = UUID(surrogate_payload["id"])

    other_org = Organization(
        id=uuid4(),
        name="Other Org",
        slug=f"other-org-{uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()

    cross_org_appt = Appointment(
        id=uuid4(),
        organization_id=other_org.id,
        user_id=test_auth.user.id,
        appointment_type_id=None,
        surrogate_id=surrogate_id,
        client_name="Cross Org",
        client_email="cross-org@example.com",
        client_phone="+15555550124",
        client_timezone="America/Los_Angeles",
        scheduled_start=datetime.now(timezone.utc) + timedelta(days=1),
        scheduled_end=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        meeting_mode=MeetingMode.PHONE.value,
        status=AppointmentStatus.CONFIRMED.value,
    )
    db.add(cross_org_appt)
    db.commit()

    response = await authed_client.post(
        f"/surrogates/{surrogate_id}/interview-outcomes",
        json={
            "outcome": "cancelled",
            "appointment_id": str(cross_org_appt.id),
        },
    )
    assert response.status_code == 400
    assert "appointment not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_log_interview_outcome_rejects_appointment_for_other_surrogate(authed_client, db, test_auth):
    surrogate_a = await _create_surrogate(
        authed_client,
        name="Outcome A",
        email="outcome-a@example.com",
    )
    surrogate_b = await _create_surrogate(
        authed_client,
        name="Outcome B",
        email="outcome-b@example.com",
    )

    appointment = _create_linked_appointment(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        surrogate_id=UUID(surrogate_b["id"]),
        client_email="other-surrogate@example.com",
    )
    db.commit()

    response = await authed_client.post(
        f"/surrogates/{surrogate_a['id']}/interview-outcomes",
        json={
            "outcome": "completed",
            "appointment_id": str(appointment.id),
        },
    )
    assert response.status_code == 400
    assert "not linked to this surrogate" in response.json()["detail"].lower()
