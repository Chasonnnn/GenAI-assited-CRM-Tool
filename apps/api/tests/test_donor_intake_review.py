"""Donor intake review: canonical source, lifecycle, linking, applications, and recovery."""

import uuid
from contextlib import asynccontextmanager

import pytest

from app.core.config import settings
from app.db.models import Donor, Form, FormSubmission, IntakeLead
from app.services import alert_service, workflow_triggers
from tests.test_hosted_donor_forms import _create_donor_form, _submit_donor_form


@pytest.fixture(autouse=True)
def _local_unscanned_storage(monkeypatch, tmp_path):
    from app.core.rate_limit import limiter

    limiter.reset()
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)


def _use_manual_routing(db, form_id: str) -> None:
    form = db.get(Form, uuid.UUID(form_id))
    form.routing_exact_match = "review"
    form.routing_no_match = "off"
    db.commit()


async def _manual_submission(client, db, *, kind="egg_donor", email="review@example.com"):
    form_id, slug = await _create_donor_form(client, lead_kind=kind)
    _use_manual_routing(db, form_id)
    response = await _submit_donor_form(client, slug=slug, email=email)
    assert response.status_code == 200, response.text
    submission_id = response.json()["id"]
    dismissed = await client.post(f"/forms/submissions/{submission_id}/routing/dismiss")
    assert dismissed.status_code == 200, dismissed.text
    return form_id, slug, db.get(FormSubmission, uuid.UUID(submission_id))


async def _create_lead_and_promote(client, submission_id, *, source="hosted_form"):
    resolved = await client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={"create_intake_lead": True},
    )
    assert resolved.status_code == 200, resolved.text
    lead_id = resolved.json()["submission"]["intake_lead_id"]
    promoted = await client.post(f"/forms/intake-leads/{lead_id}/promote", json={"source": source})
    return lead_id, promoted


@pytest.mark.asyncio
async def test_manual_donor_intake_uses_canonical_website_source(authed_client, db):
    _, _, submission = await _manual_submission(authed_client, db)

    lead_id, promoted = await _create_lead_and_promote(authed_client, submission.id)
    assert promoted.status_code == 200, promoted.text

    lead = db.get(IntakeLead, uuid.UUID(lead_id))
    assert lead.source == "website"
    assert lead.source_metadata["source"] == "manual_review_resolution"
    donor = db.get(Donor, uuid.UUID(promoted.json()["donor_id"]))
    assert donor.source == "website"


@pytest.mark.asyncio
async def test_retry_created_donor_lead_uses_canonical_website_source(authed_client, db):
    _, _, submission = await _manual_submission(authed_client, db)
    submission.match_status = "ambiguous_review"
    submission.match_reason = "donor_no_deterministic_match"
    db.commit()

    retried = await authed_client.post(
        f"/forms/submissions/{submission.id}/match/retry",
        json={
            "unlink_surrogate": False,
            "rerun_auto_match": True,
            "create_intake_lead_if_unmatched": True,
        },
    )
    assert retried.status_code == 200, retried.text
    lead = db.get(IntakeLead, uuid.UUID(retried.json()["submission"]["intake_lead_id"]))
    assert lead.source == "website"
    assert lead.source_metadata["source"] == "manual_retry_resolution"


@pytest.mark.asyncio
async def test_hosted_promotion_alerts_when_donor_side_effects_fail(
    authed_client, db, test_org, monkeypatch, caplog
):
    _, _, submission = await _manual_submission(authed_client, db, email="alerts@example.com")
    alerts: list[dict] = []

    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic failure for alerts@example.com")

    monkeypatch.setattr(workflow_triggers, "trigger_donor_created", fail)
    monkeypatch.setattr(workflow_triggers, "trigger_document_uploaded", fail)
    monkeypatch.setattr(
        alert_service, "record_alert_isolated", lambda **kwargs: alerts.append(kwargs)
    )

    _, promoted = await _create_lead_and_promote(authed_client, submission.id)

    assert promoted.status_code == 200, promoted.text
    assert db.get(Donor, uuid.UUID(promoted.json()["donor_id"])) is not None
    assert sorted(alert["integration_key"] for alert in alerts) == [
        "donor_created",
        "donor_document_uploaded",
    ]
    assert all(alert["org_id"] == test_org.id for alert in alerts)
    assert "alerts@example.com" not in caplog.text
    assert all("alerts@example.com" not in (alert.get("message") or "") for alert in alerts)


# ---------------------------------------------------------------------------
# Review lifecycle, donor linking, applications, scan recovery
# ---------------------------------------------------------------------------


def _donor(db, org_id, *, email, name="Taylor Donor", donor_type="egg", **fields) -> Donor:
    from app.schemas.donor import DonorCreate
    from app.services import donor_service

    return donor_service.create_donor(
        db,
        org_id,
        None,
        DonorCreate(donor_type=donor_type, full_name=name, email=email, source="manual", **fields),
        emit_workflow_events=False,
    )


def _foreign_org(db):
    from app.db.models import Organization

    org = Organization(name="Foreign agency", slug=f"foreign-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.flush()
    return org


def _foreign_donor_submission(db) -> FormSubmission:
    from app.db.models import Form

    org = _foreign_org(db)
    form = Form(
        organization_id=org.id,
        name="Foreign donor form",
        status="published",
        purpose="other",
        lead_kind="egg_donor",
        schema_json={"pages": []},
    )
    db.add(form)
    db.flush()
    submission = FormSubmission(
        organization_id=org.id,
        form_id=form.id,
        lead_kind="egg_donor",
        source_mode="shared",
        match_status="ambiguous_review",
        status="pending_review",
        answers_json={},
    )
    db.add(submission)
    db.commit()
    return submission


def _photo(db, submission):
    from app.db.models import FormSubmissionFile

    return (
        db.query(FormSubmissionFile)
        .filter(
            FormSubmissionFile.submission_id == submission.id,
            FormSubmissionFile.field_key == "headshot",
        )
        .one()
    )


def _promote_job(db, org_id):
    from app.db.models import Job

    return db.query(Job).filter_by(organization_id=org_id, job_type="donor_intake_promote").one()


async def _submit_and_auto_promote(client, db, org_id, *, email):
    from app.jobs.handlers.form_submissions import process_donor_intake_promote

    form_id, slug = await _create_donor_form(client)
    response = await _submit_donor_form(client, slug=slug, email=email)
    assert response.status_code == 200, response.text
    await process_donor_intake_promote(db, _promote_job(db, org_id))
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    db.refresh(submission)
    return form_id, slug, submission


@asynccontextmanager
async def _restricted_client(db, org_id, *revoked: str):
    from tests.test_hosted_donor_form_lifecycle_permissions import (
        _admin_with_revokes,
        _client_for,
    )

    user = _admin_with_revokes(db, org_id, *revoked)
    db.commit()
    async with _client_for(db, org_id, user) as client:
        yield client


@pytest.mark.asyncio
async def test_promoted_donor_submission_is_approved_and_resubmission_is_held_not_409(
    authed_client, db, test_org
):
    _, slug, submission = await _submit_and_auto_promote(
        authed_client, db, test_org.id, email="resubmit@example.com"
    )
    assert submission.donor_id is not None
    assert submission.status == "approved"
    assert submission.reviewed_at is not None
    assert submission.applied_at is not None

    again = await _submit_donor_form(authed_client, slug=slug, email="resubmit@example.com")

    assert again.status_code == 200, again.text
    follow_up = db.get(FormSubmission, uuid.UUID(again.json()["id"]))
    assert follow_up.status == "pending_review"
    assert follow_up.match_status == "ambiguous_review"
    assert follow_up.match_reason == "existing_submission_for_donor"
    assert follow_up.donor_id is None


@pytest.mark.asyncio
async def test_rejected_donor_applicant_can_resubmit_and_is_not_promoted(
    authed_client, db, test_org
):
    from app.services import donor_intake_service

    _, slug, submission = await _manual_submission(authed_client, db, email="rejected@example.com")
    resolved = await authed_client.post(
        f"/forms/submissions/{submission.id}/match/resolve", json={"create_intake_lead": True}
    )
    assert resolved.status_code == 200, resolved.text

    rejected = await authed_client.post(
        f"/forms/submissions/{submission.id}/reject", json={"review_notes": "Blurry photo"}
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    db.refresh(submission)
    lead = db.get(IntakeLead, submission.intake_lead_id)
    lead.source_metadata = {**(lead.source_metadata or {}), "auto_create_donor": True}
    db.commit()
    donor_intake_service.promote_queued_lead(db, org_id=test_org.id, lead_id=lead.id)
    db.refresh(submission)
    assert submission.donor_id is None

    again = await _submit_donor_form(authed_client, slug=slug, email="rejected@example.com")
    assert again.status_code == 200, again.text


@pytest.mark.asyncio
async def test_rejecting_donor_application_closes_its_intake_lead(authed_client, db, test_org):
    _, _, submission = await _manual_submission(authed_client, db, email="closed@example.com")
    resolved = await authed_client.post(
        f"/forms/submissions/{submission.id}/match/resolve", json={"create_intake_lead": True}
    )
    assert resolved.status_code == 200, resolved.text
    lead_id = uuid.UUID(resolved.json()["submission"]["intake_lead_id"])

    rejected = await authed_client.post(f"/forms/submissions/{submission.id}/reject", json={})
    assert rejected.status_code == 200, rejected.text

    lead = db.get(IntakeLead, lead_id)
    db.refresh(lead)
    assert lead.status == "rejected"
    promoted = await authed_client.post(f"/forms/intake-leads/{lead_id}/promote", json={})
    assert promoted.status_code == 400, promoted.text
    db.refresh(submission)
    assert submission.donor_id is None
    assert submission.status == "rejected"
    assert db.query(Donor).filter(Donor.organization_id == test_org.id).count() == 0


@pytest.mark.asyncio
async def test_rejected_donor_application_cannot_be_moved_to_intake(authed_client, db):
    _, _, submission = await _manual_submission(authed_client, db, email="noreopen@example.com")
    rejected = await authed_client.post(f"/forms/submissions/{submission.id}/reject", json={})
    assert rejected.status_code == 200, rejected.text

    resolved = await authed_client.post(
        f"/forms/submissions/{submission.id}/match/resolve", json={"create_intake_lead": True}
    )

    assert resolved.status_code == 400, resolved.text
    db.refresh(submission)
    assert submission.intake_lead_id is None
    assert db.query(IntakeLead).filter(IntakeLead.form_submission_id == submission.id).count() == 0


@pytest.mark.asyncio
async def test_bad_photo_donor_applicant_can_resubmit(authed_client, db):
    from app.services import form_submission_service

    _, slug, submission = await _manual_submission(authed_client, db, email="badphoto@example.com")
    form_submission_service.mark_submission_file_scanned(db, _photo(db, submission).id, "infected")
    db.commit()
    db.refresh(submission)
    assert submission.match_reason == "donor_photo_requires_review"

    again = await _submit_donor_form(authed_client, slug=slug, email="badphoto@example.com")
    assert again.status_code == 200, again.text


@pytest.mark.asyncio
async def test_open_donor_application_still_blocks_duplicate_submission(authed_client, db):
    _, slug, _ = await _manual_submission(authed_client, db, email="open@example.com")

    again = await _submit_donor_form(authed_client, slug=slug, email="open@example.com")

    assert again.status_code == 409


@pytest.mark.asyncio
async def test_approving_linked_donor_submission_applies_answers_and_photo(
    authed_client, db, test_org
):
    from app.db.models import AuditLog

    donor = _donor(db, test_org.id, email="approve@example.com")
    _, _, submission = await _manual_submission(authed_client, db, email="approve@example.com")
    submission.donor_id = donor.id
    submission.match_status = "linked"
    db.commit()

    approved = await authed_client.post(
        f"/forms/submissions/{submission.id}/approve", json={"review_notes": "ok"}
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    db.refresh(donor)
    assert donor.phone is not None
    assert donor.state == "NY"
    assert donor.education == "Master's degree"
    assert donor.profile_photo_attachment_id is not None
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == "form_submission_approved",
            AuditLog.target_id == submission.id,
        )
        .one()
    )
    assert audit.details["donor_id"] == str(donor.id)


@pytest.mark.asyncio
async def test_approve_unlinked_donor_submission_requires_link(authed_client, db):
    _, _, submission = await _manual_submission(authed_client, db, email="unlinked@example.com")

    approved = await authed_client.post(f"/forms/submissions/{submission.id}/approve", json={})

    assert approved.status_code == 409


@pytest.mark.asyncio
async def test_donor_approve_and_reject_require_edit_donors(authed_client, db, test_org):
    _, _, submission = await _manual_submission(authed_client, db, email="denied@example.com")

    async with _restricted_client(db, test_org.id, "edit_donors") as client:
        for action in ("approve", "reject"):
            response = await client.post(f"/forms/submissions/{submission.id}/{action}", json={})
            assert response.status_code == 403, response.text

    db.refresh(submission)
    assert submission.status == "pending_review"


@pytest.mark.asyncio
async def test_donor_approve_and_reject_cannot_reach_another_org(authed_client, db):
    foreign = _foreign_donor_submission(db)

    for action in ("approve", "reject"):
        response = await authed_client.post(f"/forms/submissions/{foreign.id}/{action}", json={})
        assert response.status_code == 404

    db.refresh(foreign)
    assert foreign.status == "pending_review"


@pytest.mark.asyncio
async def test_auto_linked_follow_up_waits_for_staff_approval_before_changing_the_donor(
    authed_client, client, db, test_org
):
    donor = _donor(db, test_org.id, email="followup@example.com", state="CA")
    _, slug = await _create_donor_form(authed_client)

    response = await _submit_donor_form(client, slug=slug, email="followup@example.com")

    assert response.status_code == 200, response.text
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    db.refresh(submission)
    assert submission.donor_id == donor.id
    assert submission.match_status == "linked"
    assert submission.status == "pending_review"
    assert submission.reviewed_by_user_id is None
    db.refresh(donor)
    assert donor.phone is None
    assert donor.education is None
    assert donor.profile_photo_attachment_id is None

    approved = await authed_client.post(f"/forms/submissions/{submission.id}/approve", json={})

    assert approved.status_code == 200, approved.text
    db.refresh(donor)
    assert donor.state == "CA"
    assert donor.education == "Master's degree"
    assert donor.phone is not None
    assert donor.profile_photo_attachment_id is not None


@pytest.mark.asyncio
async def test_clean_scan_does_not_apply_photo_from_an_unreviewed_auto_link(
    authed_client, client, db, test_org, monkeypatch
):
    from app.services import form_submission_service

    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    donor = _donor(db, test_org.id, email="unreviewed@example.com")
    _, slug = await _create_donor_form(authed_client)
    response = await _submit_donor_form(client, slug=slug, email="unreviewed@example.com")
    assert response.status_code == 200, response.text
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    db.refresh(submission)
    assert submission.donor_id == donor.id

    form_submission_service.mark_submission_file_scanned(db, _photo(db, submission).id, "clean")
    db.commit()

    db.refresh(donor)
    db.refresh(submission)
    assert donor.profile_photo_attachment_id is None
    assert submission.status == "pending_review"


@pytest.mark.asyncio
async def test_staff_approved_follow_up_applies_photo_once_scan_is_clean(
    authed_client, db, test_org, monkeypatch
):
    from app.services import form_submission_service

    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    donor = _donor(db, test_org.id, email="scanlater@example.com")
    _, slug = await _create_donor_form(authed_client)
    response = await _submit_donor_form(authed_client, slug=slug, email="scanlater@example.com")
    assert response.status_code == 200, response.text
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    db.refresh(submission)
    assert submission.donor_id == donor.id
    approved = await authed_client.post(f"/forms/submissions/{submission.id}/approve", json={})
    assert approved.status_code == 200, approved.text
    db.refresh(donor)
    assert donor.profile_photo_attachment_id is None

    photo = _photo(db, submission)
    form_submission_service.mark_submission_file_scanned(db, photo.id, "clean")
    db.commit()
    db.refresh(donor)
    first_photo = donor.profile_photo_attachment_id
    assert first_photo is not None

    form_submission_service.mark_submission_file_scanned(db, photo.id, "clean")
    db.commit()
    db.refresh(donor)
    assert donor.profile_photo_attachment_id == first_photo


@pytest.mark.asyncio
async def test_donor_applications_list_is_scoped_and_permissioned(authed_client, db, test_org):
    _, _, submission = await _submit_and_auto_promote(
        authed_client, db, test_org.id, email="apps@example.com"
    )

    listed = await authed_client.get(f"/forms/donors/{submission.donor_id}/submissions")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert [row["id"] for row in body] == [str(submission.id)]
    assert body[0]["status"] == "approved"
    assert body[0]["form_name"] == "egg_donor application"
    assert set(body[0]) == {"id", "form_id", "form_name", "status", "submitted_at", "reviewed_at"}

    foreign_org = _foreign_org(db)
    foreign = _donor(db, foreign_org.id, email="apps-foreign@example.com")
    db.commit()
    cross_org = await authed_client.get(f"/forms/donors/{foreign.id}/submissions")
    assert cross_org.status_code == 404

    async with _restricted_client(db, test_org.id, "view_donors") as client:
        denied = await client.get(f"/forms/donors/{submission.donor_id}/submissions")
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_link_held_submission_to_existing_donor_after_promotion_conflict(
    authed_client, db, test_org
):
    _, _, submission = await _manual_submission(authed_client, db, email="conflict@example.com")
    donor = _donor(db, test_org.id, email="conflict@example.com", name="Taylor Married-Name")
    lead_id, promoted = await _create_lead_and_promote(authed_client, submission.id)
    assert promoted.status_code == 409

    candidates = await authed_client.get(f"/forms/submissions/{submission.id}/donor-candidates")
    assert candidates.status_code == 200, candidates.text
    assert candidates.json() == [
        {
            "donor_id": str(donor.id),
            "donor_number": donor.donor_number,
            "full_name": "Taylor Married-Name",
            "donor_type": "egg",
            "reason": "donor_email_match",
        }
    ]

    linked = await authed_client.post(
        f"/forms/submissions/{submission.id}/match/resolve", json={"donor_id": str(donor.id)}
    )

    assert linked.status_code == 200, linked.text
    body = linked.json()["submission"]
    assert body["donor_id"] == str(donor.id)
    assert body["match_status"] == "linked"
    assert body["match_reason"] == "manually_linked"
    assert body["status"] == "approved"
    lead = db.get(IntakeLead, uuid.UUID(lead_id))
    db.refresh(lead)
    assert lead.status == "promoted"
    assert lead.promoted_donor_id == donor.id
    db.refresh(donor)
    assert donor.full_name == "Taylor Married-Name"
    assert donor.profile_photo_attachment_id is not None


@pytest.mark.asyncio
async def test_donor_link_rejects_other_org_other_subtype_and_duplicate_form_link(
    authed_client, db, test_org
):
    _, _, submission = await _manual_submission(authed_client, db, email="linkcheck@example.com")
    foreign_org = _foreign_org(db)
    foreign = _donor(db, foreign_org.id, email="linkcheck@example.com")
    sperm = _donor(db, test_org.id, email="linkcheck-sperm@example.com", donor_type="sperm")
    taken = _donor(db, test_org.id, email="linkcheck-taken@example.com")
    db.add(
        FormSubmission(
            organization_id=test_org.id,
            form_id=submission.form_id,
            donor_id=taken.id,
            lead_kind="egg_donor",
            source_mode="shared",
            match_status="linked",
            status="approved",
            answers_json={},
        )
    )
    db.commit()

    candidates = await authed_client.get(f"/forms/submissions/{submission.id}/donor-candidates")
    assert candidates.status_code == 200
    assert str(foreign.id) not in {row["donor_id"] for row in candidates.json()}

    for donor_id, expected in [(foreign.id, 404), (sperm.id, 400), (taken.id, 409)]:
        response = await authed_client.post(
            f"/forms/submissions/{submission.id}/match/resolve", json={"donor_id": str(donor_id)}
        )
        assert response.status_code == expected, response.text

    db.refresh(submission)
    assert submission.donor_id is None
    assert submission.status == "pending_review"


@pytest.mark.asyncio
async def test_donor_link_and_candidates_require_donor_permissions(authed_client, db, test_org):
    _, _, submission = await _manual_submission(authed_client, db, email="linkdeny@example.com")
    donor = _donor(db, test_org.id, email="linkdeny@example.com", name="Other Name")

    async with _restricted_client(db, test_org.id, "edit_donors") as client:
        linked = await client.post(
            f"/forms/submissions/{submission.id}/match/resolve", json={"donor_id": str(donor.id)}
        )
        assert linked.status_code == 403
    async with _restricted_client(db, test_org.id, "view_donors") as client:
        candidates = await client.get(f"/forms/submissions/{submission.id}/donor-candidates")
        assert candidates.status_code == 403

    db.refresh(submission)
    assert submission.donor_id is None


@pytest.mark.asyncio
async def test_rescan_errored_photo_then_clean_scan_auto_promotes(
    authed_client, db, test_org, monkeypatch
):
    from app.db.models import AuditLog, Job
    from app.jobs.handlers.form_submissions import process_donor_intake_promote
    from app.services import form_submission_service

    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    _, slug = await _create_donor_form(authed_client)
    response = await _submit_donor_form(authed_client, slug=slug, email="rescan@example.com")
    assert response.status_code == 200, response.text
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    photo = _photo(db, submission)
    for job in db.query(Job).filter(Job.job_type == "form_submission_file_scan").all():
        job.status = "failed"
    form_submission_service.mark_submission_file_scanned(db, photo.id, "error")
    db.commit()

    rescanned = await authed_client.post(
        f"/forms/submissions/{submission.id}/files/{photo.id}/rescan"
    )

    assert rescanned.status_code == 200, rescanned.text
    assert rescanned.json()["scan_status"] == "pending"
    assert rescanned.json()["quarantined"] is False
    pending_scans = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == "form_submission_file_scan",
            Job.status == "pending",
        )
        .all()
    )
    assert [job.payload["submission_file_id"] for job in pending_scans] == [str(photo.id)]
    assert (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == "form_submission_file_rescan_requested",
            AuditLog.target_id == photo.id,
        )
        .count()
        == 1
    )

    again = await authed_client.post(f"/forms/submissions/{submission.id}/files/{photo.id}/rescan")
    assert again.status_code == 409

    form_submission_service.mark_submission_file_scanned(db, photo.id, "clean")
    db.commit()
    await process_donor_intake_promote(db, _promote_job(db, test_org.id))
    db.refresh(submission)
    assert submission.donor_id is not None
    assert submission.status == "approved"


@pytest.mark.asyncio
async def test_rescan_is_permissioned_and_org_scoped(authed_client, db, test_org):
    from app.services import form_submission_service

    _, _, submission = await _manual_submission(authed_client, db, email="rescandeny@example.com")
    photo = _photo(db, submission)
    form_submission_service.mark_submission_file_scanned(db, photo.id, "error")
    db.commit()
    foreign = _foreign_donor_submission(db)

    cross_org = await authed_client.post(f"/forms/submissions/{foreign.id}/files/{photo.id}/rescan")
    assert cross_org.status_code == 404
    unknown_file = await authed_client.post(
        f"/forms/submissions/{submission.id}/files/{uuid.uuid4()}/rescan"
    )
    assert unknown_file.status_code == 404

    async with _restricted_client(db, test_org.id, "edit_donors") as client:
        denied = await client.post(f"/forms/submissions/{submission.id}/files/{photo.id}/rescan")
        assert denied.status_code == 403

    db.refresh(photo)
    assert photo.scan_status == "error"


@pytest.mark.asyncio
async def test_rescan_requires_edit_access_to_the_submission_subject(db, test_org, test_user):
    from tests.test_form_submission_local_download import _submission_file
    from tests.test_record_capability_access import _record

    surrogate = _record(db, test_org.id, test_user.id, "surrogate")
    donor = _record(db, test_org.id, test_user.id, "donor")
    surrogate_file = _submission_file(
        db, org_id=test_org.id, surrogate_id=surrogate.id, scan_status="error", quarantined=True
    )
    donor_file = _submission_file(
        db, org_id=test_org.id, donor_id=donor.id, scan_status="error", quarantined=True
    )
    db.commit()

    def rescan(client, file_record):
        return client.post(
            f"/forms/submissions/{file_record.submission_id}/files/{file_record.id}/rescan"
        )

    async with _restricted_client(db, test_org.id, "edit_surrogates") as donor_editor:
        assert (await rescan(donor_editor, surrogate_file)).status_code == 403
    async with _restricted_client(db, test_org.id, "edit_donors") as surrogate_editor:
        assert (await rescan(surrogate_editor, donor_file)).status_code == 403
    db.refresh(surrogate_file)
    db.refresh(donor_file)
    assert (surrogate_file.scan_status, donor_file.scan_status) == ("error", "error")

    async with _restricted_client(db, test_org.id, "edit_surrogates") as donor_editor:
        assert (await rescan(donor_editor, donor_file)).status_code == 200
    async with _restricted_client(db, test_org.id, "edit_donors") as surrogate_editor:
        assert (await rescan(surrogate_editor, surrogate_file)).status_code == 200


@pytest.mark.asyncio
async def test_submission_file_upload_and_delete_require_edit_access_to_the_subject(
    db, test_org, test_user
):
    from tests.test_form_submission_local_download import _submission_file
    from tests.test_record_capability_access import _record

    surrogate = _record(db, test_org.id, test_user.id, "surrogate")
    donor = _record(db, test_org.id, test_user.id, "donor")
    surrogate_file = _submission_file(db, org_id=test_org.id, surrogate_id=surrogate.id)
    donor_file = _submission_file(db, org_id=test_org.id, donor_id=donor.id)
    db.commit()

    def upload(client, file_record):
        return client.post(
            f"/forms/submissions/{file_record.submission_id}/files",
            files={"file": ("note.pdf", b"%PDF-1.4 test", "application/pdf")},
        )

    def delete(client, file_record):
        return client.delete(
            f"/forms/submissions/{file_record.submission_id}/files/{file_record.id}"
        )

    async with _restricted_client(db, test_org.id, "edit_surrogates") as donor_editor:
        assert (await upload(donor_editor, surrogate_file)).status_code == 403
        assert (await delete(donor_editor, surrogate_file)).status_code == 403
    async with _restricted_client(db, test_org.id, "edit_donors") as surrogate_editor:
        assert (await upload(surrogate_editor, donor_file)).status_code == 403
        assert (await delete(surrogate_editor, donor_file)).status_code == 403
    db.refresh(surrogate_file)
    db.refresh(donor_file)
    assert (surrogate_file.deleted_at, donor_file.deleted_at) == (None, None)


class _SessionProxy:
    """Lets the scan job use the test transaction without closing it."""

    def __init__(self, db):
        self._db = db

    def close(self):
        return None

    def __getattr__(self, name):
        return getattr(self._db, name)


@pytest.mark.asyncio
async def test_transient_scan_failure_retries_with_backoff_then_errors(
    authed_client, db, test_org, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    from app.db.models import Job
    from app.jobs import scan_attachment

    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    _, slug = await _create_donor_form(authed_client)
    response = await _submit_donor_form(authed_client, slug=slug, email="transient@example.com")
    assert response.status_code == 200, response.text
    photo = _photo(db, db.get(FormSubmission, uuid.UUID(response.json()["id"])))
    monkeypatch.setattr(settings, "ENV", "production", raising=False)
    monkeypatch.setattr(scan_attachment, "SessionLocal", lambda: _SessionProxy(db))
    monkeypatch.setattr(scan_attachment, "_download_storage_key_to_temp", lambda _key: "/nope")
    monkeypatch.setattr(scan_attachment, "_run_clamav_scan", lambda _path: ("timeout", "timeout"))

    def scan_jobs():
        return (
            db.query(Job)
            .filter(
                Job.organization_id == test_org.id,
                Job.job_type == "form_submission_file_scan",
                Job.payload["submission_file_id"].as_string() == str(photo.id),
            )
            .order_by(Job.created_at.asc())
            .all()
        )

    def finish_current_scan():
        for job in scan_jobs():
            if job.status == "pending":
                job.status = "running"
        db.commit()

    attempts = []
    for expected_delay in (60, 300, 900):
        finish_current_scan()
        started = datetime.now(UTC)
        assert scan_attachment.scan_form_submission_file_job(photo.id) is True
        db.refresh(photo)
        assert photo.scan_status == "pending"
        retry = [job for job in scan_jobs() if job.status == "pending"]
        assert len(retry) == 1
        assert retry[0].run_at >= started + timedelta(seconds=expected_delay - 5)
        attempts.append(retry[0].payload["scan_attempt"])
        for job in scan_jobs():
            if job.status == "running":
                job.status = "completed"
    assert attempts == [2, 3, 4]

    finish_current_scan()
    scan_attachment.scan_form_submission_file_job(photo.id)
    db.refresh(photo)
    assert photo.scan_status == "error"
    assert photo.quarantined is True
    assert not [job for job in scan_jobs() if job.status == "pending"]


@pytest.mark.asyncio
async def test_remote_scan_exception_leaves_only_the_backoff_retry_pending(
    authed_client, db, test_org, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    from app import scan_job_runner
    from app.db.models import Job
    from app.jobs import scan_attachment
    from app.services import job_service

    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    _, slug = await _create_donor_form(authed_client)
    response = await _submit_donor_form(authed_client, slug=slug, email="raises@example.com")
    assert response.status_code == 200, response.text
    photo = _photo(db, db.get(FormSubmission, uuid.UUID(response.json()["id"])))
    monkeypatch.setattr(settings, "ENV", "production", raising=False)

    class _NoRollbackSession(_SessionProxy):
        # The scan fails before it writes; a real rollback would discard the test transaction.
        def rollback(self):
            self._db.expire_all()

    monkeypatch.setattr(scan_attachment, "SessionLocal", lambda: _NoRollbackSession(db))
    monkeypatch.setattr(scan_job_runner, "SessionLocal", lambda: _SessionProxy(db))
    monkeypatch.setattr(scan_job_runner, "_prepare_scanner", lambda: None)

    def _download_fails(_key):
        raise OSError("storage unavailable")

    monkeypatch.setattr(scan_attachment, "_download_storage_key_to_temp", _download_fails)

    def scan_jobs():
        return (
            db.query(Job)
            .filter(
                Job.organization_id == test_org.id,
                Job.job_type == "form_submission_file_scan",
                Job.payload["submission_file_id"].as_string() == str(photo.id),
            )
            .all()
        )

    [first_scan] = scan_jobs()
    claimed = job_service.claim_job_for_dispatch(db, first_scan.id)
    assert claimed is not None
    started = datetime.now(UTC)

    exit_code = scan_job_runner.run_scan_job(
        scan_type="form_submission_file",
        resource_id=photo.id,
        job_id=claimed.id,
        claim_token=claimed.claim_token,
    )

    assert exit_code == 0
    db.expire_all()
    assert db.get(Job, claimed.id).status == "completed"
    pending = [job for job in scan_jobs() if job.status == "pending"]
    assert len(pending) == 1
    assert pending[0].id != claimed.id
    assert pending[0].payload["scan_attempt"] == 2
    assert pending[0].run_at >= started + timedelta(seconds=55)
    db.refresh(photo)
    assert photo.scan_status == "pending"


@pytest.mark.asyncio
async def test_retry_match_replays_failed_donor_promotion(authed_client, db, test_org):
    from app.jobs.handlers.form_submissions import process_donor_intake_promote

    _, slug = await _create_donor_form(authed_client)
    response = await _submit_donor_form(authed_client, slug=slug, email="replay@example.com")
    assert response.status_code == 200, response.text
    submission = db.get(FormSubmission, uuid.UUID(response.json()["id"]))
    job = _promote_job(db, test_org.id)
    job.status = "failed"
    job.last_error = "Donor intake promotion failed"
    db.commit()

    retried = await authed_client.post(
        f"/forms/submissions/{submission.id}/match/retry",
        json={
            "unlink_surrogate": False,
            "rerun_auto_match": True,
            "create_intake_lead_if_unmatched": False,
        },
    )

    assert retried.status_code == 200, retried.text
    assert retried.json()["submission"]["match_status"] == "lead_created"
    db.refresh(job)
    assert job.status == "pending"
    await process_donor_intake_promote(db, job)
    db.refresh(submission)
    assert submission.donor_id is not None
