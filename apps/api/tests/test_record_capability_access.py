"""Shared capabilities must authorize the actual linked record."""

import uuid

import pytest
from fastapi import HTTPException

from app.core.encryption import hash_email
from app.db.enums import Role
from app.db.models import (
    Attachment,
    Donor,
    IntendedParent,
    Membership,
    Surrogate,
    Task,
    UserPermissionOverride,
)
from app.schemas.auth import UserSession
from app.services import attachment_service, pipeline_service, task_service


def _record(db, org_id, user_id, kind):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, org_id, entity_type="egg_donor" if kind == "donor" else kind
    )
    stage = next(stage for stage in pipeline.stages if stage.is_active)
    email = f"record-{uuid.uuid4()}@example.com"
    fields = dict(
        id=uuid.uuid4(),
        organization_id=org_id,
        full_name="Test Record",
        email=email,
        email_hash=hash_email(email),
        stage_id=stage.id,
        owner_type="user",
        owner_id=user_id,
    )
    if kind == "donor":
        record = Donor(**fields, donor_number="D10001", donor_type="egg")
    elif kind == "intended_parent":
        record = IntendedParent(**fields, intended_parent_number="I10001", status=stage.stage_key)
    else:
        record = Surrogate(
            **fields,
            surrogate_number="S10001",
            created_by_user_id=user_id,
            status_label=stage.label,
        )
    db.add(record)
    db.flush()
    return record


def _session(test_user, test_org):
    return UserSession(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.ADMIN,
        email=test_user.email,
        display_name=test_user.display_name,
    )


def _revoke(db, session, permission):
    membership = (
        db.query(Membership)
        .filter_by(
            organization_id=session.org_id,
            user_id=session.user_id,
        )
        .one()
    )
    membership.role = Role.ADMIN
    db.add(
        UserPermissionOverride(
            organization_id=session.org_id,
            user_id=session.user_id,
            permission=permission,
            override_type="revoke",
        )
    )
    db.flush()


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
async def test_attachment_download_requires_actual_record_view(
    authed_client,
    db,
    test_user,
    test_org,
    kind,
):
    record = _record(db, test_org.id, test_user.id, kind)
    attachment = Attachment(
        organization_id=test_org.id,
        **{f"{kind}_id": record.id},
        uploaded_by_user_id=test_user.id,
        filename="test.txt",
        storage_key="synthetic/test.txt",
        content_type="text/plain",
        file_size=4,
        checksum_sha256="a" * 64,
        scan_status="clean",
    )
    db.add(attachment)
    db.flush()
    session = _session(test_user, test_org)
    _revoke(db, session, f"view_{kind}s")

    response = await authed_client.get(f"/attachments/{attachment.id}/download")
    assert response.status_code == 403
    assert response.json()["detail"] == f"Missing permission: view_{kind}s"


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
async def test_attachment_delete_requires_actual_record_edit(
    authed_client,
    db,
    test_user,
    test_org,
    kind,
):
    record = _record(db, test_org.id, test_user.id, kind)
    attachment = Attachment(
        organization_id=test_org.id,
        **{f"{kind}_id": record.id},
        uploaded_by_user_id=test_user.id,
        filename="test.txt",
        storage_key="synthetic/test.txt",
        content_type="text/plain",
        file_size=4,
        checksum_sha256="b" * 64,
        scan_status="clean",
    )
    db.add(attachment)
    db.flush()
    session = _session(test_user, test_org)
    _revoke(db, session, f"edit_{kind}s")

    response = await authed_client.delete(f"/attachments/{attachment.id}")
    assert response.status_code == 403
    assert attachment_service.get_attachment(db, test_org.id, attachment.id).deleted_at is None


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
def test_task_subject_requires_actual_record_permission(db, test_org, test_user, kind):
    record = _record(db, test_org.id, test_user.id, kind)
    task = Task(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Test Task",
        **{f"{kind}_id": record.id},
    )
    db.add(task)
    db.flush()
    session = _session(test_user, test_org)
    _revoke(db, session, f"view_{kind}s")

    with pytest.raises(HTTPException) as denied:
        task_service.check_task_subject_access(db, task, session)
    assert denied.value.status_code == 403


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
def test_task_subject_rejects_foreign_record(db, test_org, test_user, kind):
    from app.db.models import Organization

    foreign_org = Organization(name="Foreign", slug=f"foreign-{uuid.uuid4()}")
    db.add(foreign_org)
    db.flush()
    record = _record(db, foreign_org.id, test_user.id, kind)
    task = Task(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Test Task",
        **{f"{kind}_id": record.id},
    )
    db.add(task)
    db.flush()
    with pytest.raises(HTTPException) as denied:
        task_service.check_task_subject_access(db, task, _session(test_user, test_org))
    assert denied.value.status_code == 404


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
async def test_task_lists_filter_denied_subjects_before_counting(
    authed_client,
    db,
    test_org,
    test_user,
    kind,
):
    record = _record(db, test_org.id, test_user.id, kind)
    linked = Task(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Private Task",
        **{f"{kind}_id": record.id},
    )
    standalone = Task(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Standalone Task",
    )
    db.add_all([linked, standalone])
    db.flush()
    _revoke(db, _session(test_user, test_org), f"view_{kind}s")
    response = await authed_client.get("/tasks")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [str(standalone.id)]


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
async def test_task_creation_requires_subject_permission(
    authed_client,
    db,
    test_org,
    test_user,
    kind,
):
    record = _record(db, test_org.id, test_user.id, kind)
    _revoke(db, _session(test_user, test_org), f"view_{kind}s")
    response = await authed_client.post(
        "/tasks",
        json={
            "title": "Task",
            f"{kind}_id": str(record.id),
        },
    )
    assert response.status_code == 403


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
async def test_task_relink_requires_destination_permission(
    authed_client,
    db,
    test_org,
    test_user,
    kind,
):
    record = _record(db, test_org.id, test_user.id, kind)
    task = Task(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Task",
    )
    db.add(task)
    db.flush()
    _revoke(db, _session(test_user, test_org), f"view_{kind}s")
    response = await authed_client.patch(f"/tasks/{task.id}", json={f"{kind}_id": str(record.id)})
    assert response.status_code == 403
    assert getattr(task, f"{kind}_id") is None


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
async def test_bulk_completion_requires_each_subject_permission(
    authed_client,
    db,
    test_org,
    test_user,
    kind,
    monkeypatch,
):
    from app.services import dashboard_service

    monkeypatch.setattr(dashboard_service, "push_dashboard_stats", lambda *_args: None)
    monkeypatch.setattr(task_service, "_sync_task_to_google_best_effort", lambda *_args: None)
    record = _record(db, test_org.id, test_user.id, kind)
    fields = dict(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
    )
    private = Task(**fields, title="Restricted subject", **{f"{kind}_id": record.id})
    standalone = Task(**fields, title="Allowed standalone")
    db.add_all([private, standalone])
    db.flush()
    _revoke(db, _session(test_user, test_org), f"view_{kind}s")

    response = await authed_client.post(
        "/tasks/bulk-complete",
        json={
            "task_ids": [str(private.id), str(standalone.id)],
        },
    )

    assert response.status_code == 200
    assert response.json()["completed"] == 1
    assert response.json()["failed"] == [
        {
            "task_id": str(private.id),
            "reason": f"Missing permission: view_{kind}s",
        }
    ]
    db.refresh(private)
    db.refresh(standalone)
    assert private.is_completed is False
    assert standalone.is_completed is True


@pytest.mark.parametrize("kind", ["surrogate", "intended_parent", "donor"])
async def test_bulk_completion_rejects_foreign_subject_and_missing_task(
    authed_client,
    db,
    test_org,
    test_user,
    kind,
    monkeypatch,
):
    from app.db.models import Organization
    from app.services import dashboard_service

    monkeypatch.setattr(dashboard_service, "push_dashboard_stats", lambda *_args: None)
    monkeypatch.setattr(task_service, "_sync_task_to_google_best_effort", lambda *_args: None)
    foreign_org = Organization(name="Foreign", slug=f"foreign-bulk-{uuid.uuid4()}")
    db.add(foreign_org)
    db.flush()
    record = _record(db, foreign_org.id, test_user.id, kind)
    task = Task(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Foreign subject",
        **{f"{kind}_id": record.id},
    )
    db.add(task)
    db.flush()
    missing_id = uuid.uuid4()

    response = await authed_client.post(
        "/tasks/bulk-complete",
        json={
            "task_ids": [str(task.id), str(missing_id)],
        },
    )

    assert response.status_code == 200
    assert response.json()["completed"] == 0
    assert {failure["task_id"] for failure in response.json()["failed"]} == {
        str(task.id),
        str(missing_id),
    }
    db.refresh(task)
    assert task.is_completed is False


async def test_task_list_identifies_creator_separately_from_owner(
    authed_client,
    db,
    test_org,
    test_user,
):
    from app.db.models import User

    creator = User(email=f"creator-{uuid.uuid4()}@example.com", display_name="Task Creator")
    db.add(creator)
    db.flush()
    db.add(
        Membership(organization_id=test_org.id, user_id=creator.id, role=Role.ADMIN, is_active=True)
    )
    task = Task(
        organization_id=test_org.id,
        created_by_user_id=creator.id,
        owner_type="user",
        owner_id=test_user.id,
        title="Creator metadata",
    )
    db.add(task)
    db.flush()

    response = await authed_client.get("/tasks")

    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["id"] == str(task.id))
    assert item["created_by_user_id"] == str(creator.id)
    assert item["owner_id"] == str(test_user.id)
