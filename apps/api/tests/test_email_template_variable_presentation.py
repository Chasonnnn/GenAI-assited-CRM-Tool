import uuid

import pytest

from app.db.models import IntendedParent
from app.services import email_service, pipeline_service


def _move_to_stage(db, ip: IntendedParent, stage) -> None:
    ip.stage_id = stage.id
    ip.stage = stage
    ip.status = stage.stage_key
    db.commit()


@pytest.mark.asyncio
async def test_intended_parent_template_variables_humanize_status_label(
    authed_client, db, test_org
):
    payload = {
        "full_name": "Casey Monroe",
        "email": f"casey.{uuid.uuid4().hex[:6]}@mail.net",
        "phone": "5559876543",
    }
    create_res = await authed_client.post("/intended-parents", json=payload)
    assert create_res.status_code == 201, create_res.text
    ip_id = create_res.json()["id"]

    ip = db.query(IntendedParent).filter(IntendedParent.id == ip_id).one()
    ready = pipeline_service.get_stage_by_key(db, ip.stage.pipeline_id, "ready_to_match")
    _move_to_stage(db, ip, ready)

    variables = email_service.build_intended_parent_template_variables(db, ip)
    assert variables["status_label"] == "Ready to Match"
    assert "_" not in variables["status_label"]


@pytest.mark.asyncio
async def test_intended_parent_template_status_label_uses_the_stage_label(
    authed_client, db, test_org, test_user
):
    create_res = await authed_client.post(
        "/intended-parents",
        json={"full_name": "Jordan Lee", "email": f"jordan.{uuid.uuid4().hex[:6]}@mail.net"},
    )
    assert create_res.status_code == 201, create_res.text
    ip = db.get(IntendedParent, uuid.UUID(create_res.json()["id"]))
    stage = pipeline_service.create_stage(
        db,
        ip.stage.pipeline_id,
        slug="awaiting_docs",
        label="Awaiting Signed Documents",
        color="#475569",
        stage_type="intake",
        user_id=test_user.id,
    )
    _move_to_stage(db, ip, stage)

    variables = email_service.build_intended_parent_template_variables(db, ip)
    assert variables["status_label"] == "Awaiting Signed Documents"
