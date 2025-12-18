import uuid

import pytest


@pytest.mark.asyncio
async def test_case_create_sets_owner_fields(authed_client, test_auth):
    resp = await authed_client.post(
        "/cases",
        json={
            "full_name": "Jane Queue Test",
            "email": f"jane-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert resp.status_code == 201, resp.text

    data = resp.json()
    assert data["owner_type"] == "user"
    assert data["owner_id"] == str(test_auth.user.id)
    assert data["assigned_to_user_id"] == str(test_auth.user.id)


def test_system_case_defaults_to_unassigned_queue(db, test_org):
    from app.schemas.case import CaseCreate
    from app.services import case_service, queue_service

    case = case_service.create_case(
        db=db,
        org_id=test_org.id,
        user_id=None,
        data=CaseCreate(
            full_name="System Lead",
            email=f"system-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )

    default_queue = queue_service.get_or_create_default_queue(db, test_org.id)
    assert case.owner_type == "queue"
    assert case.owner_id == default_queue.id
    assert case.assigned_to_user_id is None


@pytest.mark.asyncio
async def test_queue_assign_claim_release_flow(authed_client):
    # Create two queues
    q1 = await authed_client.post("/queues", json={"name": f"Queue A {uuid.uuid4().hex[:6]}", "description": ""})
    assert q1.status_code == 201, q1.text
    queue_a = q1.json()

    q2 = await authed_client.post("/queues", json={"name": f"Queue B {uuid.uuid4().hex[:6]}", "description": ""})
    assert q2.status_code == 201, q2.text
    queue_b = q2.json()

    # Create a case (user-owned by default)
    c = await authed_client.post(
        "/cases",
        json={"full_name": "Claim Flow", "email": f"claim-{uuid.uuid4().hex[:8]}@example.com"},
    )
    assert c.status_code == 201, c.text
    case_id = c.json()["id"]

    # Assign to queue A
    assign = await authed_client.post(f"/queues/cases/{case_id}/assign", json={"queue_id": queue_a["id"]})
    assert assign.status_code == 200, assign.text

    after_assign = await authed_client.get(f"/cases/{case_id}")
    assert after_assign.status_code == 200, after_assign.text
    data = after_assign.json()
    assert data["owner_type"] == "queue"
    assert data["owner_id"] == queue_a["id"]
    assert data["assigned_to_user_id"] is None

    # Claim from queue
    claim = await authed_client.post(f"/queues/cases/{case_id}/claim")
    assert claim.status_code == 200, claim.text

    after_claim = await authed_client.get(f"/cases/{case_id}")
    assert after_claim.status_code == 200, after_claim.text
    data = after_claim.json()
    assert data["owner_type"] == "user"
    assert data["assigned_to_user_id"] is not None

    # Release to queue B
    release = await authed_client.post(f"/queues/cases/{case_id}/release", json={"queue_id": queue_b["id"]})
    assert release.status_code == 200, release.text

    after_release = await authed_client.get(f"/cases/{case_id}")
    assert after_release.status_code == 200, after_release.text
    data = after_release.json()
    assert data["owner_type"] == "queue"
    assert data["owner_id"] == queue_b["id"]
    assert data["assigned_to_user_id"] is None

