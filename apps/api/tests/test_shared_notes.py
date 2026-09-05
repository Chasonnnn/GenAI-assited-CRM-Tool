"""Shared notes preserve subject boundaries and transaction ownership."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.encryption import hash_email
from app.db.enums import EntityType
from app.db.models import (
    Donor,
    EntityActivityLog,
    EntityNote,
    IntendedParent,
    Surrogate,
    SurrogateActivityLog,
    Task,
)
from app.services import (
    activity_service,
    entity_activity_service,
    note_service,
    permission_service,
    workflow_triggers,
    zoom_service,
)
from app.services.ai_action_executor import AddNoteExecutor, SendEmailExecutor


@pytest.fixture(params=["surrogate", "intended_parent", "donor"])
def note_subject(request, db, test_org, test_user, default_stage):
    kind = request.param
    email = f"notes-{uuid.uuid4().hex}@example.com"
    values = dict(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        full_name="Shared Notes Test",
        email=email,
        email_hash=hash_email(email),
        stage_id=default_stage.id,
    )
    number = str(uuid.uuid4().int % 90000 + 10000)
    if kind == "surrogate":
        subject = Surrogate(
            **values,
            surrogate_number=f"S{number}",
            status_label=default_stage.label,
            owner_type="user",
            owner_id=test_user.id,
            source="manual",
        )
    elif kind == "intended_parent":
        subject = IntendedParent(**values, intended_parent_number=f"I{number}")
    else:
        subject = Donor(**values, donor_number=f"D{number}", donor_type="egg")
    db.add(subject)
    db.commit()
    return kind, subject


def _activity_query(db, kind, subject_id):
    if kind == "surrogate":
        return db.query(SurrogateActivityLog).filter(
            SurrogateActivityLog.surrogate_id == subject_id
        )
    column = EntityActivityLog.donor_id if kind == "donor" else EntityActivityLog.intended_parent_id
    return db.query(EntityActivityLog).filter(column == subject_id)


def _notes_path(kind, subject_id):
    prefix = {"surrogate": "surrogates", "intended_parent": "intended-parents", "donor": "donors"}[
        kind
    ]
    return f"/{prefix}/{subject_id}/notes"


def _isolate_failure_rollback(db, monkeypatch):
    # Keep fixture rows outside the operation's rollback boundary.
    savepoint = db.begin_nested()

    def rollback_operation():
        if savepoint.is_active:
            savepoint.rollback()

    monkeypatch.setattr(db, "rollback", rollback_operation)


@pytest.mark.asyncio
@pytest.mark.parametrize("note_subject", ["intended_parent", "donor"], indirect=True)
async def test_generic_note_delete_rejects_other_entity_types(
    authed_client,
    db,
    test_user,
    note_subject,
    monkeypatch,
):
    kind, subject = note_subject
    note = EntityNote(
        organization_id=subject.organization_id,
        entity_type=kind,
        entity_id=subject.id,
        author_id=test_user.id,
        content="Keep this note",
    )
    db.add(note)
    db.commit()
    original_check = permission_service.check_permission
    denied = {"view_donors", "edit_donors", "view_intended_parents", "edit_intended_parents"}
    monkeypatch.setattr(
        permission_service,
        "check_permission",
        lambda *args: False if args[-1] in denied else original_check(*args),
    )

    response = await authed_client.delete(f"/notes/{note.id}")

    assert response.status_code == 404
    assert db.get(EntityNote, note.id) is not None


@pytest.mark.asyncio
async def test_note_creation_and_activity_roll_back_together(
    authed_client,
    db,
    note_subject,
    monkeypatch,
):
    kind, subject = note_subject
    subject_id = subject.id
    _isolate_failure_rollback(db, monkeypatch)

    def fail_activity(*_args, **_kwargs):
        raise RuntimeError("activity persistence failed")

    if kind == "surrogate":
        monkeypatch.setattr(activity_service, "log_note_added", fail_activity)
    else:
        monkeypatch.setattr(entity_activity_service, "record_activity", fail_activity)
    payload = {"body" if kind == "surrogate" else "content": "Must roll back"}
    with pytest.raises(RuntimeError, match="activity persistence failed"):
        await authed_client.post(_notes_path(kind, subject_id), json=payload)

    assert db.query(EntityNote).filter(EntityNote.entity_id == subject_id).count() == 0
    assert _activity_query(db, kind, subject_id).count() == 0


@pytest.mark.asyncio
async def test_note_deletion_and_activity_roll_back_together(
    authed_client,
    db,
    test_user,
    note_subject,
    monkeypatch,
):
    kind, subject = note_subject
    subject_id = subject.id
    note = EntityNote(
        organization_id=subject.organization_id,
        entity_type=kind,
        entity_id=subject_id,
        author_id=test_user.id,
        content="Keep on failure",
    )
    db.add(note)
    db.commit()
    note_id = note.id
    _isolate_failure_rollback(db, monkeypatch)
    original_delete = db.delete

    def fail_note_delete(value):
        if isinstance(value, EntityNote):
            raise RuntimeError("note deletion failed")
        return original_delete(value)

    monkeypatch.setattr(db, "delete", fail_note_delete)
    path = (
        f"/notes/{note_id}" if kind == "surrogate" else f"{_notes_path(kind, subject_id)}/{note_id}"
    )
    with pytest.raises(RuntimeError, match="note deletion failed"):
        await authed_client.delete(path)

    assert db.get(EntityNote, note_id) is not None
    assert _activity_query(db, kind, subject_id).count() == 0


def test_composed_note_creation_keeps_outer_transaction_and_suppresses_events(
    db,
    test_user,
    note_subject,
    monkeypatch,
):
    kind, subject = note_subject
    subject_id = subject.id
    trigger = Mock()
    monkeypatch.setattr(workflow_triggers, "trigger_note_added", trigger)
    commit = Mock(side_effect=AssertionError("Shared operation committed outer transaction"))
    monkeypatch.setattr(db, "commit", commit)

    note = note_service.create_note(
        db,
        subject.organization_id,
        kind,
        subject_id,
        test_user.id,
        "<p>Safe</p><script>alert(1)</script>",
        commit=False,
        emit_events=False,
    )

    assert "<script>" not in note.content
    assert _activity_query(db, kind, subject_id).count() == 1
    if kind == "intended_parent":
        assert subject.last_activity == note.created_at
    trigger.assert_not_called()
    commit.assert_not_called()
    db.rollback()
    assert db.query(EntityNote).filter(EntityNote.entity_id == subject_id).count() == 0
    assert _activity_query(db, kind, subject_id).count() == 0


def test_shared_note_creation_rejects_cross_org_subject(db, test_user, note_subject):
    kind, subject = note_subject
    with pytest.raises(ValueError, match="Note subject not found in organization"):
        note_service.create_note(
            db,
            uuid.uuid4(),
            kind,
            subject.id,
            test_user.id,
            "Foreign subject",
            commit=False,
            emit_events=False,
        )
    assert db.query(EntityNote).filter(EntityNote.entity_id == subject.id).count() == 0
    assert _activity_query(db, kind, subject.id).count() == 0


@pytest.mark.asyncio
async def test_manual_note_lifecycle_emits_each_activity_once(
    authed_client,
    db,
    note_subject,
    monkeypatch,
):
    kind, subject = note_subject
    trigger = Mock()
    monkeypatch.setattr(workflow_triggers, "trigger_note_added", trigger)
    path = _notes_path(kind, subject.id)
    created = await authed_client.post(
        path, json={"body" if kind == "surrogate" else "content": "Hello"}
    )
    assert created.status_code == 201
    note_id = created.json()["id"]
    trigger.assert_called_once()
    delete_path = f"/notes/{note_id}" if kind == "surrogate" else f"{path}/{note_id}"
    deleted = await authed_client.delete(delete_path)
    assert deleted.status_code == 204
    assert sorted(row.activity_type for row in _activity_query(db, kind, subject.id)) == [
        "note_added",
        "note_deleted",
    ]


@pytest.mark.asyncio
async def test_note_lists_include_author_names(authed_client, db, test_user, note_subject):
    kind, subject = note_subject
    db.add(
        EntityNote(
            organization_id=subject.organization_id,
            entity_type=kind,
            entity_id=subject.id,
            author_id=test_user.id,
            content="Named author",
        )
    )
    db.commit()
    response = await authed_client.get(_notes_path(kind, subject.id))
    assert response.status_code == 200
    assert response.json()[0]["author_name"] == test_user.display_name


@pytest.mark.asyncio
async def test_note_save_survives_failed_postcommit_workflow(
    authed_client,
    db,
    note_subject,
    monkeypatch,
    caplog,
):
    kind, subject = note_subject
    subject_id = subject.id

    def fail_workflow(side_effect_db, note):
        side_effect_db.add(
            EntityNote(
                organization_id=note.organization_id,
                entity_type=note.entity_type,
                entity_id=note.entity_id,
                author_id=note.author_id,
                content="Failed side effect",
            )
        )
        side_effect_db.flush()
        raise RuntimeError("synthetic-sensitive-provider-error")

    trigger = Mock(side_effect=fail_workflow)
    monkeypatch.setattr(workflow_triggers, "trigger_note_added", trigger)
    response = await authed_client.post(
        _notes_path(kind, subject_id),
        json={"body" if kind == "surrogate" else "content": "Saved successfully"},
    )
    assert response.status_code == 201
    trigger.assert_called_once()
    notes = db.query(EntityNote).filter(EntityNote.entity_id == subject_id).all()
    assert [note.content for note in notes] == ["Saved successfully"]
    assert _activity_query(db, kind, subject_id).count() == 1
    assert "synthetic-sensitive-provider-error" not in caplog.text


@pytest.mark.parametrize("note_subject", ["surrogate"], indirect=True)
def test_ai_note_uses_shared_activity_without_committing(db, test_user, note_subject, monkeypatch):
    kind, subject = note_subject
    trigger = Mock()
    monkeypatch.setattr(workflow_triggers, "trigger_note_added", trigger)
    monkeypatch.setattr(db, "commit", Mock(side_effect=AssertionError("AI note committed")))
    result = AddNoteExecutor().execute(
        {"content": "AI note"}, db, test_user.id, subject.organization_id, subject.id
    )
    assert result["success"]
    assert _activity_query(db, kind, subject.id).count() == 1
    trigger.assert_called_once()
    assert subject.last_contact_method == "note"


@pytest.mark.parametrize("note_subject", ["surrogate"], indirect=True)
def test_ai_email_note_uses_shared_activity_without_committing(
    db,
    test_user,
    note_subject,
    monkeypatch,
):
    from app.services import gmail_service

    kind, subject = note_subject
    trigger = Mock()
    monkeypatch.setattr(workflow_triggers, "trigger_note_added", trigger)
    monkeypatch.setattr(db, "commit", Mock(side_effect=AssertionError("AI email note committed")))
    monkeypatch.setattr(
        gmail_service, "send_email_logged", AsyncMock(return_value={"success": True})
    )
    result = SendEmailExecutor().execute(
        {"to": "synthetic@example.com", "subject": "Test", "body": "Synthetic message"},
        db,
        test_user.id,
        subject.organization_id,
        subject.id,
    )
    assert result["success"]
    assert _activity_query(db, kind, subject.id).count() == 1
    trigger.assert_called_once()
    assert subject.last_contact_method == "email"


@pytest.mark.asyncio
@pytest.mark.parametrize("note_subject", ["surrogate", "intended_parent"], indirect=True)
async def test_zoom_note_uses_shared_activity_and_preserves_event_suppression(
    db,
    test_user,
    note_subject,
    monkeypatch,
):
    kind, subject = note_subject
    trigger = Mock()
    monkeypatch.setattr(workflow_triggers, "trigger_note_added", trigger)
    monkeypatch.setattr(zoom_service, "get_user_zoom_token", AsyncMock(return_value="synthetic"))
    monkeypatch.setattr(
        zoom_service,
        "create_zoom_meeting",
        AsyncMock(
            return_value=zoom_service.ZoomMeeting(
                id=123,
                uuid="synthetic",
                topic="Test",
                start_time=None,
                duration=30,
                timezone="UTC",
                join_url="https://example.com/join",
                start_url="https://example.com/start",
            )
        ),
    )
    result = await zoom_service.schedule_zoom_meeting(
        db,
        test_user.id,
        subject.organization_id,
        EntityType(kind),
        subject.id,
        "Test",
        start_time=datetime.now(UTC),
    )
    assert db.get(EntityNote, result.note_id) is not None
    task = db.get(Task, result.task_id)
    assert task is not None
    assert task.surrogate_id == (subject.id if kind == "surrogate" else None)
    assert task.intended_parent_id == (subject.id if kind == "intended_parent" else None)
    assert task.donor_id is None
    assert _activity_query(db, kind, subject.id).count() == 1
    trigger.assert_not_called()
