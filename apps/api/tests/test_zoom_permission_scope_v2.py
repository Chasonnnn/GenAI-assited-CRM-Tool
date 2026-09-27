"""Zoom actions authorize the saved record subject before provider work."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import EntityType, Role
from app.db.models import (
    Organization,
    OrganizationPermissionPolicy,
    RolePermission,
    RoleRecordScope,
    User,
    UserPermissionOverride,
    ZoomMeeting,
)
from app.services import zoom_service
from tests.test_email_templates_personal_scope import authed_client_for_user
from tests.test_record_scopes_v2 import _member, _record
from tests.test_record_scopes_v2 import context as context


def _grant(db, actor, permission):
    db.add(
        UserPermissionOverride(
            organization_id=actor.org_id,
            user_id=actor.user_id,
            permission=permission,
            override_type="grant",
        )
    )
    db.flush()


def _hide_kind(db, actor, kind):
    db.add(
        RoleRecordScope(
            organization_id=actor.org_id,
            role=actor.role.value,
            module="surrogates" if kind == "surrogate" else "intended_parents",
            assignment="none",
            phase="all",
            stage_ids=[],
        )
    )
    db.flush()


def _foreign_owner(db):
    org = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
    db.add(org)
    db.flush()
    return _member(db, org.id, "admin")[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["surrogate", "intended_parent"])
@pytest.mark.parametrize(
    "access", ["readonly", "delegated", "outside_scope", "other_org", "no_view"]
)
async def test_zoom_creation_requires_appointment_action_and_subject_scope(
    db, context, monkeypatch, kind, access
):
    actor, _ = _member(db, context.org.id, "operations")
    if access != "readonly":
        _grant(db, actor, "manage_appointments")
    if access == "outside_scope":
        _hide_kind(db, actor, kind)
    if access == "no_view":
        db.add(
            RolePermission(
                organization_id=context.org.id,
                role="operations",
                is_granted=False,
                permission="view_surrogates" if kind == "surrogate" else "view_intended_parents",
            )
        )
        db.flush()
    record = _record(db, _foreign_owner(db) if access == "other_org" else actor, kind)
    connected = Mock(return_value=True)
    schedule = AsyncMock(
        return_value=zoom_service.CreateMeetingResult(
            meeting=zoom_service.ZoomMeeting(
                id=123,
                uuid="synthetic",
                topic="Synthetic meeting",
                start_time=None,
                duration=30,
                timezone="UTC",
                join_url="https://example.test/j/123",
                start_url="https://example.test/s/123",
            )
        )
    )
    monkeypatch.setattr(zoom_service, "check_user_has_zoom", connected)
    monkeypatch.setattr(zoom_service, "schedule_zoom_meeting", schedule)
    async with authed_client_for_user(
        db, context.org.id, db.get(User, actor.user_id), Role.OPERATIONS
    ) as client:
        response = await client.post(
            "/integrations/zoom/meetings",
            json={
                "entity_type": kind,
                "entity_id": str(record.id),
                "topic": "Synthetic meeting",
            },
        )
    expected = 200 if access == "delegated" else 404 if access == "other_org" else 403
    assert response.status_code == expected, response.text
    if access == "delegated":
        schedule.assert_awaited_once()
        assert schedule.call_args.kwargs["entity_id"] == record.id
        assert schedule.call_args.kwargs["org_id"] == context.org.id
    else:
        connected.assert_not_called()
        schedule.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["surrogate", "intended_parent"])
@pytest.mark.parametrize(
    "access",
    [
        "readonly",
        "delegated",
        "outside_scope",
        "other_org",
        "missing_meeting",
        "mismatched_subject",
    ],
)
async def test_zoom_invite_requires_email_action_and_saved_subject_scope(
    db, context, monkeypatch, kind, access
):
    actor, _ = _member(db, context.org.id, "operations")
    if access != "readonly":
        _grant(db, actor, "send_email")
    if access == "outside_scope":
        _hide_kind(db, actor, kind)
    owner = _foreign_owner(db) if access == "other_org" else actor
    record = _record(db, owner, kind)
    meeting = ZoomMeeting(
        organization_id=owner.org_id,
        user_id=owner.user_id,
        surrogate_id=record.id if kind == "surrogate" else None,
        intended_parent_id=record.id if kind == "intended_parent" else None,
        zoom_meeting_id="456",
        topic="Stored meeting",
        duration=30,
        timezone="UTC",
        join_url="https://example.test/j/456",
        start_url="https://example.test/s/456",
    )
    db.add(meeting)
    db.flush()
    send = Mock(return_value=uuid4())
    monkeypatch.setattr(zoom_service, "send_meeting_invite", send)
    payload = {
        "recipient_email": "applicant@example.test",
        "meeting_id": 999 if access == "missing_meeting" else 456,
        "join_url": "https://untrusted.example.test/changed",
        "topic": "Changed request topic",
        "contact_name": "Synthetic applicant",
    }
    if access == "mismatched_subject":
        payload["surrogate_id"] = str(uuid4())
    async with authed_client_for_user(
        db, context.org.id, db.get(User, actor.user_id), Role.OPERATIONS
    ) as client:
        response = await client.post("/integrations/zoom/send-invite", json=payload)
    expected = (
        200
        if access == "delegated"
        else 404
        if access in {"other_org", "missing_meeting"}
        else 400
        if access == "mismatched_subject"
        else 403
    )
    assert response.status_code == expected, response.text
    if access == "delegated":
        send.assert_called_once()
        assert send.call_args.kwargs["meeting"].topic == meeting.topic
        assert send.call_args.kwargs["meeting"].join_url == meeting.join_url
        assert send.call_args.kwargs["surrogate_id"] == meeting.surrogate_id
    else:
        send.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("retry", ["same_meeting", "different_record", "different_user"])
async def test_zoom_retry_key_is_bound_to_actor_and_subject(db, context, monkeypatch, retry):
    actor, _ = _member(db, context.org.id, "operations")
    _grant(db, actor, "manage_appointments")
    record = _record(db, actor, "surrogate")
    other_record = _record(db, actor, "surrogate", suffix=2)
    saved = ZoomMeeting(
        organization_id=context.org.id,
        user_id=context.manager.user_id if retry == "different_user" else actor.user_id,
        surrogate_id=other_record.id if retry == "different_record" else record.id,
        zoom_meeting_id="789",
        idempotency_key="synthetic-retry",
        topic="Saved meeting",
        duration=30,
        timezone="UTC",
        join_url="https://example.test/j/789",
        start_url="https://example.test/s/789",
    )
    db.add(saved)
    db.flush()
    connected = Mock(return_value=True)
    schedule = AsyncMock(
        return_value=zoom_service.CreateMeetingResult(
            meeting=zoom_service._meeting_from_model(saved)
        )
    )
    monkeypatch.setattr(zoom_service, "check_user_has_zoom", connected)
    monkeypatch.setattr(zoom_service, "schedule_zoom_meeting", schedule)
    async with authed_client_for_user(
        db, context.org.id, db.get(User, actor.user_id), Role.OPERATIONS
    ) as client:
        response = await client.post(
            "/integrations/zoom/meetings",
            json={
                "entity_type": "surrogate",
                "entity_id": str(record.id),
                "topic": "Saved meeting",
                "idempotency_key": "synthetic-retry",
            },
        )
    assert response.status_code == (200 if retry == "same_meeting" else 409), response.text
    if retry == "same_meeting":
        schedule.assert_awaited_once()
    else:
        connected.assert_not_called()
        schedule.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_zoom_invite_keeps_existing_unbound_behavior(db, context, monkeypatch):
    db.query(OrganizationPermissionPolicy).filter_by(organization_id=context.org.id).delete()
    db.flush()
    send = Mock(return_value=uuid4())
    monkeypatch.setattr(zoom_service, "send_meeting_invite", send)
    async with authed_client_for_user(
        db, context.org.id, db.get(User, context.manager.user_id), Role.CASE_MANAGER
    ) as client:
        response = await client.post(
            "/integrations/zoom/send-invite",
            json={
                "recipient_email": "applicant@example.test",
                "meeting_id": 123,
                "join_url": "https://example.test/j/123",
                "topic": "Legacy meeting",
                "contact_name": "Synthetic applicant",
                "surrogate_id": "invalid-legacy-id",
            },
        )
    assert response.status_code == 200, response.text
    send.assert_called_once()
    assert send.call_args.kwargs["surrogate_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("race", [False, True])
@pytest.mark.parametrize("binding", ["same", "different_user", "different_subject"])
async def test_zoom_service_validates_actual_retry_return(db, context, monkeypatch, race, binding):
    from app.services import note_service

    record = _record(db, context.manager, "surrogate", key="approved")
    other = _record(db, context.manager, "surrogate", key="approved", suffix=2)

    def insert_winner():
        winner = ZoomMeeting(
            organization_id=context.org.id,
            user_id=context.intake.user_id
            if binding == "different_user"
            else context.manager.user_id,
            surrogate_id=other.id if binding == "different_subject" else record.id,
            zoom_meeting_id="900",
            idempotency_key="concurrent-retry",
            topic="Winner meeting",
            duration=30,
            timezone="UTC",
            join_url="https://example.test/j/900",
            start_url="https://example.test/s/900",
        )
        db.add(winner)
        db.flush()

    token = AsyncMock(return_value="synthetic-token")
    provider = AsyncMock(
        return_value=zoom_service.ZoomMeeting(
            id=901,
            uuid="synthetic",
            topic="New meeting",
            start_time=None,
            duration=30,
            timezone="UTC",
            join_url="https://example.test/j/901",
            start_url="https://example.test/s/901",
        )
    )
    monkeypatch.setattr(zoom_service, "get_user_zoom_token", token)
    monkeypatch.setattr(zoom_service, "create_zoom_meeting", provider)
    monkeypatch.setattr(note_service, "create_note", Mock(return_value=SimpleNamespace(id=uuid4())))
    if not race:
        insert_winner()
    with Session(bind=db.connection(), join_transaction_mode="create_savepoint") as worker_db:
        if race:
            original_rollback = worker_db.rollback

            def rollback_and_insert_winner():
                original_rollback()
                insert_winner()

            monkeypatch.setattr(
                worker_db, "commit", Mock(side_effect=IntegrityError("synthetic race", None, None))
            )
            monkeypatch.setattr(worker_db, "rollback", rollback_and_insert_winner)

        async def retry():
            return await zoom_service.schedule_zoom_meeting(
                worker_db,
                context.manager.user_id,
                context.org.id,
                EntityType.SURROGATE,
                record.id,
                "New meeting",
                idempotency_key="concurrent-retry",
            )

        if binding == "same":
            result = await retry()
            assert result.meeting.id == 900
        else:
            with pytest.raises(HTTPException) as denied:
                await retry()
            assert denied.value.status_code == 409
    if race:
        provider.assert_awaited_once()
    else:
        token.assert_not_awaited()
        provider.assert_not_awaited()
