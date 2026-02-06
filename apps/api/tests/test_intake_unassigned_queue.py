import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import OwnerType, Role
from app.db.models import Membership, Surrogate, User
from app.main import app
from app.services import queue_service, session_service
from app.utils.normalization import normalize_email


@pytest.mark.asyncio
async def test_intake_can_list_unassigned_queue_and_claim(db, test_org, default_stage):
    intake_user = User(
        id=uuid.uuid4(),
        email=f"intake-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Intake User",
        token_version=1,
        is_active=True,
    )
    db.add(intake_user)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=intake_user.id,
            organization_id=test_org.id,
            role=Role.INTAKE_SPECIALIST,
            is_active=True,
        )
    )
    db.flush()

    default_queue = queue_service.get_or_create_default_queue(db, test_org.id)

    normalized_email = normalize_email(f"unassigned-{uuid.uuid4().hex[:8]}@example.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type=OwnerType.QUEUE.value,
        owner_id=default_queue.id,
        created_by_user_id=None,
        full_name="Unassigned Lead",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    token = create_session_token(
        user_id=intake_user.id,
        org_id=test_org.id,
        role=Role.INTAKE_SPECIALIST.value,
        token_version=intake_user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=intake_user.id, org_id=test_org.id, token=token, request=None)

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
        resp = await client.get("/surrogates/unassigned-queue")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert any(item["id"] == str(surrogate.id) for item in data["items"])

        claim = await client.post(f"/surrogates/{surrogate.id}/claim")
        assert claim.status_code == 200, claim.text

        detail = await client.get(f"/surrogates/{surrogate.id}")
        assert detail.status_code == 200, detail.text
        detail_data = detail.json()
        assert detail_data["owner_type"] == "user"
        assert detail_data["owner_id"] == str(intake_user.id)

        after = await client.get("/surrogates/unassigned-queue")
        assert after.status_code == 200, after.text
        after_data = after.json()
        assert not any(item["id"] == str(surrogate.id) for item in after_data["items"])

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_intake_cannot_access_other_users_surrogate(db, test_org, default_stage):
    intake_user = User(
        id=uuid.uuid4(),
        email=f"intake-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Intake User",
        token_version=1,
        is_active=True,
    )
    other_user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other User",
        token_version=1,
        is_active=True,
    )
    db.add_all([intake_user, other_user])
    db.flush()

    db.add_all(
        [
            Membership(
                id=uuid.uuid4(),
                user_id=intake_user.id,
                organization_id=test_org.id,
                role=Role.INTAKE_SPECIALIST,
                is_active=True,
            ),
            Membership(
                id=uuid.uuid4(),
                user_id=other_user.id,
                organization_id=test_org.id,
                role=Role.CASE_MANAGER,
                is_active=True,
            ),
        ]
    )
    db.flush()

    normalized_email = normalize_email(f"owned-by-other-{uuid.uuid4().hex[:8]}@example.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type=OwnerType.USER.value,
        owner_id=other_user.id,
        created_by_user_id=other_user.id,
        full_name="Owned By Other",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    token = create_session_token(
        user_id=intake_user.id,
        org_id=test_org.id,
        role=Role.INTAKE_SPECIALIST.value,
        token_version=intake_user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=intake_user.id, org_id=test_org.id, token=token, request=None)

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
        resp = await client.get(f"/surrogates/{surrogate.id}")
        assert resp.status_code == 403, resp.text

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_intake_cannot_view_surrogate_pool_claim_queue(db, test_org):
    intake_user = User(
        id=uuid.uuid4(),
        email=f"intake-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Intake User",
        token_version=1,
        is_active=True,
    )
    db.add(intake_user)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=intake_user.id,
            organization_id=test_org.id,
            role=Role.INTAKE_SPECIALIST,
            is_active=True,
        )
    )
    db.flush()

    token = create_session_token(
        user_id=intake_user.id,
        org_id=test_org.id,
        role=Role.INTAKE_SPECIALIST.value,
        token_version=intake_user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=intake_user.id, org_id=test_org.id, token=token, request=None)

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
        resp = await client.get("/surrogates/claim-queue")
        assert resp.status_code == 403, resp.text

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_intake_cannot_claim_from_non_unassigned_queue(db, test_org, default_stage):
    intake_user = User(
        id=uuid.uuid4(),
        email=f"intake-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Intake User",
        token_version=1,
        is_active=True,
    )
    db.add(intake_user)
    db.flush()

    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=intake_user.id,
            organization_id=test_org.id,
            role=Role.INTAKE_SPECIALIST,
            is_active=True,
        )
    )
    db.flush()

    # Create a non-default queue and a surrogate owned by it
    q = queue_service.create_queue(db=db, org_id=test_org.id, name=f"Queue {uuid.uuid4().hex[:6]}")
    db.flush()

    normalized_email = normalize_email(f"queue-owned-{uuid.uuid4().hex[:8]}@example.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type=OwnerType.QUEUE.value,
        owner_id=q.id,
        created_by_user_id=None,
        full_name="Queue Owned",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    token = create_session_token(
        user_id=intake_user.id,
        org_id=test_org.id,
        role=Role.INTAKE_SPECIALIST.value,
        token_version=intake_user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(db=db, user_id=intake_user.id, org_id=test_org.id, token=token, request=None)

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
        resp = await client.post(f"/surrogates/{surrogate.id}/claim")
        assert resp.status_code == 403, resp.text

    app.dependency_overrides.clear()

