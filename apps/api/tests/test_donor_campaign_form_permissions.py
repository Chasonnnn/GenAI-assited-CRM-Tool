from __future__ import annotations

import io
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.encryption import hash_email
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import (
    Campaign,
    CampaignRecipient,
    CampaignRun,
    Donor,
    EmailTemplate,
    Form,
    FormSubmission,
    FormSubmissionFile,
    IntakeLead,
    Membership,
    User,
    UserPermissionOverride,
)
from app.main import app
from app.services import pipeline_service, session_service


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color=(40, 130, 210)).save(buffer, format="PNG")
    return buffer.getvalue()


def _admin_with_revokes(db, org_id: UUID, *permissions: str) -> User:
    user = User(
        id=uuid4(),
        email=f"donor-scope-{uuid4().hex[:8]}@test.com",
        display_name="Donor Scope Tester",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid4(),
            user_id=user.id,
            organization_id=org_id,
            role=Role.ADMIN.value,
        )
    )
    db.add_all(
        [
            UserPermissionOverride(
                id=uuid4(),
                organization_id=org_id,
                user_id=user.id,
                permission=permission,
                override_type="revoke",
            )
            for permission in permissions
        ]
    )
    db.flush()
    return user


@asynccontextmanager
async def _client_for(db, org_id: UUID, user: User):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=Role.ADMIN.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client
    app.dependency_overrides.clear()


def _donor_campaign_records(db, org_id: UUID, creator_id: UUID):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type="egg_donor",
    )
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
    assert stage is not None
    email = "private-campaign-donor@example.com"
    donor = Donor(
        id=uuid4(),
        organization_id=org_id,
        donor_number="D19001",
        donor_type="egg",
        full_name="Private Campaign Donor",
        email=email,
        email_hash=hash_email(email),
        stage_id=stage.id,
    )
    template = EmailTemplate(
        id=uuid4(),
        organization_id=org_id,
        name="Donor permission template",
        subject="Hello {{first_name}}",
        body="<p>Hello</p>",
        is_active=True,
    )
    db.add_all([donor, template])
    db.flush()
    campaign = Campaign(
        id=uuid4(),
        organization_id=org_id,
        name=f"Private donor campaign {uuid4().hex[:8]}",
        channel="email",
        email_template_id=template.id,
        recipient_type="egg_donor",
        filter_criteria={"stage_keys": ["new"]},
        status="completed",
        created_by_user_id=creator_id,
    )
    db.add(campaign)
    db.flush()
    run = CampaignRun(
        id=uuid4(),
        organization_id=org_id,
        campaign_id=campaign.id,
        status="completed",
        total_count=1,
        sent_count=1,
        delivered_count=0,
        failed_count=0,
        skipped_count=0,
        opened_count=0,
        clicked_count=0,
    )
    db.add(run)
    db.flush()
    recipient = CampaignRecipient(
        id=uuid4(),
        run_id=run.id,
        entity_type="egg_donor",
        entity_id=donor.id,
        recipient_email=donor.email,
        recipient_name=donor.full_name,
        status="sent",
    )
    db.add(recipient)
    db.flush()
    return donor, campaign, run


def _donor_form_records(db, org_id: UUID, creator_id: UUID):
    schema = {
        "pages": [
            {
                "fields": [
                    {
                        "key": "photo",
                        "label": "Profile Photo",
                        "type": "file",
                        "required": False,
                    }
                ]
            }
        ]
    }
    form = Form(
        id=uuid4(),
        organization_id=org_id,
        name="Private egg donor form",
        status="published",
        purpose="other",
        lead_kind="egg_donor",
        schema_json=schema,
        published_schema_json=schema,
        allowed_mime_types=["image/png"],
        created_by_user_id=creator_id,
    )
    db.add(form)
    db.flush()
    submission = FormSubmission(
        id=uuid4(),
        organization_id=org_id,
        form_id=form.id,
        lead_kind="egg_donor",
        source_mode="shared",
        match_status="unmatched",
        status="pending_review",
        answers_json={
            "full_name": "Private Form Donor",
            "email": "private-form-donor@example.com",
        },
        schema_snapshot=schema,
        mapping_snapshot=[],
    )
    db.add(submission)
    db.flush()
    file_record = FormSubmissionFile(
        id=uuid4(),
        organization_id=org_id,
        submission_id=submission.id,
        filename="private-photo.png",
        field_key="photo",
        storage_key=f"{org_id}/form-submissions/{submission.id}/private-photo.png",
        content_type="image/png",
        file_size=64,
        checksum_sha256="a" * 64,
        scan_status="clean",
        quarantined=False,
    )
    lead = IntakeLead(
        id=uuid4(),
        organization_id=org_id,
        form_id=form.id,
        form_submission_id=submission.id,
        source="shared_intake",
        lead_type="egg_donor",
        full_name="Private Form Donor",
        email="private-form-donor@example.com",
        status="pending_review",
    )
    db.add_all([file_record, lead])
    db.flush()
    submission.intake_lead_id = lead.id
    db.flush()
    return form, submission, file_record, lead


@pytest.mark.asyncio
async def test_donor_campaign_pii_requires_donor_view_in_addition_to_campaign_permissions(
    db,
    test_org,
    test_user,
):
    donor, campaign, run = _donor_campaign_records(db, test_org.id, test_user.id)
    surrogate_only = _admin_with_revokes(
        db,
        test_org.id,
        "view_donors",
        "edit_donors",
    )
    donor_only = _admin_with_revokes(
        db,
        test_org.id,
        "view_surrogates",
        "edit_surrogates",
    )
    db.commit()

    preview_payload = {
        "recipient_type": "egg_donor",
        "filter_criteria": {"stage_keys": ["new"]},
    }
    runs_path = f"/campaigns/{campaign.id}/runs"
    run_detail_path = f"{runs_path}/{run.id}"
    recipient_path = f"/campaigns/{campaign.id}/runs/{run.id}/recipients"

    async with _client_for(db, test_org.id, surrogate_only) as client:
        preview = await client.post("/campaigns/preview-filters", json=preview_payload)
        detail = await client.get(f"/campaigns/{campaign.id}")
        saved_preview = await client.get(f"/campaigns/{campaign.id}/preview")
        runs = await client.get(runs_path)
        run_detail = await client.get(run_detail_path)
        recipients = await client.get(recipient_path)
    assert preview.status_code == 403, preview.text
    assert detail.status_code == 403, detail.text
    assert saved_preview.status_code == 403, saved_preview.text
    assert runs.status_code == 403, runs.text
    assert run_detail.status_code == 403, run_detail.text
    assert recipients.status_code == 403, recipients.text

    async with _client_for(db, test_org.id, donor_only) as client:
        preview = await client.post("/campaigns/preview-filters", json=preview_payload)
        detail = await client.get(f"/campaigns/{campaign.id}")
        saved_preview = await client.get(f"/campaigns/{campaign.id}/preview")
        runs = await client.get(runs_path)
        run_detail = await client.get(run_detail_path)
        recipients = await client.get(recipient_path)
    assert preview.status_code == 200, preview.text
    assert preview.json()["sample_recipients"] == [
        {
            "entity_type": "egg_donor",
            "entity_id": str(donor.id),
            "email": donor.email,
            "phone_last4": None,
            "name": donor.full_name,
            "stage": "New",
        }
    ]
    assert detail.status_code == 200, detail.text
    assert detail.json()["recipient_type"] == "egg_donor"
    assert saved_preview.status_code == 200, saved_preview.text
    assert saved_preview.json()["sample_recipients"][0]["entity_id"] == str(donor.id)
    assert runs.status_code == 200, runs.text
    assert runs.json()[0]["id"] == str(run.id)
    assert run_detail.status_code == 200, run_detail.text
    assert run_detail.json()["id"] == str(run.id)
    assert recipients.status_code == 200, recipients.text
    assert recipients.json()[0]["recipient_email"] == donor.email
    assert recipients.json()[0]["recipient_name"] == donor.full_name


@pytest.mark.asyncio
async def test_donor_campaign_mutations_require_donor_edit_and_list_filters_revoked_donors(
    db,
    test_org,
    test_user,
):
    _donor, campaign, run = _donor_campaign_records(db, test_org.id, test_user.id)
    case_campaign = Campaign(
        id=uuid4(),
        organization_id=test_org.id,
        name="Visible surrogate campaign",
        channel="email",
        email_template_id=campaign.email_template_id,
        recipient_type="case",
        filter_criteria={},
        status="draft",
        created_by_user_id=test_user.id,
    )
    db.add(case_campaign)
    donor_revoked = _admin_with_revokes(
        db,
        test_org.id,
        "view_donors",
        "edit_donors",
    )
    donor_reader = _admin_with_revokes(db, test_org.id, "edit_donors")
    db.commit()

    async with _client_for(db, test_org.id, donor_revoked) as client:
        listed = await client.get("/campaigns")
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [str(case_campaign.id)]

    create_payload = {
        "name": "Unauthorized donor campaign",
        "channel": "email",
        "email_template_id": str(campaign.email_template_id),
        "recipient_type": "egg_donor",
        "filter_criteria": {},
    }
    async with _client_for(db, test_org.id, donor_reader) as client:
        visible = await client.get("/campaigns")
        created = await client.post("/campaigns", json=create_payload)
        updated = await client.patch(
            f"/campaigns/{campaign.id}",
            json={"name": "Unauthorized rename"},
        )
        retyped = await client.patch(
            f"/campaigns/{case_campaign.id}",
            json={"recipient_type": "sperm_donor"},
        )
        deleted = await client.delete(f"/campaigns/{campaign.id}")
        sent = await client.post(
            f"/campaigns/{campaign.id}/send",
            json={"send_now": True},
        )
        cancelled = await client.post(f"/campaigns/{campaign.id}/cancel")
        retried = await client.post(
            f"/campaigns/{campaign.id}/runs/{run.id}/retry-failed"
        )

    assert {item["id"] for item in visible.json()} == {
        str(campaign.id),
        str(case_campaign.id),
    }
    for response in (created, updated, retyped, deleted, sent, cancelled, retried):
        assert response.status_code == 403, response.text

    db.expire_all()
    persisted = db.get(Campaign, campaign.id)
    assert persisted is not None
    assert persisted.name != "Unauthorized rename"
    assert db.get(Campaign, case_campaign.id).recipient_type == "case"
    assert (
        db.query(Campaign)
        .filter(
            Campaign.organization_id == test_org.id,
            Campaign.name == "Unauthorized donor campaign",
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_hosted_donor_submission_and_lead_pii_require_exact_donor_view(
    db,
    test_org,
    test_user,
):
    form, submission, _file_record, lead = _donor_form_records(
        db,
        test_org.id,
        test_user.id,
    )
    surrogate_only = _admin_with_revokes(
        db,
        test_org.id,
        "view_donors",
        "edit_donors",
    )
    donor_only = _admin_with_revokes(
        db,
        test_org.id,
        "view_surrogates",
        "edit_surrogates",
    )
    db.commit()

    async with _client_for(db, test_org.id, surrogate_only) as client:
        submissions = await client.get(f"/forms/{form.id}/submissions")
        lead_detail = await client.get(f"/forms/intake-leads/{lead.id}")
    assert submissions.status_code == 403, submissions.text
    assert lead_detail.status_code == 403, lead_detail.text

    async with _client_for(db, test_org.id, donor_only) as client:
        submissions = await client.get(f"/forms/{form.id}/submissions")
        lead_detail = await client.get(f"/forms/intake-leads/{lead.id}")
    assert submissions.status_code == 200, submissions.text
    assert submissions.json()[0]["id"] == str(submission.id)
    assert submissions.json()[0]["answers"]["email"] == "private-form-donor@example.com"
    assert lead_detail.status_code == 200, lead_detail.text
    assert lead_detail.json()["email"] == "private-form-donor@example.com"


@pytest.mark.asyncio
async def test_hosted_donor_files_use_exact_donor_read_and_write_permissions(
    db,
    test_org,
    test_user,
):
    _form, submission, file_record, _lead = _donor_form_records(
        db,
        test_org.id,
        test_user.id,
    )
    surrogate_only = _admin_with_revokes(
        db,
        test_org.id,
        "view_donors",
        "edit_donors",
    )
    donor_only = _admin_with_revokes(
        db,
        test_org.id,
        "view_surrogates",
        "edit_surrogates",
    )
    db.commit()

    download_path = f"/forms/submissions/{submission.id}/files/{file_record.id}/download"
    delete_path = f"/forms/submissions/{submission.id}/files/{file_record.id}"
    upload_path = f"/forms/submissions/{submission.id}/files"

    async with _client_for(db, test_org.id, surrogate_only) as client:
        download = await client.get(download_path)
        upload = await client.post(
            upload_path,
            data={"field_key": "photo"},
            files={"file": ("replacement.png", _png_bytes(), "image/png")},
        )
        delete = await client.delete(delete_path)
    assert download.status_code == 403, download.text
    assert upload.status_code == 403, upload.text
    assert delete.status_code == 403, delete.text

    async with _client_for(db, test_org.id, donor_only) as client:
        download = await client.get(download_path)
        upload = await client.post(
            upload_path,
            data={"field_key": "photo"},
            files={"file": ("replacement.png", _png_bytes(), "image/png")},
        )
        delete = await client.delete(delete_path)
    assert download.status_code == 200, download.text
    assert download.json()["filename"] == "private-photo.png"
    assert upload.status_code == 200, upload.text
    assert upload.json()["filename"] == "replacement.png"
    assert delete.status_code == 200, delete.text
    assert delete.json() == {"deleted": True}
