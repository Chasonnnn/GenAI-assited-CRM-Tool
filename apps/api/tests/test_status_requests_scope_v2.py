"""Status correction review uses record scopes and delegated review authority."""

from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.db.enums import Role
from app.db.models import Organization, StatusChangeRequest, User, UserPermissionOverride
from app.services import status_change_request_service
from tests.test_email_templates_personal_scope import authed_client_for_user
from tests.test_record_scopes_v2 import _member, _record
from tests.test_record_scopes_v2 import context as context


def _request(db, record, kind, target_stage_id=None):
    request = StatusChangeRequest(
        organization_id=record.organization_id,
        entity_type=kind,
        entity_id=record.id,
        target_stage_id=target_stage_id or record.stage_id,
        status="pending",
        effective_at=datetime.now(UTC),
        reason="Synthetic correction",
        requested_by_user_id=record.owner_id,
    )
    db.add(request)
    db.flush()
    return request


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["surrogate", "donor"])
async def test_request_list_detail_and_review_use_same_scope(db, context, kind):
    mine = _record(db, context.intake, kind)
    hidden = _record(db, context.manager, kind, suffix=2)
    visible_request, hidden_request = _request(db, mine, kind), _request(db, hidden, kind)
    other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
    db.add(other)
    db.flush()
    outsider, _ = _member(db, other.id, "admin")
    other_request = _request(db, _record(db, outsider, kind), kind)
    db.add(
        UserPermissionOverride(
            organization_id=context.org.id,
            user_id=context.intake.user_id,
            permission="approve_status_change_requests",
            override_type="grant",
        )
    )
    db.flush()
    async with authed_client_for_user(
        db, context.org.id, db.get(User, context.intake.user_id), Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.get("/status-change-requests?per_page=1")
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["request"]["id"] == str(visible_request.id)
        assert (
            await client.get(f"/status-change-requests/{visible_request.id}")
        ).status_code == 200
        for request in (hidden_request, other_request):
            assert (await client.get(f"/status-change-requests/{request.id}")).status_code == 404
            denied = await client.post(
                f"/status-change-requests/{request.id}/approve",
                headers={"X-CSRF-Token": client.cookies.get("crm_csrf")},
            )
            assert denied.status_code == 404, denied.text
            assert request.status == "pending"


def test_delegated_reviewer_approves_visible_correction_in_one_transaction(
    db, context, monkeypatch
):
    from app.db.models import PipelineStage

    record = _record(db, context.manager, "surrogate", key="approved")
    first = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == record.stage.pipeline_id,
            PipelineStage.stage_key == "new_unread",
        )
        .one()
    )
    request = _request(db, record, "surrogate", first.id)
    db.add(
        UserPermissionOverride(
            organization_id=context.org.id,
            user_id=context.manager.user_id,
            permission="approve_status_change_requests",
            override_type="grant",
        )
    )
    db.flush()
    calls = []
    original_commit = db.commit

    def commit_record_change():
        original_commit()
        calls.append("commit")

    commit = Mock(side_effect=commit_record_change)
    monkeypatch.setattr(db, "commit", commit)
    from app.services import notification_facade, surrogate_events

    event = Mock(side_effect=lambda **kwargs: calls.append("status_event"))
    monkeypatch.setattr(surrogate_events, "handle_status_changed", event)
    monkeypatch.setattr(
        notification_facade, "notify_status_change_request_resolved", lambda **kwargs: None
    )
    result = status_change_request_service.approve_request(
        db, request.id, context.org.id, context.manager.user_id, Role.CASE_MANAGER
    )
    assert result.status == "approved"
    assert record.stage_id == first.id
    assert commit.call_count == 1
    event.assert_called_once()
    assert calls == ["commit", "status_event"]


def test_failed_correction_commit_rolls_back_without_status_events(db, context, monkeypatch):
    from sqlalchemy.orm import Session

    from app.db.models import PipelineStage, SurrogateStatusHistory
    from app.services import surrogate_events

    record = _record(db, context.manager, "surrogate", key="approved")
    original_stage_id = record.stage_id
    target = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == record.stage.pipeline_id,
            PipelineStage.stage_key == "new_unread",
        )
        .one()
    )
    request = _request(db, record, "surrogate", target.id)
    event = Mock()
    monkeypatch.setattr(surrogate_events, "handle_status_changed", event)
    with Session(bind=db.connection(), join_transaction_mode="create_savepoint") as approval_db:
        monkeypatch.setattr(approval_db, "commit", Mock(side_effect=RuntimeError("commit failed")))
        rollback = Mock(wraps=approval_db.rollback)
        monkeypatch.setattr(approval_db, "rollback", rollback)
        with pytest.raises(RuntimeError, match="commit failed"):
            status_change_request_service.approve_request(
                approval_db, request.id, context.org.id, context.admin.user_id, Role.ADMIN
            )
        rollback.assert_called_once()
    event.assert_not_called()
    db.refresh(record)
    db.refresh(request)
    assert record.stage_id == original_stage_id
    assert request.status == "pending"
    assert db.query(SurrogateStatusHistory).filter_by(request_id=request.id).count() == 0


def test_delegated_review_does_not_grant_applicant_approval(db, context):
    from app.db.models import PipelineStage

    record = _record(db, context.manager, "surrogate")
    target = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == record.stage.pipeline_id,
            PipelineStage.stage_key == "approved",
        )
        .one()
    )
    request = _request(db, record, "surrogate", target.id)
    # A reviewer can see this pre-approval record through an explicit scope addition.
    from app.schemas.record_scope import RecordScopeAdditionCreate
    from app.services import record_scope_service

    record_scope_service.add_scope_addition(
        db,
        context.admin,
        context.manager.user_id,
        RecordScopeAdditionCreate(module="surrogates", assignment="all", phase="all"),
    )
    db.add(
        UserPermissionOverride(
            organization_id=context.org.id,
            user_id=context.manager.user_id,
            permission="approve_status_change_requests",
            override_type="grant",
        )
    )
    db.flush()
    with pytest.raises(ValueError, match="Applicant approval permission"):
        status_change_request_service.approve_request(
            db, request.id, context.org.id, context.manager.user_id, Role.CASE_MANAGER
        )
    assert request.status == "pending"
    assert record.stage_id != target.id


@pytest.mark.parametrize("can_approve_applicant", [False, True])
def test_match_cancellation_rechecks_applicant_approval_boundary(
    db, context, monkeypatch, can_approve_applicant
):
    from app.db.models import Match
    from app.schemas.record_scope import RecordScopeAdditionCreate
    from app.services import notification_facade, record_scope_service, surrogate_events

    record_scope_service.add_scope_addition(
        db,
        context.admin,
        context.manager.user_id,
        RecordScopeAdditionCreate(module="surrogates", assignment="all", phase="all"),
    )
    record = _record(db, context.manager, "surrogate")
    parent = _record(db, context.manager, "intended_parent")
    match = Match(
        organization_id=context.org.id,
        match_number="M75001",
        surrogate_id=record.id,
        intended_parent_id=parent.id,
        proposed_by_user_id=context.manager.user_id,
        status="cancel_pending",
    )
    db.add(match)
    db.flush()
    request = StatusChangeRequest(
        organization_id=context.org.id,
        entity_type="match",
        entity_id=match.id,
        target_status="cancelled",
        status="pending",
        effective_at=datetime.now(UTC),
        reason="Synthetic correction",
        requested_by_user_id=context.manager.user_id,
    )
    db.add(request)
    for key in ["approve_status_change_requests"] + (
        ["approve_surrogates"] if can_approve_applicant else []
    ):
        db.add(
            UserPermissionOverride(
                organization_id=context.org.id,
                user_id=context.manager.user_id,
                permission=key,
                override_type="grant",
            )
        )
    db.flush()
    previous_stage_id = record.stage_id
    monkeypatch.setattr(surrogate_events, "handle_status_changed", Mock())
    monkeypatch.setattr(notification_facade, "notify_match_cancel_request_resolved", Mock())

    if can_approve_applicant:
        result = status_change_request_service.approve_request(
            db, request.id, context.org.id, context.manager.user_id, Role.CASE_MANAGER
        )
        assert result.status == "approved"
        assert match.status == "cancelled"
        assert record.stage_id != previous_stage_id
    else:
        with pytest.raises(ValueError, match="Applicant approval permission"):
            status_change_request_service.approve_request(
                db, request.id, context.org.id, context.manager.user_id, Role.CASE_MANAGER
            )
        assert request.status == "pending"
        assert match.status == "cancel_pending"
        assert record.stage_id == previous_stage_id
