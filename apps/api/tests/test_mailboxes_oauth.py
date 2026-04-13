from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.core.security import create_oauth_state_payload, generate_oauth_nonce


@pytest.fixture
def rate_limiter_reset():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.mark.asyncio
async def test_journal_mailbox_oauth_start_rate_limited(
    authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    rate_limiter_reset,
):
    from app.services import oauth_service

    calls = {"count": 0}

    def build_auth_url(*_args, **_kwargs) -> str:
        calls["count"] += 1
        return "https://example.com/oauth?state=test-state"

    monkeypatch.setattr(oauth_service, "get_gmail_auth_url", build_auth_url)

    for _ in range(5):
        response = await authed_client.post("/mailboxes/journal/gmail/oauth/start")
        assert response.status_code == 200, response.text

    blocked = await authed_client.post("/mailboxes/journal/gmail/oauth/start")

    assert blocked.status_code == 429
    assert calls["count"] == 5


@pytest.mark.asyncio
async def test_journal_mailbox_oauth_callback_rate_limited(
    authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    rate_limiter_reset,
):
    from app.services import audit_service, oauth_service, ticketing_service

    calls = {"count": 0}

    async def exchange_code(*_args, **_kwargs):
        calls["count"] += 1
        return {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/gmail.modify",
        }

    async def get_user_info(*_args, **_kwargs):
        return {"email": "journal@example.com"}

    monkeypatch.setattr(oauth_service, "exchange_gmail_code", exchange_code)
    monkeypatch.setattr(oauth_service, "get_gmail_user_info", get_user_info)
    monkeypatch.setattr(
        ticketing_service,
        "parse_granted_scopes_from_tokens",
        lambda _tokens: ["https://www.googleapis.com/auth/gmail.modify"],
    )
    monkeypatch.setattr(
        ticketing_service,
        "create_or_update_journal_mailbox",
        lambda *_args, **_kwargs: SimpleNamespace(id=uuid.uuid4()),
    )
    monkeypatch.setattr(audit_service, "log_event", lambda *_args, **_kwargs: None)

    user_agent = "pytest-mailboxes-agent"
    state = "journal-state"
    authed_client.cookies.set(
        "journal_mailbox_oauth_state",
        create_oauth_state_payload(state, generate_oauth_nonce(), user_agent),
    )

    for _ in range(5):
        authed_client.cookies.set(
            "journal_mailbox_oauth_state",
            create_oauth_state_payload(state, generate_oauth_nonce(), user_agent),
        )
        response = await authed_client.get(
            "/mailboxes/journal/gmail/oauth/callback",
            params={"code": "dummy-code", "state": state},
            follow_redirects=False,
            headers={"user-agent": user_agent},
        )
        assert response.status_code == 302, response.text

    authed_client.cookies.set(
        "journal_mailbox_oauth_state",
        create_oauth_state_payload(state, generate_oauth_nonce(), user_agent),
    )
    blocked = await authed_client.get(
        "/mailboxes/journal/gmail/oauth/callback",
        params={"code": "dummy-code", "state": state},
        follow_redirects=False,
        headers={"user-agent": user_agent},
    )

    assert blocked.status_code == 429
    assert calls["count"] == 5
