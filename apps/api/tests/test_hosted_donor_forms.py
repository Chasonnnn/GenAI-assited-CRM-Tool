import io
import json
import uuid
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.db.enums import IntakeLeadStatus, JobType
from app.db.models import (
    Attachment,
    Donor,
    Form,
    FormSubmission,
    FormSubmissionFile,
    IntakeLead,
    Job,
    Organization,
    Pipeline,
    PublishedIntakeVersion,
)
from app.jobs.handlers import storage as storage_job_handler
from app.services import (
    attachment_service,
    compliance_service,
    form_intake_service,
    workflow_triggers,
)


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color=(40, 130, 210)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _create_donor_form(client, *, lead_kind: str = "egg_donor") -> tuple[str, str]:
    schema = {
        "pages": [
            {
                "title": "Donor",
                "fields": [
                    {
                        "key": "applicant_name",
                        "label": "Full Name",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "email_address",
                        "label": "Email",
                        "type": "email",
                        "required": True,
                    },
                    {
                        "key": "mobile",
                        "label": "Phone",
                        "type": "phone",
                        "required": False,
                    },
                    {
                        "key": "home_state",
                        "label": "State",
                        "type": "text",
                        "required": False,
                    },
                    {
                        "key": "education_background",
                        "label": "Education",
                        "type": "textarea",
                        "required": False,
                    },
                    {
                        "key": "headshot",
                        "label": "Profile Photo",
                        "type": "file",
                        "required": True,
                    },
                ],
            }
        ]
    }
    create = await client.post(
        "/forms",
        json={
            "name": f"{lead_kind} application",
            "purpose": "other",
            "lead_kind": lead_kind,
            "form_schema": schema,
            "allowed_mime_types": ["image/png", "image/jpeg"],
        },
    )
    assert create.status_code == 200, create.text
    form_id = create.json()["id"]
    assert create.json()["lead_kind"] == lead_kind

    mappings = await client.put(
        f"/forms/{form_id}/mappings",
        json={
            "mappings": [
                {"field_key": "applicant_name", "surrogate_field": "full_name"},
                {"field_key": "email_address", "surrogate_field": "email"},
                {"field_key": "mobile", "surrogate_field": "phone"},
                {"field_key": "home_state", "surrogate_field": "state"},
                {
                    "field_key": "education_background",
                    "surrogate_field": "education",
                },
                {"field_key": "headshot", "surrogate_field": "profile_photo"},
            ]
        },
    )
    assert mappings.status_code == 200, mappings.text

    publish = await client.post(f"/forms/{form_id}/publish")
    assert publish.status_code == 200, publish.text
    links = await client.get(f"/forms/{form_id}/intake-links")
    assert links.status_code == 200, links.text
    return form_id, links.json()[0]["slug"]


async def _submit_donor_form(
    client,
    *,
    slug: str,
    email: str,
    idempotency_key: str | None = None,
):
    data = {
        "answers": json.dumps(
            {
                "applicant_name": "Taylor Donor",
                "email_address": email,
                "mobile": "+1 (607) 555-0199",
                "home_state": "NY",
                "education_background": "Master's degree",
            }
        ),
        "file_field_keys": json.dumps(["headshot"]),
    }
    if idempotency_key:
        data["idempotency_key"] = idempotency_key
    public_form = await client.get(f"/forms/public/intake/{slug}")
    assert public_form.status_code == 200, public_form.text
    data["published_version_id"] = public_form.json()["published_version_id"]
    return await client.post(
        f"/forms/public/intake/{slug}/submit",
        data=data,
        files=[("files", ("profile.png", _png_bytes(), "image/png"))],
    )


async def _create_and_promote_lead(client, submission_id: str):
    resolve = await client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={"create_intake_lead": True},
    )
    assert resolve.status_code == 200, resolve.text
    lead_id = resolve.json()["submission"]["intake_lead_id"]
    promote = await client.post(
        f"/forms/intake-leads/{lead_id}/promote",
        json={"source": "hosted_form"},
    )
    return lead_id, promote


@pytest.mark.asyncio
async def test_deleting_donor_form_schedules_durable_uploaded_photo_erasure(
    authed_client,
    db,
    test_org,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)
    form_id, slug = await _create_donor_form(authed_client)
    submit = await _submit_donor_form(
        authed_client,
        slug=slug,
        email=f"delete-form-{uuid.uuid4().hex[:8]}@example.com",
    )
    assert submit.status_code == 200, submit.text
    submission_id = uuid.UUID(submit.json()["id"])
    uploaded_file = (
        db.query(FormSubmissionFile)
        .filter(FormSubmissionFile.submission_id == submission_id)
        .one()
    )
    uploaded_file_id = uploaded_file.id
    storage_key = uploaded_file.storage_key
    storage_path = Path(attachment_service.resolve_local_storage_path(storage_key))
    assert storage_path.exists()

    deleted = await authed_client.delete(f"/forms/{form_id}")

    assert deleted.status_code == 200, deleted.text
    assert db.get(FormSubmissionFile, uploaded_file_id) is None
    cleanup_job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.STORAGE_DELETE.value,
        )
        .one()
    )
    assert cleanup_job.payload == {"storage_keys": [storage_key]}
    await storage_job_handler.process_storage_delete(db, cleanup_job)
    assert not storage_path.exists()


@pytest.mark.asyncio
async def test_donor_form_deletion_respects_submission_legal_hold(
    authed_client,
    db,
    test_org,
    test_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False, raising=False)
    form_id, slug = await _create_donor_form(authed_client)
    submit = await _submit_donor_form(
        authed_client,
        slug=slug,
        email=f"held-form-{uuid.uuid4().hex[:8]}@example.com",
    )
    assert submit.status_code == 200, submit.text
    submission_id = uuid.UUID(submit.json()["id"])
    compliance_service.create_legal_hold(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        entity_type="form_submission",
        entity_id=submission_id,
        reason="Preserve donor application",
    )

    blocked = await authed_client.delete(f"/forms/{form_id}")

    assert blocked.status_code == 409
    assert "legal hold" in blocked.json()["detail"].lower()
    assert db.get(Form, uuid.UUID(form_id)) is not None
    assert db.get(FormSubmission, submission_id) is not None
    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.STORAGE_DELETE.value,
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lead_kind", "donor_type", "pipeline_entity_type"),
    [
        ("egg_donor", "egg", "egg_donor"),
        ("sperm_donor", "sperm", "sperm_donor"),
    ],
)
async def test_hosted_donor_form_promotes_exact_subtype_with_clean_profile_photo(
    authed_client,
    db,
    test_org,
    monkeypatch,
    lead_kind,
    donor_type,
    pipeline_entity_type,
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    donor_trigger_ids: list[uuid.UUID] = []
    document_trigger_ids: list[uuid.UUID] = []
    monkeypatch.setattr(
        workflow_triggers,
        "trigger_donor_created",
        lambda _db, donor: donor_trigger_ids.append(donor.id),
    )
    monkeypatch.setattr(
        workflow_triggers,
        "trigger_document_uploaded",
        lambda _db, attachment: document_trigger_ids.append(attachment.id),
    )
    form_id, slug = await _create_donor_form(authed_client, lead_kind=lead_kind)
    submit = await _submit_donor_form(
        authed_client,
        slug=slug,
        email=f"{donor_type}-{uuid.uuid4().hex[:8]}@example.com",
    )
    assert submit.status_code == 200, submit.text
    submission_id = submit.json()["id"]
    assert submit.json()["donor_id"] is None

    submitted_file = (
        db.query(FormSubmissionFile)
        .filter(FormSubmissionFile.submission_id == uuid.UUID(submission_id))
        .one()
    )
    preview = await authed_client.get(
        f"/forms/submissions/{submission_id}/files/{submitted_file.id}/download"
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["filename"] == "profile.png"

    lead_id, promote = await _create_and_promote_lead(authed_client, submission_id)
    assert promote.status_code == 200, promote.text
    donor_id = promote.json()["donor_id"]
    assert donor_id
    assert promote.json()["surrogate_id"] is None
    assert promote.json()["linked_submission_count"] == 1

    donor = db.query(Donor).filter(Donor.id == uuid.UUID(donor_id)).one()
    assert donor.organization_id == test_org.id
    assert donor.donor_type == donor_type
    assert donor.full_name == "Taylor Donor"
    assert donor.phone == "+16075550199"
    assert donor.state == "NY"
    assert donor.education == "Master's degree"
    assert donor.profile_photo_attachment_id is not None
    assert (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == test_org.id,
            Pipeline.entity_type == pipeline_entity_type,
            Pipeline.is_default.is_(True),
        )
        .count()
        == 1
    )

    source_file = (
        db.query(FormSubmissionFile)
        .filter(FormSubmissionFile.submission_id == uuid.UUID(submission_id))
        .one()
    )
    attachment = (
        db.query(Attachment).filter(Attachment.id == donor.profile_photo_attachment_id).one()
    )
    assert attachment.organization_id == test_org.id
    assert attachment.donor_id == donor.id
    assert attachment.scan_status == "clean"
    assert attachment.quarantined is False
    assert attachment.storage_key != source_file.storage_key
    assert attachment.checksum_sha256 == source_file.checksum_sha256

    submission = db.query(FormSubmission).filter(FormSubmission.id == submission_id).one()
    lead = db.query(IntakeLead).filter(IntakeLead.id == uuid.UUID(lead_id)).one()
    assert submission.lead_kind == lead_kind
    assert submission.donor_id == donor.id
    assert submission.surrogate_id is None
    assert lead.lead_type == lead_kind
    assert lead.promoted_donor_id == donor.id
    assert lead.promoted_surrogate_id is None

    submissions = await authed_client.get(f"/forms/{form_id}/submissions")
    assert submissions.status_code == 200, submissions.text
    linked_submission = next(
        item for item in submissions.json() if item["id"] == submission_id
    )
    assert linked_submission["donor_id"] == donor_id
    assert linked_submission["donor_number"] == donor.donor_number

    retry = await authed_client.post(
        f"/forms/intake-leads/{lead_id}/promote",
        json={"source": "hosted_form"},
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["donor_id"] == donor_id
    assert retry.json()["linked_submission_count"] == 1
    assert db.query(Donor).filter(Donor.organization_id == test_org.id).count() == 1
    assert db.query(Attachment).filter(Attachment.donor_id == donor.id).count() == 1
    assert donor_trigger_ids == [donor.id]
    assert document_trigger_ids == [attachment.id]

    form = db.query(Form).filter(Form.id == uuid.UUID(form_id)).one()
    assert form.lead_kind == lead_kind


@pytest.mark.asyncio
async def test_republishing_donor_form_advances_link_version_and_subtype(
    authed_client,
    db,
    test_org,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    form_id, slug = await _create_donor_form(authed_client, lead_kind="egg_donor")

    first_public = await authed_client.get(f"/forms/public/intake/{slug}")
    assert first_public.status_code == 200, first_public.text
    first_version_id = uuid.UUID(first_public.json()["published_version_id"])
    first_version = db.get(PublishedIntakeVersion, first_version_id)
    assert first_version is not None
    assert first_version.lead_kind_snapshot == "egg_donor"
    first_snapshot = json.loads(json.dumps(first_version.form_schema_snapshot_json))
    first_mapping_snapshot = json.loads(json.dumps(first_version.mapping_snapshot_json))
    first_version_number = first_version.version
    second_link_create = await authed_client.post(
        f"/forms/{form_id}/intake-links",
        json={"campaign_name": "Secondary donor campaign"},
    )
    assert second_link_create.status_code == 200, second_link_create.text
    second_slug = second_link_create.json()["slug"]
    second_link_first_version_id = uuid.UUID(
        second_link_create.json()["published_version_id"]
    )

    sperm_schema = {
        "pages": [
            {
                "title": "Sperm Donor",
                "fields": [
                    {
                        "key": "sperm_name",
                        "label": "Full Name",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "sperm_email",
                        "label": "Email",
                        "type": "email",
                        "required": True,
                    },
                    {
                        "key": "sperm_education",
                        "label": "Education",
                        "type": "textarea",
                        "required": False,
                    },
                    {
                        "key": "sperm_photo",
                        "label": "Profile Photo",
                        "type": "file",
                        "required": True,
                    },
                ],
            }
        ]
    }
    update = await authed_client.patch(
        f"/forms/{form_id}",
        json={"lead_kind": "sperm_donor", "form_schema": sperm_schema},
    )
    assert update.status_code == 200, update.text
    mappings = await authed_client.put(
        f"/forms/{form_id}/mappings",
        json={
            "mappings": [
                {"field_key": "sperm_name", "surrogate_field": "full_name"},
                {"field_key": "sperm_email", "surrogate_field": "email"},
                {"field_key": "sperm_education", "surrogate_field": "education"},
                {"field_key": "sperm_photo", "surrogate_field": "profile_photo"},
            ]
        },
    )
    assert mappings.status_code == 200, mappings.text

    republish = await authed_client.post(f"/forms/{form_id}/publish")
    assert republish.status_code == 200, republish.text
    second_public = await authed_client.get(f"/forms/public/intake/{slug}")
    assert second_public.status_code == 200, second_public.text
    second_payload = second_public.json()
    second_version_id = uuid.UUID(second_payload["published_version_id"])
    assert second_version_id != first_version_id
    assert second_payload["form_schema"]["pages"][0]["fields"][0]["key"] == "sperm_name"

    db.expire_all()
    first_version = db.get(PublishedIntakeVersion, first_version_id)
    second_version = db.get(PublishedIntakeVersion, second_version_id)
    assert first_version is not None
    assert first_version.lead_kind_snapshot == "egg_donor"
    assert first_version.form_schema_snapshot_json == first_snapshot
    assert first_version.mapping_snapshot_json == first_mapping_snapshot
    assert first_version.version == first_version_number
    assert second_version is not None
    assert second_version.lead_kind_snapshot == "sperm_donor"
    assert second_version.version == first_version_number + 1
    assert {
        item["surrogate_field"]: item["field_key"]
        for item in second_version.mapping_snapshot_json
    } == {
        "full_name": "sperm_name",
        "email": "sperm_email",
        "education": "sperm_education",
        "profile_photo": "sperm_photo",
    }
    second_link_public = await authed_client.get(f"/forms/public/intake/{second_slug}")
    assert second_link_public.status_code == 200, second_link_public.text
    assert uuid.UUID(second_link_public.json()["published_version_id"]) != (
        second_link_first_version_id
    )
    second_link_version = db.get(
        PublishedIntakeVersion,
        uuid.UUID(second_link_public.json()["published_version_id"]),
    )
    assert second_link_version is not None
    assert second_link_version.lead_kind_snapshot == "sperm_donor"

    submission_payload = {
        "answers": json.dumps(
            {
                "sperm_name": "Republished Donor",
                "sperm_email": f"republished-{uuid.uuid4().hex[:8]}@example.com",
                "sperm_education": "Bachelor's degree",
            }
        ),
        "file_field_keys": json.dumps(["sperm_photo"]),
    }
    stale = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={**submission_payload, "published_version_id": str(first_version_id)},
        files=[("files", ("profile.png", _png_bytes(), "image/png"))],
    )
    assert stale.status_code == 409, stale.text
    missing_version = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data=submission_payload,
        files=[("files", ("profile.png", _png_bytes(), "image/png"))],
    )
    assert missing_version.status_code == 409, missing_version.text

    submit = await authed_client.post(
        f"/forms/public/intake/{slug}/submit",
        data={**submission_payload, "published_version_id": str(second_version_id)},
        files=[("files", ("profile.png", _png_bytes(), "image/png"))],
    )
    assert submit.status_code == 200, submit.text
    submission = db.get(FormSubmission, uuid.UUID(submit.json()["id"]))
    assert submission is not None
    assert submission.published_version_id == second_version_id
    assert submission.lead_kind == "sperm_donor"
    assert submission.schema_snapshot == second_version.form_schema_snapshot_json
    assert submission.mapping_snapshot == second_version.mapping_snapshot_json

    egg_donors_before = (
        db.query(Donor)
        .filter(
            Donor.organization_id == test_org.id,
            Donor.donor_type == "egg",
        )
        .count()
    )
    sperm_donors_before = (
        db.query(Donor)
        .filter(
            Donor.organization_id == test_org.id,
            Donor.donor_type == "sperm",
        )
        .count()
    )
    _lead_id, promote = await _create_and_promote_lead(authed_client, str(submission.id))
    assert promote.status_code == 200, promote.text
    donor = db.get(Donor, uuid.UUID(promote.json()["donor_id"]))
    assert donor is not None
    assert donor.donor_type == "sperm"
    assert donor.full_name == "Republished Donor"
    assert donor.education == "Bachelor's degree"
    assert (
        db.query(Donor)
        .filter(
            Donor.organization_id == test_org.id,
            Donor.donor_type == "egg",
        )
        .count()
        == egg_donors_before
    )
    assert (
        db.query(Donor)
        .filter(
            Donor.organization_id == test_org.id,
            Donor.donor_type == "sperm",
        )
        .count()
        == sperm_donors_before + 1
    )


@pytest.mark.asyncio
async def test_republishing_form_rolls_back_all_link_versions_when_reconciliation_fails(
    authed_client,
    db,
    monkeypatch,
):
    form_id, first_slug = await _create_donor_form(
        authed_client,
        lead_kind="egg_donor",
    )
    second_link_create = await authed_client.post(
        f"/forms/{form_id}/intake-links",
        json={"campaign_name": "Rollback donor campaign"},
    )
    assert second_link_create.status_code == 200, second_link_create.text
    second_slug = second_link_create.json()["slug"]

    first_public = await authed_client.get(f"/forms/public/intake/{first_slug}")
    second_public = await authed_client.get(f"/forms/public/intake/{second_slug}")
    assert first_public.status_code == 200, first_public.text
    assert second_public.status_code == 200, second_public.text
    original_version_ids = {
        uuid.UUID(first_public.json()["published_version_id"]),
        uuid.UUID(second_public.json()["published_version_id"]),
    }
    original_version_count = (
        db.query(PublishedIntakeVersion)
        .filter(PublishedIntakeVersion.form_id == uuid.UUID(form_id))
        .count()
    )

    def fail_routing_reconciliation(*_args, **_kwargs):
        raise RuntimeError("forced routing reconciliation failure")

    monkeypatch.setattr(
        form_intake_service,
        "ensure_default_intake_routing_workflow",
        fail_routing_reconciliation,
    )

    from sqlalchemy.orm import Session

    from app.core.deps import get_db
    from app.main import app

    publish_db = Session(
        bind=db.get_bind(),
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    original_db_override = app.dependency_overrides[get_db]

    def override_publish_db():
        yield publish_db

    app.dependency_overrides[get_db] = override_publish_db
    try:
        with pytest.raises(RuntimeError, match="forced routing reconciliation failure"):
            await authed_client.post(f"/forms/{form_id}/publish")
    finally:
        publish_db.close()
        app.dependency_overrides[get_db] = original_db_override

    db.expire_all()
    first_after = await authed_client.get(f"/forms/public/intake/{first_slug}")
    second_after = await authed_client.get(f"/forms/public/intake/{second_slug}")
    assert first_after.status_code == 200, first_after.text
    assert second_after.status_code == 200, second_after.text
    assert {
        uuid.UUID(first_after.json()["published_version_id"]),
        uuid.UUID(second_after.json()["published_version_id"]),
    } == original_version_ids
    assert (
        db.query(PublishedIntakeVersion)
        .filter(PublishedIntakeVersion.form_id == uuid.UUID(form_id))
        .count()
        == original_version_count
    )


@pytest.mark.asyncio
async def test_donor_publish_requires_required_mapped_profile_photo(authed_client):
    create = await authed_client.post(
        "/forms",
        json={
            "name": "Incomplete donor form",
            "purpose": "other",
            "lead_kind": "egg_donor",
            "form_schema": {
                "pages": [
                    {
                        "fields": [
                            {
                                "key": "name",
                                "label": "Name",
                                "type": "text",
                                "required": True,
                            },
                            {
                                "key": "email",
                                "label": "Email",
                                "type": "email",
                                "required": True,
                            },
                            {
                                "key": "photo",
                                "label": "Photo",
                                "type": "file",
                                "required": False,
                            },
                        ]
                    }
                ]
            },
        },
    )
    form_id = create.json()["id"]
    mappings = await authed_client.put(
        f"/forms/{form_id}/mappings",
        json={
            "mappings": [
                {"field_key": "name", "surrogate_field": "full_name"},
                {"field_key": "email", "surrogate_field": "email"},
                {"field_key": "photo", "surrogate_field": "profile_photo"},
            ]
        },
    )
    assert mappings.status_code == 200

    publish = await authed_client.post(f"/forms/{form_id}/publish")
    assert publish.status_code == 400
    assert "Profile Photo" in publish.json()["detail"]
    assert "marked required" in publish.json()["detail"]


@pytest.mark.asyncio
async def test_donor_promotion_fails_closed_until_profile_scan_is_clean(
    authed_client,
    db,
    test_org,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True)
    donors_before = (
        db.query(Donor).filter(Donor.organization_id == test_org.id).count()
    )
    donor_attachments_before = (
        db.query(Attachment)
        .filter(
            Attachment.organization_id == test_org.id,
            Attachment.donor_id.is_not(None),
        )
        .count()
    )
    _form_id, slug = await _create_donor_form(authed_client)
    submit = await _submit_donor_form(
        authed_client,
        slug=slug,
        email=f"pending-{uuid.uuid4().hex[:8]}@example.com",
    )
    assert submit.status_code == 200, submit.text
    submission_id = submit.json()["id"]
    resolve = await authed_client.post(
        f"/forms/submissions/{submission_id}/match/resolve",
        json={"create_intake_lead": True},
    )
    lead_id = resolve.json()["submission"]["intake_lead_id"]

    blocked = await authed_client.post(
        f"/forms/intake-leads/{lead_id}/promote",
        json={},
    )
    assert blocked.status_code == 400
    assert "pass security scanning" in blocked.json()["detail"]
    assert (
        db.query(Donor).filter(Donor.organization_id == test_org.id).count()
        == donors_before
    )
    assert (
        db.query(Attachment)
        .filter(
            Attachment.organization_id == test_org.id,
            Attachment.donor_id.is_not(None),
        )
        .count()
        == donor_attachments_before
    )

    source_file = (
        db.query(FormSubmissionFile)
        .filter(FormSubmissionFile.submission_id == uuid.UUID(submission_id))
        .one()
    )
    source_file.scan_status = "clean"
    source_file.quarantined = False
    db.commit()

    promoted = await authed_client.post(
        f"/forms/intake-leads/{lead_id}/promote",
        json={},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["donor_id"]
    assert (
        db.query(Donor).filter(Donor.organization_id == test_org.id).count()
        == donors_before + 1
    )


@pytest.mark.asyncio
async def test_donor_promotion_rejects_active_email_conflict_without_partial_records(
    authed_client,
    db,
    test_org,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    donors_before = (
        db.query(Donor).filter(Donor.organization_id == test_org.id).count()
    )
    donor_attachments_before = (
        db.query(Attachment)
        .filter(
            Attachment.organization_id == test_org.id,
            Attachment.donor_id.is_not(None),
        )
        .count()
    )
    email = f"duplicate-{uuid.uuid4().hex[:8]}@example.com"
    existing = await authed_client.post(
        "/donors",
        json={
            "donor_type": "egg",
            "full_name": "Existing Donor",
            "email": email,
        },
    )
    assert existing.status_code == 201, existing.text

    _form_id, slug = await _create_donor_form(authed_client)
    submit = await _submit_donor_form(authed_client, slug=slug, email=email)
    assert submit.status_code == 200, submit.text
    lead_id, promote = await _create_and_promote_lead(authed_client, submit.json()["id"])

    assert promote.status_code == 409
    assert "active donor" in promote.json()["detail"].lower()
    assert (
        db.query(Donor).filter(Donor.organization_id == test_org.id).count()
        == donors_before + 1
    )
    assert (
        db.query(Attachment)
        .filter(
            Attachment.organization_id == test_org.id,
            Attachment.donor_id.is_not(None),
        )
        .count()
        == donor_attachments_before
    )
    lead = db.query(IntakeLead).filter(IntakeLead.id == uuid.UUID(lead_id)).one()
    assert lead.status == IntakeLeadStatus.PENDING_REVIEW.value
    assert lead.promoted_donor_id is None


@pytest.mark.asyncio
async def test_donor_form_target_is_immutable_after_submission_and_foreign_lead_is_hidden(
    authed_client,
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)
    form_id, slug = await _create_donor_form(authed_client)
    submit = await _submit_donor_form(
        authed_client,
        slug=slug,
        email=f"immutable-{uuid.uuid4().hex[:8]}@example.com",
    )
    assert submit.status_code == 200

    change_target = await authed_client.patch(
        f"/forms/{form_id}",
        json={"lead_kind": "sperm_donor"},
    )
    assert change_target.status_code == 400
    assert "cannot change" in change_target.json()["detail"].lower()
    form = db.query(Form).filter(Form.id == uuid.UUID(form_id)).one()
    assert form.lead_kind == "egg_donor"

    foreign_org = Organization(
        id=uuid.uuid4(),
        name="Foreign Donor Form Org",
        slug=f"foreign-donor-form-{uuid.uuid4().hex[:8]}",
    )
    db.add(foreign_org)
    db.flush()
    foreign_lead = IntakeLead(
        id=uuid.uuid4(),
        organization_id=foreign_org.id,
        lead_type="egg_donor",
        full_name="Foreign Lead",
        email="foreign@example.com",
        status=IntakeLeadStatus.PENDING_REVIEW.value,
    )
    db.add(foreign_lead)
    db.commit()

    foreign_get = await authed_client.get(f"/forms/intake-leads/{foreign_lead.id}")
    assert foreign_get.status_code == 404
    foreign_promote = await authed_client.post(
        f"/forms/intake-leads/{foreign_lead.id}/promote",
        json={},
    )
    assert foreign_promote.status_code == 404
