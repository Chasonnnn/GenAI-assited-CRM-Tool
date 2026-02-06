import uuid

import pytest

from app.db.models import IntendedParent
from app.services import email_service


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
    ip.status = "ready_to_match"
    db.commit()

    variables = email_service.build_intended_parent_template_variables(db, ip)
    assert variables["status_label"] == "Ready to Match"
    assert "_" not in variables["status_label"]
