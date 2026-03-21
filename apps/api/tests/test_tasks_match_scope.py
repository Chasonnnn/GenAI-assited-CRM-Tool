from __future__ import annotations

import uuid

import pytest

from app.db.models import IntendedParent, Match, Membership, Organization, Task, User
from app.db.enums import Role
from app.core.encryption import hash_email
from app.utils.normalization import normalize_email


def _create_ip_stage(db, org_id):
    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type="intended_parent",
    )
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
    assert stage is not None
    return stage


def _create_intended_parent(db, org_id):
    stage = _create_ip_stage(db, org_id)
    email = f"match-ip-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    intended_parent = IntendedParent(
        id=uuid.uuid4(),
        organization_id=org_id,
        intended_parent_number=f"I{uuid.uuid4().int % 90000 + 10000:05d}",
        full_name="Match IP",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        stage_id=stage.id,
        status=stage.stage_key,
    )
    db.add(intended_parent)
    db.flush()
    return intended_parent


def _create_match(db, org_id, user_id, surrogate_id, intended_parent_id):
    match = Match(
        id=uuid.uuid4(),
        organization_id=org_id,
        match_number=f"M{uuid.uuid4().int % 90000 + 10000:05d}",
        surrogate_id=surrogate_id,
        intended_parent_id=intended_parent_id,
        proposed_by_user_id=user_id,
    )
    db.add(match)
    db.flush()
    return match


def _create_surrogate(db, org_id, user_id, stage):
    email = f"match-surrogate-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    from app.db.models import Surrogate

    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Match Surrogate",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


@pytest.mark.asyncio
async def test_create_task_with_match_id_links_surrogate_and_intended_parent(
    authed_client,
    db,
    test_auth,
    default_stage,
):
    surrogate = _create_surrogate(db, test_auth.org.id, test_auth.user.id, default_stage)
    intended_parent = _create_intended_parent(db, test_auth.org.id)
    match = _create_match(db, test_auth.org.id, test_auth.user.id, surrogate.id, intended_parent.id)

    response = await authed_client.post(
        "/tasks",
        json={
            "title": "Coordinate next steps",
            "task_type": "follow_up",
            "match_id": str(match.id),
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["surrogate_id"] == str(surrogate.id)
    assert payload["intended_parent_id"] == str(intended_parent.id)

    created_task = db.query(Task).filter(Task.id == uuid.UUID(payload["id"])).one()
    assert created_task.surrogate_id == surrogate.id
    assert created_task.intended_parent_id == intended_parent.id


@pytest.mark.asyncio
async def test_create_task_with_match_id_rejects_missing_match(authed_client):
    response = await authed_client.post(
        "/tasks",
        json={
            "title": "Coordinate next steps",
            "match_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Match not found"


@pytest.mark.asyncio
async def test_create_task_with_match_id_rejects_cross_org_match(
    authed_client,
    db,
    test_auth,
):
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Org",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()

    other_user = User(
        id=uuid.uuid4(),
        email=f"other-user-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Other User",
        token_version=1,
        is_active=True,
    )
    db.add(other_user)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=other_user.id,
            organization_id=other_org.id,
            role=Role.ADMIN.value,
            is_active=True,
        )
    )
    db.flush()

    from app.services import pipeline_service

    other_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, other_org.id, entity_type="surrogate"
    )
    other_default_stage = pipeline_service.get_stage_by_slug(db, other_pipeline.id, "new_unread")
    assert other_default_stage is not None

    surrogate = _create_surrogate(db, other_org.id, other_user.id, other_default_stage)
    intended_parent = _create_intended_parent(db, other_org.id)
    match = _create_match(db, other_org.id, other_user.id, surrogate.id, intended_parent.id)

    response = await authed_client.post(
        "/tasks",
        json={
            "title": "Cross-org task",
            "match_id": str(match.id),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Match not found"


@pytest.mark.asyncio
async def test_create_task_with_match_id_rejects_explicit_entity_ids(
    authed_client,
    db,
    test_auth,
    default_stage,
):
    surrogate = _create_surrogate(db, test_auth.org.id, test_auth.user.id, default_stage)
    intended_parent = _create_intended_parent(db, test_auth.org.id)
    match = _create_match(db, test_auth.org.id, test_auth.user.id, surrogate.id, intended_parent.id)

    response = await authed_client.post(
        "/tasks",
        json={
            "title": "Ambiguous task",
            "match_id": str(match.id),
            "surrogate_id": str(surrogate.id),
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "match_id cannot be combined with surrogate_id or intended_parent_id"
    )


@pytest.mark.asyncio
async def test_create_task_rejects_missing_intended_parent(authed_client):
    response = await authed_client.post(
        "/tasks",
        json={
            "title": "Call intended parent",
            "intended_parent_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Intended parent not found"
