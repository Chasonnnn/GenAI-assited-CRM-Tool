from __future__ import annotations

import uuid
from uuid import UUID

import pytest

from app.db.enums import Role
from app.db.models import Surrogate
from app.services import pipeline_service, surrogate_status_service


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


@pytest.mark.asyncio
async def test_shared_stage_change_to_matched_requires_accepted_match(authed_client, db, test_auth):
    # Bulk change stage, mass edit and the single status route all call change_status.
    # The bulk route turns this ValueError into a per-row failure; the test runs the
    # service directly because the bulk route's per-row rollback also ends the test transaction.
    matched_stage = _get_stage(db, test_auth.org.id, "matched")
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Matched Guard Test",
            "email": f"matched-guard-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    surrogate = db.query(Surrogate).filter(Surrogate.id == UUID(response.json()["id"])).one()
    original_stage_id = surrogate.stage_id

    with pytest.raises(ValueError, match="Cannot set to Matched without an accepted Match."):
        surrogate_status_service.change_status(
            db=db,
            surrogate=surrogate,
            new_stage_id=matched_stage.id,
            user_id=test_auth.user.id,
            user_role=Role.ADMIN,
        )

    db.refresh(surrogate)
    assert surrogate.stage_id == original_stage_id
