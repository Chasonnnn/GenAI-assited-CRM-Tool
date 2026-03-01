import json
import uuid

import pytest

from app.core.encryption import hash_email
from app.db.enums import Role
from app.db.models import AutomationWorkflow, Membership, Queue, Surrogate, User
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


@pytest.mark.asyncio
async def test_dedicated_public_form_endpoint_returns_410(client):
    res = await client.get("/forms/public/legacy-token")
    assert res.status_code == 410
    assert "retired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dedicated_public_draft_endpoints_return_410(client):
    token = "legacy-token"

    get_res = await client.get(f"/forms/public/{token}/draft")
    assert get_res.status_code == 410

    put_res = await client.put(
        f"/forms/public/{token}/draft",
        json={"answers": {"full_name": "Test"}},
    )
    assert put_res.status_code == 410

    delete_res = await client.delete(f"/forms/public/{token}/draft")
    assert delete_res.status_code == 410


@pytest.mark.asyncio
async def test_dedicated_public_submit_endpoint_returns_410(client):
    token = "legacy-token"
    submit_res = await client.post(
        f"/forms/public/{token}/submit",
        data={"answers": json.dumps({"full_name": "Legacy"})},
    )
    assert submit_res.status_code == 410
    assert "retired" in submit_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_org_workflow_send_email_all_admins_runs_for_queue_owned_surrogate(
    db, test_org, default_stage
):
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

    from app.db.enums import JobType
    from app.db.models import Job
    from app.services import workflow_triggers

    workflow_triggers.trigger_surrogate_created(db, surrogate)

    jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_EMAIL.value,
        )
        .all()
    )
    assert len(jobs) == 2
