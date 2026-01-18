from io import BytesIO
import uuid

from app.core.config import settings
from app.core.encryption import hash_email
from app.db.enums import JobType
from app.db.models import Job, Surrogate
from app.services import attachment_service
from app.utils.normalization import normalize_email


def test_upload_attachment_enqueues_scan_job(
    db, test_org, test_user, default_stage, monkeypatch
):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", True, raising=False)
    monkeypatch.setattr(attachment_service, "store_file", lambda *_args, **_kwargs: None)

    normalized_email = normalize_email("scan@test.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Scan Test",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()

    payload = b"%PDF-1.4"
    attachment = attachment_service.upload_attachment(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="scan.pdf",
        content_type="application/pdf",
        file=BytesIO(payload),
        file_size=len(payload),
        surrogate_id=surrogate.id,
    )

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.ATTACHMENT_SCAN.value,
        )
        .first()
    )
    assert job is not None
    assert job.payload.get("attachment_id") == str(attachment.id)
