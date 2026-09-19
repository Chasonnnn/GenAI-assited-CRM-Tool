"""Profile persistence, submitted-question fidelity and access boundaries."""

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.csrf import CSRF_HEADER
from app.db.enums import Role
from app.db.models import AuditLog, Donor, Form, FormSubmission, Organization
from app.schemas.donor import DonorUpdate
from app.services import donor_profile_service, donor_service, entity_activity_service
from tests.test_donors import _client_for_org, _create_donor


@pytest.fixture
def other_org(db):
    org = Organization(
        id=uuid.uuid4(), name="Other tenant", slug=f"donor-other-{uuid.uuid4().hex[:8]}"
    )
    db.add(org)
    db.flush()
    return org


def _submission(db, donor, *, org_id=None, answers=None, fields=None, submitted_at=None):
    org_id = org_id or donor.organization_id
    fields = fields if fields is not None else [
        {"key": "birth", "label": "Date of birth", "type": "date"},
        {"key": "height", "label": "Height", "type": "height"},
        {"key": "weight", "label": "Weight", "type": "number"},
        {"key": "race", "label": "Race / ethnicity", "type": "text"},
        *[
            {
                "key": spec["key"],
                "label": spec["question"],
                "type": "select" if spec["options"] else "text",
                "options": spec["options"] or None,
            }
            for spec in donor_profile_service.DEFAULT_QUESTIONS
        ],
    ]
    schema = {"pages": [{"title": "Donor questions", "fields": fields}]}
    form = Form(id=uuid.uuid4(), organization_id=org_id, name="Donor screening", schema_json=schema)
    db.add(form)
    db.flush()
    submission = FormSubmission(
        id=uuid.uuid4(),
        organization_id=org_id,
        form_id=form.id,
        donor_id=donor.id,
        schema_snapshot=schema,
        mapping_snapshot=[{"field_key": "birth", "surrogate_field": "date_of_birth"}],
        answers_json=answers if answers is not None else {
            "birth": "2000-05-14",
            "height": "5.5",
            "weight": 135,
            "race": "Asian",
            "education": "Master’s degree",
            "college": "Example University",
            "nicotine": "No",
            "cannabis": "No",
            "previous_donation": "Yes",
            "infectious_disease": "Prefer to discuss with the team",
        },
    )
    if submitted_at is not None:
        submission.submitted_at = submitted_at
    db.add(submission)
    db.flush()
    return submission


@pytest.mark.asyncio
async def test_donor_profile_roundtrip_masks_ssn_and_encrypts_sensitive_columns(db, test_org):
    async with _client_for_org(db, test_org) as client:
        created = await _create_donor(client)
        donor_id = created["id"]
        values = {
            "date_of_birth": "2000-05-14",
            "race": "Asian",
            "height_ft": "5.5",
            "weight_lb": 135,
            "education": "Master’s degree",
            "college": "Example University",
            "marital_status": "Single",
            "ssn": "111223333",
            "partner_ssn": "999-88-7777",
            "partner_name": "Sample Partner",
            "address_line1": "100 Sample Avenue",
            "clinic_name": "Example IVF",
            "clinic_email": "clinic@example.com",
            "insurance_policy_number": "sample-policy",
            "nicotine": "No",
            "cannabis": "No",
            "infectious_disease": "Prefer to discuss with the team",
            "previous_donation": "Yes",
        }
        response = await client.patch(f"/donors/{donor_id}", json=values)
        assert response.status_code == 200
        profile_response = await client.get(f"/donors/{donor_id}/profile")
        assert profile_response.status_code == 200
        assert profile_response.headers["cache-control"] == "no-store"
        profile = profile_response.json()
        assert profile["ssn_masked"] == "***-**-3333"
        assert profile["partner_ssn_masked"] == "***-**-7777"
        assert "ssn" not in profile and "partner_ssn" not in profile
        assert profile["height_ft"] == "5.50"
        for field in ("college", "clinic_email", "infectious_disease", "insurance_policy_number"):
            assert profile[field] == values[field]
        raw = db.execute(
            text(
                "SELECT ssn, date_of_birth, college, infectious_disease, insurance_policy_number FROM donors WHERE id = :id"
            ),
            {"id": donor_id},
        ).one()
        for stored, original in zip(
            raw,
            (
                "111-22-3333",
                values["date_of_birth"],
                values["college"],
                values["infectious_disease"],
                values["insurance_policy_number"],
            ),
            strict=True,
        ):
            assert stored and stored != original
        reveal = await client.post(f"/donors/{donor_id}/sensitive-info/reveal")
        assert reveal.status_code == 200
        assert reveal.json()["ssn"] == "111-22-3333"
        assert reveal.headers["cache-control"] == "no-store"
        logs = db.query(AuditLog).filter(AuditLog.target_id == uuid.UUID(donor_id)).all()
        details = json.dumps([log.details for log in logs])
        for value in (
            "111-22-3333",
            "999-88-7777",
            "sample-policy",
            "Prefer to discuss with the team",
            "Example University",
        ):
            assert value not in details


@pytest.mark.asyncio
async def test_form_answers_populate_profile_but_manual_edits_and_explicit_clears_win(db, test_org):
    async with _client_for_org(db, test_org) as client:
        created = await _create_donor(client)
        donor = db.get(Donor, uuid.UUID(created["id"]))
        submission = _submission(db, donor)
        before = dict(submission.answers_json)
        profile = (await client.get(f"/donors/{donor.id}/profile")).json()
        assert profile["date_of_birth"] == "2000-05-14"
        assert Decimal(profile["height_ft"]) == Decimal("5.5")
        assert profile["weight_lb"] == 135
        assert profile["race"] == "Asian"
        assert profile["college"] == "Example University"
        # Existing structured education is authoritative; no invented minimum education criterion.
        assert profile["education"] == created["education"]
        assert [item["key"] for item in profile["eligibility_checklist"]] == [
            item["key"] for item in donor_profile_service.DEFAULT_QUESTIONS
        ]
        assert profile["infectious_disease"] == "Prefer to discuss with the team"
        assert (
            await client.patch(f"/donors/{donor.id}", json={"nicotine": "Yes", "college": None})
        ).status_code == 200
        assert (
            await client.patch(f"/donors/{donor.id}", json={"nicotine": None})
        ).status_code == 200
        refreshed = (await client.get(f"/donors/{donor.id}/profile")).json()
        assert refreshed["nicotine"] is None and refreshed["college"] is None
        assert refreshed["cannabis"] == "No"
        assert refreshed["infectious_disease"] == "Prefer to discuss with the team"
        db.refresh(submission)
        assert submission.answers_json == before


@pytest.mark.asyncio
async def test_checklist_uses_submitted_option_labels_and_only_questions_asked(db, test_org):
    async with _client_for_org(db, test_org) as client:
        created = await _create_donor(client)
        donor = db.get(Donor, uuid.UUID(created["id"]))
        submission = _submission(db, donor, answers={"infectious_disease": "call"})
        submission.schema_snapshot = {"pages": [{"title": "Follow-up", "fields": [{
            "key": "infectious_disease", "type": "radio", "label": "Discuss screening history?",
            "options": [{"value": "call", "label": "Discuss privately"}, {"value": "none", "label": "No history"}],
        }]}]}
        db.flush()
        profile = (await client.get(f"/donors/{donor.id}/profile")).json()
        item = next(item for item in profile["eligibility_checklist"] if item["key"] == "infectious_disease")
        assert item["value"] == "Discuss privately"
        assert item["question"] == "Discuss screening history?"
        assert item["options"][0] == {"value": "Discuss privately", "label": "Discuss privately"}
        assert "nicotine" not in {item["key"] for item in profile["eligibility_checklist"]}
        assert (await client.patch(f"/donors/{donor.id}", json={"infectious_disease": "No history"})).status_code == 200
        assert (await client.get(f"/donors/{donor.id}/profile")).json()["infectious_disease"] == "No history"


@pytest.mark.asyncio
async def test_profile_retains_earlier_answers_when_later_forms_omit_questions(db, test_org):
    async with _client_for_org(db, test_org) as client:
        created = await _create_donor(client)
        donor = db.get(Donor, uuid.UUID(created["id"]))
        now = datetime.now(UTC)
        original = _submission(db, donor, submitted_at=now - timedelta(days=2))
        before = dict(original.answers_json)
        _submission(
            db, donor, submitted_at=now - timedelta(days=1),
            answers={"nicotine": "current", "birth": "2001-02-03"},
            fields=[
                {"key": "birth", "type": "date", "label": "Updated birth date"},
                {"key": "nicotine", "type": "radio", "label": "Updated nicotine question",
                 "options": [{"value": "current", "label": "Current use"}]},
            ],
        )
        _submission(
            db, donor, submitted_at=now, answers={"followup": "Received"},
            fields=[{"key": "followup", "type": "text", "label": "Follow-up"}],
        )
        profile = (await client.get(f"/donors/{donor.id}/profile")).json()
        assert profile["date_of_birth"] == "2001-02-03"
        assert profile["weight_lb"] == 135
        assert profile["college"] == "Example University"
        assert profile["infectious_disease"] == "Prefer to discuss with the team"
        item = next(item for item in profile["eligibility_checklist"] if item["key"] == "nicotine")
        assert item["value"] == "Current use"
        assert item["question"] == "Updated nicotine question"
        assert item["options"] == [{"value": "Current use", "label": "Current use"}]
        assert (await client.patch(
            f"/donors/{donor.id}", json={"college": None, "nicotine": "Manual answer"}
        )).status_code == 200
        refreshed = (await client.get(f"/donors/{donor.id}/profile")).json()
        assert refreshed["college"] is None
        assert refreshed["nicotine"] == "Manual answer"
        assert refreshed["weight_lb"] == 135
        db.refresh(original)
        assert original.answers_json == before


@pytest.mark.asyncio
async def test_profile_respects_newer_unanswered_and_hidden_questions(db, test_org):
    async with _client_for_org(db, test_org) as client:
        created = await _create_donor(client)
        donor = db.get(Donor, uuid.UUID(created["id"]))
        now = datetime.now(UTC)
        _submission(db, donor, submitted_at=now - timedelta(days=1))
        _submission(
            db, donor, submitted_at=now,
            answers={"college": "", "nicotine": None, "show": "No", "cannabis": "Yes"},
            fields=[
                {"key": "college", "type": "text", "label": "Current college"},
                {"key": "nicotine", "type": "text", "label": "Current nicotine use"},
                {"key": "show", "type": "text", "label": "Ask cannabis question"},
                {"key": "cannabis", "type": "text", "label": "Hidden question",
                 "show_if": {"field_key": "show", "operator": "equals", "value": "Yes"}},
            ],
        )
        profile = (await client.get(f"/donors/{donor.id}/profile")).json()
        assert profile["college"] is None
        assert profile["nicotine"] is None
        assert profile["cannabis"] == "No"
        assert profile["previous_donation"] == "Yes"
        assert {item["key"] for item in profile["eligibility_checklist"]} == {
            item["key"] for item in donor_profile_service.DEFAULT_QUESTIONS
        }


@pytest.mark.asyncio
async def test_profile_history_excludes_other_tenants_and_donors(db, test_org, other_org):
    async with _client_for_org(db, test_org) as client:
        created = await _create_donor(client)
        donor = db.get(Donor, uuid.UUID(created["id"]))
        now = datetime.now(UTC)
        _submission(db, donor, submitted_at=now - timedelta(days=2))
        _submission(
            db, donor, submitted_at=now, org_id=other_org.id,
            answers={"college": "Other tenant college"},
        )
        _submission(
            db, donor, submitted_at=now - timedelta(days=1), answers={}, fields=[]
        )
        from app.schemas.donor import DonorCreate

        other_donor = donor_service.create_donor(
            db, test_org.id, None,
            DonorCreate(donor_type="egg", full_name="Another Donor", email="another@example.com"),
        )
        _submission(db, other_donor, submitted_at=now, answers={"college": "Other donor college"})
        profile = (await client.get(f"/donors/{donor.id}/profile")).json()
        assert profile["college"] == "Example University"


@pytest.mark.asyncio
async def test_profile_access_is_org_scoped_and_requires_permissions_and_csrf(
    db, test_org, other_org
):
    async with _client_for_org(db, test_org) as client:
        created = await _create_donor(client)
        donor_id = created["id"]
        donor = db.get(Donor, uuid.UUID(donor_id))
        _submission(db, donor, org_id=other_org.id)
        # Even a malformed cross-org relationship must not expose another tenant's submission.
        assert (await client.get(f"/donors/{donor_id}/profile")).json()["college"] is None
        token = client.headers.pop(CSRF_HEADER)
        assert (
            await client.patch(f"/donors/{donor_id}", json={"college": "Example"})
        ).status_code == 403
        assert (await client.post(f"/donors/{donor_id}/sensitive-info/reveal")).status_code == 403
        client.headers[CSRF_HEADER] = token
    async with _client_for_org(db, other_org) as client:
        assert (await client.get(f"/donors/{donor_id}/profile")).status_code == 404
        assert (
            await client.patch(f"/donors/{donor_id}", json={"nicotine": "No"})
        ).status_code == 404
        assert (await client.post(f"/donors/{donor_id}/sensitive-info/reveal")).status_code == 404
    async with _client_for_org(db, test_org, role=Role.ADMIN, revokes=("view_donors",)) as client:
        assert (await client.get(f"/donors/{donor_id}/profile")).status_code == 403
        assert (await client.post(f"/donors/{donor_id}/sensitive-info/reveal")).status_code == 403
    async with _client_for_org(db, test_org, role=Role.ADMIN, revokes=("edit_donors",)) as client:
        assert (
            await client.patch(f"/donors/{donor_id}", json={"weight_lb": 140})
        ).status_code == 403


@pytest.mark.asyncio
async def test_profile_validation_and_archive_guard(db, test_org):
    async with _client_for_org(db, test_org) as client:
        donor_id = (await _create_donor(client))["id"]
        for changes in (
            {"height_ft": 11},
            {"weight_lb": -1},
            {"ssn": "123"},
            {"clinic_email": "bad-email"},
            {"marital_status": "invalid"},
            {"organization_id": str(uuid.uuid4())},
        ):
            assert (await client.patch(f"/donors/{donor_id}", json=changes)).status_code == 422
        assert (await client.post(f"/donors/{donor_id}/archive")).status_code == 200
        assert (
            await client.patch(f"/donors/{donor_id}", json={"college": "Example"})
        ).status_code == 400


def test_profile_update_and_activity_are_atomic(db, test_org, test_user, monkeypatch):
    from app.schemas.donor import DonorCreate

    atomic_db = Session(bind=db.connection(), join_transaction_mode="create_savepoint")

    donor = donor_service.create_donor(
        atomic_db,
        test_org.id,
        test_user.id,
        DonorCreate(donor_type="egg", full_name="Sample Donor", email="atomic@example.com"),
        emit_workflow_events=False,
    )

    def fail_activity(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(entity_activity_service, "record_activity", fail_activity)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        donor_service.update_donor(
            atomic_db,
            donor,
            test_user.id,
            DonorUpdate(date_of_birth=date(2000, 1, 1), nicotine="No"),
            emit_workflow_events=False,
        )
    atomic_db.refresh(donor)
    assert donor.date_of_birth is None
    assert donor.nicotine is None
    assert donor.profile_updated_fields == []

    atomic_db.close()
