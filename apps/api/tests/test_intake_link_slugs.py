from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.enums import Role
from app.db.models import Membership, Organization, User
from app.services import form_intake_service, form_service


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


def _create_published_form(db, org_id, user_id, name: str):
    form = form_service.create_form(
        db=db,
        org_id=org_id,
        user_id=user_id,
        name=name,
        description="Candidate application",
        schema={"pages": [{"title": "Basics", "fields": []}]},
        max_file_size_bytes=None,
        max_file_count=None,
        allowed_mime_types=None,
    )
    return form_service.publish_form(db, form, user_id)


def test_create_intake_link_uses_event_name_slug(db, test_org, test_user):
    form = _create_published_form(db, test_org.id, test_user.id, "Shared Intake Form")

    link = form_intake_service.create_intake_link(
        db=db,
        org_id=test_org.id,
        form=form,
        user_id=test_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )

    assert link.slug == "austin-expo"


def test_create_intake_link_falls_back_to_campaign_name(db, test_org, test_user):
    form = _create_published_form(db, test_org.id, test_user.id, "Shared Intake Form")

    link = form_intake_service.create_intake_link(
        db=db,
        org_id=test_org.id,
        form=form,
        user_id=test_user.id,
        campaign_name="Spring Event",
        event_name=None,
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )

    assert link.slug == "spring-event"


def test_ensure_default_intake_link_falls_back_to_form_name(db, test_org, test_user):
    form = _create_published_form(db, test_org.id, test_user.id, "PR334 QA Form 20260315 211811")

    link = form_intake_service.ensure_default_intake_link(
        db=db,
        org_id=test_org.id,
        form=form,
        user_id=test_user.id,
    )

    assert link.slug == "pr334-qa-form-20260315-211811"


def test_create_intake_link_adds_suffix_for_same_org_collision(db, test_org, test_user):
    form = _create_published_form(db, test_org.id, test_user.id, "Shared Intake Form")

    first_link = form_intake_service.create_intake_link(
        db=db,
        org_id=test_org.id,
        form=form,
        user_id=test_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )
    second_link = form_intake_service.create_intake_link(
        db=db,
        org_id=test_org.id,
        form=form,
        user_id=test_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )

    assert first_link.slug == "austin-expo"
    assert second_link.slug == "austin-expo-2"


def test_rotate_intake_link_generates_next_readable_slug(db, test_org, test_user):
    form = _create_published_form(db, test_org.id, test_user.id, "Shared Intake Form")

    link = form_intake_service.create_intake_link(
        db=db,
        org_id=test_org.id,
        form=form,
        user_id=test_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )

    rotated = form_intake_service.rotate_intake_link(db=db, link=link)

    assert rotated.slug == "austin-expo-2"


def test_create_intake_link_allows_same_slug_in_different_orgs(db, test_org):
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
    first_form = _create_published_form(db, test_org.id, first_user.id, "Shared Intake Form")
    second_form = _create_published_form(db, other_org.id, second_user.id, "Shared Intake Form")

    first_link = form_intake_service.create_intake_link(
        db=db,
        org_id=test_org.id,
        form=first_form,
        user_id=first_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )
    second_link = form_intake_service.create_intake_link(
        db=db,
        org_id=other_org.id,
        form=second_form,
        user_id=second_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )

    assert first_link.slug == "austin-expo"
    assert second_link.slug == "austin-expo"


@pytest.mark.asyncio
async def test_public_intake_page_resolves_slug_by_origin_org(client, db, monkeypatch):
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
    alpha_form = _create_published_form(db, alpha_org.id, alpha_user.id, "Alpha Intake Form")
    beta_form = _create_published_form(db, beta_org.id, beta_user.id, "Beta Intake Form")

    form_intake_service.create_intake_link(
        db=db,
        org_id=alpha_org.id,
        form=alpha_form,
        user_id=alpha_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )
    form_intake_service.create_intake_link(
        db=db,
        org_id=beta_org.id,
        form=beta_form,
        user_id=beta_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )

    alpha_response = await client.get(
        "/forms/public/intake/austin-expo",
        headers={
            "host": "api.surrogacyforce.com",
            "origin": "https://alpha-org.surrogacyforce.com",
        },
    )
    assert alpha_response.status_code == 200
    assert alpha_response.json()["name"] == "Alpha Intake Form"

    beta_response = await client.get(
        "/forms/public/intake/austin-expo",
        headers={
            "host": "api.surrogacyforce.com",
            "origin": "https://beta-org.surrogacyforce.com",
        },
    )
    assert beta_response.status_code == 200
    assert beta_response.json()["name"] == "Beta Intake Form"


@pytest.mark.asyncio
async def test_public_intake_page_returns_404_for_ambiguous_slug_without_org_context(client, db):
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
    alpha_form = _create_published_form(db, alpha_org.id, alpha_user.id, "Alpha Intake Form")
    beta_form = _create_published_form(db, beta_org.id, beta_user.id, "Beta Intake Form")

    form_intake_service.create_intake_link(
        db=db,
        org_id=alpha_org.id,
        form=alpha_form,
        user_id=alpha_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )
    form_intake_service.create_intake_link(
        db=db,
        org_id=beta_org.id,
        form=beta_form,
        user_id=beta_user.id,
        campaign_name="Spring Event",
        event_name="Austin Expo",
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
    )

    response = await client.get(
        "/forms/public/intake/austin-expo",
        headers={"host": "api.surrogacyforce.com"},
    )

    assert response.status_code == 404
