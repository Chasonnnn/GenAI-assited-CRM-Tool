import pytest

from app.core.config import settings
from app.core.deps import COOKIE_NAME
from app.services import session_service


@pytest.mark.asyncio
async def test_dev_login_creates_session(client, db, test_user):
    response = await client.post(
        f"/dev/login-as/{test_user.id}",
        headers={"X-Dev-Secret": settings.DEV_SECRET},
    )

    assert response.status_code == 200

    token = response.cookies.get(COOKIE_NAME) or client.cookies.get(COOKIE_NAME)
    assert token

    token_hash = session_service.hash_token(token)
    db_session = session_service.get_session_by_token_hash(db, token_hash)
    assert db_session is not None

    me_response = await client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["user_id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_dev_seed_idempotent_and_includes_developer(client):
    headers = {"X-Dev-Secret": settings.DEV_SECRET}

    first = await client.post("/dev/seed", headers=headers)
    assert first.status_code == 200
    first_payload = first.json()

    expected_roles = {
        "admin@test.com": "admin",
        "intake@test.com": "intake_specialist",
        "specialist@test.com": "case_manager",
        "developer@test.com": "developer",
    }
    first_roles = {u["email"]: u["role"] for u in first_payload["users"]}
    assert first_roles == expected_roles
    assert first_payload["org_slug"] == "test-org"

    second = await client.post("/dev/seed", headers=headers)
    assert second.status_code == 200
    second_payload = second.json()

    second_roles = {u["email"]: u["role"] for u in second_payload["users"]}
    assert second_roles == expected_roles
    assert second_payload["org_id"] == first_payload["org_id"]


@pytest.mark.asyncio
async def test_dev_login_as_seeded_developer(client):
    headers = {"X-Dev-Secret": settings.DEV_SECRET}
    seed_response = await client.post("/dev/seed", headers=headers)
    assert seed_response.status_code == 200
    payload = seed_response.json()

    developer_id = next(u["user_id"] for u in payload["users"] if u["role"] == "developer")

    login_response = await client.post(f"/dev/login-as/{developer_id}", headers=headers)
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["role"] == "developer"
    assert login_payload["email"] == "developer@test.com"
