import json
import uuid

import pytest

from app.core.encryption import hash_email
from app.db.models import (
    AutomationWorkflow,
    EntityNote,
    Membership,
    Notification,
    PipelineStage,
    Queue,
    Surrogate,
    User,
)
from app.db.enums import NotificationType, Role
from app.utils.normalization import normalize_email


def _create_surrogate(db, org_id, owner_type, owner_id, stage):
    email = f"draft-test-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type=owner_type,
        owner_id=owner_id,
        created_by_user_id=None,
        full_name="Draft Candidate",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


async def _create_published_form_and_token(*, authed_client, surrogate_id: str):
    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [
                    {"key": "full_name", "label": "Full Name", "type": "text", "required": False},
                    {"key": "has_child", "label": "Has Child", "type": "checkbox"},
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={"name": "Application Form", "description": "Test form", "form_schema": schema},
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    token_res = await authed_client.post(
        f"/forms/{form_id}/tokens",
        json={"surrogate_id": surrogate_id, "expires_in_days": 7},
    )
    assert token_res.status_code == 200
    token = token_res.json()["token"]

    return form_id, token


@pytest.mark.asyncio
async def test_public_form_draft_sets_started_at_only_when_non_empty(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        owner_type="user",
        owner_id=test_user.id,
        stage=default_stage,
    )
    form_id, token = await _create_published_form_and_token(
        authed_client=authed_client, surrogate_id=str(surrogate.id)
    )

    # Save empty/whitespace answer -> should NOT set started_at
    put_res = await authed_client.put(
        f"/forms/public/{token}/draft",
        json={"answers": {"full_name": "   "}},
    )
    assert put_res.status_code == 200
    assert put_res.json()["started_at"] is None
    assert put_res.json()["updated_at"]

    # False should count as non-empty (checkbox answer present)
    put_res2 = await authed_client.put(
        f"/forms/public/{token}/draft",
        json={"answers": {"has_child": False}},
    )
    assert put_res2.status_code == 200
    assert put_res2.json()["started_at"] is not None

    get_res = await authed_client.get(f"/forms/public/{token}/draft")
    assert get_res.status_code == 200
    payload = get_res.json()
    assert payload["answers"]["has_child"] is False
    assert payload["started_at"] is not None
    assert payload["updated_at"]

    # Internal endpoint should show draft status
    internal_res = await authed_client.get(f"/forms/{form_id}/surrogates/{surrogate.id}/draft")
    assert internal_res.status_code == 200
    assert internal_res.json()["started_at"] is not None
    assert internal_res.json()["updated_at"]


@pytest.mark.asyncio
async def test_public_form_draft_returns_409_when_already_submitted(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        owner_type="user",
        owner_id=test_user.id,
        stage=default_stage,
    )
    _form_id, token = await _create_published_form_and_token(
        authed_client=authed_client, surrogate_id=str(surrogate.id)
    )

    # Submit
    submit_res = await authed_client.post(
        f"/forms/public/{token}/submit",
        data={"answers": json.dumps({"full_name": "Jane Doe"})},
    )
    assert submit_res.status_code == 200

    # Draft writes should now be blocked
    put_res = await authed_client.put(
        f"/forms/public/{token}/draft",
        json={"answers": {"full_name": "New Name"}},
    )
    assert put_res.status_code == 409

    del_res = await authed_client.delete(f"/forms/public/{token}/draft")
    assert del_res.status_code == 409

    # Draft reads should be 404 after submission
    get_res = await authed_client.get(f"/forms/public/{token}/draft")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_form_submission_advances_stage_notifies_owner_and_admins_and_clears_draft(
    authed_client, db, test_org, test_user, default_stage
):
    # Extra admin member
    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Admin User",
        token_version=1,
        is_active=True,
    )
    db.add(admin_user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            organization_id=test_org.id,
            role=Role.ADMIN,
        )
    )
    db.flush()

    surrogate = _create_surrogate(
        db,
        test_org.id,
        owner_type="user",
        owner_id=test_user.id,
        stage=default_stage,
    )
    form_id, token = await _create_published_form_and_token(
        authed_client=authed_client, surrogate_id=str(surrogate.id)
    )

    # Start a draft first
    put_res = await authed_client.put(
        f"/forms/public/{token}/draft",
        json={"answers": {"full_name": "Draft Name"}},
    )
    assert put_res.status_code == 200
    assert put_res.json()["started_at"] is not None

    submit_res = await authed_client.post(
        f"/forms/public/{token}/submit",
        data={"answers": json.dumps({"full_name": "Jane Doe"})},
    )
    assert submit_res.status_code == 200

    # Draft should be cleared/hidden after submission
    draft_get_res = await authed_client.get(f"/forms/public/{token}/draft")
    assert draft_get_res.status_code == 404

    internal_draft_res = await authed_client.get(
        f"/forms/{form_id}/surrogates/{surrogate.id}/draft"
    )
    assert internal_draft_res.status_code == 404

    # Stage should advance to application_submitted (best effort)
    db.refresh(surrogate)
    stage = db.query(PipelineStage).filter(PipelineStage.id == surrogate.stage_id).first()
    assert stage is not None
    assert stage.slug == "application_submitted"

    # In-app notifications should go to owner + admins (admin + developer)
    notifs = (
        db.query(Notification)
        .filter(
            Notification.organization_id == test_org.id,
            Notification.type == NotificationType.FORM_SUBMISSION_RECEIVED.value,
            Notification.entity_type == "surrogate",
            Notification.entity_id == surrogate.id,
        )
        .all()
    )
    notif_user_ids = {n.user_id for n in notifs}
    assert test_user.id in notif_user_ids
    assert admin_user.id in notif_user_ids


@pytest.mark.asyncio
async def test_form_started_workflow_trigger_fires_once(
    authed_client, db, test_org, test_user, default_stage
):
    surrogate = _create_surrogate(
        db,
        test_org.id,
        owner_type="user",
        owner_id=test_user.id,
        stage=default_stage,
    )
    form_id, token = await _create_published_form_and_token(
        authed_client=authed_client, surrogate_id=str(surrogate.id)
    )

    wf = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Form started {uuid.uuid4().hex[:6]}",
        trigger_type="form_started",
        trigger_config={"form_id": form_id},
        conditions=[],
        condition_logic="AND",
        actions=[{"action_type": "add_note", "content": "Draft started"}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(wf)
    db.flush()

    # First non-empty save should trigger workflow
    put_res = await authed_client.put(
        f"/forms/public/{token}/draft",
        json={"answers": {"full_name": "Jane"}},
    )
    assert put_res.status_code == 200
    assert put_res.json()["started_at"] is not None

    notes = (
        db.query(EntityNote)
        .filter(
            EntityNote.organization_id == test_org.id,
            EntityNote.entity_type == "surrogate",
            EntityNote.entity_id == surrogate.id,
            EntityNote.content == "Draft started",
        )
        .all()
    )
    assert len(notes) == 1

    # Subsequent saves should not re-trigger
    put_res2 = await authed_client.put(
        f"/forms/public/{token}/draft",
        json={"answers": {"full_name": "Jane Updated"}},
    )
    assert put_res2.status_code == 200

    notes2 = (
        db.query(EntityNote)
        .filter(
            EntityNote.organization_id == test_org.id,
            EntityNote.entity_type == "surrogate",
            EntityNote.entity_id == surrogate.id,
            EntityNote.content == "Draft started",
        )
        .all()
    )
    assert len(notes2) == 1


@pytest.mark.asyncio
async def test_org_workflow_send_email_all_admins_runs_for_queue_owned_surrogate(
    db, test_org, default_stage
):
    # Create org admin + developer memberships (developer implied by fixture user in other tests)
    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Admin User",
        token_version=1,
        is_active=True,
    )
    dev_user = User(
        id=uuid.uuid4(),
        email=f"dev-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Dev User",
        token_version=1,
        is_active=True,
    )
    db.add_all([admin_user, dev_user])
    db.flush()
    db.add_all(
        [
            Membership(
                id=uuid.uuid4(),
                user_id=admin_user.id,
                organization_id=test_org.id,
                role=Role.ADMIN,
            ),
            Membership(
                id=uuid.uuid4(),
                user_id=dev_user.id,
                organization_id=test_org.id,
                role=Role.DEVELOPER,
            ),
        ]
    )
    db.flush()

    queue = Queue(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Unassigned",
    )
    db.add(queue)
    db.flush()

    surrogate = _create_surrogate(
        db,
        test_org.id,
        owner_type="queue",
        owner_id=queue.id,
        stage=default_stage,
    )

    wf = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Email admins {uuid.uuid4().hex[:6]}",
        trigger_type="surrogate_created",
        trigger_config={},
        conditions=[],
        condition_logic="AND",
        actions=[
            {
                "action_type": "send_email",
                "template_id": str(uuid.uuid4()),
                "recipients": "all_admins",
            }
        ],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
    )
    db.add(wf)
    db.flush()

    from app.services import workflow_triggers
    from app.db.models import Job
    from app.db.enums import JobType

    workflow_triggers.trigger_surrogate_created(db, surrogate)

    jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_EMAIL.value,
        )
        .all()
    )
    # Should queue one email per admin/developer member
    assert len(jobs) == 2
