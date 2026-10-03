"""Module routing modes, review transitions, replay, and API isolation."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.csrf import CSRF_HEADER
from app.db.enums import Role
from app.db.models import (
    AuditLog,
    Form,
    FormSubmission,
    IntakeLead,
    Notification,
    Organization,
    Task,
)
from app.schemas.donor import DonorCreate
from app.schemas.forms import FormRoutingUpdate
from app.services import donor_service, form_intake_service, form_routing_service
from tests.test_email_templates_personal_scope import authed_client_for_user, create_user_with_role
from tests.test_forms import _create_surrogate

KINDS = ["surrogate", "egg_donor", "sperm_donor"]
ANSWERS = {
    "full_name": "Routing Applicant",
    "email": "routing@example.com",
    "phone": "+16075550199",
    "date_of_birth": "1990-01-01",
}
SCHEMA = {"pages": [{"fields": [{"key": key, "label": key, "type": "text"} for key in ANSWERS]}]}


def routing_submission(db, org_id, user_id, *, kind="surrogate", exact="review", no_match="review"):
    form = Form(
        organization_id=org_id,
        name="Application",
        lead_kind=kind,
        schema_json=SCHEMA,
        published_schema_json=SCHEMA,
        status="published",
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
        routing_exact_match=exact,
        routing_no_match=no_match,
        routing_lead_source=None,
        routing_auto_create_donor=False,
    )
    db.add(form)
    db.flush()
    submission = FormSubmission(
        organization_id=org_id,
        form_id=form.id,
        lead_kind=kind,
        source_mode="shared",
        match_status="workflow_pending",
        answers_json=dict(ANSWERS),
        schema_snapshot=SCHEMA,
        mapping_snapshot=[{"field_key": key, "surrogate_field": key} for key in ANSWERS],
    )
    db.add(submission)
    db.commit()
    return form, submission


def tasks(db, submission):
    return (
        db.query(Task).filter_by(form_submission_id=submission.id).order_by(Task.created_at).all()
    )


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("exact", ["auto", "review"])
@pytest.mark.parametrize("no_match", ["auto", "review", "off"])
@pytest.mark.parametrize("match", ["none", "exact", "ambiguous"])
def test_routing_mode_matrix(db, test_org, test_user, default_stage, kind, exact, no_match, match):
    form, submission = routing_submission(
        db, test_org.id, test_user.id, kind=kind, exact=exact, no_match=no_match
    )
    records = []
    for index in range({"none": 0, "exact": 1, "ambiguous": 2}[match]):
        email = ANSWERS["email"] if index == 0 else "other@example.com"
        if kind == "surrogate":
            records.append(
                _create_surrogate(
                    db,
                    test_org.id,
                    test_user.id,
                    default_stage,
                    full_name=ANSWERS["full_name"],
                    email=email,
                    phone=ANSWERS["phone"],
                    date_of_birth=ANSWERS["date_of_birth"],
                )
            )
        else:
            records.append(
                donor_service.create_donor(
                    db,
                    test_org.id,
                    test_user.id,
                    DonorCreate(
                        donor_type=kind.removesuffix("_donor"),
                        full_name=ANSWERS["full_name"],
                        email=email,
                        phone=ANSWERS["phone"],
                    ),
                )
            )
    db.commit()
    form_intake_service.process_form_submission_workflow(
        db, org_id=test_org.id, submission_id=submission.id
    )
    db.refresh(submission)
    if exact == "review":
        expected = ("routing_review", "match")
    elif match == "exact":
        expected = ("linked", None)
        assert (submission.surrogate_id or submission.donor_id) == records[0].id
    elif match == "ambiguous" or no_match == "off":
        expected = ("ambiguous_review", None)
    elif no_match == "review":
        expected = ("routing_review", "create_lead")
    else:
        expected = ("lead_created", None)
        lead = db.get(IntakeLead, submission.intake_lead_id)
        assert lead.organization_id == test_org.id
        assert lead.lead_type == kind
    assert (submission.match_status, submission.routing_review_step) == expected
    review_tasks = tasks(db, submission)
    assert len(review_tasks) == int(expected[0] == "routing_review")
    if review_tasks:
        task = review_tasks[0]
        assert task.task_type == "review"
        assert task.status == "pending"
        assert task.owner_type == "user" and task.owner_id == test_user.id
        assert task.title == "Review submission: Application"
        assert task.due_at is not None
        assert task.due_at > datetime.now(task.due_at.tzinfo)
        assert (
            db.query(Notification).filter_by(entity_id=task.id, user_id=test_user.id).count() == 1
        )
    snapshot = (submission.match_reason, submission.intake_lead_id, [t.id for t in review_tasks])
    audit_count = db.query(AuditLog).filter_by(target_id=submission.id).count()
    form_intake_service.process_form_submission_workflow(
        db, org_id=test_org.id, submission_id=submission.id
    )
    db.refresh(submission)
    assert (
        submission.match_reason,
        submission.intake_lead_id,
        [t.id for t in tasks(db, submission)],
    ) == snapshot
    assert db.query(AuditLog).filter_by(target_id=submission.id).count() == audit_count


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_review_lifecycle(authed_client, db, test_org, test_user, kind):
    form, submission = routing_submission(db, test_org.id, test_user.id, kind=kind)
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    first = tasks(db, submission)[0]
    base = f"/forms/submissions/{submission.id}/routing"
    response = await authed_client.post(f"{base}/run-match")
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "routing_review"
    assert response.json()["submission"]["routing_review_step"] == "create_lead"
    assert response.json()["candidate_count"] == 0
    db.refresh(first)
    assert first.status == "completed" and first.is_completed
    assert first.completed_by_user_id == test_user.id
    pending = [t for t in tasks(db, submission) if t.status == "pending"]
    assert len(pending) == 1 and pending[0].id != first.id
    listed = await authed_client.get(
        f"/forms/{form.id}/submissions", params={"match_status": "routing_review"}
    )
    assert listed.status_code == 200, listed.text
    assert [s["id"] for s in listed.json()] == [str(submission.id)]
    assert listed.json()[0]["routing_review_step"] == "create_lead"
    response = await authed_client.post(f"{base}/create-lead")
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "lead_created"
    assert response.json()["submission"]["routing_review_step"] is None
    assert response.json()["submission"]["intake_lead_id"]
    assert all(t.status == "completed" and t.is_completed for t in tasks(db, submission))
    audits = db.query(AuditLog).filter_by(target_id=submission.id).all()
    assert {a.details.get("action") for a in audits} >= {"routing_run_match", "routing_create_lead"}


@pytest.mark.asyncio
@pytest.mark.parametrize("step", ["match", "create_lead"])
async def test_review_dismiss(authed_client, db, test_org, test_user, step):
    _, submission = routing_submission(
        db, test_org.id, test_user.id, exact="review" if step == "match" else "auto"
    )
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    response = await authed_client.post(f"/forms/submissions/{submission.id}/routing/dismiss")
    assert response.status_code == 200, response.text
    result = response.json()["submission"]
    assert result["match_status"] == "ambiguous_review"
    assert result["match_reason"] == "routing_review_dismissed"
    assert result["routing_review_step"] is None
    assert all(t.status == "completed" for t in tasks(db, submission))
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    assert submission.match_reason == "routing_review_dismissed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step", "operation"),
    [("match", "create-lead"), ("create_lead", "run-match"), (None, "dismiss")],
)
async def test_review_wrong_step_is_conflict(
    authed_client, db, test_org, test_user, step, operation
):
    _, submission = routing_submission(
        db,
        test_org.id,
        test_user.id,
        exact="review" if step == "match" else "auto",
        no_match="review" if step else "off",
    )
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    before = submission.match_status
    response = await authed_client.post(f"/forms/submissions/{submission.id}/routing/{operation}")
    assert response.status_code == 409, response.text
    db.refresh(submission)
    assert submission.match_status == before and submission.routing_review_step == step


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["run-match", "create-lead", "dismiss"])
@pytest.mark.parametrize("denial", ["role", "foreign", "csrf"])
async def test_review_access_boundaries(authed_client, db, test_org, test_user, operation, denial):
    org = test_org
    if denial == "foreign":
        org = Organization(name="Other", slug=uuid4().hex)
        db.add(org)
        db.flush()
    _, submission = routing_submission(
        db, org.id, test_user.id, exact="auto" if operation == "create-lead" else "review"
    )
    # Set the valid step directly: access checks must reject before the operation runs.
    submission.match_status = "routing_review"
    submission.routing_review_step = "create_lead" if operation == "create-lead" else "match"
    db.commit()
    path = f"/forms/submissions/{submission.id}/routing/{operation}"
    if denial == "role":
        user = create_user_with_role(db, test_org.id, Role.CASE_MANAGER)
        async with authed_client_for_user(db, test_org.id, user, Role.CASE_MANAGER) as client:
            response = await client.post(path)
    elif denial == "csrf":
        token = authed_client.headers.pop(CSRF_HEADER)
        try:
            response = await authed_client.post(path)
        finally:
            authed_client.headers[CSRF_HEADER] = token
    else:
        response = await authed_client.post(path)
    assert response.status_code == (404 if denial == "foreign" else 403), response.text
    db.refresh(submission)
    assert submission.match_status == "routing_review"
    assert submission.intake_lead_id is None


def test_review_failure_rolls_back_submission_tasks_and_audit(db, test_org, test_user, monkeypatch):
    from app.schemas.auth import UserSession
    from app.services import audit_service

    _, submission = routing_submission(db, test_org.id, test_user.id)
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    task_id = tasks(db, submission)[0].id
    before_audits = db.query(AuditLog).filter_by(target_id=submission.id).count()

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(audit_service, "log_event", fail)
    session = UserSession(
        org_id=test_org.id,
        user_id=test_user.id,
        role=Role.DEVELOPER,
        email=test_user.email,
        display_name=test_user.display_name,
    )
    with Session(bind=db.connection(), join_transaction_mode="create_savepoint") as review_db:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            form_routing_service.run_match(review_db, submission_id=submission.id, session=session)
    db.expire_all()
    assert submission.routing_review_step == "match"
    assert [(t.id, t.status) for t in tasks(db, submission)] == [(task_id, "pending")]
    assert db.query(AuditLog).filter_by(target_id=submission.id).count() == before_audits


def test_routing_precedes_application_workflows_and_keeps_incomplete_failure(
    db, test_org, test_user, monkeypatch
):
    from types import SimpleNamespace

    from app.services import workflow_triggers

    _, submission = routing_submission(db, test_org.id, test_user.id, exact="auto", no_match="auto")
    observed = []

    def trigger(**kwargs):
        db.refresh(submission)
        observed.append((submission.match_status, submission.intake_lead_id))
        return [SimpleNamespace(id=uuid4(), status="failed")]

    monkeypatch.setattr(workflow_triggers, "trigger_form_submitted", trigger)
    with pytest.raises(RuntimeError, match="execution incomplete"):
        form_intake_service.process_form_submission_workflow(
            db, org_id=test_org.id, submission_id=submission.id
        )
    assert observed == [("lead_created", submission.intake_lead_id)]
    assert submission.intake_lead_id is not None
    assert db.query(IntakeLead).filter_by(form_id=submission.form_id).count() == 1


@pytest.mark.parametrize(
    "field,value", [("exact_match", "off"), ("no_match", "disabled"), ("lead_source", "manual")]
)
def test_routing_schema_rejects_unknown_modes(field, value):
    body = {
        "exact_match": "review",
        "no_match": "review",
        "lead_source": None,
        "auto_create_donor": False,
    }
    with pytest.raises(ValidationError):
        FormRoutingUpdate.model_validate({**body, field: value})


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["resolve", "retry"])
async def test_manual_matching_requires_finishing_routing_review(
    authed_client, db, test_org, test_user, operation
):
    _, submission = routing_submission(db, test_org.id, test_user.id)
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    response = await authed_client.post(
        f"/forms/submissions/{submission.id}/match/{operation}",
        json={"create_intake_lead": True} if operation == "resolve" else {},
    )
    assert response.status_code == 409, response.text
    db.refresh(submission)
    assert submission.routing_review_step == "match"
    assert tasks(db, submission)[0].status == "pending"


def test_routing_is_shared_only_and_tenant_scoped(db, test_org, test_user):
    _, submission = routing_submission(db, test_org.id, test_user.id)
    submission.source_mode = "direct"
    db.commit()
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    assert submission.match_status == "workflow_pending"
    assert tasks(db, submission) == []
    with pytest.raises(ValueError, match="Submission not found"):
        form_routing_service.route_submission(db, org_id=uuid4(), submission_id=submission.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_run_match_links_exact_record_and_completes_task(
    authed_client, db, test_org, test_user, default_stage, kind
):
    _, submission = routing_submission(db, test_org.id, test_user.id, kind=kind)
    if kind == "surrogate":
        record = _create_surrogate(
            db,
            test_org.id,
            test_user.id,
            default_stage,
            full_name=ANSWERS["full_name"],
            email=ANSWERS["email"],
            phone=ANSWERS["phone"],
            date_of_birth=ANSWERS["date_of_birth"],
        )
    else:
        record = donor_service.create_donor(
            db,
            test_org.id,
            test_user.id,
            DonorCreate(
                donor_type=kind.removesuffix("_donor"),
                full_name=ANSWERS["full_name"],
                email=ANSWERS["email"],
                phone=ANSWERS["phone"],
            ),
        )
    db.commit()
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    response = await authed_client.post(f"/forms/submissions/{submission.id}/routing/run-match")
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "linked"
    result = response.json()["submission"]
    assert result["routing_review_step"] is None
    assert result["surrogate_id" if kind == "surrogate" else "donor_id"] == str(record.id)
    assert [t.status for t in tasks(db, submission)] == ["completed"]
