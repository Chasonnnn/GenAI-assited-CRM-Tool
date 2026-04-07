from __future__ import annotations

from uuid import UUID
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, Surrogate, SurrogateStatusHistory, User
from app.main import app
from app.services import pipeline_service, session_service


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


async def _create_surrogate(client: AsyncClient, **overrides):
    payload = {
        "full_name": "Bulk Change Stage Test",
        "email": f"bulk-change-stage-{uuid.uuid4().hex[:8]}@example.com",
        **overrides,
    }
    response = await client.post("/surrogates", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


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

        response = await client.post(
            "/surrogates/bulk-change-stage",
            json={
                "surrogate_ids": [surrogate["id"]],
                "stage_id": str(contacted_stage.id),
            },
        )

        assert response.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.ADMIN, Role.DEVELOPER])
async def test_bulk_change_stage_allows_admin_and_developer(db, test_org, role: Role):
    client = await _client_with_role(db, test_org, role)
    async with client:
        surrogate = await _create_surrogate(client)
        contacted_stage = _get_stage(db, test_org.id, "contacted")

        response = await client.post(
            "/surrogates/bulk-change-stage",
            json={
                "surrogate_ids": [surrogate["id"]],
                "stage_id": str(contacted_stage.id),
            },
        )

        assert response.status_code == 200, response.text
        assert response.json() == {
            "requested": 1,
            "applied": 1,
            "failed": [],
        }

        row = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate["id"])).first()
        assert row is not None
        assert row.stage_id == contacted_stage.id
        assert row.status_label == contacted_stage.label

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

    same_stage_response = await authed_client.patch(
        f"/surrogates/{same_stage['id']}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert same_stage_response.status_code == 200, same_stage_response.text

    archive_response = await authed_client.post(f"/surrogates/{archived['id']}/archive")
    assert archive_response.status_code == 200, archive_response.text

    move_on_hold_source_response = await authed_client.patch(
        f"/surrogates/{on_hold['id']}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert move_on_hold_source_response.status_code == 200, move_on_hold_source_response.text

    move_on_hold_response = await authed_client.patch(
        f"/surrogates/{on_hold['id']}/status",
        json={
            "stage_id": str(on_hold_stage.id),
            "reason": "Waiting on surrogate response",
            "on_hold_follow_up_months": 1,
        },
    )
    assert move_on_hold_response.status_code == 200, move_on_hold_response.text

    missing_id = str(uuid.uuid4())
    response = await authed_client.post(
        "/surrogates/bulk-change-stage",
        json={
            "surrogate_ids": [
                successful["id"],
                same_stage["id"],
                archived["id"],
                on_hold["id"],
                missing_id,
            ],
            "stage_id": str(contacted_stage.id),
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["requested"] == 5
    assert payload["applied"] == 1
    assert {entry["surrogate_id"] for entry in payload["failed"]} == {
        same_stage["id"],
        archived["id"],
        on_hold["id"],
        missing_id,
    }

    failure_reasons = {entry["surrogate_id"]: entry["reason"] for entry in payload["failed"]}
    assert failure_reasons[same_stage["id"]] == "Target stage is same as current stage"
    assert failure_reasons[archived["id"]] == "Cannot change status of archived surrogate"
    assert failure_reasons[on_hold["id"]] == "Cannot bulk change stage for surrogates currently on hold"
    assert failure_reasons[missing_id] == "Surrogate not found"

    successful_row = db.query(Surrogate).filter(Surrogate.id == UUID(successful["id"])).first()
    same_stage_row = db.query(Surrogate).filter(Surrogate.id == UUID(same_stage["id"])).first()
    archived_row = db.query(Surrogate).filter(Surrogate.id == UUID(archived["id"])).first()
    on_hold_row = db.query(Surrogate).filter(Surrogate.id == UUID(on_hold["id"])).first()

    assert successful_row is not None and successful_row.stage_id == contacted_stage.id
    assert successful_row.status_label == contacted_stage.label
    assert same_stage_row is not None and same_stage_row.stage_id == contacted_stage.id
    assert archived_row is not None and archived_row.is_archived is True
    assert on_hold_row is not None and on_hold_row.stage_id == on_hold_stage.id

    successful_history = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id == successful_row.id)
        .all()
    )
    assert len(successful_history) == 1
    assert successful_history[0].to_stage_id == contacted_stage.id


@pytest.mark.asyncio
async def test_bulk_change_stage_rejects_regressions_per_row_without_aborting_batch(
    authed_client, db, test_auth
):
    contacted_stage = _get_stage(db, test_auth.org.id, "contacted")
    approved_stage = _get_stage(db, test_auth.org.id, "approved")

    regression_row = await _create_surrogate(authed_client, full_name="Regression Row")
    success_row = await _create_surrogate(authed_client, full_name="Success Row")

    move_regression_source_response = await authed_client.patch(
        f"/surrogates/{regression_row['id']}/status",
        json={"stage_id": str(approved_stage.id)},
    )
    assert move_regression_source_response.status_code == 200, move_regression_source_response.text

    response = await authed_client.post(
        "/surrogates/bulk-change-stage",
        json={
            "surrogate_ids": [regression_row["id"], success_row["id"]],
            "stage_id": str(contacted_stage.id),
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["requested"] == 2
    assert payload["applied"] == 1
    assert payload["failed"] == [
        {
            "surrogate_id": regression_row["id"],
            "reason": "Bulk stage changes do not support regressions",
        }
    ]

    refreshed_regression_row = (
        db.query(Surrogate).filter(Surrogate.id == UUID(regression_row["id"])).first()
    )
    refreshed_success_row = db.query(Surrogate).filter(Surrogate.id == UUID(success_row["id"])).first()
    assert refreshed_regression_row is not None
    assert refreshed_regression_row.stage_id == approved_stage.id
    assert refreshed_success_row is not None
    assert refreshed_success_row.stage_id == contacted_stage.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target_slug", "expected_detail"),
    [
        ("on_hold", "Bulk stage changes only support immediate stages"),
        ("delivered", "Bulk stage changes only support immediate stages"),
    ],
)
async def test_bulk_change_stage_rejects_targets_that_require_extra_input(
    authed_client, db, test_auth, target_slug: str, expected_detail: str
):
    surrogate = await _create_surrogate(authed_client)
    target_stage = _get_stage(db, test_auth.org.id, target_slug)

    response = await authed_client.post(
        "/surrogates/bulk-change-stage",
        json={
            "surrogate_ids": [surrogate["id"]],
            "stage_id": str(target_stage.id),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail
