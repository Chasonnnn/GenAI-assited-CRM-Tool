from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

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


async def _create_surrogate(authed_client, **overrides):
    payload = {
        "full_name": "Mass Edit Test",
        "email": f"mass-edit-{uuid.uuid4().hex[:8]}@example.com",
        **overrides,
    }
    res = await authed_client.post("/surrogates", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


async def _client_with_role(db, test_org, role: Role) -> AsyncClient:
    user = User(
        id=uuid.uuid4(),
        email=f"mass-edit-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Mass Edit User",
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
        db=db, user_id=user.id, org_id=test_org.id, token=token, request=None
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
async def test_mass_edit_stage_requires_developer_role(db, test_org):
    admin_client = await _client_with_role(db, test_org, Role.ADMIN)
    async with admin_client:
        preview = await admin_client.post(
            "/surrogates/mass-edit/stage/preview",
            json={"filters": {"states": ["CA"]}},
        )
        assert preview.status_code == 403

        apply_res = await admin_client.post(
            "/surrogates/mass-edit/stage",
            json={
                "filters": {"states": ["CA"]},
                "stage_id": str(uuid.uuid4()),
                "expected_total": 0,
            },
        )
        assert apply_res.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mass_edit_stage_preview_and_apply_updates_surrogates_and_history(
    authed_client, db, test_auth
):
    disqualified_stage = _get_stage(db, test_auth.org.id, "disqualified")

    s1 = await _create_surrogate(authed_client, state="CA")
    s2 = await _create_surrogate(authed_client, state="CA")
    s3 = await _create_surrogate(authed_client, state="TX")

    preview = await authed_client.post(
        "/surrogates/mass-edit/stage/preview",
        json={"filters": {"states": ["CA"]}},
    )
    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["total"] == 2
    assert preview_payload["over_limit"] is False

    apply_res = await authed_client.post(
        "/surrogates/mass-edit/stage",
        json={
            "filters": {"states": ["CA"]},
            "stage_id": str(disqualified_stage.id),
            "expected_total": 2,
            "trigger_workflows": False,
            "reason": "Bulk disqualify obvious non-fits",
        },
    )
    assert apply_res.status_code == 200, apply_res.text
    payload = apply_res.json()
    assert payload["matched"] == 2
    assert payload["applied"] == 2
    assert payload["pending_approval"] == 0
    assert payload["failed"] == []

    s1_row = db.query(Surrogate).filter(Surrogate.id == UUID(s1["id"])).first()
    s2_row = db.query(Surrogate).filter(Surrogate.id == UUID(s2["id"])).first()
    s3_row = db.query(Surrogate).filter(Surrogate.id == UUID(s3["id"])).first()
    assert s1_row is not None and s2_row is not None and s3_row is not None
    assert s1_row.stage_id == disqualified_stage.id
    assert s2_row.stage_id == disqualified_stage.id
    assert s3_row.stage_id != disqualified_stage.id
    assert s1_row.status_label == disqualified_stage.label
    assert s2_row.status_label == disqualified_stage.label

    history_rows = (
        db.query(SurrogateStatusHistory)
        .filter(SurrogateStatusHistory.surrogate_id.in_([s1_row.id, s2_row.id]))
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .all()
    )
    assert len(history_rows) == 2
    for h in history_rows:
        assert h.changed_by_user_id == test_auth.user.id
        assert h.to_stage_id == disqualified_stage.id
        assert h.recorded_at is not None
        assert h.effective_at is not None
        assert abs((h.recorded_at - h.effective_at).total_seconds()) < 10


@pytest.mark.asyncio
async def test_mass_edit_stage_can_filter_by_age(authed_client, db, test_auth):
    disqualified_stage = _get_stage(db, test_auth.org.id, "disqualified")

    # Today is derived from runtime; choose DOBs relative to today's date
    today = date.today()
    dob_30 = date(today.year - 30, today.month, today.day)
    dob_40 = date(today.year - 40, today.month, today.day)

    s1 = await _create_surrogate(authed_client, date_of_birth=dob_30.isoformat(), state="CA")
    await _create_surrogate(authed_client, date_of_birth=dob_40.isoformat(), state="CA")

    preview = await authed_client.post(
        "/surrogates/mass-edit/stage/preview",
        json={"filters": {"age_max": 35}},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["total"] == 1

    apply_res = await authed_client.post(
        "/surrogates/mass-edit/stage",
        json={
            "filters": {"age_max": 35},
            "stage_id": str(disqualified_stage.id),
            "expected_total": 1,
            "trigger_workflows": False,
        },
    )
    assert apply_res.status_code == 200, apply_res.text

    s1_row = db.query(Surrogate).filter(Surrogate.id == UUID(s1["id"])).first()
    assert s1_row is not None
    assert s1_row.stage_id == disqualified_stage.id


@pytest.mark.asyncio
async def test_mass_edit_stage_can_filter_by_race(authed_client, db, test_auth):
    disqualified_stage = _get_stage(db, test_auth.org.id, "disqualified")

    s1 = await _create_surrogate(authed_client, race="Hispanic or Latino", state="CA")
    await _create_surrogate(authed_client, race="White", state="CA")

    preview = await authed_client.post(
        "/surrogates/mass-edit/stage/preview",
        json={"filters": {"races": ["hispanic_or_latino"]}},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["total"] == 1

    apply_res = await authed_client.post(
        "/surrogates/mass-edit/stage",
        json={
            "filters": {"races": ["Hispanic or Latino"]},
            "stage_id": str(disqualified_stage.id),
            "expected_total": 1,
            "trigger_workflows": False,
        },
    )
    assert apply_res.status_code == 200, apply_res.text

    s1_row = db.query(Surrogate).filter(Surrogate.id == UUID(s1["id"])).first()
    assert s1_row is not None
    assert s1_row.stage_id == disqualified_stage.id


@pytest.mark.asyncio
async def test_mass_edit_options_returns_race_keys(authed_client, db, test_auth):
    await _create_surrogate(authed_client, race="Hispanic or Latino", state="CA")
    await _create_surrogate(authed_client, race="White", state="CA")

    res = await authed_client.get("/surrogates/mass-edit/options")
    assert res.status_code == 200, res.text
    payload = res.json()
    assert "races" in payload
    assert "hispanic_or_latino" in payload["races"]
    assert "white" in payload["races"]


@pytest.mark.asyncio
async def test_mass_edit_stage_rejects_effective_at_field(authed_client, db, test_auth):
    disqualified_stage = _get_stage(db, test_auth.org.id, "disqualified")
    await _create_surrogate(authed_client, state="CA")

    # effective_at must be rejected (mass edit cannot be backdated)
    apply_res = await authed_client.post(
        "/surrogates/mass-edit/stage",
        json={
            "filters": {"states": ["CA"]},
            "stage_id": str(disqualified_stage.id),
            "expected_total": 1,
            "effective_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert apply_res.status_code == 422
