from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.db.enums import ContactStatus
from app.db.models import PipelineStage, Surrogate, SurrogateActivityLog


@pytest.fixture
def shared_contact_record(db, test_org):
    from app.db.models import OrganizationPermissionPolicy
    from app.db.models.record_access import RecordCollaborator
    from app.services import queue_service
    from tests.test_record_scopes_v2 import _member, _record

    actor, member = _member(db, test_org.id, "intake_specialist")
    record = _record(db, actor, "surrogate", key="approved")
    pool = queue_service.get_or_create_surrogate_pool_queue(db, test_org.id)
    record.owner_type, record.owner_id, record.assigned_at = "queue", pool.id, None
    record.created_at = datetime.now(UTC) - timedelta(days=2)
    policy = OrganizationPermissionPolicy(organization_id=test_org.id, version=2)
    collaborator = RecordCollaborator(
        organization_id=test_org.id,
        membership_id=member.id,
        user_id=actor.user_id,
        surrogate_id=record.id,
    )
    db.add_all([policy, collaborator])
    db.flush()
    return record, member, pool, policy, collaborator


@pytest.mark.asyncio
async def test_retained_intake_logs_shared_pool_followup_without_regressing_approval(
    db,
    test_org,
    shared_contact_record,
):
    from app.db.enums import Role
    from app.db.models import SurrogateContactAttempt
    from tests.test_email_templates_personal_scope import authed_client_for_user

    record, member, pool, _, _ = shared_contact_record
    approved_id = record.stage_id
    async with authed_client_for_user(
        db, test_org.id, member.user, Role.INTAKE_SPECIALIST
    ) as client:
        for outcome in ("no_answer", "reached"):
            result = await client.post(
                f"/surrogates/{record.id}/contact-attempts",
                json={"contact_methods": ["phone"], "outcome": outcome},
            )
            assert result.status_code == 201, result.text
            assert result.json()["surrogate_owner_id_at_attempt"] == str(pool.id)
        summary = await client.get(f"/surrogates/{record.id}/contact-attempts")
        assert summary.status_code == 200, summary.text
        assert summary.json()["current_assignment_attempts"] == 2
        assert summary.json()["distinct_days_current_assignment"] == 1
    db.refresh(record)
    assert (record.owner_type, record.owner_id, record.stage_id, record.assigned_at) == (
        "queue",
        pool.id,
        approved_id,
        None,
    )
    assert record.contact_status == ContactStatus.REACHED.value
    assert db.query(SurrogateContactAttempt).filter_by(surrogate_id=record.id).count() == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("boundary", "expected_status"),
    [
        ("ordinary_queue", 400),
        ("v1_pool", 400),
        ("preapproval_pool", 400),
        ("inactive_pool", 400),
        ("foreign_queue", 400),
        ("missing_collaborator", 403),
        ("edit_denied", 403),
        ("archived", 403),
        ("foreign_record", 404),
        ("before_creation", 400),
    ],
)
async def test_shared_pool_contact_attempt_keeps_assignment_and_access_boundaries(
    db,
    test_org,
    shared_contact_record,
    boundary,
    expected_status,
):
    from uuid import uuid4

    from app.db.enums import Role
    from app.db.models import Organization, RolePermission, SurrogateContactAttempt
    from app.services import pipeline_service, queue_service
    from tests.test_email_templates_personal_scope import authed_client_for_user

    record, member, pool, policy, collaborator = shared_contact_record
    actor_role = Role.INTAKE_SPECIALIST
    payload = {"contact_methods": ["phone"], "outcome": "no_answer"}
    if boundary == "ordinary_queue":
        record.owner_id = queue_service.create_queue(db, test_org.id, "Other Queue").id
    elif boundary == "v1_pool":
        policy.version = 1
        member.role = "admin"
        actor_role = Role.ADMIN
    elif boundary == "preapproval_pool":
        pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
        record.stage_id = next(
            stage.id for stage in pipeline.stages if stage.stage_key == "contacted"
        )
    elif boundary == "inactive_pool":
        pool.is_active = False
    elif boundary == "missing_collaborator":
        db.delete(collaborator)
    elif boundary == "edit_denied":
        db.add(
            RolePermission(
                organization_id=test_org.id,
                role="intake_specialist",
                permission="edit_surrogates",
                is_granted=False,
            )
        )
    elif boundary == "archived":
        record.is_archived = True
    elif boundary == "before_creation":
        payload["attempted_at"] = (record.created_at - timedelta(days=1)).isoformat()
    else:
        other = Organization(id=uuid4(), name="Other", slug=uuid4().hex)
        db.add(other)
        db.flush()
        if boundary == "foreign_queue":
            record.owner_id = queue_service.create_queue(db, other.id, "Surrogate Pool").id
        else:
            record.organization_id = other.id
    db.flush()
    async with authed_client_for_user(db, test_org.id, member.user, actor_role) as client:
        response = await client.post(f"/surrogates/{record.id}/contact-attempts", json=payload)
        assert response.status_code == expected_status, response.text
    assert db.query(SurrogateContactAttempt).filter_by(surrogate_id=record.id).count() == 0


@pytest.mark.asyncio
async def test_contact_attempt_blocked_for_queue_owned(authed_client):
    queue_res = await authed_client.post("/queues", json={"name": "Queue A", "description": ""})
    assert queue_res.status_code == 201, queue_res.text
    queue_id = queue_res.json()["id"]

    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Queue Attempt", "email": "queue-attempt@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    assign_res = await authed_client.post(
        f"/queues/surrogates/{surrogate_id}/assign", json={"queue_id": queue_id}
    )
    assert assign_res.status_code == 200, assign_res.text

    attempt_res = await authed_client.post(
        f"/surrogates/{surrogate_id}/contact-attempts",
        json={"contact_methods": ["phone"], "outcome": "no_answer"},
    )
    assert attempt_res.status_code == 400, attempt_res.text


@pytest.mark.asyncio
async def test_contact_attempt_rejects_before_assignment(authed_client):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Backdated", "email": "backdated@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    attempted_at = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    attempt_res = await authed_client.post(
        f"/surrogates/{surrogate_id}/contact-attempts",
        json={
            "contact_methods": ["phone"],
            "outcome": "no_answer",
            "attempted_at": attempted_at,
        },
    )
    assert attempt_res.status_code == 400, attempt_res.text


@pytest.mark.asyncio
async def test_contact_attempt_reached_updates_stage_and_status(authed_client, db):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Reached", "email": "reached@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    attempt_res = await authed_client.post(
        f"/surrogates/{surrogate_id}/contact-attempts",
        json={"contact_methods": ["phone"], "outcome": "reached"},
    )
    assert attempt_res.status_code == 201, attempt_res.text

    case = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate_id)).first()
    assert case is not None
    assert case.contact_status == ContactStatus.REACHED.value
    assert case.contacted_at is not None

    stage = db.query(PipelineStage).filter(PipelineStage.id == case.stage_id).first()
    assert stage is not None
    assert stage.slug == "contacted"


@pytest.mark.asyncio
async def test_contact_attempt_updates_surrogate_last_modified(authed_client, db):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Contact Modified", "email": "contact-modified@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    case = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate_id)).first()
    assert case is not None
    before_modified_at = datetime.now(UTC) - timedelta(days=30)
    case.updated_at = before_modified_at
    db.commit()

    attempt_res = await authed_client.post(
        f"/surrogates/{surrogate_id}/contact-attempts",
        json={"contact_methods": ["phone"], "outcome": "no_answer"},
    )
    assert attempt_res.status_code == 201, attempt_res.text

    db.refresh(case)
    assert case.updated_at is not None
    assert case.updated_at > before_modified_at

    list_res = await authed_client.get("/surrogates")
    assert list_res.status_code == 200, list_res.text
    match = next((item for item in list_res.json()["items"] if item["id"] == surrogate_id), None)
    assert match is not None
    assert datetime.fromisoformat(match["updated_at"].replace("Z", "+00:00")) > before_modified_at


@pytest.mark.asyncio
async def test_manual_stage_change_sets_contact_status(authed_client, db):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Manual Contacted", "email": "manual@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    case = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate_id)).first()
    assert case is not None
    current_stage = db.query(PipelineStage).filter(PipelineStage.id == case.stage_id).first()
    assert current_stage is not None

    contacted_stage = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == current_stage.pipeline_id,
            PipelineStage.slug == "contacted",
        )
        .first()
    )
    assert contacted_stage is not None

    change_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert change_res.status_code == 200, change_res.text

    db.refresh(case)
    assert case.contact_status == ContactStatus.REACHED.value
    assert case.contacted_at is not None


@pytest.mark.asyncio
async def test_manual_stage_change_updates_surrogate_last_modified(authed_client, db):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Stage Modified", "email": "stage-modified@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    case = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate_id)).first()
    assert case is not None
    current_stage = db.query(PipelineStage).filter(PipelineStage.id == case.stage_id).first()
    assert current_stage is not None

    contacted_stage = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == current_stage.pipeline_id,
            PipelineStage.slug == "contacted",
        )
        .first()
    )
    assert contacted_stage is not None

    before_modified_at = datetime.now(UTC) - timedelta(days=30)
    case.updated_at = before_modified_at
    db.commit()

    change_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert change_res.status_code == 200, change_res.text

    db.refresh(case)
    assert case.updated_at is not None
    assert case.updated_at > before_modified_at


@pytest.mark.asyncio
async def test_manual_stage_change_uses_contacted_stage_key_when_slug_is_renamed(authed_client, db):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Manual Custom Contacted", "email": "manual-custom@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    case = db.query(Surrogate).filter(Surrogate.id == UUID(surrogate_id)).first()
    assert case is not None
    current_stage = db.query(PipelineStage).filter(PipelineStage.id == case.stage_id).first()
    assert current_stage is not None

    contacted_stage = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == current_stage.pipeline_id,
            PipelineStage.stage_key == "contacted",
        )
        .first()
    )
    assert contacted_stage is not None
    contacted_stage.slug = "first_touch"
    db.commit()

    change_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}/status",
        json={"stage_id": str(contacted_stage.id)},
    )
    assert change_res.status_code == 200, change_res.text

    db.refresh(case)
    assert case.stage_id == contacted_stage.id
    assert case.contact_status == ContactStatus.REACHED.value
    assert case.contacted_at is not None


@pytest.mark.asyncio
async def test_contact_attempt_activity_includes_note_preview(authed_client, db):
    case_res = await authed_client.post(
        "/surrogates",
        json={"full_name": "Contact Notes", "email": "contact-notes@example.com"},
    )
    assert case_res.status_code == 201, case_res.text
    surrogate_id = case_res.json()["id"]

    attempt_res = await authed_client.post(
        f"/surrogates/{surrogate_id}/contact-attempts",
        json={
            "contact_methods": ["phone"],
            "outcome": "no_answer",
            "notes": "<p>Left voicemail and asked for callback.</p>",
        },
    )
    assert attempt_res.status_code == 201, attempt_res.text

    activity = (
        db.query(SurrogateActivityLog)
        .filter(
            SurrogateActivityLog.surrogate_id == UUID(surrogate_id),
            SurrogateActivityLog.activity_type == "contact_attempt",
        )
        .order_by(SurrogateActivityLog.created_at.desc())
        .first()
    )
    assert activity is not None
    details = activity.details or {}
    assert details.get("note_preview") == "Left voicemail and asked for callback."
