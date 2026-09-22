"""Donor assignment requires its own action without granting ordinary editing."""

import pytest

from app.core.csrf import CSRF_HEADER
from app.db.models import Membership, RolePermission
from tests.test_record_scopes_v2 import _record
from tests.test_record_scopes_v2 import context as context


@pytest.mark.asyncio
async def test_v2_assignment_without_edit_cannot_change_profile(
    db, context, authed_client, test_auth
):
    member = (
        db.query(Membership)
        .filter_by(organization_id=context.org.id, user_id=test_auth.user.id)
        .one()
    )
    member.role = "operations"
    record = _record(db, context.intake, "donor")
    db.add(
        RolePermission(
            organization_id=context.org.id,
            role="operations",
            permission="assign_donors",
            is_granted=True,
        )
    )
    db.flush()
    assert (await authed_client.get("/donors/owner-options")).status_code == 200
    for payload in (
        {"full_name": "Changed"},
        {"owner_id": str(context.manager.user_id), "full_name": "Changed"},
        {},
    ):
        response = await authed_client.patch(f"/donors/{record.id}", json=payload)
        assert response.status_code == 403
    csrf = authed_client.headers.pop(CSRF_HEADER)
    payload = {"owner_type": "user", "owner_id": str(context.manager.user_id)}
    assert (await authed_client.patch(f"/donors/{record.id}", json=payload)).status_code == 403
    authed_client.headers[CSRF_HEADER] = csrf
    response = await authed_client.patch(f"/donors/{record.id}", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["owner_id"] == str(context.manager.user_id)
    assert record.full_name != "Changed"
