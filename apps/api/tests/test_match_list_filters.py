"""GET /matches proposed date range filter."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Match, Membership, Organization, User
from app.main import app
from app.services import session_service
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate


async def _propose(authed_client: AsyncClient) -> dict:
    surrogate = await _create_surrogate(authed_client)
    intended_parent = await _create_intended_parent(authed_client)
    response = await authed_client.post(
        "/matches/",
        json={"surrogate_id": surrogate["id"], "intended_parent_id": intended_parent["id"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_proposed_at(db, match_id: str, value: datetime) -> None:
    match = db.get(Match, UUID(match_id))
    assert match is not None
    match.proposed_at = value
    db.flush()


@asynccontextmanager
async def _client_for_other_org(db):
    org = Organization(
        id=uuid.uuid4(),
        name="Other Match Org",
        slug=f"other-match-org-{uuid.uuid4().hex[:8]}",
    )
    user = User(
        id=uuid.uuid4(),
        email=f"other-match-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other Match User",
        token_version=1,
        is_active=True,
    )
    db.add_all([org, user])
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=org.id,
            role=Role.DEVELOPER.value,
            is_active=True,
        )
    )
    db.flush()
    token = create_session_token(
        user_id=user.id,
        org_id=org.id,
        role=Role.DEVELOPER.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=user.id, org_id=org.id, token=token, request=None)
    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_list_matches_filters_by_inclusive_proposed_date_range(authed_client, db):
    early = await _propose(authed_client)
    inside = await _propose(authed_client)
    boundary = await _propose(authed_client)
    late = await _propose(authed_client)
    _set_proposed_at(db, early["id"], datetime(2026, 8, 31, 23, 59, tzinfo=UTC))
    _set_proposed_at(db, inside["id"], datetime(2026, 9, 10, 12, 0, tzinfo=UTC))
    _set_proposed_at(db, boundary["id"], datetime(2026, 9, 20, 23, 59, tzinfo=UTC))
    _set_proposed_at(db, late["id"], datetime(2026, 9, 21, 0, 0, tzinfo=UTC))

    response = await authed_client.get(
        "/matches/", params={"proposed_from": "2026-09-01", "proposed_to": "2026-09-20"}
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {inside["id"], boundary["id"]}
    assert response.json()["total"] == 2

    only_from = await authed_client.get("/matches/", params={"proposed_from": "2026-09-21"})
    assert only_from.status_code == 200, only_from.text
    assert {item["id"] for item in only_from.json()["items"]} == {late["id"]}


@pytest.mark.asyncio
async def test_list_matches_rejects_invalid_proposed_date(authed_client):
    response = await authed_client.get("/matches/", params={"proposed_from": "not-a-date"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_matches_proposed_date_range_is_org_scoped(authed_client, db):
    match = await _propose(authed_client)
    _set_proposed_at(db, match["id"], datetime(2026, 9, 10, 12, 0, tzinfo=UTC))
    params = {"proposed_from": "2026-09-01", "proposed_to": "2026-09-30"}

    own = await authed_client.get("/matches/", params=params)
    assert own.status_code == 200, own.text
    assert match["id"] in {item["id"] for item in own.json()["items"]}

    async with _client_for_other_org(db) as other_client:
        other = await other_client.get("/matches/", params=params)

    assert other.status_code == 200, other.text
    assert other.json()["total"] == 0
    assert other.json()["items"] == []
