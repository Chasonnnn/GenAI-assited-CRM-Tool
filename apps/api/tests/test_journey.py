from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID
import uuid
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_export_token, create_session_token
from app.db.enums import Role
from app.db.models import Membership, Surrogate, User
from app.main import app
from app.services import pdf_export_service, pipeline_service, session_service


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


@asynccontextmanager
async def _authed_client_for_user(db, org_id, user, role):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=role.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def _create_surrogate(authed_client):
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Journey Test",
            "email": f"journey-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _set_stage(authed_client, surrogate_id: str, stage_id: UUID, effective_at: str | None = None):
    payload: dict[str, str] = {"stage_id": str(stage_id)}
    if effective_at:
        payload["effective_at"] = effective_at
    response = await authed_client.patch(f"/surrogates/{surrogate_id}/status", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"


def _iter_milestones(payload: dict):
    for phase in payload.get("phases", []):
        for milestone in phase.get("milestones", []):
            yield milestone


def _find_milestone(payload: dict, slug: str):
    for milestone in _iter_milestones(payload):
        if milestone.get("slug") == slug:
            return milestone
    raise AssertionError(f"Missing milestone {slug}")


def _org_today(org_timezone: str | None) -> str:
    tz_name = org_timezone or "America/Los_Angeles"
    return datetime.now(ZoneInfo(tz_name)).date().isoformat()


@pytest.mark.asyncio
async def test_journey_completion_date_uses_next_milestone_entry(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ready_to_match = _get_stage(db, test_auth.org.id, "ready_to_match")
    matched = _get_stage(db, test_auth.org.id, "matched")

    await _set_stage(authed_client, surrogate["id"], ready_to_match.id)
    today = _org_today(test_auth.org.timezone)
    await _set_stage(authed_client, surrogate["id"], matched.id, effective_at=today)

    response = await authed_client.get(f"/journey/surrogates/{surrogate['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()

    approved_matching = _find_milestone(payload, "approved_matching")
    assert approved_matching["status"] == "completed"
    assert approved_matching["completed_at"] is not None
    expected_date = datetime.now(timezone.utc).date().isoformat()
    assert approved_matching["completed_at"].startswith(expected_date)

    match_confirmed = _find_milestone(payload, "match_confirmed")
    assert match_confirmed["status"] == "current"


@pytest.mark.asyncio
async def test_journey_terminal_state_has_banner_and_no_current(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    lost_stage = _get_stage(db, test_auth.org.id, "lost")
    today = _org_today(test_auth.org.timezone)

    await _set_stage(authed_client, surrogate["id"], lost_stage.id, effective_at=today)

    response = await authed_client.get(f"/journey/surrogates/{surrogate['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["is_terminal"] is True
    assert payload["terminal_date"] is not None
    expected_date = datetime.now(timezone.utc).date().isoformat()
    assert payload["terminal_date"].startswith(expected_date)
    assert all(milestone["status"] != "current" for milestone in _iter_milestones(payload))


@pytest.mark.asyncio
async def test_journey_unknown_stage_falls_back_to_first_milestone(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_auth.org.id)

    unknown_stage = pipeline_service.create_stage(
        db=db,
        pipeline_id=pipeline.id,
        slug=f"unknown_{uuid.uuid4().hex[:6]}",
        label="Unknown Stage",
        color="#6B7280",
        stage_type="intake",
        order=0,
        user_id=test_auth.user.id,
    )

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    surrogate_row.stage_id = unknown_stage.id
    surrogate_row.status_label = unknown_stage.label
    db.commit()

    response = await authed_client.get(f"/journey/surrogates/{surrogate['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()

    application_intake = _find_milestone(payload, "application_intake")
    assert application_intake["status"] == "current"


@pytest.mark.asyncio
async def test_journey_requires_surrogate_access(db, test_org, authed_client):
    surrogate = await _create_surrogate(authed_client)

    intake_user = User(
        id=uuid.uuid4(),
        email=f"intake-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Intake User",
        token_version=1,
        is_active=True,
    )
    db.add(intake_user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=intake_user.id,
        organization_id=test_org.id,
        role=Role.INTAKE_SPECIALIST,
    )
    db.add(membership)
    db.flush()

    async with _authed_client_for_user(
        db, test_org.id, intake_user, Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.get(f"/journey/surrogates/{surrogate['id']}")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_journey_completed_milestones_do_not_roll_back(authed_client, db, test_auth):
    surrogate = await _create_surrogate(authed_client)
    ready_to_match = _get_stage(db, test_auth.org.id, "ready_to_match")
    matched = _get_stage(db, test_auth.org.id, "matched")

    await _set_stage(authed_client, surrogate["id"], ready_to_match.id)
    await _set_stage(authed_client, surrogate["id"], matched.id)

    surrogate_row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
    assert surrogate_row is not None
    surrogate_row.stage_id = ready_to_match.id
    surrogate_row.status_label = ready_to_match.label
    db.commit()

    response = await authed_client.get(f"/journey/surrogates/{surrogate['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()

    approved_matching = _find_milestone(payload, "approved_matching")
    assert approved_matching["status"] == "completed"


@pytest.mark.asyncio
async def test_journey_export_pdf_returns_pdf(authed_client, monkeypatch):
    surrogate = await _create_surrogate(authed_client)

    def fake_export_journey_pdf(*_args, **_kwargs):
        return b"%PDF-1.4\njourney"

    monkeypatch.setattr(pdf_export_service, "export_journey_pdf", fake_export_journey_pdf)

    response = await authed_client.get(f"/journey/surrogates/{surrogate['id']}/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_journey_export_view_rejects_invalid_token(authed_client):
    surrogate = await _create_surrogate(authed_client)

    response = await authed_client.get(
        f"/journey/surrogates/{surrogate['id']}/export-view?export_token=invalid"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_journey_export_view_returns_payload(authed_client, test_auth):
    surrogate = await _create_surrogate(authed_client)
    token = create_export_token(test_auth.org.id, UUID(surrogate["id"]))

    response = await authed_client.get(
        f"/journey/surrogates/{surrogate['id']}/export-view?export_token={token}"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["surrogate_id"] == surrogate["id"]
    assert payload["phases"]
