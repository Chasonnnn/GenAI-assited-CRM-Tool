"""New case writes stay fenced while API and worker revisions are mixed."""

import uuid

import pytest

from app.core.config import settings
from app.db.models import Match
from tests.match_fixtures import seed_attempt
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _accept, _case, _donor


@pytest.mark.asyncio
async def test_disabled_expansion_preserves_legacy_match_operations(
    authed_client, db, test_auth, monkeypatch
):
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    ip = await _create_intended_parent(authed_client)
    surrogate = await _create_surrogate(authed_client)
    case = await _case(authed_client, ip, surrogate=surrogate)
    accepted = await _accept(authed_client, case)
    assert accepted["status"] == "accepted"
    assert (await authed_client.get(f"/matches/{case['id']}")).status_code == 200
    before = db.query(Match).filter_by(organization_id=test_auth.org.id).count()
    donor = await _donor(authed_client)
    response = await authed_client.post(
        "/matches/", json={"donor_id": donor["id"], "intended_parent_id": ip["id"]}
    )
    assert response.status_code == 503
    assert db.query(Match).filter_by(organization_id=test_auth.org.id).count() == before
    response = await authed_client.put(
        f"/matches/{case['id']}/complete", json={"outcome": "Completed"}
    )
    assert response.status_code == 503
    db.expire_all()
    assert db.get(Match, uuid.UUID(case["id"])).status == "accepted"


@pytest.mark.asyncio
async def test_disabled_expansion_rejects_repeat_pairs(authed_client, db, test_auth, monkeypatch):
    ip = await _create_intended_parent(authed_client)
    surrogate = await _create_surrogate(authed_client)
    case = await _case(authed_client, ip, surrogate=surrogate)
    response = await authed_client.put(
        f"/matches/{case['id']}/decline", json={"reason": "Not proceeding"}
    )
    assert response.status_code == 200
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    response = await authed_client.post(
        "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
    )
    assert response.status_code == 503
    assert db.query(Match).filter(Match.organization_id == test_auth.org.id).count() == 1


@pytest.mark.asyncio
async def test_disabled_expansion_allows_parallel_ip_surrogate_commitment(
    authed_client, monkeypatch
):
    ip = await _create_intended_parent(authed_client)
    first = await _create_surrogate(authed_client)
    second = await _create_surrogate(authed_client)
    await _accept(authed_client, await _case(authed_client, ip, surrogate=first))
    second_case = await _case(authed_client, ip, surrogate=second)
    assert second_case["status"] == "under_review"
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    response = await authed_client.put(f"/matches/{second_case['id']}/accept", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_expansion_requires_explicit_activation(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("MATCH_CASE_EXPANSION_ENABLED", raising=False)
    assert Settings(_env_file=None).MATCH_CASE_EXPANSION_ENABLED is False


def _png() -> bytes:
    import io

    from PIL import Image

    content = io.BytesIO()
    Image.new("RGB", (1, 1)).save(content, format="PNG")
    return content.getvalue()


@pytest.mark.asyncio
async def test_disabling_expansion_keeps_history_readable_and_match_work_open(
    authed_client, db, test_auth, monkeypatch
):
    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    case = await _accept(authed_client, await _case(authed_client, ip, donor=donor))
    attempt = seed_attempt(db, case["id"], attempt_type="retrieval")
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    assert (await authed_client.get(f"/matches/{case['id']}")).status_code == 200
    history = await authed_client.get(
        f"/matches/{case['id']}/work", params={"attempt_id": str(attempt.id)}
    )
    assert history.status_code == 200, history.text
    note = await authed_client.post(f"/matches/{case['id']}/notes", json={"content": "Open"})
    assert note.status_code == 201, note.text
    task = await authed_client.post("/tasks", json={"title": "Open", "match_id": case["id"]})
    assert task.status_code == 201, task.text
    file = await authed_client.post(
        f"/matches/{case['id']}/attachments",
        files={"file": ("open.png", _png(), "image/png")},
    )
    assert file.status_code == 201, file.text


@pytest.mark.asyncio
async def test_disabled_expansion_allows_surrogate_match_work_and_appointment_links(
    authed_client, db, test_auth, test_user, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    from app.db.models import Appointment
    from app.services import appointment_integrations, appointment_service

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
            appointment_service.TimeSlot(start, start + timedelta(minutes=30))
        ],
    )
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    ip = await _create_intended_parent(authed_client)
    surrogate = await _create_surrogate(authed_client)
    case = await _accept(authed_client, await _case(authed_client, ip, surrogate=surrogate))

    note = await authed_client.post(f"/matches/{case['id']}/notes", json={"content": "Kickoff"})
    assert note.status_code == 201, note.text
    task = await authed_client.post(
        "/tasks", json={"title": "Book transfer", "match_id": case["id"]}
    )
    assert task.status_code == 201, task.text
    assert task.json()["match_id"] == case["id"]
    file = await authed_client.post(
        f"/matches/{case['id']}/attachments",
        files={"file": ("contract.png", _png(), "image/png")},
    )
    assert file.status_code == 201, file.text
    work = (await authed_client.get(f"/matches/{case['id']}/work")).json()
    assert note.json()["id"] in {item["id"] for item in work["notes"]}
    assert file.json()["id"] in {item["id"] for item in work["files"]}
    assert task.json()["id"] in {item["id"] for item in work["tasks"]}

    appointment_type = await authed_client.post(
        "/appointments/types",
        json={"name": "Match consultation", "duration_minutes": 30, "meeting_mode": "phone"},
    )
    assert appointment_type.status_code == 201, appointment_type.text
    created = await authed_client.post(
        "/appointments",
        json={
            "appointment_type_id": appointment_type.json()["id"],
            "intended_parent_id": ip["id"],
            "match_id": case["id"],
            "client_name": "QA",
            "client_email": "qa@example.com",
            "client_phone": "6075550100",
            "client_timezone": "UTC",
            "scheduled_start": start.isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["match_id"] == case["id"]
    general = Appointment(
        organization_id=test_auth.org.id,
        user_id=test_user.id,
        intended_parent_id=uuid.UUID(ip["id"]),
        client_name="QA",
        client_email="qa@example.com",
        client_phone="6075550100",
        client_timezone="UTC",
        scheduled_start=start + timedelta(hours=2),
        scheduled_end=start + timedelta(hours=2, minutes=30),
        duration_minutes=30,
        meeting_mode="phone",
        status="confirmed",
    )
    db.add(general)
    db.flush()
    linked = await authed_client.patch(
        f"/appointments/{general.id}/link", json={"match_id": case["id"]}
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["match_id"] == case["id"]
