"""Website donor routing must preserve identity, tenant and upload boundaries."""

import json
import uuid
from pathlib import Path

import pytest

from app.core.config import settings
from app.db.models import Donor, FormSubmission, FormSubmissionFile, IntakeLead, Job
from app.services import form_intake_service
from tests.test_hosted_donor_forms import _create_donor_form, _submit_donor_form


def _workflow_template():
    from app.schemas.platform_templates import PlatformWorkflowTemplateDraft

    path = Path(__file__).resolve().parents[3] / "scripts/fixtures/donor-intake-workflow.json"
    return PlatformWorkflowTemplateDraft.model_validate(json.loads(path.read_text())).model_dump()


@pytest.fixture
def donor_storage(monkeypatch, tmp_path):
    from app.core.rate_limit import limiter

    limiter.reset()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)


async def _submission(client, db, *, kind="egg_donor", email="routing@example.com"):
    _, slug = await _create_donor_form(client, lead_kind=kind)
    response = await _submit_donor_form(client, slug=slug, email=email)
    assert response.status_code == 200, response.text
    return db.query(FormSubmission).filter_by(id=uuid.UUID(response.json()["id"])).one()


def _jobs(db, org_id):
    return db.query(Job).filter_by(organization_id=org_id, job_type="donor_intake_promote").all()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["egg_donor", "sperm_donor"])
async def test_donor_routing_creates_then_matches_without_duplicates(
    authed_client, db, test_org, donor_storage, kind
):
    from app.jobs.handlers.form_submissions import process_donor_intake_promote

    submission = await _submission(authed_client, db, kind=kind)
    form_intake_service.auto_match_submission(db, submission=submission)
    assert submission.match_reason == "donor_no_deterministic_match"
    _, lead = form_intake_service.create_intake_lead_for_submission(
        db, submission=submission, user_id=None, source="website", auto_promote=True
    )
    jobs = _jobs(db, test_org.id)
    assert len(jobs) == 1
    await process_donor_intake_promote(db, jobs[0])
    await process_donor_intake_promote(db, jobs[0])
    db.refresh(submission)
    db.refresh(lead)
    assert submission.donor_id == lead.promoted_donor_id
    donor = db.get(Donor, submission.donor_id)
    assert donor.donor_type == kind.removesuffix("_donor")
    assert donor.profile_photo_attachment_id is not None
    assert donor.source == "website"

    repeat = await _submission(authed_client, db, kind=kind)
    form_intake_service.auto_match_submission(db, submission=repeat)
    assert repeat.donor_id == donor.id
    assert repeat.match_status == "linked"
    _, skipped = form_intake_service.create_intake_lead_for_submission(
        db, submission=repeat, user_id=None, auto_promote=True
    )
    assert skipped is None
    assert db.query(Donor).filter_by(organization_id=test_org.id).count() == 1
    assert db.query(IntakeLead).filter_by(organization_id=test_org.id).count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["egg_donor", "sperm_donor"])
@pytest.mark.parametrize("queued", [False, True])
async def test_same_form_repeat_is_held_for_review_without_linking_or_promoting(
    authed_client, db, test_org, test_user, donor_storage, monkeypatch, kind, queued
):
    from app.jobs.handlers.form_submissions import process_donor_intake_promote
    from app.schemas.donor import DonorCreate
    from app.services import donor_service

    monkeypatch.setattr(settings, "FORMS_SHARED_DUPLICATE_WINDOW_SECONDS", 0)
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type=kind.removesuffix("_donor"),
            full_name="Taylor Donor",
            email="repeat@example.com",
            phone="+16075550199",
        ),
    )
    form_id, slug = await _create_donor_form(authed_client, shared_donor=True)
    donor_type = "Egg donor" if kind == "egg_donor" else "Sperm donor"
    first_response = await _submit_donor_form(
        authed_client, slug=slug, email="repeat@example.com", donor_type=donor_type
    )
    assert first_response.status_code == 200, first_response.text
    first = db.get(FormSubmission, uuid.UUID(first_response.json()["id"]))
    form_intake_service.auto_match_submission(db, submission=first)
    assert first.donor_id == donor.id
    first.status = "approved"
    db.commit()

    repeat_response = await _submit_donor_form(
        authed_client, slug=slug, email="repeat@example.com", donor_type=donor_type
    )
    assert repeat_response.status_code == 200, repeat_response.text
    repeat = db.get(FormSubmission, uuid.UUID(repeat_response.json()["id"]))
    answers = dict(repeat.answers_json)
    if queued:
        # A pending lead can be queued before deterministic matching runs.
        _, lead = form_intake_service.create_intake_lead_for_submission(
            db, submission=repeat, user_id=None
        )
        form_intake_service.create_intake_lead_for_submission(
            db, submission=repeat, user_id=None, auto_promote=True
        )
        job = _jobs(db, test_org.id)[0]
        await process_donor_intake_promote(db, job)
        await process_donor_intake_promote(db, job)
        db.refresh(lead)
        assert lead.status == "pending_review"
        assert lead.promoted_donor_id is None
    else:
        for _ in range(2):
            _, outcome = form_intake_service.auto_match_submission(db, submission=repeat)
            assert outcome == "ambiguous_review"
        for auto_promote in (False, True):
            _, lead = form_intake_service.create_intake_lead_for_submission(
                db, submission=repeat, user_id=None, auto_promote=auto_promote
            )
            assert lead is None
        assert not _jobs(db, test_org.id)
    db.refresh(repeat)
    assert repeat.donor_id is None
    assert repeat.match_status == "ambiguous_review"
    assert repeat.match_reason == "existing_submission_for_donor"
    assert repeat.matched_at is None
    assert repeat.answers_json == answers
    assert db.query(Donor).filter_by(organization_id=test_org.id).count() == 1
    assert db.query(FormSubmission).filter_by(
        form_id=uuid.UUID(form_id), donor_id=donor.id
    ).count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "infected", "error"])
async def test_donor_creation_waits_for_clean_scan_and_queues_once(
    authed_client, db, test_org, donor_storage, status
):
    from app.services.form_submission_service import mark_submission_file_scanned

    submission = await _submission(authed_client, db)
    photo = db.query(FormSubmissionFile).filter_by(submission_id=submission.id).one()
    photo.scan_status = status
    photo.quarantined = status in {"infected", "error"}
    db.commit()
    for _ in range(2):
        form_intake_service.create_intake_lead_for_submission(
            db, submission=submission, user_id=None, auto_promote=True
        )
    assert not _jobs(db, test_org.id)
    assert db.query(Donor).filter_by(organization_id=test_org.id).count() == 0
    mark_submission_file_scanned(db, photo.id, "clean")
    db.commit()
    mark_submission_file_scanned(db, photo.id, "clean")
    db.commit()
    assert len(_jobs(db, test_org.id)) == 1


@pytest.mark.asyncio
async def test_donor_creation_is_opt_in(authed_client, db, test_org, donor_storage):
    submission = await _submission(authed_client, db)
    form_intake_service.create_intake_lead_for_submission(db, submission=submission, user_id=None)
    assert not _jobs(db, test_org.id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"donor_type": "sperm"},
        {"full_name": "Different Applicant"},
        {"phone": "+16075550198"},
        {"email": "different@example.com"},
    ],
)
async def test_conflicting_identity_is_held_for_review(
    authed_client, db, test_org, test_user, donor_storage, change
):
    from app.schemas.donor import DonorCreate
    from app.services import donor_service

    donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            **{
                "donor_type": "egg",
                "full_name": "Taylor Donor",
                "email": "routing@example.com",
                "phone": "+16075550199",
                **change,
            }
        ),
    )
    submission = await _submission(authed_client, db)
    form_intake_service.auto_match_submission(db, submission=submission)
    assert submission.match_reason == "donor_identity_conflict"
    _, lead = form_intake_service.create_intake_lead_for_submission(
        db, submission=submission, user_id=None, auto_promote=True
    )
    assert lead is None
    assert submission.donor_id is None
    assert not _jobs(db, test_org.id)


@pytest.mark.asyncio
async def test_matching_does_not_cross_organizations(
    authed_client, db, test_org, test_user, donor_storage
):
    from app.db.models import Organization
    from app.schemas.donor import DonorCreate
    from app.services import donor_service

    other_org = Organization(name="Other agency", slug=f"other-{uuid.uuid4().hex}")
    db.add(other_org)
    db.flush()
    donor_service.create_donor(
        db,
        other_org.id,
        None,
        DonorCreate(
            donor_type="egg",
            full_name="Taylor Donor",
            email="routing@example.com",
            phone="+16075550199",
        ),
    )
    submission = await _submission(authed_client, db)
    form_intake_service.auto_match_submission(db, submission=submission)
    assert submission.donor_id is None
    assert submission.match_reason == "donor_no_deterministic_match"


@pytest.mark.asyncio
async def test_late_donor_match_reuses_record_instead_of_failing_job(
    authed_client, db, test_org, test_user, donor_storage
):
    from app.jobs.handlers.form_submissions import process_donor_intake_promote
    from app.schemas.donor import DonorCreate
    from app.services import donor_service

    submission = await _submission(authed_client, db)
    _, lead = form_intake_service.create_intake_lead_for_submission(
        db, submission=submission, user_id=None, auto_promote=True
    )
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Taylor Donor",
            email="routing@example.com",
            phone="+16075550199",
        ),
    )
    await process_donor_intake_promote(db, _jobs(db, test_org.id)[0])
    assert lead.promoted_donor_id == donor.id
    assert submission.donor_id == donor.id
    assert db.query(Donor).filter_by(organization_id=test_org.id).count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["egg_donor", "sperm_donor"])
async def test_published_form_workflow_routes_both_donor_types(
    authed_client, db, test_org, test_user, donor_storage, kind
):
    import copy
    import json

    from app.db.models import Form, FormFieldMapping
    from app.jobs.handlers.form_submissions import process_donor_intake_promote
    from app.schemas.workflow import WorkflowCreate
    from app.services import workflow_service
    from tests.test_hosted_donor_forms import _png_bytes

    form_id, slug = await _create_donor_form(authed_client, lead_kind="egg_donor")
    schema = copy.deepcopy(db.get(Form, uuid.UUID(form_id)).schema_json)
    schema["pages"][0]["fields"].insert(
        0,
        {
            "key": "donation_program",
            "label": "Which donor program are you applying for?",
            "type": "radio",
            "required": True,
            "options": [{"label": value, "value": value} for value in ["Egg donor", "Sperm donor"]],
        },
    )
    update = await authed_client.patch(f"/forms/{form_id}", json={"form_schema": schema})
    assert update.status_code == 200, update.text
    mappings = [
        {"field_key": item.field_key, "surrogate_field": item.surrogate_field}
        for item in db.query(FormFieldMapping).filter_by(form_id=uuid.UUID(form_id)).all()
    ]
    mappings.append({"field_key": "donation_program", "surrogate_field": "donor_type"})
    update = await authed_client.put(f"/forms/{form_id}/mappings", json={"mappings": mappings})
    assert update.status_code == 200, update.text
    assert (await authed_client.post(f"/forms/{form_id}/publish")).status_code == 200
    workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            **{**_workflow_template(), "trigger_config": {"form_id": form_id}},
            subject_type="form_submission",
            is_enabled=True,
        ),
    )
    version = (await authed_client.get(f"/forms/public/intake/{slug}")).json()[
        "published_version_id"
    ]
    response = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={
            "answers": json.dumps(
                {
                    "donation_program": "Egg donor" if kind == "egg_donor" else "Sperm donor",
                    "applicant_name": "Taylor Donor",
                    "email_address": "workflow@example.com",
                    "mobile": "+16075550199",
                    "home_state": "NY",
                    "education_background": "College",
                }
            ),
            "file_field_keys": json.dumps(["headshot"]),
            "published_version_id": version,
        },
        files=[("files", ("recent.png", _png_bytes(), "image/png"))],
    )
    assert response.status_code == 200, response.text
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    assert submission.intake_lead_id is not None
    jobs = _jobs(db, test_org.id)
    assert len(jobs) == 1
    await process_donor_intake_promote(db, jobs[0])
    db.refresh(submission)
    assert submission.donor_id is not None
    assert db.get(Donor, submission.donor_id).donor_type == kind.removesuffix("_donor")


@pytest.mark.asyncio
async def test_promotion_failure_rolls_back_and_retry_creates_one_donor(
    authed_client, db, test_org, donor_storage, monkeypatch
):
    from sqlalchemy.orm import Session

    from app.jobs.handlers.form_submissions import process_donor_intake_promote

    submission = await _submission(authed_client, db)
    form_intake_service.create_intake_lead_for_submission(
        db, submission=submission, user_id=None, auto_promote=True
    )
    job = _jobs(db, test_org.id)[0]
    original_copy = form_intake_service._copy_profile_photo_to_donor_attachment

    def unavailable_storage(*args, **kwargs):
        raise RuntimeError("provider returned applicant@example.com")

    monkeypatch.setattr(
        form_intake_service, "_copy_profile_photo_to_donor_attachment", unavailable_storage
    )
    with Session(bind=db.connection(), join_transaction_mode="create_savepoint") as worker_db:
        worker_job = worker_db.get(Job, job.id)
        with pytest.raises(RuntimeError, match="^Donor intake promotion failed$"):
            await process_donor_intake_promote(worker_db, worker_job)
        assert worker_db.query(Donor).filter_by(organization_id=test_org.id).count() == 0
        monkeypatch.setattr(
            form_intake_service, "_copy_profile_photo_to_donor_attachment", original_copy
        )
        await process_donor_intake_promote(worker_db, worker_job)
    assert db.query(Donor).filter_by(organization_id=test_org.id).count() == 1


def test_donor_template_condition_excludes_surrogates():
    from types import SimpleNamespace

    from app.services.workflow_engine import engine

    conditions = [{"field": "lead_kind", "operator": "in", "value": ["egg_donor", "sperm_donor"]}]
    assert not engine._evaluate_conditions(
        conditions, "AND", SimpleNamespace(lead_kind="surrogate")
    )
    for kind in ["egg_donor", "sperm_donor"]:
        assert engine._evaluate_conditions(conditions, "AND", SimpleNamespace(lead_kind=kind))


@pytest.mark.asyncio
async def test_donor_job_rejects_other_organization(authed_client, db, test_org, donor_storage):
    from types import SimpleNamespace

    from app.jobs.handlers.form_submissions import process_donor_intake_promote

    submission = await _submission(authed_client, db)
    _, lead = form_intake_service.create_intake_lead_for_submission(
        db, submission=submission, user_id=None, auto_promote=True
    )
    with pytest.raises(RuntimeError, match="Donor intake promotion failed"):
        await process_donor_intake_promote(
            db,
            SimpleNamespace(organization_id=uuid.uuid4(), payload={"intake_lead_id": str(lead.id)}),
        )
    assert db.query(Donor).filter_by(organization_id=test_org.id).count() == 0
