"""Integration tests for shared/public intake submission flows."""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

from app.core.encryption import hash_email, hash_phone
from app.db.enums import FormSubmissionMatchStatus
from app.db.enums import IntakeLeadStatus
from app.db.models import (
    AutomationWorkflow,
    FormSubmission,
    IntakeLead,
    Surrogate,
    Task,
    WorkflowExecution,
)
from app.utils.normalization import (
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_search_text,
)


def _create_surrogate(
    db,
    *,
    org_id,
    user_id,
    stage,
    full_name: str,
    email: str,
    phone: str,
    date_of_birth: str,
):
    normalized_full_name = normalize_name(full_name)
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)

    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name=normalized_full_name,
        full_name_normalized=normalize_search_text(normalized_full_name),
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        phone=normalized_phone,
        phone_hash=hash_phone(normalized_phone),
        date_of_birth=date.fromisoformat(date_of_birth),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


async def _create_published_form_and_shared_link(authed_client):
    schema = {
        "pages": [
            {
                "title": "Identity",
                "fields": [
                    {"key": "full_name", "label": "Full Name", "type": "text", "required": True},
                    {"key": "date_of_birth", "label": "DOB", "type": "date", "required": True},
                    {"key": "phone", "label": "Phone", "type": "text", "required": True},
                    {"key": "email", "label": "Email", "type": "email", "required": True},
                ],
            }
        ]
    }

    create_res = await authed_client.post(
        "/forms",
        json={
            "name": "Shared Intake Form",
            "description": "Campaign intake",
            "form_schema": schema,
        },
    )
    assert create_res.status_code == 200
    form_id = create_res.json()["id"]

    publish_res = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish_res.status_code == 200

    link_res = await authed_client.post(
        f"/forms/{form_id}/intake-links",
        json={
            "campaign_name": "Spring Event",
            "event_name": "Austin Expo",
            "utm_defaults": {"utm_source": "expo"},
        },
    )
    assert link_res.status_code == 200
    link_payload = link_res.json()
    return form_id, link_payload["id"], link_payload["slug"]


@pytest.mark.asyncio
async def test_shared_draft_lifecycle(authed_client):
    _form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)
    draft_session_id = "draft-shared-1"

    missing_res = await authed_client.get(f"/forms/public/intake/{slug}/draft/{draft_session_id}")
    assert missing_res.status_code == 404

    upsert_res = await authed_client.put(
        f"/forms/public/intake/{slug}/draft/{draft_session_id}",
        json={"answers": {"full_name": "Draft Person", "email": "draft@example.com"}},
    )
    assert upsert_res.status_code == 200

    get_res = await authed_client.get(f"/forms/public/intake/{slug}/draft/{draft_session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["answers"]["full_name"] == "Draft Person"

    delete_res = await authed_client.delete(f"/forms/public/intake/{slug}/draft/{draft_session_id}")
    assert delete_res.status_code == 204

    after_delete_res = await authed_client.get(
        f"/forms/public/intake/{slug}/draft/{draft_session_id}"
    )
    assert after_delete_res.status_code == 404


@pytest.mark.asyncio
async def test_shared_submit_no_match_defaults_to_ambiguous_review_without_workflow_actions(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    _form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    payload = {
        "full_name": "No Match Candidate",
        "date_of_birth": "1993-04-12",
        "phone": "+1 (555) 100-1000",
        "email": "nomatch@example.com",
    }
    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={"answers": json.dumps(payload)},
    )
    assert submit_res.status_code == 200
    body = submit_res.json()
    assert body["outcome"] == "ambiguous_review"
    assert body["surrogate_id"] is None
    assert body["intake_lead_id"] is None

    submission = db.query(FormSubmission).filter(FormSubmission.id == body["id"]).first()
    assert submission is not None
    assert submission.source_mode == "shared"
    assert submission.match_status == FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
    assert submission.intake_lead_id is None

    lead = (
        db.query(IntakeLead)
        .filter(
            IntakeLead.organization_id == test_org.id,
            IntakeLead.full_name == "No Match Candidate",
        )
        .first()
    )
    assert lead is None


@pytest.mark.asyncio
async def test_shared_submit_exact_match_links_surrogate(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    surrogate = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Exact Match",
        email="exact@example.com",
        phone="+1 (555) 222-3333",
        date_of_birth="1991-07-10",
    )

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Auto match shared submit {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[{"action_type": "auto_match_submission"}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Exact Match",
                    "date_of_birth": "1991-07-10",
                    "phone": "+1 (555) 222-3333",
                    "email": "exact@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200

    body = submit_res.json()
    assert body["outcome"] == "linked"
    assert body["surrogate_id"] == str(surrogate.id)
    assert body["intake_lead_id"] is None


@pytest.mark.asyncio
async def test_shared_submit_auto_match_requires_approval_without_surrogate_context(
    authed_client,
    db,
    test_org,
    test_user,
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Approval gated auto-match {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[{"action_type": "auto_match_submission", "requires_approval": True}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Needs Approval",
                    "date_of_birth": "1993-04-12",
                    "phone": "+1 (555) 111-2222",
                    "email": "approval-needed@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200
    submission_id = submit_res.json()["id"]

    execution = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == test_org.id,
            WorkflowExecution.workflow_id == workflow.id,
            WorkflowExecution.entity_id == uuid.UUID(submission_id),
        )
        .order_by(WorkflowExecution.executed_at.desc())
        .first()
    )
    assert execution is not None
    assert execution.status == "paused"

    task = (
        db.query(Task)
        .filter(
            Task.organization_id == test_org.id,
            Task.workflow_execution_id == execution.id,
            Task.task_type == "workflow_approval",
        )
        .first()
    )
    assert task is not None
    assert task.owner_id == test_user.id
    assert task.surrogate_id is None

    resolve_res = await authed_client.post(
        f"/tasks/{task.id}/resolve",
        json={"decision": "approve"},
    )
    assert resolve_res.status_code == 200
    db.refresh(task)
    assert task.status == "completed"


@pytest.mark.asyncio
async def test_shared_submit_ambiguous_then_manual_resolve(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    surrogate_a = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Ambiguous Person",
        email="ambiguous-a@example.com",
        phone="+1 (555) 444-5555",
        date_of_birth="1990-01-01",
    )
    surrogate_b = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Ambiguous Person",
        email="ambiguous-b@example.com",
        phone="+1 (555) 444-5555",
        date_of_birth="1990-01-01",
    )

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Ambiguous matcher {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[{"action_type": "auto_match_submission"}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Ambiguous Person",
                    "date_of_birth": "1990-01-01",
                    "phone": "+1 (555) 444-5555",
                    "email": "unknown@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert payload["outcome"] == "ambiguous_review"

    submission_id = payload["id"]
    queue_res = await authed_client.get(
        f"/forms/{form_id}/submissions",
        params={"match_status": "ambiguous_review", "source_mode": "shared"},
    )
    assert queue_res.status_code == 200
    assert any(row["id"] == submission_id for row in queue_res.json())

    candidates_res = await authed_client.get(f"/forms/submissions/{submission_id}/match-candidates")
    assert candidates_res.status_code == 200
    candidate_ids = {candidate["surrogate_id"] for candidate in candidates_res.json()}
    assert candidate_ids == {str(surrogate_a.id), str(surrogate_b.id)}

    resolve_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={
            "surrogate_id": str(surrogate_a.id),
            "create_intake_lead": False,
            "review_notes": "Confirmed by intake specialist",
        },
    )
    assert resolve_res.status_code == 200
    resolved = resolve_res.json()
    assert resolved["outcome"] == "linked"
    assert resolved["candidate_count"] == 0
    assert resolved["submission"]["surrogate_id"] == str(surrogate_a.id)
    assert resolved["submission"]["review_notes"] == "Confirmed by intake specialist"

    surrogate_submission_res = await authed_client.get(
        f"/forms/{form_id}/surrogates/{surrogate_a.id}/submission"
    )
    assert surrogate_submission_res.status_code == 200


@pytest.mark.asyncio
async def test_shared_submission_retry_allows_unlink_and_relink(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    surrogate_a = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Retry Person",
        email="retry-a@example.com",
        phone="+1 (555) 200-3000",
        date_of_birth="1991-02-03",
    )
    surrogate_b = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Correct Person",
        email="retry-b@example.com",
        phone="+1 (555) 777-3000",
        date_of_birth="1992-03-04",
    )

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Retry matcher {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[{"action_type": "auto_match_submission"}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Retry Person",
                    "date_of_birth": "1991-02-03",
                    "phone": "+1 (555) 200-3000",
                    "email": "retry-a@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert payload["outcome"] == "linked"
    assert payload["surrogate_id"] == str(surrogate_a.id)

    submission_id = payload["id"]
    retry_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/retry",
        json={
            "unlink_surrogate": True,
            "unlink_intake_lead": False,
            "rerun_auto_match": False,
            "create_intake_lead_if_unmatched": False,
            "review_notes": "Reset incorrect auto-link",
        },
    )
    assert retry_res.status_code == 200
    retry_payload = retry_res.json()
    assert retry_payload["outcome"] == "ambiguous_review"
    assert retry_payload["submission"]["surrogate_id"] is None
    assert retry_payload["submission"]["review_notes"] == "Reset incorrect auto-link"

    relink_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={
            "surrogate_id": str(surrogate_b.id),
            "create_intake_lead": False,
            "review_notes": "Corrected to surrogate B",
        },
    )
    assert relink_res.status_code == 200
    relink_payload = relink_res.json()
    assert relink_payload["outcome"] == "linked"
    assert relink_payload["submission"]["surrogate_id"] == str(surrogate_b.id)


@pytest.mark.asyncio
async def test_shared_submission_retry_reuses_existing_lead_without_duplicates(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Retry lead workflow {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[{"action_type": "create_intake_lead"}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Lead Retry Candidate",
                    "date_of_birth": "1995-06-07",
                    "phone": "+1 (555) 812-3411",
                    "email": "lead-retry@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert payload["outcome"] == "lead_created"
    assert payload["intake_lead_id"] is not None

    submission_id = payload["id"]
    original_lead_id = payload["intake_lead_id"]

    retry_reuse_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/retry",
        json={
            "unlink_surrogate": False,
            "unlink_intake_lead": True,
            "rerun_auto_match": True,
            "create_intake_lead_if_unmatched": True,
            "review_notes": "Re-run lead flow",
        },
    )
    assert retry_reuse_res.status_code == 200
    retry_reuse_payload = retry_reuse_res.json()
    assert retry_reuse_payload["outcome"] == "lead_created"
    assert retry_reuse_payload["submission"]["intake_lead_id"] == original_lead_id

    lead_count = (
        db.query(IntakeLead)
        .filter(
            IntakeLead.organization_id == test_org.id,
            IntakeLead.full_name == normalize_name("Lead Retry Candidate"),
        )
        .count()
    )
    assert lead_count == 1

    retry_clear_res = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/retry",
        json={
            "unlink_surrogate": False,
            "unlink_intake_lead": True,
            "rerun_auto_match": True,
            "create_intake_lead_if_unmatched": False,
            "review_notes": "Undo lead link",
        },
    )
    assert retry_clear_res.status_code == 200
    retry_clear_payload = retry_clear_res.json()
    assert retry_clear_payload["outcome"] == "ambiguous_review"
    assert retry_clear_payload["submission"]["intake_lead_id"] is None


@pytest.mark.asyncio
async def test_promote_intake_lead_links_pending_submission(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Create intake lead from form submit {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[{"action_type": "create_intake_lead"}],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add(workflow)
    db.commit()

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Lead Candidate",
                    "date_of_birth": "1994-06-06",
                    "phone": "+1 (555) 999-0000",
                    "email": "lead-candidate@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert payload["outcome"] == "lead_created"

    lead_id = payload["intake_lead_id"]
    promote_res = await authed_client.post(
        f"/forms/intake-leads/{lead_id}/promote",
        json={"source": "manual", "is_priority": True},
    )
    assert promote_res.status_code == 200
    promote_payload = promote_res.json()
    assert promote_payload["intake_lead_id"] == lead_id
    assert promote_payload["linked_submission_count"] == 1
    assert promote_payload["surrogate_id"]

    submission = db.query(FormSubmission).filter(FormSubmission.id == payload["id"]).first()
    assert submission is not None
    assert submission.surrogate_id is not None
    assert submission.match_status == FormSubmissionMatchStatus.LINKED.value


@pytest.mark.asyncio
async def test_shared_submit_no_match_workflow_can_auto_promote_to_surrogate(
    authed_client,
    db,
    test_org,
    test_user,
    default_stage,
):
    form_id, _link_id, slug = await _create_published_form_and_shared_link(authed_client)

    create_lead_workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Create lead from submit {uuid.uuid4().hex[:6]}",
        trigger_type="form_submitted",
        trigger_config={"form_id": form_id},
        conditions=[{"field": "source_mode", "operator": "equals", "value": "shared"}],
        condition_logic="AND",
        actions=[
            {
                "action_type": "create_intake_lead",
            }
        ],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    promote_workflow = AutomationWorkflow(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name=f"Auto promote intake {uuid.uuid4().hex[:6]}",
        trigger_type="intake_lead_created",
        trigger_config={"form_id": form_id},
        conditions=[],
        condition_logic="AND",
        actions=[
            {
                "action_type": "promote_intake_lead",
                "source": "manual",
                "is_priority": True,
            }
        ],
        is_enabled=True,
        scope="org",
        owner_user_id=None,
        created_by_user_id=test_user.id,
    )
    db.add_all([create_lead_workflow, promote_workflow])
    db.commit()

    submit_res = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "full_name": "Workflow Promote Candidate",
                    "date_of_birth": "1992-05-08",
                    "phone": "+1 (555) 121-3434",
                    "email": "workflow-promote@example.com",
                }
            )
        },
    )
    assert submit_res.status_code == 200
    payload = submit_res.json()
    assert payload["outcome"] == "linked"
    assert payload["surrogate_id"] is not None
    assert payload["intake_lead_id"] is not None

    submission = db.query(FormSubmission).filter(FormSubmission.id == payload["id"]).first()
    assert submission is not None
    assert submission.surrogate_id is not None
    assert submission.match_status == FormSubmissionMatchStatus.LINKED.value
    assert submission.match_reason == "lead_promoted_to_surrogate"

    lead = db.query(IntakeLead).filter(IntakeLead.id == submission.intake_lead_id).first()
    assert lead is not None
    assert lead.status == IntakeLeadStatus.PROMOTED.value
    assert lead.promoted_surrogate_id == submission.surrogate_id
