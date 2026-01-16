from datetime import datetime, timezone
import uuid

import pytest

from app.core.encryption import hash_email
from app.db.enums import Role
from app.db.models import Organization, Pipeline, PipelineStage, StatusChangeRequest, Surrogate
from app.services import status_change_request_service
from app.utils.normalization import normalize_email


def _seed_org2_request(db):
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

    request = StatusChangeRequest(
        organization_id=org2.id,
        entity_type="surrogate",
        entity_id=surrogate.id,
        target_stage_id=stage.id,
        effective_at=datetime.now(timezone.utc),
        reason="Regression request",
        status="pending",
    )
    db.add(request)
    db.flush()

    return org2, surrogate, request


def test_status_change_request_get_scoped_to_org(db, test_auth):
    _, _, request = _seed_org2_request(db)

    result = status_change_request_service.get_request(
        db=db,
        request_id=request.id,
        org_id=test_auth.org.id,
    )

    assert result is None


def test_status_change_request_details_scoped_to_org(db, test_auth):
    _, _, request = _seed_org2_request(db)

    details = status_change_request_service.get_request_with_details(
        db=db,
        request_id=request.id,
        org_id=test_auth.org.id,
    )

    assert details is None


def test_status_change_request_approve_scoped_to_org(db, test_auth):
    _, _, request = _seed_org2_request(db)

    with pytest.raises(ValueError, match="Request not found"):
        status_change_request_service.approve_request(
            db=db,
            request_id=request.id,
            admin_user_id=test_auth.user.id,
            admin_role=Role.DEVELOPER,
            org_id=test_auth.org.id,
        )
