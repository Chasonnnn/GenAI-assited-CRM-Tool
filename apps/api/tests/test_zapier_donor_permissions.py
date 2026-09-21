"""Permission boundaries for donor data in the shared Zapier integration."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import JobStatus, JobType, Role
from app.db.models import (
    Donor,
    Job,
    Membership,
    Organization,
    User,
    UserPermissionOverride,
    ZapierOutboundEvent,
)
from app.main import app
from app.services import session_service, zapier_settings_service


def _integration_user(
    db,
    org_id: UUID,
    *,
    can_view_donors: bool,
    can_edit_donors: bool,
) -> User:
    user = User(
        id=uuid4(),
        email=f"zapier-access-{uuid4().hex[:8]}@test.com",
        display_name="Zapier Access Tester",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid4(),
            user_id=user.id,
            organization_id=org_id,
            role=Role.CASE_MANAGER.value,
        )
    )
    db.add_all(
        [
            UserPermissionOverride(
                id=uuid4(),
                organization_id=org_id,
                user_id=user.id,
                permission="manage_integrations",
                override_type="grant",
            ),
            UserPermissionOverride(
                id=uuid4(),
                organization_id=org_id,
                user_id=user.id,
                permission="view_donors",
                override_type="grant" if can_view_donors else "revoke",
            ),
            UserPermissionOverride(
                id=uuid4(),
                organization_id=org_id,
                user_id=user.id,
                permission="edit_donors",
                override_type="grant" if can_edit_donors else "revoke",
            ),
        ]
    )
    db.flush()
    return user


@asynccontextmanager
async def _client_for(db, org_id: UUID, user: User, *, include_csrf: bool = True):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=Role.CASE_MANAGER.value,
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

    csrf_token = generate_csrf_token()
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
            headers={CSRF_HEADER: csrf_token} if include_csrf else None,
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _configure_donor_export(db, org_id: UUID):
    settings = zapier_settings_service.get_or_create_settings(db, org_id)
    settings.outbound_webhook_url = "https://hooks.zapier.com/hooks/catch/original"
    settings.outbound_webhook_secret_encrypted = zapier_settings_service.encrypt_secret(
        "original-secret"
    )
    settings.outbound_send_hashed_pii = False
    settings.donor_outbound_enabled = True
    settings.donor_outbound_event_mapping = [
        {
            "donor_type": "egg",
            "pipeline_id": str(uuid4()),
            "stage_id": str(uuid4()),
            "event_name": "Qualified",
            "enabled": True,
        }
    ]
    db.commit()
    return settings


def _failed_event(db, org_id: UUID, *, donor: bool) -> tuple[Job, ZapierOutboundEvent]:
    job = Job(
        organization_id=org_id,
        job_type=JobType.ZAPIER_STAGE_EVENT.value,
        payload={"data": {"event_id": f"event-{uuid4()}"}},
        status=JobStatus.FAILED.value,
        attempts=3,
        max_attempts=3,
        last_error="Webhook timeout",
    )
    db.add(job)
    db.flush()
    event = ZapierOutboundEvent(
        organization_id=org_id,
        source="automatic",
        status="failed",
        job_id=job.id,
        event_id=f"event-{uuid4()}",
        event_name="Qualified",
        lead_id=f"lead-{uuid4()}",
        stage_key="qualified",
        stage_label="Qualified",
        donor_type="egg" if donor else None,
        attempts=3,
        last_error="Webhook timeout",
        last_attempt_at=datetime.now(UTC),
    )
    db.add(event)
    db.commit()
    return job, event


@pytest.mark.asyncio
async def test_zapier_settings_omit_donor_config_without_view_permission(db, test_org):
    _configure_donor_export(db, test_org.id)
    user = _integration_user(
        db,
        test_org.id,
        can_view_donors=False,
        can_edit_donors=False,
    )

    async with _client_for(db, test_org.id, user) as client:
        response = await client.get("/integrations/zapier/settings")

    assert response.status_code == 200
    assert "donor_outbound_enabled" not in response.json()
    assert "donor_event_mapping" not in response.json()
    assert response.json()["outbound_webhook_url"].endswith("/original")


@pytest.mark.asyncio
async def test_zapier_donor_settings_require_view_and_edit_permissions(db, test_org):
    settings = _configure_donor_export(db, test_org.id)
    no_view = _integration_user(
        db,
        test_org.id,
        can_view_donors=False,
        can_edit_donors=False,
    )
    view_only = _integration_user(
        db,
        test_org.id,
        can_view_donors=True,
        can_edit_donors=False,
    )
    editor = _integration_user(
        db,
        test_org.id,
        can_view_donors=True,
        can_edit_donors=True,
    )

    async with _client_for(db, test_org.id, no_view) as client:
        denied_view = await client.post(
            "/integrations/zapier/settings/outbound",
            json={"donor_outbound_enabled": False},
        )
    assert denied_view.status_code == 403
    assert denied_view.json()["detail"] == "Missing permission: view_donors"

    async with _client_for(db, test_org.id, view_only) as client:
        denied_edit = await client.post(
            "/integrations/zapier/settings/outbound",
            json={"donor_outbound_enabled": False},
        )
    assert denied_edit.status_code == 403
    assert denied_edit.json()["detail"] == "Missing permission: edit_donors"

    db.refresh(settings)
    assert settings.donor_outbound_enabled is True

    async with _client_for(db, test_org.id, editor) as client:
        allowed = await client.post(
            "/integrations/zapier/settings/outbound",
            json={"donor_outbound_enabled": False},
        )
    assert allowed.status_code == 200
    assert allowed.json()["donor_outbound_enabled"] is False
    assert "donor_event_mapping" in allowed.json()


@pytest.mark.asyncio
async def test_zapier_shared_delivery_settings_require_donor_edit_only_while_enabled(db, test_org):
    settings = _configure_donor_export(db, test_org.id)
    user = _integration_user(
        db,
        test_org.id,
        can_view_donors=True,
        can_edit_donors=False,
    )

    async with _client_for(db, test_org.id, user) as client:
        unchanged = await client.post(
            "/integrations/zapier/settings/outbound",
            json={
                "outbound_webhook_url": "https://hooks.zapier.com/hooks/catch/original",
                "outbound_webhook_secret": "original-secret",
                "outbound_enabled": True,
                "send_hashed_pii": False,
            },
        )
        assert unchanged.status_code == 200

        for payload in (
            {"outbound_webhook_url": "https://hooks.zapier.com/hooks/catch/changed"},
            {"outbound_webhook_secret": "changed-secret"},
            {"send_hashed_pii": True},
        ):
            response = await client.post(
                "/integrations/zapier/settings/outbound",
                json=payload,
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Missing permission: edit_donors"

        settings.donor_outbound_enabled = False
        db.commit()
        allowed = await client.post(
            "/integrations/zapier/settings/outbound",
            json={"outbound_webhook_url": "https://hooks.zapier.com/hooks/catch/changed"},
        )

    assert allowed.status_code == 200
    assert allowed.json()["outbound_webhook_url"].endswith("/changed")


@pytest.mark.asyncio
async def test_zapier_unicode_shared_secret_comparison_preserves_donor_access_boundary(
    db, test_org
):
    settings = _configure_donor_export(db, test_org.id)
    unicode_secret = "zapier-sécret-🔐"
    settings.outbound_webhook_secret_encrypted = zapier_settings_service.encrypt_secret(
        unicode_secret
    )
    db.commit()
    user = _integration_user(
        db,
        test_org.id,
        can_view_donors=True,
        can_edit_donors=False,
    )

    async with _client_for(db, test_org.id, user) as client:
        unchanged = await client.post(
            "/integrations/zapier/settings/outbound",
            json={
                "outbound_webhook_secret": unicode_secret,
                "outbound_enabled": True,
            },
        )
        changed = await client.post(
            "/integrations/zapier/settings/outbound",
            json={"outbound_webhook_secret": "zapier-sécret-changé-🔑"},
        )

    assert unchanged.status_code == 200
    assert changed.status_code == 403
    assert changed.json()["detail"] == "Missing permission: edit_donors"


@pytest.mark.asyncio
async def test_zapier_monitoring_filters_donor_events_without_view_permission(
    db, test_org, default_stage
):
    now = datetime.now(UTC)
    donor = Donor(
        organization_id=test_org.id,
        donor_number="D10001",
        donor_type="egg",
        full_name="Private donor",
        email="private-donor@example.com",
        email_hash="0" * 64,
        stage_id=default_stage.id,
    )
    db.add(donor)
    db.flush()
    db.add_all(
        [
            ZapierOutboundEvent(
                organization_id=test_org.id,
                source="automatic",
                status="delivered",
                event_id="surrogate-event",
                event_name="Qualified",
                lead_id="surrogate-lead",
                stage_key="qualified",
                stage_label="Qualified",
                attempts=1,
                created_at=now - timedelta(minutes=2),
                updated_at=now - timedelta(minutes=2),
                delivered_at=now - timedelta(minutes=2),
            ),
            ZapierOutboundEvent(
                organization_id=test_org.id,
                source="automatic",
                status="failed",
                event_id="donor-event",
                event_name="Converted",
                lead_id="private-donor-lead",
                stage_key="ready_to_match",
                stage_label="Private donor stage",
                donor_type="egg",
                attempts=3,
                last_error="Webhook timeout",
                created_at=now - timedelta(minutes=1),
                updated_at=now - timedelta(minutes=1),
                last_attempt_at=now - timedelta(minutes=1),
            ),
            ZapierOutboundEvent(
                organization_id=test_org.id,
                source="automatic",
                status="queued",
                event_id="legacy-donor-event",
                event_name="Lead",
                lead_id="private-legacy-donor-lead",
                stage_key="new",
                stage_label="Private legacy donor stage",
                donor_id=donor.id,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db.commit()
    no_view = _integration_user(
        db,
        test_org.id,
        can_view_donors=False,
        can_edit_donors=False,
    )
    viewer = _integration_user(
        db,
        test_org.id,
        can_view_donors=True,
        can_edit_donors=False,
    )

    async with _client_for(db, test_org.id, no_view) as client:
        events = await client.get("/integrations/zapier/events")
        summary = await client.get("/integrations/zapier/events/summary")
    assert events.status_code == 200
    assert events.json()["total"] == 1
    assert [item["event_id"] for item in events.json()["items"]] == ["surrogate-event"]
    assert summary.status_code == 200
    assert summary.json()["total_count"] == 1
    assert summary.json()["failed_count"] == 0

    async with _client_for(db, test_org.id, viewer) as client:
        visible = await client.get("/integrations/zapier/events")
    assert visible.status_code == 200
    assert visible.json()["total"] == 3
    assert {item["event_id"] for item in visible.json()["items"]} == {
        "surrogate-event",
        "donor-event",
        "legacy-donor-event",
    }


@pytest.mark.asyncio
async def test_zapier_donor_retry_requires_edit_and_remains_org_scoped(db, test_org):
    job, event = _failed_event(db, test_org.id, donor=True)
    no_view = _integration_user(
        db,
        test_org.id,
        can_view_donors=False,
        can_edit_donors=False,
    )
    view_only = _integration_user(
        db,
        test_org.id,
        can_view_donors=True,
        can_edit_donors=False,
    )
    editor = _integration_user(
        db,
        test_org.id,
        can_view_donors=True,
        can_edit_donors=True,
    )

    async with _client_for(db, test_org.id, no_view) as client:
        denied_view = await client.post(
            f"/integrations/zapier/events/{event.id}/retry",
            json={},
        )
    assert denied_view.status_code == 403
    assert denied_view.json()["detail"] == "Missing permission: view_donors"

    async with _client_for(db, test_org.id, view_only) as client:
        denied_edit = await client.post(
            f"/integrations/zapier/events/{event.id}/retry",
            json={},
        )
    assert denied_edit.status_code == 403
    assert denied_edit.json()["detail"] == "Missing permission: edit_donors"

    other_org = Organization(
        id=uuid4(),
        name="Other Zapier tenant",
        slug=f"other-zapier-{uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.commit()
    _other_job, other_event = _failed_event(db, other_org.id, donor=True)
    async with _client_for(db, test_org.id, editor) as client:
        cross_org = await client.post(
            f"/integrations/zapier/events/{other_event.id}/retry",
            json={},
        )
        allowed = await client.post(
            f"/integrations/zapier/events/{event.id}/retry",
            json={},
        )

    assert cross_org.status_code == 404
    assert allowed.status_code == 200
    db.refresh(job)
    assert job.status == JobStatus.PENDING.value


@pytest.mark.asyncio
async def test_zapier_surrogate_retry_remains_available_without_donor_permissions(db, test_org):
    job, event = _failed_event(db, test_org.id, donor=False)
    user = _integration_user(
        db,
        test_org.id,
        can_view_donors=False,
        can_edit_donors=False,
    )

    async with _client_for(db, test_org.id, user) as client:
        response = await client.post(
            f"/integrations/zapier/events/{event.id}/retry",
            json={},
        )

    assert response.status_code == 200
    db.refresh(job)
    assert job.status == JobStatus.PENDING.value


@pytest.mark.asyncio
async def test_zapier_donor_settings_update_keeps_csrf_guard(db, test_org):
    _configure_donor_export(db, test_org.id)
    editor = _integration_user(
        db,
        test_org.id,
        can_view_donors=True,
        can_edit_donors=True,
    )

    async with _client_for(db, test_org.id, editor, include_csrf=False) as client:
        response = await client.post(
            "/integrations/zapier/settings/outbound",
            json={"donor_outbound_enabled": False},
        )

    assert response.status_code == 403
    assert "Missing or invalid CSRF token" in response.json()["detail"]
