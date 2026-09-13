"""Staff availability exposes no configuration or provider credentials."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_workflow_personal_defaults_v2 import client_for
from test_workflow_personal_defaults_v2 import staff as staff_fixture

from app.db.models import AISettings, Organization

staff = staff_fixture


@pytest.mark.asyncio
async def test_staff_reads_availability_without_ai_settings_permission(db, staff):
    org, user, _ = staff
    db.add(
        AISettings(
            organization_id=org.id,
            is_enabled=True,
            provider="gemini",
            model="gemini-3.8-flash",
            api_key_encrypted="unread-test-ciphertext",
            consent_accepted_at=datetime.now(UTC),
        )
    )
    db.flush()
    async with client_for(db, org, user) as client:
        response = await client.get("/ai/availability")
        assert response.status_code == 200
        assert response.json() == {
            "is_enabled": True,
            "provider": "gemini",
            "model": "gemini-3.8-flash",
        }
        settings = await client.get("/ai/settings")
        assert settings.status_code == 403
        update = await client.patch("/ai/settings", json={"is_enabled": False})
        assert update.status_code == 403


@pytest.mark.asyncio
async def test_disabled_availability_is_readable_and_does_not_create_settings(db, staff):
    org, user, _ = staff
    org.ai_enabled = False
    db.flush()
    async with client_for(db, org, user) as client:
        response = await client.get("/ai/availability")
    assert response.status_code == 200
    assert response.json() == {"is_enabled": False, "provider": None, "model": None}
    assert db.query(AISettings).filter_by(organization_id=org.id).count() == 0


@pytest.mark.asyncio
async def test_availability_cannot_select_another_organizations_configuration(db, staff):
    org, user, _ = staff
    other = Organization(id=uuid4(), name="Other", slug=f"other-{uuid4()}", ai_enabled=True)
    db.add(other)
    db.flush()
    db.add(
        AISettings(
            organization_id=other.id,
            is_enabled=True,
            provider="gemini",
            model="gemini-3.8-flash",
            consent_accepted_at=datetime.now(UTC),
        )
    )
    db.flush()
    async with client_for(db, org, user) as client:
        response = await client.get(f"/ai/availability?organization_id={other.id}")
    assert response.status_code == 200
    assert response.json() == {"is_enabled": False, "provider": None, "model": None}


@pytest.mark.asyncio
async def test_inactive_membership_cannot_read_availability(db, staff):
    org, user, membership = staff
    async with client_for(db, org, user) as client:
        membership.is_active = False
        db.flush()
        response = await client.get("/ai/availability")
    assert response.status_code == 403
