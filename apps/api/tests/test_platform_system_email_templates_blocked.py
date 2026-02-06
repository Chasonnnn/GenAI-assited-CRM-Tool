from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_platform_system_templates_blocked_in_org_endpoints(
    authed_client, db, test_org, test_user
):
    from app.db.models import EmailTemplate

    legacy_platform_invite = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Organization Invite",
        subject="Invitation to join {{org_name}} as {{role_title}}",
        body="<p>Invite</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
        is_system_template=True,
        system_key="org_invite",
    )
    db.add(legacy_platform_invite)
    db.commit()

    # Copy should always be blocked (even though it doesn't require manage permission)
    res = await authed_client.post(
        f"/email-templates/{legacy_platform_invite.id}/copy",
        json={"name": "Copy"},
    )
    assert res.status_code == 403
    assert "platform" in (res.text or "").lower()

    # Test send should be blocked
    res = await authed_client.post(
        f"/email-templates/{legacy_platform_invite.id}/test",
        json={"to_email": "test@example.com"},
    )
    assert res.status_code == 403
    assert "platform" in (res.text or "").lower()

    # Org send endpoint should be blocked (must use platform/system sender)
    res = await authed_client.post(
        "/email-templates/send",
        json={"template_id": str(legacy_platform_invite.id), "recipient_email": "test@example.com"},
    )
    assert res.status_code == 403
    assert "platform" in (res.text or "").lower()
