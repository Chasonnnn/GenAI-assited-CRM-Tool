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
