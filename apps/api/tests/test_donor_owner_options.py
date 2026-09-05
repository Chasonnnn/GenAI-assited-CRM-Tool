import uuid

import pytest

from app.db.enums import Role
from app.db.models import Membership, Organization, Queue, User, UserPermissionOverride


async def test_donor_editor_can_list_only_active_current_org_owners(
    authed_client,
    db,
    test_org,
    test_user,
):
    membership = (
        db.query(Membership)
        .filter_by(
            organization_id=test_org.id,
            user_id=test_user.id,
        )
        .one()
    )
    membership.role = Role.INTAKE_SPECIALIST
    other_org = Organization(name="Other", slug=f"owners-{uuid.uuid4()}")
    db.add(other_org)
    db.flush()
    for label, org_id, member_active, user_active in (
        ("Foreign", other_org.id, True, True),
        ("Inactive membership", test_org.id, False, True),
        ("Disabled user", test_org.id, True, False),
    ):
        user = User(email=f"{uuid.uuid4()}@example.com", display_name=label, is_active=user_active)
        db.add(user)
        db.flush()
        db.add(
            Membership(
                organization_id=org_id,
                user_id=user.id,
                role=Role.ADMIN,
                is_active=member_active,
            )
        )
    queue = Queue(organization_id=test_org.id, name="Active queue", is_active=True)
    db.add_all(
        [
            queue,
            Queue(organization_id=test_org.id, name="Inactive queue", is_active=False),
            Queue(organization_id=other_org.id, name="Foreign queue", is_active=True),
        ]
    )
    db.flush()

    response = await authed_client.get("/donors/owner-options")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "users": [{"id": str(test_user.id), "display_name": test_user.display_name}],
        "queues": [{"id": str(queue.id), "name": "Active queue"}],
    }


@pytest.mark.parametrize("permission", ["view_donors", "edit_donors"])
async def test_donor_owner_options_require_donor_permissions(
    authed_client,
    db,
    test_org,
    test_user,
    permission,
):
    membership = (
        db.query(Membership)
        .filter_by(
            organization_id=test_org.id,
            user_id=test_user.id,
        )
        .one()
    )
    membership.role = Role.ADMIN
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=test_user.id,
            permission=permission,
            override_type="revoke",
        )
    )
    db.flush()
    response = await authed_client.get("/donors/owner-options")
    assert response.status_code == 403


async def test_donor_owner_options_require_authentication(client):
    response = await client.get("/donors/owner-options")
    assert response.status_code == 401
