"""Occurrence isolation and authorization for match work."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.models import Attachment, AuditLog, EntityNote, Match, Task
from app.db.models.matches import MatchAttempt
from app.services import note_service
from tests.test_tasks_match_scope import _create_intended_parent, _create_surrogate


@pytest.fixture
def cases(db, test_auth, default_stage):
    surrogate = _create_surrogate(db, test_auth.org.id, test_auth.user.id, default_stage)
    ip = _create_intended_parent(db, test_auth.org.id)
    old = Match(
        organization_id=test_auth.org.id,
        match_number="M70001",
        surrogate_id=surrogate.id,
        intended_parent_id=ip.id,
        proposed_by_user_id=test_auth.user.id,
        status="completed",
    )
    current = Match(
        organization_id=test_auth.org.id,
        match_number="M70002",
        surrogate_id=surrogate.id,
        intended_parent_id=ip.id,
        proposed_by_user_id=test_auth.user.id,
        status="accepted",
    )
    db.add_all([old, current])
    db.flush()
    attempt = MatchAttempt(
        organization_id=test_auth.org.id,
        match_id=current.id,
        sequence=1,
        attempt_type="embryo_transfer",
        status="planned",
    )
    db.add(attempt)
    db.flush()
    return old, current, attempt


@pytest.mark.asyncio
async def test_work_isolates_repeated_cases_attempts_and_general_notes(
    authed_client, db, test_auth, cases
):
    old, current, attempt = cases
    note_service.create_note(
        db,
        test_auth.org.id,
        "surrogate",
        current.surrogate_id,
        test_auth.user.id,
        "General intake note",
        emit_events=False,
    )
    db.add(
        EntityNote(
            organization_id=test_auth.org.id,
            entity_type="match",
            entity_id=old.id,
            match_id=old.id,
            author_id=test_auth.user.id,
            content="Previous case only",
        )
    )
    db.flush()
    response = await authed_client.post(
        f"/matches/{current.id}/notes",
        json={
            "content": "<p>Attempt one</p><script>alert(1)</script>",
            "source": "surrogate",
            "attempt_id": str(attempt.id),
        },
    )
    assert response.status_code == 201, response.text
    assert "script" not in response.json()["content"]
    response = await authed_client.post(
        "/tasks",
        json={
            "title": "Attempt-specific task",
            "work_source": "ip",
            "match_id": str(current.id),
            "attempt_id": str(attempt.id),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["match_id"] == str(current.id)
    assert response.json()["attempt_id"] == str(attempt.id)
    work = await authed_client.get(
        f"/matches/{current.id}/work", params={"attempt_id": str(attempt.id)}
    )
    assert work.status_code == 200, work.text
    assert len(work.json()["notes"]) == 1
    assert work.json()["notes"][0]["source"] == "surrogate"
    assert [task["title"] for task in work.json()["tasks"]] == ["Attempt-specific task"]
    assert work.json()["tasks"][0]["source"] == "ip"
    assert "Previous case only" not in work.text and "General intake note" not in work.text
    old_work = await authed_client.get(f"/matches/{old.id}/work")
    assert [note["content"] for note in old_work.json()["notes"]] == ["Previous case only"]
    assert old_work.json()["tasks"] == []


@pytest.mark.asyncio
async def test_wrong_attempt_source_and_closed_case_are_rejected(authed_client, cases):
    old, current, attempt = cases
    wrong_attempt = await authed_client.get(
        f"/matches/{old.id}/work", params={"attempt_id": str(attempt.id)}
    )
    assert wrong_attempt.status_code == 404
    wrong_source = await authed_client.post(
        f"/matches/{current.id}/notes", json={"content": "bad", "source": "donor"}
    )
    assert wrong_source.status_code == 400
    closed = await authed_client.post(f"/matches/{old.id}/notes", json={"content": "bad"})
    assert closed.status_code == 409
    orphan_attempt = await authed_client.post(
        "/tasks", json={"title": "bad", "attempt_id": str(attempt.id)}
    )
    assert orphan_attempt.status_code == 400


@pytest.mark.asyncio
async def test_case_file_upload_download_and_delete(authed_client, db, cases):
    _, current, attempt = cases
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    png_bytes = buffer.getvalue()
    upload = await authed_client.post(
        f"/matches/{current.id}/attachments",
        params={"attempt_id": str(attempt.id)},
        files={"file": ("case.png", png_bytes, "image/png")},
    )
    assert upload.status_code == 201, upload.text
    attachment_id = upload.json()["id"]
    work = await authed_client.get(f"/matches/{current.id}/work")
    assert [f["id"] for f in work.json()["files"]] == [attachment_id]
    db.get(Attachment, uuid.UUID(attachment_id)).scan_status = "pending"
    db.flush()
    download = await authed_client.get(f"/attachments/{attachment_id}/download")
    assert download.status_code == 409, download.text
    db.get(Attachment, uuid.UUID(attachment_id)).scan_status = "clean"
    db.flush()
    download = await authed_client.get(f"/attachments/{attachment_id}/download")
    assert download.status_code == 200, download.text
    delete = await authed_client.delete(f"/attachments/{attachment_id}")
    assert delete.status_code in {200, 204}, delete.text
    final_work = (
        await authed_client.get(
            f"/matches/{current.id}/work", params={"attempt_id": str(attempt.id)}
        )
    ).json()
    assert final_work["files"] == []
    assert any(event["event_type"] == "Attachment Deleted" for event in final_work["activity"])


@pytest.mark.asyncio
async def test_work_cross_org_and_missing_csrf(authed_client, db, test_auth, cases):
    from app.db.models import Organization

    current, _, _ = cases
    other = Organization(name="Other org", slug=f"other-{uuid.uuid4().hex}")
    db.add(other)
    db.flush()
    # The access path must derive organization scope before traversing participants.
    db.execute(
        text("UPDATE matches SET organization_id = :org WHERE id = :id"),
        {"org": other.id, "id": current.id},
    )
    db.expire(current)
    read = await authed_client.get(f"/matches/{current.id}/work")
    assert read.status_code == 404
    write = await authed_client.post(f"/matches/{current.id}/notes", json={"content": "bad"})
    assert write.status_code == 404
    no_csrf = await authed_client.post(
        f"/matches/{current.id}/notes", headers={"X-CSRF-Token": ""}, json={"content": "bad"}
    )
    assert no_csrf.status_code == 403


def test_database_rejects_attempt_from_another_case(db, test_auth, cases):
    old, _, attempt = cases
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            EntityNote(
                organization_id=test_auth.org.id,
                entity_type="match",
                entity_id=old.id,
                match_id=old.id,
                attempt_id=attempt.id,
                author_id=test_auth.user.id,
                content="invalid",
            )
        )
        db.flush()


@pytest.mark.asyncio
async def test_note_and_activity_rollback_together(authed_client, db, cases, monkeypatch):
    _, current, _ = cases

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic audit failure")

    current_id = current.id
    db.commit()
    monkeypatch.setattr("app.services.audit_service.log_event", fail)
    with pytest.raises(RuntimeError, match="Synthetic audit failure"):
        await authed_client.post(f"/matches/{current_id}/notes", json={"content": "must roll back"})
    assert db.query(EntityNote).filter(EntityNote.match_id == current_id).count() == 0
    assert db.query(AuditLog).filter(AuditLog.target_id == current_id).count() == 0


@pytest.mark.asyncio
async def test_task_participants_cannot_be_relinked(authed_client, db, cases):
    _, current, _ = cases
    created = await authed_client.post(
        "/tasks", json={"title": "case task", "match_id": str(current.id)}
    )
    assert created.status_code == 201, created.text
    changed = await authed_client.patch(
        f"/tasks/{created.json()['id']}", json={"intended_parent_id": None}
    )
    assert changed.status_code == 400
    task = db.get(Task, uuid.UUID(created.json()["id"]))
    assert task.intended_parent_id == current.intended_parent_id


def test_work_lock_refreshes_preloaded_closed_case(db, test_auth, cases):
    from fastapi import HTTPException

    from app.services.match_work_service import validate_context

    _, current, _ = cases
    assert current.status == "accepted"
    db.execute(text("UPDATE matches SET status = 'completed' WHERE id = :id"), {"id": current.id})
    assert current.status == "accepted"
    with pytest.raises(HTTPException) as exc:
        validate_context(db, test_auth.org.id, current.id, write=True)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_work_permissions_denied(authed_client, cases, monkeypatch):
    from app.services import permission_service

    _, current, _ = cases
    original = permission_service.check_permission

    def restricted(db, org_id, user_id, role, permission):
        if permission == "propose_matches":
            return False
        return original(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", restricted)
    response = await authed_client.post(f"/matches/{current.id}/notes", json={"content": "denied"})
    assert response.status_code == 403
    monkeypatch.setattr(permission_service, "check_permission", lambda *a, **k: False)
    response = await authed_client.get(f"/matches/{current.id}/work")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_owned_case_note_delete_requires_current_source_permission(
    authed_client, cases, monkeypatch
):
    from app.services import permission_service

    _, current, _ = cases
    created = await authed_client.post(
        f"/matches/{current.id}/notes", json={"content": "kept", "source": "ip"}
    )
    assert created.status_code == 201
    original = permission_service.check_permission

    def restricted(db, org_id, user_id, role, permission):
        if permission in {"edit_intended_parents", "edit_surrogate_notes"}:
            return False
        return original(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", restricted)
    deleted = await authed_client.delete(f"/matches/{current.id}/notes/{created.json()['id']}")
    assert deleted.status_code == 403
    assert len((await authed_client.get(f"/matches/{current.id}/work")).json()["notes"]) == 1
