import uuid

from app.core.encryption import hash_email
from app.db.models import Attachment, Organization, Pipeline, PipelineStage, Surrogate
from app.services import workflow_triggers
from app.utils.normalization import normalize_email


def test_trigger_document_uploaded_skips_cross_org_attachment(db, test_org, monkeypatch):
    org2 = Organization(
        id=uuid.uuid4(),
        name="Org 2",
        slug=f"org2-{uuid.uuid4().hex[:8]}",
    )
    db.add(org2)
    db.flush()

    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=org2.id,
        name="Org 2 Pipeline",
        is_default=True,
        current_version=1,
    )
    db.add(pipeline)
    db.flush()

    stage = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=pipeline.id,
        slug="new_unread",
        label="New Unread",
        color="#3B82F6",
        stage_type="intake",
        order=1,
        is_active=True,
        is_intake_stage=True,
    )
    db.add(stage)
    db.flush()

    email = f"org2-{uuid.uuid4().hex[:8]}@example.com"
    surrogate = Surrogate(
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        organization_id=org2.id,
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=uuid.uuid4(),
        full_name="Org 2 Surrogate",
        email=normalize_email(email),
        email_hash=hash_email(email),
    )
    db.add(surrogate)
    db.flush()

    attachment = Attachment(
        organization_id=test_org.id,
        surrogate_id=surrogate.id,
        filename="doc.pdf",
        storage_key="attachments/doc.pdf",
        content_type="application/pdf",
        file_size=123,
        checksum_sha256="0" * 64,
        scan_status="clean",
        quarantined=False,
    )
    db.add(attachment)
    db.flush()

    captured: dict[str, object] = {}

    def fake_trigger(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(workflow_triggers.engine, "trigger", fake_trigger)

    workflow_triggers.trigger_document_uploaded(db, attachment)

    assert captured == {}
