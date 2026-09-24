"""Manual donor rematching follows v2 record scope before linking or creating leads."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import AuditEventType, Role
from app.db.models import AuditLog, Form, FormSubmission, IntakeLead, Organization
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.schemas.donor import DonorCreate
from app.services import donor_service, form_intake_service, record_scope_service
from tests.test_email_templates_personal_scope import authed_client_for_user, create_user_with_role


@pytest.mark.asyncio
@pytest.mark.parametrize("donor_type", ["egg", "sperm"])
@pytest.mark.parametrize("visibility", ["hidden", "visible", "foreign"])
async def test_manual_donor_retry_applies_record_scope_before_matching(
    db, test_org, test_user, monkeypatch, donor_type, visibility
):
    actor = create_user_with_role(db, test_org.id, Role.INTAKE_SPECIALIST)
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    donor_org = test_org
    donor_owner = actor if visibility == "visible" else test_user
    if visibility == "foreign":
        donor_org = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
        db.add(donor_org)
        db.flush()
        donor_owner = create_user_with_role(db, donor_org.id, Role.INTAKE_SPECIALIST)
    email = f"candidate-{uuid4()}@example.com"
    donor = donor_service.create_donor(
        db,
        donor_org.id,
        donor_owner.id,
        DonorCreate(
            donor_type=donor_type,
            full_name="Donor Applicant",
            email=email,
            phone="+14155550145",
            owner_type="user",
            owner_id=donor_owner.id,
        ),
    )
    actor_session = SimpleNamespace(
        org_id=test_org.id, user_id=actor.id, role=Role.INTAKE_SPECIALIST
    )
    assert record_scope_service.can_access_record(db, actor_session, "donor", donor) is (
        visibility == "visible"
    )
    form = Form(organization_id=test_org.id, name="Donor matching", schema_json={"pages": []})
    db.add(form)
    db.flush()
    submission = FormSubmission(
        organization_id=test_org.id,
        form_id=form.id,
        source_mode="shared",
        lead_kind=f"{donor_type}_donor",
        match_status="ambiguous_review",
        match_reason="original_match",
        answers_json={
            "full_name": "Donor Applicant",
            "email": email,
            "phone": "+14155550145",
            "date_of_birth": "1995-01-01",
        },
        mapping_snapshot=[
            {"field_key": field, "surrogate_field": field}
            for field in ("full_name", "email", "phone", "date_of_birth")
        ],
    )
    db.add(submission)
    db.commit()
    monkeypatch.setattr(
        form_intake_service, "_trigger_intake_lead_created_workflow", lambda *_args, **_kwargs: None
    )

    async with authed_client_for_user(db, test_org.id, actor, Role.INTAKE_SPECIALIST) as client:
        response = await client.post(
            f"/forms/submissions/{submission.id}/match/retry",
            json={"rerun_auto_match": True, "create_intake_lead_if_unmatched": True},
        )
    assert response.status_code == 200, response.text
    db.refresh(submission)
    matched_audits = (
        db.query(AuditLog)
        .filter_by(
            organization_id=test_org.id,
            target_id=submission.id,
            event_type=AuditEventType.FORM_SUBMISSION_MATCHED.value,
        )
        .count()
    )
    if visibility == "visible":
        assert response.json()["outcome"] == "linked"
        assert submission.donor_id == donor.id
        assert submission.intake_lead_id is None
        assert matched_audits == 1
    elif visibility == "hidden":
        assert response.json()["outcome"] == "ambiguous_review"
        assert submission.match_reason == "manual_review_required"
        assert submission.donor_id is None
        assert submission.intake_lead_id is None
        assert db.query(IntakeLead).filter_by(form_id=form.id).count() == 0
        assert matched_audits == 0
    else:
        assert response.json()["outcome"] == "lead_created"
        assert submission.donor_id is None
        lead = db.get(IntakeLead, submission.intake_lead_id)
        assert lead.organization_id == test_org.id
        assert lead.lead_type == f"{donor_type}_donor"
        assert matched_audits == 0
    db.refresh(donor)
    assert donor.organization_id == donor_org.id
    assert donor.owner_id == donor_owner.id
