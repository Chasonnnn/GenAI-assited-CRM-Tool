from uuid import uuid4

import pytest

from app.db.enums import Role
from app.db.models import Membership, Organization, User
from app.services import appointment_service


def _create_user_in_org(db, org: Organization, display_name: str, email_prefix: str) -> User:
    user = User(
        id=uuid4(),
        email=f"{email_prefix}-{uuid4().hex[:8]}@example.com",
        display_name=display_name,
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid4(),
        user_id=user.id,
        organization_id=org.id,
        role=Role.DEVELOPER,
    )
    db.add(membership)
    db.flush()
    return user


def test_get_or_create_booking_link_uses_readable_slug(db, test_org, test_user):
    link = appointment_service.get_or_create_booking_link(
        db=db,
        user_id=test_user.id,
        org_id=test_org.id,
    )

    assert link.public_slug == "test-user"


def test_get_or_create_booking_link_adds_suffix_for_same_org_collision(db, test_org):
    first_user = _create_user_in_org(db, test_org, "Jordan Lee", "jordan-a")
    second_user = _create_user_in_org(db, test_org, "Jordan Lee", "jordan-b")

    first_link = appointment_service.get_or_create_booking_link(
        db=db,
        user_id=first_user.id,
        org_id=test_org.id,
    )
    second_link = appointment_service.get_or_create_booking_link(
        db=db,
        user_id=second_user.id,
        org_id=test_org.id,
    )

    assert first_link.public_slug == "jordan-lee"
    assert second_link.public_slug == "jordan-lee-2"


def test_get_or_create_booking_link_allows_same_slug_in_different_orgs(db, test_org):
    other_org = Organization(
        id=uuid4(),
        name="Other Org",
        slug=f"other-org-{uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()

    first_user = _create_user_in_org(db, test_org, "Taylor Brooks", "taylor-a")
    second_user = _create_user_in_org(db, other_org, "Taylor Brooks", "taylor-b")

    first_link = appointment_service.get_or_create_booking_link(
        db=db,
        user_id=first_user.id,
        org_id=test_org.id,
    )
    second_link = appointment_service.get_or_create_booking_link(
        db=db,
        user_id=second_user.id,
        org_id=other_org.id,
    )

    assert first_link.public_slug == "taylor-brooks"
    assert second_link.public_slug == "taylor-brooks"


@pytest.mark.asyncio
async def test_public_booking_page_resolves_slug_by_origin_org(client, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)

    alpha_org = Organization(
        id=uuid4(),
        name="Alpha Org",
        slug="alpha-org",
        ai_enabled=True,
    )
    beta_org = Organization(
        id=uuid4(),
        name="Beta Org",
        slug="beta-org",
        ai_enabled=True,
    )
    db.add(alpha_org)
    db.add(beta_org)
    db.flush()

    alpha_user = _create_user_in_org(db, alpha_org, "Jordan Lee", "alpha-jordan")
    beta_user = _create_user_in_org(db, beta_org, "Jordan Lee", "beta-jordan")

    appointment_service.get_or_create_booking_link(
        db=db,
        user_id=alpha_user.id,
        org_id=alpha_org.id,
    )
    appointment_service.get_or_create_booking_link(
        db=db,
        user_id=beta_user.id,
        org_id=beta_org.id,
    )

    alpha_response = await client.get(
        "/book/jordan-lee",
        headers={
            "host": "api.surrogacyforce.com",
            "origin": "https://alpha-org.surrogacyforce.com",
        },
    )
    assert alpha_response.status_code == 200
    assert alpha_response.json()["org_name"] == "Alpha Org"

    beta_response = await client.get(
        "/book/jordan-lee",
        headers={
            "host": "api.surrogacyforce.com",
            "origin": "https://beta-org.surrogacyforce.com",
        },
    )
    assert beta_response.status_code == 200
    assert beta_response.json()["org_name"] == "Beta Org"
