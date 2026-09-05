"""Shared email context for existing surrogate, IP, and donor send paths."""

from uuid import uuid4

import pytest

from app.db.models import Membership, Organization, Queue, User
from app.schemas.donor import DonorCreate
from app.schemas.surrogate import SurrogateCreate
from app.services import donor_service, email_service, ip_service, surrogate_service


@pytest.fixture(params=["surrogate", "intended_parent", "donor"])
def record_context(request, db, test_org, test_user):
    fields = {
        "full_name": "Synthetic Contact",
        "email": f"context-{uuid4()}@example.com",
        "owner_type": "user",
        "owner_id": test_user.id,
    }
    if request.param == "surrogate":
        record = surrogate_service.create_surrogate(
            db, test_org.id, test_user.id, SurrogateCreate(**fields)
        )
        builder = email_service.build_surrogate_template_variables
    elif request.param == "intended_parent":
        record = ip_service.create_intended_parent(db, test_org.id, test_user.id, **fields)
        builder = email_service.build_intended_parent_template_variables
    else:
        record = donor_service.create_donor(
            db, test_org.id, test_user.id, DonorCreate(donor_type="egg", **fields)
        )
        builder = email_service.build_donor_template_variables
    return record, builder


@pytest.mark.parametrize(
    "owner_state",
    [
        "active_user",
        "foreign_user",
        "inactive_membership",
        "inactive_user",
        "local_queue",
        "foreign_queue",
    ],
)
def test_record_email_context_scopes_owner_identity(
    db, test_org, test_user, record_context, owner_state
):
    record, builder = record_context
    expected_owner = test_user.display_name
    if owner_state in {"foreign_user", "foreign_queue"}:
        other_org = Organization(name="Synthetic Other Org", slug=f"context-{uuid4()}")
        db.add(other_org)
        db.flush()
        expected_owner = ""
        if owner_state == "foreign_user":
            other_user = User(
                email=f"foreign-{uuid4()}@example.com",
                display_name="Foreign Owner",
                token_version=1,
            )
            db.add(other_user)
            db.flush()
            db.add(
                Membership(
                    organization_id=other_org.id,
                    user_id=other_user.id,
                    role="admin",
                    is_active=True,
                )
            )
            record.owner_id = other_user.id
        else:
            queue = Queue(organization_id=other_org.id, name="Foreign Queue")
            db.add(queue)
            db.flush()
            record.owner_type = "queue"
            record.owner_id = queue.id
    elif owner_state == "inactive_membership":
        membership = (
            db.query(Membership)
            .filter(
                Membership.organization_id == test_org.id,
                Membership.user_id == test_user.id,
            )
            .one()
        )
        membership.is_active = False
        expected_owner = ""
    elif owner_state == "inactive_user":
        test_user.is_active = False
        expected_owner = ""
    elif owner_state == "local_queue":
        queue = Queue(organization_id=test_org.id, name="Local Queue")
        db.add(queue)
        db.flush()
        record.owner_type = "queue"
        record.owner_id = queue.id
        expected_owner = queue.name
    db.commit()

    variables = builder(db, record)

    assert variables["owner_name"] == expected_owner
    assert variables["first_name"] == "Synthetic"
    assert variables["full_name"] == record.full_name
    assert variables["email"] == record.email
    assert variables["org_name"] == test_org.name
    assert variables["unsubscribe_url"].startswith(
        f"https://{test_org.slug}.surrogacyforce.com/email/unsubscribe/"
    )
