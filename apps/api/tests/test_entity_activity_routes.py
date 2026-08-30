from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import (
    Attachment,
    Donor,
    EntityActivityLog,
    EntityNote,
    IntendedParent,
    IntendedParentStatusHistory,
    Membership,
    Organization,
    Task,
    User,
    UserPermissionOverride,
)
from app.main import app
from app.schemas.task import TaskCreate
from app.services import entity_activity_service, pipeline_service, session_service, task_service
from app.utils.normalization import normalize_email


def _stage(db, org_id: UUID, entity_type: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type=entity_type,
    )
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
    assert stage is not None
    return stage


def _create_intended_parent(
    db,
    org_id: UUID,
    *,
    entity_id: UUID | None = None,
) -> IntendedParent:
    stage = _stage(db, org_id, "intended_parent")
    email = normalize_email(f"activity-ip-{uuid.uuid4().hex[:8]}@example.com")
    intended_parent = IntendedParent(
        id=entity_id or uuid.uuid4(),
        organization_id=org_id,
        intended_parent_number=f"I{uuid.uuid4().int % 90000 + 10000:05d}",
        full_name="Activity Intended Parent",
        email=email,
        email_hash=hash_email(email),
        stage_id=stage.id,
        status=stage.stage_key,
    )
    db.add(intended_parent)
    db.flush()
    return intended_parent


def _create_donor(
    db,
    org_id: UUID,
    *,
    entity_id: UUID | None = None,
    donor_type: str = "egg",
) -> Donor:
    stage = _stage(db, org_id, f"{donor_type}_donor")
    email = normalize_email(f"activity-donor-{uuid.uuid4().hex[:8]}@example.com")
    donor = Donor(
        id=entity_id or uuid.uuid4(),
        organization_id=org_id,
        donor_number=f"D{uuid.uuid4().int % 90000 + 10001:05d}",
        donor_type=donor_type,
        full_name="Activity Donor",
        email=email,
        email_hash=hash_email(email),
        stage_id=stage.id,
    )
    db.add(donor)
    db.flush()
    return donor


@asynccontextmanager
async def _client_with_revoked_permission(db, org, permission: str):
    user = User(
        id=uuid.uuid4(),
        email=f"activity-rbac-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Activity RBAC User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add_all(
        [
            Membership(
                id=uuid.uuid4(),
                user_id=user.id,
                organization_id=org.id,
                role=Role.ADMIN.value,
                is_active=True,
            ),
            UserPermissionOverride(
                id=uuid.uuid4(),
                organization_id=org.id,
                user_id=user.id,
                permission=permission,
                override_type="revoke",
            ),
        ]
    )
    db.flush()

    token = create_session_token(
        user_id=user.id,
        org_id=org.id,
        role=Role.ADMIN.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org.id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
            cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
            headers={CSRF_HEADER: csrf_token},
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _seed_shared_activity(db, *, org_id: UUID, user_id: UUID, entity_type: str, entity_id: UUID):
    note = EntityNote(
        id=uuid.uuid4(),
        organization_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        author_id=user_id,
        content="<p>Screening follow-up completed.</p>",
        created_at=datetime(2026, 8, 29, 14, 0, tzinfo=UTC),
    )
    task = Task(
        id=uuid.uuid4(),
        organization_id=org_id,
        intended_parent_id=entity_id if entity_type == "intended_parent" else None,
        donor_id=entity_id if entity_type == "donor" else None,
        created_by_user_id=user_id,
        owner_type="user",
        owner_id=user_id,
        title="Review screening documents",
        task_type="review",
        created_at=datetime(2026, 8, 29, 15, 0, tzinfo=UTC),
        updated_at=datetime(2026, 8, 29, 15, 0, tzinfo=UTC),
    )
    attachment = Attachment(
        id=uuid.uuid4(),
        organization_id=org_id,
        intended_parent_id=entity_id if entity_type == "intended_parent" else None,
        donor_id=entity_id if entity_type == "donor" else None,
        uploaded_by_user_id=user_id,
        filename="screening.pdf",
        storage_key=f"{org_id}/{entity_id}/screening.pdf",
        content_type="application/pdf",
        file_size=128,
        checksum_sha256="a" * 64,
        scan_status="clean",
        quarantined=False,
        created_at=datetime(2026, 8, 29, 16, 0, tzinfo=UTC),
    )
    db.add_all([note, task, attachment])
    db.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "route_prefix"),
    [
        ("intended_parent", "/intended-parents"),
        ("donor", "/donors"),
    ],
)
async def test_entity_activity_combines_shared_sources_and_paginates(
    authed_client,
    db,
    test_auth,
    entity_type: str,
    route_prefix: str,
):
    entity = (
        _create_intended_parent(db, test_auth.org.id)
        if entity_type == "intended_parent"
        else _create_donor(db, test_auth.org.id)
    )
    _seed_shared_activity(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        entity_type=entity_type,
        entity_id=entity.id,
    )

    response = await authed_client.get(
        f"{route_prefix}/{entity.id}/activity",
        params={"page": 1, "per_page": 2},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["page"] == 1
    assert payload["pages"] == 2
    assert payload["total"] == 3
    assert len(payload["items"]) == 2
    assert [item["activity_type"] for item in payload["items"]] == [
        "attachment_added",
        "task_created",
    ]
    assert payload["items"][0]["actor_name"] == test_auth.user.display_name
    assert payload["items"][0]["details"]["filename"] == "screening.pdf"

    second_page = await authed_client.get(
        f"{route_prefix}/{entity.id}/activity",
        params={"page": 2, "per_page": 2},
    )
    assert second_page.status_code == 200, second_page.text
    assert [item["activity_type"] for item in second_page.json()["items"]] == ["note_added"]
    assert second_page.json()["items"][0]["details"]["preview"] == (
        "Screening follow-up completed."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "route_prefix"),
    [
        ("intended_parent", "/intended-parents"),
        ("donor", "/donors"),
    ],
)
async def test_entity_activity_redacts_task_preview_and_audits_visible_note_preview(
    db,
    test_auth,
    entity_type: str,
    route_prefix: str,
):
    entity = (
        _create_intended_parent(db, test_auth.org.id)
        if entity_type == "intended_parent"
        else _create_donor(db, test_auth.org.id)
    )
    _seed_shared_activity(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        entity_type=entity_type,
        entity_id=entity.id,
    )
    db.commit()

    async with _client_with_revoked_permission(
        db,
        test_auth.org,
        "view_tasks",
    ) as restricted_client:
        response = await restricted_client.get(
            f"{route_prefix}/{entity.id}/activity",
            params={"per_page": 100},
        )
        note_audit = await restricted_client.get(
            "/audit/",
            params={"event_type": "data_view_note", "per_page": 100},
        )
        phi_audit = await restricted_client.get(
            "/audit/",
            params={"event_type": "phi_viewed", "per_page": 100},
        )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    note_event = next(item for item in items if item["activity_type"] == "note_added")
    task_event = next(item for item in items if item["activity_type"] == "task_created")
    assert note_event["details"]["preview"] == "Screening follow-up completed."
    assert "title" not in (task_event["details"] or {})
    assert "due_date" not in (task_event["details"] or {})

    assert note_audit.status_code == 200, note_audit.text
    assert phi_audit.status_code == 200, phi_audit.text
    assert any(item["target_id"] == str(entity.id) for item in note_audit.json()["items"])
    assert any(item["target_id"] == str(entity.id) for item in phi_audit.json()["items"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "route_prefix"),
    [
        ("intended_parent", "/intended-parents"),
        ("donor", "/donors"),
    ],
)
async def test_entity_activity_audits_visible_task_preview(
    authed_client,
    db,
    test_auth,
    entity_type: str,
    route_prefix: str,
):
    entity = (
        _create_intended_parent(db, test_auth.org.id)
        if entity_type == "intended_parent"
        else _create_donor(db, test_auth.org.id)
    )
    task = Task(
        id=uuid.uuid4(),
        organization_id=test_auth.org.id,
        intended_parent_id=entity.id if entity_type == "intended_parent" else None,
        donor_id=entity.id if entity_type == "donor" else None,
        created_by_user_id=test_auth.user.id,
        owner_type="user",
        owner_id=test_auth.user.id,
        title="Private task preview",
        task_type="review",
    )
    db.add(task)
    db.commit()

    response = await authed_client.get(f"{route_prefix}/{entity.id}/activity")
    phi_audit = await authed_client.get(
        "/audit/",
        params={"event_type": "phi_viewed", "per_page": 100},
    )

    assert response.status_code == 200, response.text
    task_event = next(
        item for item in response.json()["items"] if item["activity_type"] == "task_created"
    )
    assert task_event["details"]["title"] == "Private task preview"
    assert phi_audit.status_code == 200, phi_audit.text
    assert any(
        item["target_id"] == str(entity.id) and item["details"]["view"] == "activity_tasks"
        for item in phi_audit.json()["items"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "route_prefix"),
    [
        ("intended_parent", "/intended-parents"),
        ("donor", "/donors"),
    ],
)
async def test_entity_activity_hides_cross_org_records(
    authed_client,
    db,
    entity_type: str,
    route_prefix: str,
):
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Activity Organization",
        slug=f"other-activity-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    entity = (
        _create_intended_parent(db, other_org.id)
        if entity_type == "intended_parent"
        else _create_donor(db, other_org.id)
    )

    response = await authed_client.get(f"{route_prefix}/{entity.id}/activity")

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "route_prefix", "permission"),
    [
        ("intended_parent", "/intended-parents", "view_intended_parents"),
        ("donor", "/donors", "view_donors"),
    ],
)
async def test_entity_activity_requires_entity_view_permission(
    db,
    test_org,
    entity_type: str,
    route_prefix: str,
    permission: str,
):
    entity = (
        _create_intended_parent(db, test_org.id)
        if entity_type == "intended_parent"
        else _create_donor(db, test_org.id)
    )

    async with _client_with_revoked_permission(db, test_org, permission) as restricted_client:
        response = await restricted_client.get(f"{route_prefix}/{entity.id}/activity")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_donor_activity_keeps_egg_and_sperm_stage_labels_isolated(
    authed_client,
    db,
    test_auth,
):
    egg_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_auth.org.id,
        entity_type="egg_donor",
    )
    sperm_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        test_auth.org.id,
        entity_type="sperm_donor",
    )
    egg_ready = pipeline_service.get_stage_by_key(db, egg_pipeline.id, "ready_to_match")
    sperm_ready = pipeline_service.get_stage_by_key(db, sperm_pipeline.id, "available")
    assert egg_ready is not None
    assert sperm_ready is not None
    egg_ready.label = "Egg Ready"
    sperm_ready.label = "Sperm Available"
    db.commit()

    created_ids: dict[str, str] = {}
    for donor_type in ("egg", "sperm"):
        created = await authed_client.post(
            "/donors",
            json={
                "donor_type": donor_type,
                "full_name": f"{donor_type.title()} Activity Donor",
                "email": f"{donor_type}-activity-{uuid.uuid4().hex[:8]}@example.com",
            },
        )
        assert created.status_code == 201, created.text
        created_ids[donor_type] = created.json()["id"]

    for donor_type, target_stage in (("egg", egg_ready), ("sperm", sperm_ready)):
        changed = await authed_client.patch(
            f"/donors/{created_ids[donor_type]}/status",
            json={"stage_id": str(target_stage.id)},
        )
        assert changed.status_code == 200, changed.text

    egg_activity = await authed_client.get(
        f"/donors/{created_ids['egg']}/activity",
        params={"per_page": 100},
    )
    sperm_activity = await authed_client.get(
        f"/donors/{created_ids['sperm']}/activity",
        params={"per_page": 100},
    )
    assert egg_activity.status_code == 200, egg_activity.text
    assert sperm_activity.status_code == 200, sperm_activity.text

    egg_statuses = [
        item for item in egg_activity.json()["items"] if item["activity_type"] == "status_changed"
    ]
    sperm_statuses = [
        item for item in sperm_activity.json()["items"] if item["activity_type"] == "status_changed"
    ]
    egg_transition = next(
        item for item in egg_statuses if item["details"]["to_stage_id"] == str(egg_ready.id)
    )
    sperm_transition = next(
        item for item in sperm_statuses if item["details"]["to_stage_id"] == str(sperm_ready.id)
    )
    assert egg_transition["details"]["to"] == "Egg Ready"
    assert sperm_transition["details"]["to"] == "Sperm Available"
    assert all(item["details"]["to_stage_id"] != str(sperm_ready.id) for item in egg_statuses)
    assert all(item["details"]["to_stage_id"] != str(egg_ready.id) for item in sperm_statuses)


@pytest.mark.asyncio
async def test_entity_activity_pagination_is_stable_for_equal_timestamps(
    authed_client,
    db,
    test_auth,
):
    intended_parent = _create_intended_parent(db, test_auth.org.id)
    occurred_at = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    event_ids = [UUID(int=value) for value in range(1, 5)]
    db.add_all(
        [
            EntityActivityLog(
                id=event_id,
                organization_id=test_auth.org.id,
                intended_parent_id=intended_parent.id,
                activity_type=f"test_event_{index}",
                actor_user_id=test_auth.user.id,
                occurred_at=occurred_at,
            )
            for index, event_id in enumerate(event_ids, start=1)
        ]
    )
    db.commit()

    first_page = await authed_client.get(
        f"/intended-parents/{intended_parent.id}/activity",
        params={"page": 1, "per_page": 2},
    )
    second_page = await authed_client.get(
        f"/intended-parents/{intended_parent.id}/activity",
        params={"page": 2, "per_page": 2},
    )
    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text

    first_ids = [item["id"] for item in first_page.json()["items"]]
    second_ids = [item["id"] for item in second_page.json()["items"]]
    assert first_ids == [str(event_ids[3]), str(event_ids[2])]
    assert second_ids == [str(event_ids[1]), str(event_ids[0])]
    assert len(set(first_ids + second_ids)) == 4


def test_record_activity_rejects_subject_from_another_organization(db, test_auth):
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Activity Writer Organization",
        slug=f"other-activity-writer-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    intended_parent = _create_intended_parent(db, other_org.id)

    with pytest.raises(ValueError, match="subject not found in organization"):
        entity_activity_service.record_activity(
            db,
            org_id=test_auth.org.id,
            entity_type="intended_parent",
            entity_id=intended_parent.id,
            activity_type="info_edited",
            actor_user_id=test_auth.user.id,
            details={"changed_fields": ["state"]},
        )


@pytest.mark.asyncio
async def test_intended_parent_activity_ignores_history_scoped_to_another_organization(
    authed_client,
    db,
    test_auth,
):
    intended_parent = _create_intended_parent(db, test_auth.org.id)
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other History Organization",
        slug=f"other-history-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    db.add(
        IntendedParentStatusHistory(
            id=uuid.uuid4(),
            intended_parent_id=intended_parent.id,
            organization_id=other_org.id,
            changed_by_user_id=test_auth.user.id,
            old_stage_id=None,
            new_stage_id=intended_parent.stage_id,
            old_status=None,
            new_status=intended_parent.status,
            old_label_snapshot=None,
            new_label_snapshot="Foreign history",
            effective_at=datetime(2026, 8, 29, 12, 0, tzinfo=UTC),
            recorded_at=datetime(2026, 8, 29, 12, 0, tzinfo=UTC),
        )
    )
    db.commit()

    response = await authed_client.get(f"/intended-parents/{intended_parent.id}/activity")

    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "route_prefix"),
    [
        ("intended_parent", "/intended-parents"),
        ("donor", "/donors"),
    ],
)
async def test_deleted_note_keeps_durable_activity_without_copying_content(
    authed_client,
    db,
    test_auth,
    entity_type: str,
    route_prefix: str,
):
    entity = (
        _create_intended_parent(db, test_auth.org.id)
        if entity_type == "intended_parent"
        else _create_donor(db, test_auth.org.id)
    )
    created = await authed_client.post(
        f"{route_prefix}/{entity.id}/notes",
        json={"content": "<p>Private note text must not be copied into the ledger.</p>"},
    )
    assert created.status_code == 201, created.text

    deleted = await authed_client.delete(f"{route_prefix}/{entity.id}/notes/{created.json()['id']}")
    assert deleted.status_code == 204, deleted.text

    response = await authed_client.get(f"{route_prefix}/{entity.id}/activity")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["activity_type"] for item in items] == ["note_deleted", "note_added"]
    assert all("preview" not in (item["details"] or {}) for item in items)

    from app.db.models import EntityActivityLog

    rows = (
        db.query(EntityActivityLog)
        .filter(EntityActivityLog.organization_id == test_auth.org.id)
        .order_by(EntityActivityLog.recorded_at)
        .all()
    )
    assert [row.activity_type for row in rows] == ["note_added", "note_deleted"]
    assert all("Private note text" not in str(row.details) for row in rows)


@pytest.mark.asyncio
async def test_intended_parent_note_delete_rejects_donor_note_with_same_entity_id(
    authed_client,
    db,
    test_auth,
):
    shared_id = uuid.uuid4()
    intended_parent = _create_intended_parent(
        db,
        test_auth.org.id,
        entity_id=shared_id,
    )
    donor = _create_donor(
        db,
        test_auth.org.id,
        entity_id=shared_id,
    )
    note = EntityNote(
        id=uuid.uuid4(),
        organization_id=test_auth.org.id,
        entity_type="donor",
        entity_id=donor.id,
        author_id=test_auth.user.id,
        content="<p>Donor-only note.</p>",
    )
    db.add(note)
    db.commit()

    response = await authed_client.delete(f"/intended-parents/{intended_parent.id}/notes/{note.id}")

    assert response.status_code == 404
    donor_notes = await authed_client.get(f"/donors/{donor.id}/notes")
    assert donor_notes.status_code == 200, donor_notes.text
    assert [item["id"] for item in donor_notes.json()] == [str(note.id)]


@pytest.mark.asyncio
async def test_synthesized_activity_event_ids_are_unique_and_deterministic(
    authed_client,
    db,
    test_auth,
):
    intended_parent = _create_intended_parent(db, test_auth.org.id)
    created_at = datetime(2026, 8, 29, 14, 0, tzinfo=UTC)
    completed_at = datetime(2026, 8, 29, 15, 0, tzinfo=UTC)
    task = Task(
        id=uuid.uuid4(),
        organization_id=test_auth.org.id,
        intended_parent_id=intended_parent.id,
        created_by_user_id=test_auth.user.id,
        owner_type="user",
        owner_id=test_auth.user.id,
        title="Historical completed task",
        task_type="review",
        is_completed=True,
        completed_at=completed_at,
        completed_by_user_id=test_auth.user.id,
        created_at=created_at,
        updated_at=completed_at,
    )
    attachment = Attachment(
        id=uuid.uuid4(),
        organization_id=test_auth.org.id,
        intended_parent_id=intended_parent.id,
        uploaded_by_user_id=test_auth.user.id,
        deleted_by_user_id=test_auth.user.id,
        filename="historical.pdf",
        storage_key=f"{test_auth.org.id}/{intended_parent.id}/historical.pdf",
        content_type="application/pdf",
        file_size=128,
        checksum_sha256="b" * 64,
        scan_status="clean",
        quarantined=False,
        created_at=created_at,
        deleted_at=completed_at,
    )
    db.add_all([task, attachment])
    db.commit()

    first = await authed_client.get(
        f"/intended-parents/{intended_parent.id}/activity",
        params={"per_page": 100},
    )
    second = await authed_client.get(
        f"/intended-parents/{intended_parent.id}/activity",
        params={"per_page": 100},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_items = first.json()["items"]
    second_items = second.json()["items"]
    assert len(first_items) == 4
    assert len({item["id"] for item in first_items}) == len(first_items)
    assert [(item["activity_type"], item["id"]) for item in first_items] == [
        (item["activity_type"], item["id"]) for item in second_items
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "route_prefix", "create_payload"),
    [
        (
            "intended_parent",
            "/intended-parents",
            {
                "full_name": "Lifecycle Intended Parent",
                "email": "lifecycle-ip@example.com",
            },
        ),
        (
            "donor",
            "/donors",
            {
                "donor_type": "egg",
                "full_name": "Lifecycle Donor",
                "email": "lifecycle-donor@example.com",
            },
        ),
    ],
)
async def test_entity_activity_tracks_record_lifecycle(
    authed_client,
    db,
    test_auth,
    entity_type: str,
    route_prefix: str,
    create_payload: dict[str, str],
):
    _stage(db, test_auth.org.id, entity_type if entity_type != "donor" else "egg_donor")
    created = await authed_client.post(route_prefix, json=create_payload)
    assert created.status_code == 201, created.text
    entity_id = created.json()["id"]

    updated = await authed_client.patch(
        f"{route_prefix}/{entity_id}",
        json={"full_name": f"Updated {create_payload['full_name']}"},
    )
    assert updated.status_code == 200, updated.text
    assert (await authed_client.post(f"{route_prefix}/{entity_id}/archive")).status_code == 200
    assert (await authed_client.post(f"{route_prefix}/{entity_id}/restore")).status_code == 200

    response = await authed_client.get(
        f"{route_prefix}/{entity_id}/activity",
        params={"per_page": 100},
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    types = [item["activity_type"] for item in items]
    assert {"record_created", "info_edited", "archived", "restored"} <= set(types)
    edited = next(item for item in items if item["activity_type"] == "info_edited")
    assert edited["details"] == {"changed_fields": ["full_name"]}

    if entity_type == "intended_parent":
        archive_status = next(
            item
            for item in items
            if item["activity_type"] == "status_changed" and item["details"]["reason"] == "Archived"
        )
        restore_status = next(
            item
            for item in items
            if item["activity_type"] == "status_changed"
            and item["details"]["reason"] == "Restored from archive"
        )
        assert archive_status["details"]["to"] == "Archived"
        assert restore_status["details"]["from"] == "Archived"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "route_prefix", "subject_field"),
    [
        ("intended_parent", "/intended-parents", "intended_parent_id"),
        ("donor", "/donors", "donor_id"),
    ],
)
async def test_public_task_lifecycle_is_durable_without_source_duplicates(
    authed_client,
    db,
    test_auth,
    entity_type: str,
    route_prefix: str,
    subject_field: str,
):
    entity = (
        _create_intended_parent(db, test_auth.org.id)
        if entity_type == "intended_parent"
        else _create_donor(db, test_auth.org.id)
    )
    created = await authed_client.post(
        "/tasks",
        json={"title": "Activity task", subject_field: str(entity.id)},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    updated = await authed_client.patch(
        f"/tasks/{task_id}",
        json={"title": "Updated activity task"},
    )
    assert updated.status_code == 200, updated.text
    completed = await authed_client.post(f"/tasks/{task_id}/complete")
    assert completed.status_code == 200, completed.text
    reopened = await authed_client.post(f"/tasks/{task_id}/uncomplete")
    assert reopened.status_code == 200, reopened.text
    deleted = await authed_client.delete(f"/tasks/{task_id}")
    assert deleted.status_code == 204, deleted.text

    response = await authed_client.get(
        f"{route_prefix}/{entity.id}/activity",
        params={"per_page": 100},
    )
    assert response.status_code == 200, response.text
    task_items = [
        item for item in response.json()["items"] if item["activity_type"].startswith("task_")
    ]
    assert [item["activity_type"] for item in reversed(task_items)] == [
        "task_created",
        "task_updated",
        "task_completed",
        "task_uncompleted",
        "task_deleted",
    ]
    assert len({item["id"] for item in task_items}) == 5
    assert all(item["actor_user_id"] == str(test_auth.user.id) for item in task_items)
    assert db.get(Task, UUID(task_id)) is None


def test_task_creation_rolls_back_when_activity_recording_fails(
    db,
    test_auth,
    monkeypatch,
):
    intended_parent = _create_intended_parent(db, test_auth.org.id)
    title = f"Rollback activity task {uuid.uuid4().hex}"

    def fail_activity(*_args, **_kwargs):
        raise RuntimeError("activity persistence failed")

    monkeypatch.setattr(entity_activity_service, "record_activity", fail_activity)

    with pytest.raises(RuntimeError, match="activity persistence failed"):
        task_service.create_task(
            db,
            test_auth.org.id,
            test_auth.user.id,
            TaskCreate(title=title, intended_parent_id=intended_parent.id),
        )
    db.rollback()

    assert db.query(Task).filter(Task.title == title).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "route_prefix", "attachment_scope"),
    [
        ("intended_parent", "/intended-parents", "intended-parents"),
        ("donor", "/donors", "donors"),
    ],
)
async def test_public_attachment_lifecycle_is_durable_without_source_duplicates(
    authed_client,
    db,
    test_auth,
    tmp_path,
    monkeypatch,
    entity_type: str,
    route_prefix: str,
    attachment_scope: str,
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)
    entity = (
        _create_intended_parent(db, test_auth.org.id)
        if entity_type == "intended_parent"
        else _create_donor(db, test_auth.org.id)
    )

    uploaded = await authed_client.post(
        f"/attachments/{attachment_scope}/{entity.id}/attachments",
        files={"file": ("activity.pdf", b"%PDF-1.4 activity", "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    attachment_id = uploaded.json()["id"]
    deleted = await authed_client.delete(f"/attachments/{attachment_id}")
    assert deleted.status_code == 200, deleted.text

    response = await authed_client.get(
        f"{route_prefix}/{entity.id}/activity",
        params={"per_page": 100},
    )
    assert response.status_code == 200, response.text
    attachment_items = [
        item for item in response.json()["items"] if item["activity_type"].startswith("attachment_")
    ]
    assert [item["activity_type"] for item in reversed(attachment_items)] == [
        "attachment_added",
        "attachment_deleted",
    ]
    assert len({item["id"] for item in attachment_items}) == 2
    assert all(item["actor_user_id"] == str(test_auth.user.id) for item in attachment_items)
