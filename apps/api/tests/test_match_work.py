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
    assert {note["content"] for note in old_work.json()["notes"]} == {
        "Previous case only",
        "General intake note",
    }
    assert old_work.json()["tasks"] == []


@pytest.mark.asyncio
async def test_match_workspace_preserves_unassigned_history_without_other_case_work(
    authed_client, db, test_auth, cases
):
    from app.db.models import EntityActivityLog, SurrogateActivityLog

    old, current, attempt = cases
    org_id, user_id = test_auth.org.id, test_auth.user.id
    general_note = note_service.create_note(
        db,
        org_id,
        "surrogate",
        current.surrogate_id,
        user_id,
        "Historical participant note",
        emit_events=False,
    )
    general_task = Task(
        organization_id=org_id,
        created_by_user_id=user_id,
        owner_type="user",
        owner_id=user_id,
        title="Historical participant task",
        intended_parent_id=current.intended_parent_id,
    )
    old_task = Task(
        organization_id=org_id,
        created_by_user_id=user_id,
        owner_type="user",
        owner_id=user_id,
        title="Other case task",
        intended_parent_id=old.intended_parent_id,
        surrogate_id=old.surrogate_id,
        match_id=old.id,
    )
    general_file = Attachment(
        organization_id=org_id,
        intended_parent_id=current.intended_parent_id,
        uploaded_by_user_id=user_id,
        filename="participant.txt",
        storage_key="qa/participant",
        content_type="text/plain",
        file_size=1,
        checksum_sha256="a" * 64,
        scan_status="clean",
    )
    other_file = Attachment(
        organization_id=org_id,
        intended_parent_id=current.intended_parent_id,
        match_id=old.id,
        uploaded_by_user_id=user_id,
        filename="other-case.txt",
        storage_key="qa/other-case",
        content_type="text/plain",
        file_size=1,
        checksum_sha256="b" * 64,
        scan_status="clean",
    )
    db.add_all([general_task, old_task, general_file, other_file])
    db.flush()
    generic_activity = SurrogateActivityLog(
        organization_id=org_id,
        surrogate_id=current.surrogate_id,
        activity_type="created",
        details={},
        actor_user_id=user_id,
    )
    other_activity = EntityActivityLog(
        organization_id=org_id,
        intended_parent_id=current.intended_parent_id,
        activity_type="task_created",
        details={"task_id": str(old_task.id)},
    )
    explicit_other_activity = SurrogateActivityLog(
        organization_id=org_id,
        surrogate_id=current.surrogate_id,
        activity_type="match_accepted",
        details={"match_id": str(old.id)},
    )
    db.add_all([generic_activity, other_activity, explicit_other_activity])
    db.flush()
    result = await authed_client.get(f"/matches/{current.id}/work")
    assert result.status_code == 200, result.text
    data = result.json()
    note = next(n for n in data["notes"] if n["id"] == str(general_note.id))
    assert note["scope"] == "record" and note["source"] == "surrogate"
    assert [t["id"] for t in data["tasks"]] == [str(general_task.id)]
    assert data["tasks"][0]["scope"] == "record"
    assert [f["id"] for f in data["files"]] == [str(general_file.id)]
    assert data["files"][0]["scope"] == "record"
    activity_ids = {a["id"] for a in data["activity"]}
    assert str(generic_activity.id) in activity_ids
    assert str(other_activity.id) not in activity_ids
    assert str(explicit_other_activity.id) not in activity_ids
    scoped = (
        await authed_client.get(
            f"/matches/{current.id}/work", params={"attempt_id": str(attempt.id)}
        )
    ).json()
    assert all(scoped[key] == [] for key in ("notes", "files", "tasks", "activity"))
    assert general_note.match_id is None and general_task.match_id is None

    # Calendar opts into the same NULL-context history; exact filters keep their contract.
    exact = (await authed_client.get("/tasks", params={"match_id": str(current.id)})).json()
    assert exact["items"] == []
    combined = (
        await authed_client.get(
            "/tasks", params={"match_id": str(current.id), "include_record_history": True}
        )
    ).json()
    assert [t["id"] for t in combined["items"]] == [str(general_task.id)]
    scoped_tasks = (
        await authed_client.get(
            "/tasks",
            params={
                "match_id": str(current.id),
                "attempt_id": str(attempt.id),
                "include_record_history": True,
            },
        )
    ).json()
    assert scoped_tasks["items"] == []
    assert (
        await authed_client.get("/tasks", params={"include_record_history": True})
    ).status_code == 400


@pytest.mark.asyncio
async def test_archived_match_history_read_preserves_role_checks_and_denies_writes(
    authed_client, db, test_auth, cases, monkeypatch
):
    from app.core import deps
    from app.core.deps import get_current_session
    from app.db.enums import Role
    from app.db.models import PipelineStage, Surrogate
    from app.main import app
    from app.schemas.auth import UserSession

    _, current, _ = cases
    surrogate = db.get(Surrogate, current.surrogate_id)
    intake_stage_id = surrogate.stage_id
    stage = PipelineStage(
        pipeline_id=surrogate.stage.pipeline_id,
        stage_key="approved",
        slug="approved",
        label="Approved",
        color="#3B82F6",
        stage_type="post_approval",
        order=2,
        is_active=True,
    )
    db.add(stage)
    db.flush()
    surrogate.stage_id = stage.id
    surrogate.is_archived = True
    db.flush()
    session = UserSession(
        user_id=test_auth.user.id,
        org_id=test_auth.org.id,
        role=Role.CASE_MANAGER,
        email=test_auth.user.email,
        display_name=test_auth.user.display_name,
    )
    app.dependency_overrides[get_current_session] = lambda: session
    monkeypatch.setattr(deps, "get_current_session", lambda request, db: session)
    try:
        listed = await authed_client.get("/matches/")
        assert listed.status_code == 200, listed.text
        assert str(current.id) in {item["id"] for item in listed.json()["items"]}
        for path in (
            f"/matches/{current.id}",
            f"/matches/{current.id}/work",
            f"/matches/{current.id}/attempts",
        ):
            response = await authed_client.get(path)
            assert response.status_code == 200, response.text
        denied = await authed_client.post(
            f"/matches/{current.id}/notes", json={"content": "No archived writes"}
        )
        assert denied.status_code == 403, denied.text
        # Case visibility still follows the existing approved-stage role boundary.
        surrogate.stage_id = intake_stage_id
        db.flush()
        assert (await authed_client.get(f"/matches/{current.id}/work")).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_session, None)


@pytest.mark.asyncio
async def test_historical_ip_notes_do_not_expose_denied_surrogate_notes(
    authed_client, db, test_auth, cases, monkeypatch
):
    from app.services import permission_service

    _, current, attempt = cases
    for kind, record_id in (
        ("surrogate", current.surrogate_id),
        ("intended_parent", current.intended_parent_id),
    ):
        note_service.create_note(
            db,
            test_auth.org.id,
            kind,
            record_id,
            test_auth.user.id,
            f"{kind} history",
            emit_events=False,
        )
    original = permission_service.check_permission
    monkeypatch.setattr(
        permission_service,
        "check_permission",
        lambda db, org, user, role, permission: (
            False
            if permission == "view_surrogate_notes"
            else original(db, org, user, role, permission)
        ),
    )
    history = (await authed_client.get(f"/matches/{current.id}/work")).json()
    assert [note["content"] for note in history["notes"]] == ["intended_parent history"]
    assert history["can_view_notes"] is True
    scoped = (
        await authed_client.get(
            f"/matches/{current.id}/work", params={"attempt_id": str(attempt.id)}
        )
    ).json()
    assert scoped["notes"] == [] and scoped["can_view_notes"] is False


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
