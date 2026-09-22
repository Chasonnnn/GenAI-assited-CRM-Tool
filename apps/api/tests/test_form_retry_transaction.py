"""Retry commits matching and lead changes together while preserving donor snapshots."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.encryption import hash_email
from app.db.enums import AuditEventType, Role
from app.db.models import AuditLog, Form, FormSubmission, FormSubmissionMatchCandidate, IntakeLead
from app.services import audit_service, form_intake_service, meta_crm_dataset_service
from tests.test_email_templates_personal_scope import authed_client_for_user, create_user_with_role
from tests.test_forms_public_shared_intake import _create_surrogate


@pytest.fixture
def db(db_engine):
    """Preserve committed setup across an application rollback."""
    with db_engine.connect() as connection, connection.begin():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        connection.rollback()


@pytest.fixture
def retry_context(db, test_org, test_user, default_stage):
    form = Form(organization_id=test_org.id, name="Retry form", schema_json={"pages": []})
    db.add(form)
    record = _create_surrogate(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        stage=default_stage,
        full_name="Original Applicant",
        email=f"original-{uuid4()}@example.com",
        phone="+14155550142",
        date_of_birth="1990-01-01",
    )
    db.flush()
    submission = FormSubmission(
        organization_id=test_org.id,
        form_id=form.id,
        surrogate_id=record.id,
        source_mode="shared",
        match_status="linked",
        match_reason="original_match",
        answers_json={
            "full_name": "New Applicant",
            "date_of_birth": "1991-01-01",
            "phone": "+14155550143",
            "email": f"new-{uuid4()}@example.com",
        },
    )
    db.add(submission)
    db.flush()
    candidate = FormSubmissionMatchCandidate(
        organization_id=test_org.id,
        submission_id=submission.id,
        surrogate_id=record.id,
        reason="original_candidate",
    )
    db.add(candidate)
    db.commit()
    return SimpleNamespace(form=form, record=record, submission=submission, candidate=candidate)


@pytest.fixture
def callbacks(monkeypatch):
    events = []
    monkeypatch.setattr(
        meta_crm_dataset_service,
        "link_website_lead_event_to_intake_lead",
        lambda *args, **kwargs: events.append("tracking"),
    )
    monkeypatch.setattr(
        form_intake_service,
        "_trigger_intake_lead_created_workflow",
        lambda *args, **kwargs: events.append("workflow"),
    )
    return events


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["rematch", "lead", "commit"])
async def test_retry_failure_restores_original_link_candidates_and_audit(
    db, authed_client, retry_context, test_org, test_user, monkeypatch, callbacks, failure
):
    ctx = retry_context
    original_id, candidate_id = ctx.record.id, ctx.candidate.id
    baseline_audits = db.query(AuditLog).filter_by(organization_id=test_org.id).count()
    baseline_leads = db.query(IntakeLead).filter_by(organization_id=test_org.id).count()
    name = "auto_match_submission" if failure == "rematch" else "create_intake_lead_for_submission"
    original = getattr(form_intake_service, name)

    def fail():
        audit_service.log_event(
            db=db,
            org_id=test_org.id,
            event_type=AuditEventType.FORM_SUBMISSION_RECEIVED,
            actor_user_id=test_user.id,
            target_type="form_submission",
            target_id=ctx.submission.id,
        )
        db.flush()
        raise RuntimeError("Synthetic retry failure")

    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        fail()

    if failure == "commit":
        monkeypatch.setattr(db, "commit", fail)
    else:
        monkeypatch.setattr(form_intake_service, name, fail_after_write)
    with pytest.raises(RuntimeError, match="Synthetic retry failure"):
        await authed_client.post(
            f"/forms/submissions/{ctx.submission.id}/match/retry",
            json={
                "unlink_surrogate": True,
                "rerun_auto_match": failure == "rematch",
                "create_intake_lead_if_unmatched": failure != "rematch",
                "review_notes": "Changed notes",
            },
        )
    db.expire_all()
    assert ctx.submission.surrogate_id == original_id
    assert ctx.submission.intake_lead_id is None
    assert ctx.submission.match_status == "linked"
    assert ctx.submission.match_reason == "original_match"
    assert ctx.submission.review_notes is None
    assert db.get(FormSubmissionMatchCandidate, candidate_id) is not None
    assert db.query(IntakeLead).filter_by(organization_id=test_org.id).count() == baseline_leads
    assert db.query(AuditLog).filter_by(organization_id=test_org.id).count() == baseline_audits
    assert callbacks == []


@pytest.mark.asyncio
@pytest.mark.parametrize("donor_type", ["egg", "sperm"])
async def test_donor_retry_matching_failure_rolls_back_link_and_matching_audit(
    db, authed_client, retry_context, test_org, test_user, monkeypatch, donor_type
):
    from app.schemas.donor import DonorCreate
    from app.services import donor_service

    ctx = retry_context
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type=donor_type,
            full_name="New Applicant",
            email=ctx.submission.answers_json["email"],
            phone=ctx.submission.answers_json["phone"],
        ),
    )
    ctx.submission.lead_kind = f"{donor_type}_donor"
    ctx.submission.surrogate_id = None
    ctx.submission.match_status = "ambiguous_review"
    ctx.submission.mapping_snapshot = [
        {"field_key": key, "surrogate_field": key}
        for key in ("full_name", "email", "phone", "date_of_birth")
    ]
    db.commit()
    baseline_audits = db.query(AuditLog).filter_by(organization_id=test_org.id).count()
    candidate_id = ctx.candidate.id
    original = form_intake_service.auto_match_submission

    def fail_after_match(*args, **kwargs):
        submission, outcome = original(*args, **kwargs)
        assert outcome == "linked"
        assert submission.donor_id == donor.id
        db.flush()
        raise RuntimeError("Synthetic donor matching failure")

    monkeypatch.setattr(form_intake_service, "auto_match_submission", fail_after_match)
    with pytest.raises(RuntimeError, match="Synthetic donor matching failure"):
        await authed_client.post(
            f"/forms/submissions/{ctx.submission.id}/match/retry",
            json={"rerun_auto_match": True, "review_notes": "Changed notes"},
        )
    db.expire_all()
    assert ctx.submission.donor_id is None
    assert ctx.submission.match_status == "ambiguous_review"
    assert ctx.submission.match_reason == "original_match"
    assert ctx.submission.review_notes is None
    assert db.get(FormSubmissionMatchCandidate, candidate_id) is not None
    assert db.query(AuditLog).filter_by(organization_id=test_org.id).count() == baseline_audits


@pytest.mark.asyncio
@pytest.mark.parametrize("lead_kind", ["egg_donor", "sperm_donor"])
async def test_donor_retry_preserves_subtype_published_mapping_and_existing_lead(
    db, authed_client, retry_context, callbacks, lead_kind
):
    ctx = retry_context
    ctx.form.lead_kind = "egg_donor"
    ctx.submission.lead_kind = lead_kind
    ctx.submission.surrogate_id = None
    ctx.submission.match_status = "ambiguous_review"
    ctx.submission.answers_json = {
        "published_name": "Donor Applicant",
        "published_email": f"donor-{uuid4()}@example.com",
        "published_dob": "1995-01-01",
        "published_phone": "+14155550144",
    }
    ctx.submission.mapping_snapshot = [
        {"field_key": "published_name", "surrogate_field": "full_name"},
        {"field_key": "published_email", "surrogate_field": "email"},
        {"field_key": "published_dob", "surrogate_field": "date_of_birth"},
        {"field_key": "published_phone", "surrogate_field": "phone"},
    ]
    db.commit()
    response = await authed_client.post(
        f"/forms/submissions/{ctx.submission.id}/match/retry",
        json={"create_intake_lead_if_unmatched": True},
    )
    assert response.status_code == 200, response.text
    lead_id = ctx.submission.intake_lead_id
    lead = db.get(IntakeLead, lead_id)
    assert response.json()["outcome"] == "lead_created"
    assert lead.lead_type == lead_kind
    assert lead.full_name == "Donor Applicant"
    assert lead.email == ctx.submission.answers_json["published_email"]
    assert callbacks == ["tracking", "workflow"]

    response = await authed_client.post(
        f"/forms/submissions/{ctx.submission.id}/match/retry",
        json={"unlink_intake_lead": True, "create_intake_lead_if_unmatched": True},
    )
    assert response.status_code == 200, response.text
    assert ctx.submission.intake_lead_id == lead_id
    assert ctx.submission.match_reason == "existing_lead_relinked"
    assert db.query(IntakeLead).filter_by(form_id=ctx.form.id).count() == 1
    assert callbacks == ["tracking", "workflow"]


def test_retry_runs_intake_callbacks_only_after_commit(
    db, retry_context, test_user, monkeypatch, callbacks
):
    ctx = retry_context
    original_commit = db.commit

    def commit():
        original_commit()
        callbacks.append("commit")

    monkeypatch.setattr(db, "commit", commit)
    submission, outcome = form_intake_service.retry_submission_match(
        db,
        submission=ctx.submission,
        unlink_surrogate=True,
        unlink_intake_lead=False,
        rerun_auto_match=False,
        create_intake_lead_if_unmatched=True,
        reviewer_id=test_user.id,
        review_notes="Reviewed",
    )
    assert outcome == "lead_created"
    assert submission.review_notes == "Reviewed"
    assert callbacks == ["commit", "tracking", "workflow"]


@pytest.mark.asyncio
async def test_retry_outcome_reflects_intake_workflow_promotion(
    db, authed_client, retry_context, test_org, test_user, monkeypatch
):
    from app.db.models import AutomationWorkflow

    ctx = retry_context
    db.add(
        AutomationWorkflow(
            id=uuid4(),
            organization_id=test_org.id,
            name="Promote retried lead",
            trigger_type="intake_lead_created",
            trigger_config={"form_id": str(ctx.form.id)},
            conditions=[],
            condition_logic="AND",
            actions=[{"action_type": "promote_intake_lead", "source": "manual"}],
            is_enabled=True,
            scope="org",
            owner_user_id=None,
            created_by_user_id=test_user.id,
        )
    )
    db.commit()
    monkeypatch.setattr(
        meta_crm_dataset_service,
        "link_website_lead_event_to_intake_lead",
        lambda *args, **kwargs: None,
    )

    response = await authed_client.post(
        f"/forms/submissions/{ctx.submission.id}/match/retry",
        json={
            "unlink_surrogate": True,
            "rerun_auto_match": False,
            "create_intake_lead_if_unmatched": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["submission"]["match_status"] == "linked"
    assert payload["outcome"] == "linked"
    lead = db.get(IntakeLead, ctx.submission.intake_lead_id)
    assert lead.status == "promoted"
    assert str(lead.promoted_surrogate_id) == payload["submission"]["surrogate_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("donor_type", ["egg", "sperm"])
async def test_retry_retains_linked_donor_outcome_without_callbacks(
    db, authed_client, retry_context, test_org, callbacks, donor_type
):
    from app.db.models import Donor
    from app.services import pipeline_service

    ctx = retry_context
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type=f"{donor_type}_donor"
    )
    stage = min(
        (stage for stage in pipeline.stages if stage.is_active), key=lambda stage: stage.order
    )
    email = f"linked-{uuid4()}@example.com"
    donor = Donor(
        organization_id=test_org.id,
        donor_number="D12345",
        donor_type=donor_type,
        full_name="Linked Donor",
        email=email,
        email_hash=hash_email(email),
        stage_id=stage.id,
    )
    db.add(donor)
    db.flush()
    ctx.submission.surrogate_id = None
    ctx.submission.donor_id = donor.id
    ctx.submission.lead_kind = f"{donor_type}_donor"
    db.commit()
    response = await authed_client.post(
        f"/forms/submissions/{ctx.submission.id}/match/retry",
        json={"rerun_auto_match": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "linked"
    assert response.json()["submission"]["donor_id"] == str(donor.id)
    assert callbacks == []


@pytest.mark.asyncio
async def test_retry_other_organization_submission_is_unchanged(db, retry_context):
    from app.db.models import Organization

    ctx = retry_context
    other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
    db.add(other)
    db.flush()
    user = create_user_with_role(db, other.id, Role.DEVELOPER)
    db.commit()
    async with authed_client_for_user(db, other.id, user, Role.DEVELOPER) as client:
        response = await client.post(
            f"/forms/submissions/{ctx.submission.id}/match/retry",
            json={"unlink_surrogate": True},
        )
    assert response.status_code == 404
    assert ctx.submission.surrogate_id == ctx.record.id
    assert ctx.submission.match_reason == "original_match"


@pytest.mark.asyncio
async def test_retry_missing_form_permission_is_denied(db, test_org, retry_context):
    ctx = retry_context
    user = create_user_with_role(db, test_org.id, Role.INTAKE_SPECIALIST)
    db.commit()
    async with authed_client_for_user(db, test_org.id, user, Role.INTAKE_SPECIALIST) as client:
        response = await client.post(
            f"/forms/submissions/{ctx.submission.id}/match/retry",
            json={"unlink_surrogate": True},
        )
    assert response.status_code == 403
    assert ctx.submission.surrogate_id == ctx.record.id
    assert ctx.submission.match_reason == "original_match"
