"""Update Field actions are validated at save time against the record they update."""

from __future__ import annotations

import uuid

import pytest

from app.db.enums import WorkflowTriggerType
from app.schemas.donor import DonorCreate
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services import donor_service, workflow_service
from app.services.workflow_engine import engine


def _update_source(value: object) -> dict[str, object]:
    return {"action_type": "update_field", "field": "source", "value": value}


def _donor_workflow(db, org_id, user_id, actions, *, subject_type="egg_donor"):
    return workflow_service.create_workflow(
        db,
        org_id,
        user_id,
        WorkflowCreate(
            name=f"Donor source {uuid.uuid4()}",
            subject_type=subject_type,
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            actions=actions,
        ),
    )


@pytest.mark.parametrize(
    ("value", "error"),
    [
        ("Facebook", "Invalid donor source"),
        (7, "Donor source must be text"),
        ("  ", "Donor source is required"),
        (None, "Donor source is required"),
    ],
)
def test_donor_source_update_rejects_unknown_source_at_save(db, test_org, test_user, value, error):
    with pytest.raises(ValueError, match=error):
        _donor_workflow(db, test_org.id, test_user.id, [_update_source(value)])


@pytest.mark.parametrize(
    ("value", "canonical"),
    [("Meta", "meta"), (" TikTok ", "tiktok"), ("website_intake", "website")],
)
def test_donor_source_update_stores_the_canonical_source(db, test_org, test_user, value, canonical):
    workflow = _donor_workflow(db, test_org.id, test_user.id, [_update_source(value)])

    assert workflow.actions[0]["value"] == canonical


def test_donor_source_update_rejects_unknown_source_on_edit(db, test_org, test_user):
    workflow = _donor_workflow(db, test_org.id, test_user.id, [_update_source("google")])

    with pytest.raises(ValueError, match="Invalid donor source"):
        workflow_service.update_workflow(
            db,
            workflow,
            test_user.id,
            WorkflowUpdate(actions=[_update_source("Facebook")]),
        )
    db.refresh(workflow)
    assert workflow.actions[0]["value"] == "google"


def test_saved_donor_source_update_runs(db, test_org, test_user):
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Source Donor",
            email=f"source-{uuid.uuid4().hex[:8]}@example.com",
        ),
        emit_workflow_events=False,
    )
    workflow = _donor_workflow(
        db,
        test_org.id,
        test_user.id,
        [_update_source("Referral")],
        subject_type="sperm_donor",
    )

    execution = engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="sperm_donor",
        subject_id=donor.id,
        event_data={"donor_id": str(donor.id)},
    )

    assert execution is not None
    assert execution.status == "success", execution.actions_executed
    db.refresh(donor)
    assert donor.source == "referral"


@pytest.mark.asyncio
async def test_api_rejects_unknown_donor_source_update(authed_client):
    response = await authed_client.post(
        "/workflows",
        json={
            "name": "API donor source",
            "subject_type": "egg_donor",
            "trigger_type": "donor_created",
            "trigger_config": {},
            "conditions": [],
            "condition_logic": "AND",
            "actions": [_update_source("Facebook")],
            "is_enabled": True,
            "scope": "org",
        },
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"].startswith("Invalid donor source")
