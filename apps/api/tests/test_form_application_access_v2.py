"""Application metadata uses record access instead of form-builder authority."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.config import settings
from app.db.enums import Role
from app.db.models import (
    Form,
    FormIntakeLink,
    Organization,
    OrganizationPermissionPolicy,
    RolePermission,
    User,
    UserPermissionOverride,
)
from app.services import email_service
from tests.test_email_templates_personal_scope import authed_client_for_user
from tests.test_record_scopes_v2 import _member, _record
from tests.test_record_scopes_v2 import context as context


def _form(db, org_id, **values):
    row = Form(
        organization_id=org_id,
        name=f"Application {uuid4().hex[:8]}",
        status=values.pop("status", "published"),
        lead_kind=values.pop("lead_kind", "surrogate"),
        **values,
    )
    db.add(row)
    db.flush()
    return row


def _link(db, form, **values):
    row = FormIntakeLink(
        organization_id=values.pop("organization_id", form.organization_id),
        form_id=form.id,
        slug=uuid4().hex,
        **values,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def application(db, context, monkeypatch):
    monkeypatch.setattr(settings, "FORMS_SHARED_INTAKE", True)
    record = _record(db, context.intake, "surrogate")
    form = _form(db, context.org.id)
    context.org.default_surrogate_application_form_id = form.id
    link = _link(db, form)
    db.flush()
    return SimpleNamespace(record=record, form=form, link=link)


def _path(application):
    return f"/forms/surrogates/{application.record.id}/application-forms"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["intake_specialist", "operations"])
async def test_application_picker_includes_published_forms_without_submissions(
    db, context, application, role
):
    _form(db, context.org.id, status="draft")
    _form(db, context.org.id, status="archived")
    _form(db, context.org.id, lead_kind="egg_donor")
    other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
    db.add(other)
    db.flush()
    _form(db, other.id)
    if role == "operations":
        actor, _ = _member(db, context.org.id, role)
    else:
        actor = context.intake
    async with authed_client_for_user(
        db, context.org.id, db.get(User, actor.user_id), Role(role)
    ) as client:
        assert (await client.get("/forms")).status_code == 403
        response = await client.get(_path(application))
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()] == [str(application.form.id)]
        assert response.json()[0]["is_default_surrogate_application"] is True
        assert "form_schema" not in response.json()[0]
        if role == "operations":
            links = await client.get(f"{_path(application)}/{application.form.id}/intake-links")
            assert links.status_code == 403


@pytest.mark.asyncio
async def test_application_links_expose_only_available_same_org_links_without_creating(
    db, context, application
):
    _link(db, application.form, is_active=False)
    _link(db, application.form, expires_at=datetime.now(UTC) - timedelta(days=1))
    _link(db, application.form, max_submissions=1, submissions_count=1)
    other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
    db.add(other)
    db.flush()
    _link(db, application.form, organization_id=other.id)
    before = db.query(FormIntakeLink).count()
    user = db.get(User, context.intake.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.INTAKE_SPECIALIST) as client:
        path = f"{_path(application)}/{application.form.id}/intake-links"
        response = await client.get(path)
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()] == [str(application.link.id)]
        assert response.json()[0]["intake_url"].endswith(f"/intake/{application.link.slug}")
        application.link.is_active = False
        db.flush()
        assert (await client.get(path)).json() == []
    assert db.query(FormIntakeLink).count() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["picker", "links"])
@pytest.mark.parametrize(
    "denial", ["scope", "other_org", "view_form_submissions", "view_surrogates"]
)
async def test_application_metadata_requires_view_action_and_record_scope(
    db, context, application, endpoint, denial
):
    record_id = application.record.id
    if denial == "scope":
        application.record.owner_id = context.manager.user_id
    elif denial == "other_org":
        other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
        db.add(other)
        db.flush()
        owner, _ = _member(db, other.id, "admin")
        record_id = _record(db, owner, "surrogate").id
    else:
        db.add(
            RolePermission(
                organization_id=context.org.id,
                role="intake_specialist",
                permission=denial,
                is_granted=False,
            )
        )
    db.flush()
    path = f"/forms/surrogates/{record_id}/application-forms"
    if endpoint == "links":
        path += f"/{application.form.id}/intake-links"
    async with authed_client_for_user(
        db, context.org.id, db.get(User, context.intake.user_id), Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.get(path)
    assert response.status_code == (404 if denial == "other_org" else 403), response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", ["edit_surrogates", "send_email"])
async def test_application_links_require_record_edit_and_email_send(
    db, context, application, permission
):
    db.add(
        RolePermission(
            organization_id=context.org.id,
            role="intake_specialist",
            permission=permission,
            is_granted=False,
        )
    )
    db.flush()
    async with authed_client_for_user(
        db, context.org.id, db.get(User, context.intake.user_id), Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.get(f"{_path(application)}/{application.form.id}/intake-links")
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["other_org", "donor", "draft"])
async def test_application_links_reject_incompatible_form(db, context, application, kind):
    org_id = context.org.id
    if kind == "other_org":
        other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
        db.add(other)
        db.flush()
        org_id = other.id
    form = _form(
        db,
        org_id,
        lead_kind="egg_donor" if kind == "donor" else "surrogate",
        status="draft" if kind == "draft" else "published",
    )
    _link(db, form)
    async with authed_client_for_user(
        db, context.org.id, db.get(User, context.intake.user_id), Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.get(f"{_path(application)}/{form.id}/intake-links")
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_form_intake_send_denies_missing_email_permission_before_template_or_provider_lookup(
    db, context, application, monkeypatch
):
    db.add(
        RolePermission(
            organization_id=context.org.id,
            role="intake_specialist",
            permission="send_email",
            is_granted=False,
        )
    )
    db.flush()
    template_lookup = Mock(side_effect=AssertionError("must authorize before template lookup"))
    monkeypatch.setattr(email_service, "get_template", template_lookup)
    async with authed_client_for_user(
        db, context.org.id, db.get(User, context.intake.user_id), Role.INTAKE_SPECIALIST
    ) as client:
        response = await client.post(
            f"/forms/{application.form.id}/intake-links/{application.link.id}/send",
            json={
                "surrogate_id": str(application.record.id),
                "template_id": str(uuid4()),
                "idempotency_key": f"application/{uuid4()}",
            },
        )
        assert response.status_code == 403, response.text
        template_lookup.assert_not_called()

        db.add(
            UserPermissionOverride(
                organization_id=context.org.id,
                user_id=context.intake.user_id,
                permission="send_email",
                override_type="grant",
            )
        )
        db.flush()
        template = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(email_service, "get_template", Mock(return_value=template))
        queued_email = SimpleNamespace(id=uuid4(), created_at=datetime.now(UTC))
        send = Mock(return_value=(queued_email, None))
        monkeypatch.setattr(email_service, "send_from_template", send)
        allowed = await client.post(
            f"/forms/{application.form.id}/intake-links/{application.link.id}/send",
            json={
                "surrogate_id": str(application.record.id),
                "template_id": str(template.id),
                "idempotency_key": f"application/{uuid4()}",
            },
        )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["email_log_id"] == str(queued_email.id)
    send.assert_called_once()
    assert send.call_args.kwargs["org_id"] == context.org.id
    assert send.call_args.kwargs["surrogate_id"] == application.record.id


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["picker", "links"])
async def test_application_metadata_requires_activated_policy(db, context, application, endpoint):
    db.query(OrganizationPermissionPolicy).filter_by(organization_id=context.org.id).delete()
    db.flush()
    path = _path(application)
    if endpoint == "links":
        path += f"/{application.form.id}/intake-links"
    async with authed_client_for_user(
        db, context.org.id, db.get(User, context.admin.user_id), Role.ADMIN
    ) as client:
        response = await client.get(path)
    assert response.status_code == 404, response.text
