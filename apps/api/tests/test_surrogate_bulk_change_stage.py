from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import AuditEventType, Role, SurrogateActivityType
from app.db.models import (
    Appointment,
    AppointmentType,
    AuditLog,
    AvailabilityRule,
    EntityNote,
    Match,
    Membership,
    Organization,
    Surrogate,
    SurrogateActivityLog,
    SurrogateStatusHistory,
    Task,
    User,
)
from app.main import app
from app.services import pipeline_service, session_service
from app.services.surrogate_status_service import _add_calendar_months
from tests.test_match_cancel_request import _create_intended_parent

BULK_PATH = "/surrogates/bulk-change-stage"


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


def _row(db, surrogate_id: str) -> Surrogate:
    db.expire_all()
    row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate_id)).one()
    return row


def _org_today(org) -> date:
    return datetime.now(ZoneInfo(org.timezone or "America/Los_Angeles")).date()


def _history(db, surrogate_id: str) -> list[SurrogateStatusHistory]:
    return (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == UUID(surrogate_id))
        .order_by(SurrogateStatusHistory.recorded_at)
        .all()
    )


def _notes(db, surrogate_id: str) -> list[EntityNote]:
    return db.query(EntityNote).filter(EntityNote.entity_id == UUID(surrogate_id)).all()


def _future_minute(*, days: int, hours: int = 0) -> datetime:
    value = datetime.now(UTC) + timedelta(days=days, hours=hours)
    return value.replace(second=0, microsecond=0)


async def _create_surrogate(client: AsyncClient, **overrides):
    payload = {
        "full_name": "Bulk Change Stage Test",
        "email": f"bulk-change-stage-{uuid.uuid4().hex[:8]}@example.com",
        **overrides,
    }
    response = await client.post("/surrogates", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _move(client: AsyncClient, surrogate_id: str, stage, **extra) -> None:
    response = await client.patch(
        f"/surrogates/{surrogate_id}/status",
        json={"stage_id": str(stage.id), **extra},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"


async def _bulk(client: AsyncClient, surrogate_ids: list[str], stage, **extra):
    return await client.post(
        BULK_PATH,
        json={"surrogate_ids": surrogate_ids, "stage_id": str(stage.id), **extra},
    )


async def _client_with_role(db, test_org, role: Role) -> AsyncClient:
    user = User(
        id=uuid.uuid4(),
        email=f"bulk-change-stage-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Bulk Change Stage User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=test_org.id,
        role=role.value,
    )
    db.add(membership)
    db.commit()

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=test_org.id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    csrf_token = generate_csrf_token()
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.CASE_MANAGER, Role.INTAKE_SPECIALIST])
async def test_bulk_change_stage_requires_admin_or_developer_role(db, test_org, role: Role):
    client = await _client_with_role(db, test_org, role)
    async with client:
        surrogate = await _create_surrogate(client)
        contacted_stage = _get_stage(db, test_org.id, "contacted")

        response = await _bulk(client, [surrogate["id"]], contacted_stage)

        assert response.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.ADMIN, Role.DEVELOPER])
async def test_bulk_change_stage_allows_admin_and_developer(db, test_org, role: Role):
    client = await _client_with_role(db, test_org, role)
    async with client:
        surrogate = await _create_surrogate(client)
        contacted_stage = _get_stage(db, test_org.id, "contacted")

        response = await _bulk(client, [surrogate["id"]], contacted_stage)

        assert response.status_code == 200, response.text
        assert response.json() == {
            "requested": 1,
            "applied": 1,
            "pending_approval": 0,
            "failed": [],
        }

        row = _row(db, surrogate["id"])
        assert row.stage_id == contacted_stage.id
        assert row.status_label == contacted_stage.label

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bulk_change_stage_requires_csrf_header(db, test_org):
    client = await _client_with_role(db, test_org, Role.ADMIN)
    async with client:
        surrogate = await _create_surrogate(client)
        original_stage_id = _row(db, surrogate["id"]).stage_id
        contacted_stage = _get_stage(db, test_org.id, "contacted")
        client.headers.pop(CSRF_HEADER)

        response = await _bulk(client, [surrogate["id"]], contacted_stage)

        assert response.status_code == 403
        assert _row(db, surrogate["id"]).stage_id == original_stage_id

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bulk_change_stage_applies_valid_rows_and_collects_failures(
    authed_client, db, test_auth
):
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    on_hold_stage = _get_stage(db, test_auth.org.id, "on_hold")

    successful = await _create_surrogate(authed_client, full_name="Bulk Success")
    same_stage = await _create_surrogate(authed_client, full_name="Already Contacted")
    archived = await _create_surrogate(authed_client, full_name="Archived Lead")
    on_hold = await _create_surrogate(authed_client, full_name="Paused Lead")

    await _move(authed_client, same_stage["id"], contacted_stage)
    archive_response = await authed_client.post(f"/surrogates/{archived['id']}/archive")
    assert archive_response.status_code == 200, archive_response.text
    await _move(authed_client, on_hold["id"], contacted_stage)
    await _move(
        authed_client,
        on_hold["id"],
        on_hold_stage,
        reason="Waiting on surrogate response",
        on_hold_follow_up_months=1,
    )
    follow_up_task_id = _row(db, on_hold["id"]).on_hold_follow_up_task_id
    assert follow_up_task_id is not None

    missing_id = str(uuid.uuid4())
    response = await _bulk(
        authed_client,
        [successful["id"], same_stage["id"], archived["id"], on_hold["id"], missing_id],
        contacted_stage,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["requested"] == 5
    assert payload["applied"] == 2
    assert payload["pending_approval"] == 0
    assert {entry["surrogate_id"]: entry["reason"] for entry in payload["failed"]} == {
        same_stage["id"]: "Target stage is same as current stage",
        archived["id"]: "Cannot change status of archived surrogate",
        missing_id: "Surrogate not found",
    }

    successful_row = _row(db, successful["id"])
    assert successful_row.stage_id == contacted_stage.id
    assert successful_row.status_label == contacted_stage.label
    assert [entry.to_stage_id for entry in _history(db, successful["id"])] == [contacted_stage.id]
    assert _row(db, archived["id"]).is_archived is True

    resumed_row = _row(db, on_hold["id"])
    assert resumed_row.stage_id == contacted_stage.id
    assert resumed_row.paused_from_stage_id is None
    assert resumed_row.on_hold_follow_up_task_id is None
    assert db.get(Task, follow_up_task_id) is None


@pytest.mark.asyncio
async def test_bulk_change_stage_moves_on_hold_row_forward(authed_client, db, test_auth):
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    on_hold_stage = _get_stage(db, test_auth.org.id, "on_hold")
    disqualified_stage = _get_stage(db, test_auth.org.id, "disqualified")
    surrogate = await _create_surrogate(authed_client)
    await _move(authed_client, surrogate["id"], contacted_stage)
    await _move(authed_client, surrogate["id"], on_hold_stage, reason="Paused")

    response = await _bulk(
        authed_client, [surrogate["id"]], disqualified_stage, reason="Not eligible"
    )

    assert response.status_code == 200, response.text
    assert response.json()["applied"] == 1
    row = _row(db, surrogate["id"])
    assert row.stage_id == disqualified_stage.id
    assert row.paused_from_stage_id is None


@pytest.mark.asyncio
async def test_bulk_change_stage_rejects_other_org_rows_without_leaking(
    authed_client, db, test_auth
):
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    local = await _create_surrogate(authed_client, full_name="Local Row")
    foreign = await _create_surrogate(authed_client, full_name="Foreign Secret Name")
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Bulk Org",
        slug=f"other-bulk-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    other_org_id = other_org.id
    foreign_row = _row(db, foreign["id"])
    foreign_stage_id = foreign_row.stage_id
    foreign_row.organization_id = other_org_id
    db.commit()

    response = await _bulk(authed_client, [local["id"], foreign["id"]], contacted_stage)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "requested": 2,
        "applied": 1,
        "pending_approval": 0,
        "failed": [{"surrogate_id": foreign["id"], "reason": "Surrogate not found"}],
    }
    assert "Foreign Secret Name" not in response.text
    foreign_row = _row(db, foreign["id"])
    assert foreign_row.organization_id == other_org_id
    assert foreign_row.stage_id == foreign_stage_id
    assert _history(db, foreign["id"]) == []


@pytest.mark.asyncio
async def test_bulk_change_stage_rejects_invalid_or_foreign_target_stage(
    authed_client, db, test_auth
):
    surrogate = await _create_surrogate(authed_client)

    response = await authed_client.post(
        BULK_PATH,
        json={"surrogate_ids": [surrogate["id"]], "stage_id": str(uuid.uuid4())},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or inactive stage"


@pytest.mark.asyncio
async def test_bulk_backward_move_without_reason_fails_per_row(authed_client, db, test_auth):
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    approved_stage = _get_stage(db, test_auth.org.id, "approved")
    regression_row = await _create_surrogate(authed_client, full_name="Regression Row")
    success_row = await _create_surrogate(authed_client, full_name="Success Row")
    await _move(authed_client, regression_row["id"], approved_stage)

    response = await _bulk(
        authed_client, [regression_row["id"], success_row["id"]], contacted_stage
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["applied"] == 1
    assert payload["failed"] == [
        {
            "surrogate_id": regression_row["id"],
            "reason": "Reason required for backdated or regressed stage changes",
        }
    ]
    assert _row(db, regression_row["id"]).stage_id == approved_stage.id
    assert _row(db, success_row["id"]).stage_id == contacted_stage.id


@pytest.mark.asyncio
async def test_bulk_backward_move_with_reason_is_self_approved(authed_client, db, test_auth):
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    approved_stage = _get_stage(db, test_auth.org.id, "approved")
    regression_row = await _create_surrogate(authed_client)
    await _move(authed_client, regression_row["id"], approved_stage)
    reason = "Documents expired"

    response = await _bulk(
        authed_client, [regression_row["id"]], contacted_stage, reason=f"  {reason}  "
    )

    assert response.status_code == 200, response.text
    assert response.json()["applied"] == 1
    assert _row(db, regression_row["id"]).stage_id == contacted_stage.id
    latest = _history(db, regression_row["id"])[-1]
    assert latest.to_stage_id == contacted_stage.id
    assert latest.reason == reason
    assert latest.approved_by_user_id == test_auth.user.id
    assert latest.approved_at is not None
    assert any(reason in note.content for note in _notes(db, regression_row["id"]))


@pytest.mark.asyncio
@pytest.mark.parametrize("target_slug", ["cold_leads", "lost", "disqualified"])
async def test_bulk_reason_required_stages(authed_client, db, test_auth, target_slug: str):
    target_stage = _get_stage(db, test_auth.org.id, target_slug)
    first = await _create_surrogate(authed_client)
    second = await _create_surrogate(authed_client)

    missing = await _bulk(authed_client, [first["id"], second["id"]], target_stage)
    assert missing.status_code == 400
    assert missing.json()["detail"] == f"Reason required when moving to {target_stage.label}"
    assert _history(db, first["id"]) == []

    reason = "Failed <screening> & declined"
    response = await _bulk(authed_client, [first["id"], second["id"]], target_stage, reason=reason)

    assert response.status_code == 200, response.text
    assert response.json()["applied"] == 2
    for surrogate in (first, second):
        assert _row(db, surrogate["id"]).stage_id == target_stage.id
        [history] = _history(db, surrogate["id"])
        assert history.reason == reason
        [note] = _notes(db, surrogate["id"])
        assert f"Stage changed to {target_stage.label}" in note.content
        assert "Failed &lt;screening&gt; &amp; declined" in note.content

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_auth.org.id,
            AuditLog.event_type == AuditEventType.SURROGATE_BULK_STATUS_CHANGED.value,
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.details["reason_provided"] is True
    assert reason not in str(audit.details)


@pytest.mark.asyncio
async def test_bulk_on_hold_with_follow_up(authed_client, db, test_auth):
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    on_hold_stage = _get_stage(db, test_auth.org.id, "on_hold")
    new_row = await _create_surrogate(authed_client)
    contacted_row = await _create_surrogate(authed_client)
    await _move(authed_client, contacted_row["id"], contacted_stage)
    new_stage_id = _row(db, new_row["id"]).stage_id

    missing = await _bulk(authed_client, [new_row["id"]], on_hold_stage, on_hold_follow_up_months=3)
    assert missing.status_code == 400

    response = await _bulk(
        authed_client,
        [new_row["id"], contacted_row["id"]],
        on_hold_stage,
        reason="Travelling",
        on_hold_follow_up_months=3,
    )

    assert response.status_code == 200, response.text
    assert response.json()["applied"] == 2
    expected_due = _add_calendar_months(_org_today(test_auth.org), 3)
    for surrogate, paused_from in (
        (new_row, new_stage_id),
        (contacted_row, contacted_stage.id),
    ):
        row = _row(db, surrogate["id"])
        assert row.stage_id == on_hold_stage.id
        assert row.paused_from_stage_id == paused_from
        task = db.get(Task, row.on_hold_follow_up_task_id)
        assert task is not None
        assert task.title == "On-Hold follow-up"
        assert task.due_date == expected_due
        assert _history(db, surrogate["id"])[-1].reason == "Travelling"


@pytest.mark.asyncio
async def test_bulk_follow_up_requires_on_hold_target(authed_client, db, test_auth):
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    surrogate = await _create_surrogate(authed_client)

    response = await _bulk(
        authed_client, [surrogate["id"]], contacted_stage, on_hold_follow_up_months=1
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Follow-up timing is only allowed when moving to On-Hold"


@pytest.mark.asyncio
async def test_bulk_delivered_sets_actual_delivery_date(authed_client, db, test_auth):
    delivered_stage = _get_stage(db, test_auth.org.id, "delivered")
    missing_date = await _create_surrogate(authed_client)
    existing_date = await _create_surrogate(authed_client)
    existing_row = _row(db, existing_date["id"])
    existing_row.actual_delivery_date = date(2026, 1, 15)
    db.commit()

    response = await _bulk(
        authed_client, [missing_date["id"], existing_date["id"]], delivered_stage
    )

    assert response.status_code == 200, response.text
    assert response.json()["applied"] == 2
    assert _row(db, missing_date["id"]).actual_delivery_date == _org_today(test_auth.org)
    assert _row(db, existing_date["id"]).actual_delivery_date == date(2026, 1, 15)


@pytest.mark.asyncio
async def test_bulk_matched_requires_accepted_match_per_row(authed_client, db, test_auth):
    matched_stage = _get_stage(db, test_auth.org.id, "matched")
    with_match = await _create_surrogate(authed_client, full_name="Has Match")
    without_match = await _create_surrogate(authed_client, full_name="No Match")
    intended_parent = await _create_intended_parent(authed_client, ready=False)
    db.add(
        Match(
            organization_id=test_auth.org.id,
            surrogate_id=UUID(with_match["id"]),
            intended_parent_id=UUID(intended_parent["id"]),
            match_kind="surrogate",
            match_number=f"M{uuid.uuid4().hex[:6]}",
            status="accepted",
            proposed_by_user_id=test_auth.user.id,
        )
    )
    db.commit()

    response = await _bulk(authed_client, [with_match["id"], without_match["id"]], matched_stage)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["applied"] == 1
    assert payload["failed"] == [
        {
            "surrogate_id": without_match["id"],
            "reason": "Cannot set to Matched without an accepted Match.",
        }
    ]
    assert _row(db, with_match["id"]).stage_id == matched_stage.id
    assert _row(db, without_match["id"]).stage_id != matched_stage.id
    assert _history(db, without_match["id"]) == []


@pytest.mark.asyncio
async def test_single_matched_change_still_requires_accepted_match(authed_client, db, test_auth):
    matched_stage = _get_stage(db, test_auth.org.id, "matched")
    surrogate = await _create_surrogate(authed_client)

    response = await authed_client.patch(
        f"/surrogates/{surrogate['id']}/status",
        json={"stage_id": str(matched_stage.id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot set to Matched without an accepted Match."


@pytest.mark.asyncio
async def test_bulk_interview_scheduled_uses_per_row_times(authed_client, db, test_auth):
    interview_stage = _get_stage(db, test_auth.org.id, "interview_scheduled")
    first = await _create_surrogate(authed_client, full_name="Interview One")
    second = await _create_surrogate(authed_client, full_name="Interview Two")
    no_time = await _create_surrogate(authed_client, full_name="Interview Missing")
    past_time = await _create_surrogate(authed_client, full_name="Interview Past")
    first_start = _future_minute(days=2)
    second_start = _future_minute(days=3, hours=2)

    response = await _bulk(
        authed_client,
        [first["id"], second["id"], no_time["id"], past_time["id"]],
        interview_stage,
        interview_times=[
            {"surrogate_id": first["id"], "scheduled_at": first_start.isoformat()},
            {"surrogate_id": second["id"], "scheduled_at": second_start.isoformat()},
            {
                "surrogate_id": past_time["id"],
                "scheduled_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            },
        ],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["applied"] == 2
    assert {entry["surrogate_id"]: entry["reason"] for entry in payload["failed"]} == {
        no_time["id"]: "Interview date and time required when moving to Interview Scheduled",
        past_time["id"]: "Interview date and time must be in the future",
    }
    for surrogate, start in ((first, first_start), (second, second_start)):
        assert _row(db, surrogate["id"]).stage_id == interview_stage.id
        [appointment] = (
            db.query(Appointment).filter(Appointment.surrogate_id == UUID(surrogate["id"])).all()
        )
        assert appointment.scheduled_start == start
        assert (
            db.query(SurrogateActivityLog)
            .filter(
                SurrogateActivityLog.surrogate_id == UUID(surrogate["id"]),
                SurrogateActivityLog.activity_type
                == SurrogateActivityType.INTERVIEW_SCHEDULED.value,
            )
            .count()
            == 1
        )
    for surrogate in (no_time, past_time):
        assert _row(db, surrogate["id"]).stage_id != interview_stage.id
        assert (
            db.query(Appointment).filter(Appointment.surrogate_id == UUID(surrogate["id"])).count()
            == 0
        )


def _next_weekday_at(hour: int, days_ahead: int = 7) -> datetime:
    start = (datetime.now(UTC) + timedelta(days=days_ahead)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    while start.weekday() > 4:
        start += timedelta(days=1)
    return start


@pytest.mark.asyncio
async def test_bulk_interview_checks_owner_availability_without_override(
    authed_client, db, test_auth, monkeypatch
):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    interview_stage = _get_stage(db, test_auth.org.id, "interview_scheduled")
    slot = _next_weekday_at(10)
    db.add(
        AvailabilityRule(
            organization_id=test_auth.org.id,
            user_id=test_auth.user.id,
            day_of_week=slot.weekday(),
            start_time=time(8),
            end_time=time(18),
            timezone="UTC",
        )
    )
    db.commit()
    first = await _create_surrogate(authed_client, full_name="Same Slot First")
    second = await _create_surrogate(authed_client, full_name="Same Slot Second")
    outside = await _create_surrogate(authed_client, full_name="Outside Hours")
    outside_start = slot.replace(hour=20)

    response = await _bulk(
        authed_client,
        [first["id"], second["id"], outside["id"]],
        interview_stage,
        interview_times=[
            {"surrogate_id": first["id"], "scheduled_at": slot.isoformat()},
            {"surrogate_id": second["id"], "scheduled_at": slot.isoformat()},
            {"surrogate_id": outside["id"], "scheduled_at": outside_start.isoformat()},
        ],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["applied"] == 1
    assert payload["failed"] == [
        {"surrogate_id": second["id"], "reason": "Selected time is no longer available"},
        {"surrogate_id": outside["id"], "reason": "Selected time is no longer available"},
    ]
    [appointment] = (
        db.query(Appointment)
        .filter(
            Appointment.surrogate_id.in_(
                [UUID(first["id"]), UUID(second["id"]), UUID(outside["id"])]
            )
        )
        .all()
    )
    assert appointment.surrogate_id == UUID(first["id"])
    assert appointment.scheduled_start == slot
    assert appointment.availability_override_reason is None
    for surrogate in (second, outside):
        assert _row(db, surrogate["id"]).stage_id != interview_stage.id
        assert _history(db, surrogate["id"]) == []


@pytest.mark.asyncio
async def test_bulk_interview_override_uses_shared_reason(
    authed_client, db, test_auth, monkeypatch
):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    interview_stage = _get_stage(db, test_auth.org.id, "interview_scheduled")
    surrogate = await _create_surrogate(authed_client)
    start = _future_minute(days=4)

    response = await _bulk(
        authed_client,
        [surrogate["id"]],
        interview_stage,
        reason="Booked by phone",
        override_availability=True,
        interview_times=[{"surrogate_id": surrogate["id"], "scheduled_at": start.isoformat()}],
    )

    assert response.status_code == 200, response.text
    assert response.json()["applied"] == 1
    appointment = (
        db.query(Appointment).filter(Appointment.surrogate_id == UUID(surrogate["id"])).one()
    )
    assert appointment.scheduled_start == start
    assert appointment.availability_override_reason == "Booked by phone"
    assert _history(db, surrogate["id"])[-1].reason == "Booked by phone"


@pytest.mark.asyncio
async def test_bulk_availability_override_requires_reason_and_interview_target(
    authed_client, db, test_auth
):
    interview_stage = _get_stage(db, test_auth.org.id, "interview_scheduled")
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    surrogate = await _create_surrogate(authed_client)
    times = [{"surrogate_id": surrogate["id"], "scheduled_at": _future_minute(days=2).isoformat()}]

    missing_reason = await _bulk(
        authed_client,
        [surrogate["id"]],
        interview_stage,
        override_availability=True,
        interview_times=times,
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"] == "Reason required to override availability"

    wrong_target = await _bulk(
        authed_client,
        [surrogate["id"]],
        contacted_stage,
        reason="Booked",
        override_availability=True,
    )
    assert wrong_target.status_code == 400
    assert (
        wrong_target.json()["detail"]
        == "Availability override applies only to interview scheduling"
    )
    assert _history(db, surrogate["id"]) == []


@pytest.mark.asyncio
async def test_bulk_interview_times_must_match_selection_and_target(authed_client, db, test_auth):
    interview_stage = _get_stage(db, test_auth.org.id, "interview_scheduled")
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    surrogate = await _create_surrogate(authed_client)
    start = _future_minute(days=2).isoformat()

    unselected = await _bulk(
        authed_client,
        [surrogate["id"]],
        interview_stage,
        reason="Booked",
        interview_times=[{"surrogate_id": str(uuid.uuid4()), "scheduled_at": start}],
    )
    assert unselected.status_code == 422

    wrong_target = await _bulk(
        authed_client,
        [surrogate["id"]],
        contacted_stage,
        interview_times=[{"surrogate_id": surrogate["id"], "scheduled_at": start}],
    )
    assert wrong_target.status_code == 400
    assert (
        wrong_target.json()["detail"]
        == "Interview times are only allowed when moving to Interview Scheduled"
    )


@pytest.mark.asyncio
async def test_bulk_change_stage_rejects_duplicate_surrogate_ids(authed_client, db, test_auth):
    on_hold_stage = _get_stage(db, test_auth.org.id, "on_hold")
    surrogate = await _create_surrogate(authed_client)

    response = await _bulk(
        authed_client,
        [surrogate["id"], surrogate["id"]],
        on_hold_stage,
        reason="Travelling",
        on_hold_follow_up_months=1,
    )

    assert response.status_code == 422
    assert "Each surrogate can be selected only once" in response.text
    assert _history(db, surrogate["id"]) == []
    assert db.query(Task).filter(Task.surrogate_id == UUID(surrogate["id"])).count() == 0


@pytest.mark.asyncio
async def test_bulk_row_failing_after_writes_rolls_back_only_that_row(
    authed_client, db, test_auth, monkeypatch
):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    on_hold_stage = _get_stage(db, test_auth.org.id, "on_hold")
    interview_stage = _get_stage(db, test_auth.org.id, "interview_scheduled")
    failing = await _create_surrogate(authed_client, full_name="Inactive Owner Row")
    succeeding = await _create_surrogate(authed_client, full_name="Next Row")
    await _move(authed_client, failing["id"], contacted_stage)
    await _move(
        authed_client, failing["id"], on_hold_stage, reason="Paused", on_hold_follow_up_months=1
    )

    inactive_owner = User(
        id=uuid.uuid4(),
        email=f"bulk-inactive-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Inactive Owner",
        token_version=1,
        is_active=False,
    )
    db.add(inactive_owner)
    db.flush()
    inactive_owner_id = inactive_owner.id
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=inactive_owner_id,
            organization_id=test_auth.org.id,
            role=Role.CASE_MANAGER.value,
        )
    )
    row = _row(db, failing["id"])
    row.owner_type = "user"
    row.owner_id = inactive_owner_id
    follow_up_task_id = row.on_hold_follow_up_task_id
    db.commit()
    assert follow_up_task_id is not None
    history_before = len(_history(db, failing["id"]))
    notes_before = len(_notes(db, failing["id"]))

    # The follow-up cleanup and appointment type are flushed before the owner check fails.
    response = await _bulk(
        authed_client,
        [failing["id"], succeeding["id"]],
        interview_stage,
        reason="Booked",
        override_availability=True,
        interview_times=[
            {"surrogate_id": failing["id"], "scheduled_at": _future_minute(days=2).isoformat()},
            {"surrogate_id": succeeding["id"], "scheduled_at": _future_minute(days=3).isoformat()},
        ],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["applied"] == 1
    assert payload["failed"] == [
        {"surrogate_id": failing["id"], "reason": "Appointment owner is unavailable"}
    ]
    row = _row(db, failing["id"])
    assert row.stage_id == on_hold_stage.id
    assert row.paused_from_stage_id == contacted_stage.id
    assert row.on_hold_follow_up_task_id == follow_up_task_id
    assert db.get(Task, follow_up_task_id) is not None
    assert len(_history(db, failing["id"])) == history_before
    assert len(_notes(db, failing["id"])) == notes_before
    assert (
        db.query(Appointment).filter(Appointment.surrogate_id == UUID(failing["id"])).count() == 0
    )
    assert (
        db.query(AppointmentType).filter(AppointmentType.user_id == inactive_owner_id).count() == 0
    )
    assert _row(db, succeeding["id"]).stage_id == interview_stage.id


@pytest.mark.asyncio
async def test_bulk_row_database_error_is_sanitized_and_rolled_back(
    authed_client, db, test_auth, monkeypatch
):
    from app.services import activity_service

    interview_stage = _get_stage(db, test_auth.org.id, "interview_scheduled")
    failing = await _create_surrogate(authed_client, full_name="Database Error Row")
    succeeding = await _create_surrogate(authed_client, full_name="After Database Error")
    original_log_activity = activity_service.log_activity
    calls = {"count": 0}

    def fail_first_activity(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise IntegrityError(
                "INSERT secret-sql", {"param": "secret-param"}, Exception("secret-detail")
            )
        return original_log_activity(*args, **kwargs)

    monkeypatch.setattr(activity_service, "log_activity", fail_first_activity)

    response = await _bulk(
        authed_client,
        [failing["id"], succeeding["id"]],
        interview_stage,
        interview_times=[
            {"surrogate_id": failing["id"], "scheduled_at": _future_minute(days=2).isoformat()},
            {"surrogate_id": succeeding["id"], "scheduled_at": _future_minute(days=3).isoformat()},
        ],
    )

    assert response.status_code == 200, response.text
    assert "secret" not in response.text
    payload = response.json()
    assert payload["applied"] == 1
    assert payload["failed"] == [{"surrogate_id": failing["id"], "reason": "Stage change failed"}]
    assert _row(db, failing["id"]).stage_id != interview_stage.id
    assert _history(db, failing["id"]) == []
    assert _notes(db, failing["id"]) == []
    assert (
        db.query(Appointment).filter(Appointment.surrogate_id == UUID(failing["id"])).count() == 0
    )
    assert _row(db, succeeding["id"]).stage_id == interview_stage.id
