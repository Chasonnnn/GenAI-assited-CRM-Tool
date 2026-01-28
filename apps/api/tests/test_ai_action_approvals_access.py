from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import (
    AIActionApproval,
    AIConversation,
    AIMessage,
    Membership,
    Surrogate,
    User,
    UserPermissionOverride,
)
from app.main import app
from app.services import session_service
from app.utils.normalization import normalize_email


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


@pytest.mark.asyncio
async def test_ai_action_approval_requires_surrogate_access(
    db, test_org, test_user, default_stage
):
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

    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=intake_user.id,
            permission="approve_ai_actions",
            override_type="grant",
        )
    )

    normalized_email = normalize_email("access@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Access Test",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    conversation = AIConversation(
        organization_id=test_org.id,
        user_id=intake_user.id,
        entity_type="surrogate",
        entity_id=surrogate.id,
    )
    db.add(conversation)
    db.flush()

    message = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content="Suggested action",
        proposed_actions=[{"type": "add_note", "content": "AI note"}],
    )
    db.add(message)
    db.flush()

    approval = AIActionApproval(
        message_id=message.id,
        action_index=0,
        action_type="add_note",
        action_payload={"type": "add_note", "content": "AI note"},
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(approval)
    db.flush()

    async with _authed_client_for_user(
        db, test_org.id, intake_user, Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.post(f"/ai/actions/{approval.id}/approve")
        assert response.status_code == 403
