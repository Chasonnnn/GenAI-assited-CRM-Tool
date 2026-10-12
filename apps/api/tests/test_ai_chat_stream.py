import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from anyio import CapacityLimiter
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.models import AIMessage, AISettings
from app.services import ai_settings_service
from app.services.ai_provider import ChatStreamChunk


def _create_ai_settings(db, org_id, user_id) -> AISettings:
    settings = AISettings(
        organization_id=org_id,
        is_enabled=True,
        provider="gemini",
        model="gemini-3.8-flash",
        current_version=1,
        consent_accepted_at=datetime.now(UTC),
        consent_accepted_by=user_id,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()
    db.commit()
    return settings


@pytest.mark.asyncio
async def test_chat_stream_returns_events(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    _create_ai_settings(db, test_org.id, test_user.id)

    class StubProvider:
        async def stream_chat(self, messages, **kwargs):  # noqa: ARG002
            yield ChatStreamChunk(text="Hello", model="gemini-3.8-flash")
            yield ChatStreamChunk(text=" world", model="gemini-3.8-flash")
            yield ChatStreamChunk(
                text="",
                prompt_tokens=1,
                completion_tokens=2,
                total_tokens=3,
                model="gemini-3.8-flash",
                is_final=True,
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    response = await authed_client.post("/ai/chat/stream", json={"message": "Hi"})
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/event-stream")
    body = response.text
    assert "event: delta" in body
    assert "Hello" in body
    assert "event: done" in body

    messages = db.query(AIMessage).all()
    assert any(msg.role == "assistant" for msg in messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("concurrency", [1, 2])
async def test_chat_streams_complete_with_one_connection_per_request(
    db_engine, monkeypatch, concurrency
):
    from app.core import deps
    from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
    from app.core.security import create_session_token
    from app.db.enums import Role
    from app.db.models import AuditLog, Membership, Organization, User
    from app.main import app
    from app.services import session_service

    request_engine = create_engine(
        db_engine.url, pool_size=concurrency, max_overflow=0, pool_timeout=0.3
    )
    monkeypatch.setattr(deps, "SessionLocal", sessionmaker(bind=request_engine))
    monkeypatch.setattr(
        app.state, "request_db_limiter", CapacityLimiter(concurrency), raising=False
    )
    org_id, user_id = uuid4(), uuid4()
    barrier = asyncio.Barrier(concurrency)

    class StubProvider:
        async def stream_chat(self, messages, **kwargs):
            await asyncio.wait_for(barrier.wait(), timeout=2)
            yield ChatStreamChunk(text="Hello", model="gemini-3.8-flash")
            yield ChatStreamChunk(text="", model="gemini-3.8-flash", is_final=True)

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider", lambda *_args, **_kwargs: StubProvider()
    )
    try:
        # Independent request sessions must see committed fixture data.
        with sessionmaker(bind=db_engine)() as seed:
            seed.add_all(
                [
                    Organization(
                        id=org_id, name="Stream QA", slug=f"stream-{org_id}", ai_enabled=True
                    ),
                    User(
                        id=user_id,
                        email=f"stream-{user_id}@example.test",
                        display_name="Stream QA",
                        token_version=1,
                        is_active=True,
                    ),
                ]
            )
            seed.flush()
            seed.add(Membership(user_id=user_id, organization_id=org_id, role=Role.DEVELOPER))
            _create_ai_settings(seed, org_id, user_id)
            token = create_session_token(
                user_id=user_id,
                org_id=org_id,
                role=Role.DEVELOPER.value,
                token_version=1,
                mfa_verified=True,
                mfa_required=True,
            )
            session_service.create_session(
                db=seed, user_id=user_id, org_id=org_id, token=token, request=None
            )
            seed.commit()

        csrf = generate_csrf_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={deps.COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf},
            headers={CSRF_HEADER: csrf},
        ) as client:
            responses = await asyncio.gather(
                *(
                    client.post("/ai/chat/stream", json={"message": "Hi"})
                    for _ in range(concurrency)
                )
            )
            for response in responses:
                assert response.status_code == 200
                assert "event: done" in response.text, response.text
                assert "event: error" not in response.text
            assert (await client.get("/auth/me")).status_code == 200
        assert request_engine.pool.checkedout() == 0
        with sessionmaker(bind=db_engine)() as observer:
            from app.db.models import AIConversation

            messages = (
                observer.query(AIMessage)
                .join(AIConversation)
                .filter(AIConversation.organization_id == org_id, AIMessage.role == "assistant")
                .all()
            )
            assert len(messages) == concurrency
    finally:
        request_engine.dispose()
        with sessionmaker(bind=db_engine)() as cleanup:
            cleanup.execute(text("SET LOCAL session_replication_role = replica"))
            cleanup.query(AuditLog).filter(AuditLog.organization_id == org_id).delete()
            cleanup.execute(text("SET LOCAL session_replication_role = origin"))
            cleanup.query(Organization).filter(Organization.id == org_id).delete(
                synchronize_session=False
            )
            cleanup.query(User).filter(User.id == user_id).delete(synchronize_session=False)
            cleanup.commit()
