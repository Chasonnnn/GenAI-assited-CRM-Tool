from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import (
    AutomationWorkflow,
    EmailLog,
    Form,
    FormFieldMapping,
    FormIntakeLink,
    Job,
    Membership,
    PlatformFormTemplate,
    PlatformFormTemplateHiddenOrg,
    User,
    UserPermissionOverride,
)
from app.main import app
from app.services import session_service

DONOR_SCHEMA = {
    "pages": [
        {
            "title": "Donor",
            "fields": [
                {
                    "key": "applicant_name",
                    "label": "Full Name",
                    "type": "text",
                    "required": True,
                },
                {
                    "key": "email_address",
                    "label": "Email",
                    "type": "email",
                    "required": True,
                },
                {
                    "key": "headshot",
                    "label": "Profile Photo",
                    "type": "file",
                    "required": True,
                },
            ],
        }
    ]
}

DONOR_MAPPINGS = [
    {"field_key": "applicant_name", "surrogate_field": "full_name"},
    {"field_key": "email_address", "surrogate_field": "email"},
    {"field_key": "headshot", "surrogate_field": "profile_photo"},
]


def _admin_with_revokes(db, org_id: UUID, *permissions: str) -> User:
    user = User(
        id=uuid4(),
        email=f"hosted-donor-scope-{uuid4().hex[:8]}@test.com",
        display_name="Hosted Donor Scope Tester",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid4(),
            user_id=user.id,
            organization_id=org_id,
            role=Role.ADMIN.value,
        )
    )
    db.add_all(
        [
            UserPermissionOverride(
                id=uuid4(),
                organization_id=org_id,
                user_id=user.id,
                permission=permission,
                override_type="revoke",
            )
            for permission in permissions
        ]
    )
    db.flush()
    return user


@asynccontextmanager
async def _client_for(db, org_id: UUID, user: User):
    token = create_session_token(
        user_id=user.id,
        org_id=org_id,
        role=Role.ADMIN.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=org_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client
    app.dependency_overrides.clear()


def _form_record(
    db,
    *,
    org_id: UUID,
    user_id: UUID,
    lead_kind: str,
    name: str,
    status: str = "draft",
) -> Form:
    form = Form(
        id=uuid4(),
        organization_id=org_id,
        name=name,
        status=status,
        purpose="other" if lead_kind != "surrogate" else "surrogate_application",
        lead_kind=lead_kind,
        schema_json=DONOR_SCHEMA,
        published_schema_json=DONOR_SCHEMA if status == "published" else None,
        allowed_mime_types=["image/png", "image/jpeg"],
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(form)
    db.flush()
    return form


def _published_donor_template(db) -> PlatformFormTemplate:
    now = datetime.now(UTC)
    template = PlatformFormTemplate(
        id=uuid4(),
        name="Donor application",
        description="Donor application",
        schema_json=DONOR_SCHEMA,
        settings_json={
            "purpose": "other",
            "lead_kind": "egg_donor",
            "allowed_mime_types": ["image/png", "image/jpeg"],
            "mappings": DONOR_MAPPINGS,
        },
        published_name="Donor application",
        published_description="Donor application",
        published_schema_json=DONOR_SCHEMA,
        published_settings_json={
            "purpose": "other",
            "lead_kind": "egg_donor",
            "allowed_mime_types": ["image/png", "image/jpeg"],
            "mappings": DONOR_MAPPINGS,
        },
        status="published",
        current_version=1,
        published_version=1,
        is_published_globally=True,
        published_at=now,
    )
    db.add(template)
    db.flush()
    return template


@pytest.mark.asyncio
async def test_donor_form_create_and_both_reclassification_directions_require_edit_donors(
    db,
    test_org,
):
    user = _admin_with_revokes(db, test_org.id, "edit_donors")
    donor_form = _form_record(
        db,
        org_id=test_org.id,
        user_id=user.id,
        lead_kind="egg_donor",
        name="Protected donor form",
    )
    surrogate_form = _form_record(
        db,
        org_id=test_org.id,
        user_id=user.id,
        lead_kind="surrogate",
        name="Surrogate form",
    )
    db.commit()
    form_count = db.query(Form).filter(Form.organization_id == test_org.id).count()

    async with _client_for(db, test_org.id, user) as client:
        create = await client.post(
            "/forms",
            json={
                "name": "Blocked donor create",
                "purpose": "other",
                "lead_kind": "sperm_donor",
                "form_schema": DONOR_SCHEMA,
            },
        )
        donor_to_surrogate = await client.patch(
            f"/forms/{donor_form.id}",
            json={"lead_kind": "surrogate"},
        )
        surrogate_to_donor = await client.patch(
            f"/forms/{surrogate_form.id}",
            json={"lead_kind": "egg_donor"},
        )

    assert create.status_code == 403
    assert donor_to_surrogate.status_code == 403
    assert surrogate_to_donor.status_code == 403
    db.expire_all()
    assert db.query(Form).filter(Form.organization_id == test_org.id).count() == form_count
    assert db.get(Form, donor_form.id).lead_kind == "egg_donor"
    assert db.get(Form, surrogate_form.id).lead_kind == "surrogate"


@pytest.mark.asyncio
async def test_donor_form_configuration_mutations_require_edit_without_side_effects(
    db,
    test_org,
):
    user = _admin_with_revokes(db, test_org.id, "view_donors", "edit_donors")
    draft = _form_record(
        db,
        org_id=test_org.id,
        user_id=user.id,
        lead_kind="egg_donor",
        name="Protected draft",
    )
    published = _form_record(
        db,
        org_id=test_org.id,
        user_id=user.id,
        lead_kind="sperm_donor",
        name="Protected published",
        status="published",
    )
    published_without_link = _form_record(
        db,
        org_id=test_org.id,
        user_id=user.id,
        lead_kind="egg_donor",
        name="Protected implicit link",
        status="published",
    )
    mapping = FormFieldMapping(
        id=uuid4(),
        form_id=draft.id,
        field_key="applicant_name",
        surrogate_field="full_name",
    )
    link = FormIntakeLink(
        id=uuid4(),
        organization_id=test_org.id,
        form_id=published.id,
        slug=f"protected-{uuid4().hex[:12]}",
        campaign_name="Original campaign",
        created_by_user_id=user.id,
    )
    db.add_all([mapping, link])
    db.commit()

    baseline = {
        "links": db.query(FormIntakeLink)
        .filter(FormIntakeLink.organization_id == test_org.id)
        .count(),
        "workflows": db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.organization_id == test_org.id)
        .count(),
        "emails": db.query(EmailLog).filter(EmailLog.organization_id == test_org.id).count(),
        "jobs": db.query(Job).filter(Job.organization_id == test_org.id).count(),
    }
    original_slug = link.slug

    async with _client_for(db, test_org.id, user) as client:
        reads = [
            await client.get(f"/forms/{published.id}"),
            await client.get(f"/forms/{published.id}/mappings"),
            await client.get(f"/forms/{published.id}/intake-links"),
        ]
        responses = [
            await client.patch(f"/forms/{draft.id}", json={"name": "Mutated"}),
            await client.delete(f"/forms/{draft.id}"),
            await client.post(f"/forms/{draft.id}/set-default-surrogate-application"),
            await client.patch(
                f"/forms/{draft.id}/delivery-settings",
                json={"default_application_email_template_id": None},
            ),
            await client.post(f"/forms/{draft.id}/publish"),
            await client.put(
                f"/forms/{draft.id}/mappings",
                json={"mappings": [{"field_key": "email_address", "surrogate_field": "email"}]},
            ),
            await client.post(f"/forms/{published.id}/intake-links", json={}),
            await client.patch(
                f"/forms/intake-links/{link.id}",
                json={"campaign_name": "Mutated campaign"},
            ),
            await client.post(f"/forms/intake-links/{link.id}/rotate"),
            await client.post(
                f"/forms/{published.id}/intake-links/{link.id}/send",
                json={"surrogate_id": str(uuid4()), "idempotency_key": uuid4().hex},
            ),
            await client.get(f"/forms/{published_without_link.id}/intake-links"),
        ]

    assert [response.status_code for response in reads] == [200, 200, 200]
    assert all(response.status_code == 403 for response in responses), [
        (response.status_code, response.text) for response in responses
    ]
    db.expire_all()
    assert db.get(Form, draft.id).name == "Protected draft"
    assert db.get(Form, draft.id).status == "draft"
    assert db.get(FormFieldMapping, mapping.id).surrogate_field == "full_name"
    protected_link = db.get(FormIntakeLink, link.id)
    assert protected_link.slug == original_slug
    assert protected_link.campaign_name == "Original campaign"
    assert (
        db.query(FormIntakeLink).filter(FormIntakeLink.organization_id == test_org.id).count()
        == baseline["links"]
    )
    assert (
        db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.organization_id == test_org.id)
        .count()
        == baseline["workflows"]
    )
    assert (
        db.query(EmailLog).filter(EmailLog.organization_id == test_org.id).count()
        == baseline["emails"]
    )
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == baseline["jobs"]


@pytest.mark.asyncio
async def test_donor_form_template_mutations_require_edit_donors_without_side_effects(
    db,
    test_org,
):
    user = _admin_with_revokes(db, test_org.id, "edit_donors")
    template = _published_donor_template(db)
    db.commit()
    form_count = db.query(Form).filter(Form.organization_id == test_org.id).count()

    async with _client_for(db, test_org.id, user) as client:
        instantiate = await client.post(
            f"/forms/templates/{template.id}/use",
            json={"name": "Blocked template form"},
        )
        remove = await client.delete(f"/forms/templates/{template.id}")

    assert instantiate.status_code == 403
    assert remove.status_code == 403
    assert db.query(Form).filter(Form.organization_id == test_org.id).count() == form_count
    assert (
        db.query(PlatformFormTemplateHiddenOrg)
        .filter(
            PlatformFormTemplateHiddenOrg.organization_id == test_org.id,
            PlatformFormTemplateHiddenOrg.template_id == template.id,
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_admin_with_edit_donors_can_manage_hosted_donor_form_lifecycle(
    db,
    test_org,
):
    user = _admin_with_revokes(db, test_org.id, "view_surrogates", "edit_surrogates")
    template = _published_donor_template(db)
    db.commit()

    async with _client_for(db, test_org.id, user) as client:
        instantiated = await client.post(
            f"/forms/templates/{template.id}/use",
            json={"name": "Authorized template donor form"},
        )
        assert instantiated.status_code == 200, instantiated.text
        removed_template = await client.delete(f"/forms/templates/{template.id}")
        assert removed_template.status_code == 204, removed_template.text

        created = await client.post(
            "/forms",
            json={
                "name": "Authorized donor form",
                "purpose": "other",
                "lead_kind": "egg_donor",
                "form_schema": DONOR_SCHEMA,
                "allowed_mime_types": ["image/png", "image/jpeg"],
            },
        )
        assert created.status_code == 200, created.text
        form_id = created.json()["id"]

        updated = await client.patch(
            f"/forms/{form_id}",
            json={"name": "Authorized donor application"},
        )
        assert updated.status_code == 200, updated.text
        mapped = await client.put(
            f"/forms/{form_id}/mappings",
            json={"mappings": DONOR_MAPPINGS},
        )
        assert mapped.status_code == 200, mapped.text
        delivery = await client.patch(
            f"/forms/{form_id}/delivery-settings",
            json={"default_application_email_template_id": None},
        )
        assert delivery.status_code == 200, delivery.text
        published = await client.post(f"/forms/{form_id}/publish")
        assert published.status_code == 200, published.text

        links = await client.get(f"/forms/{form_id}/intake-links")
        assert links.status_code == 200, links.text
        assert links.json()
        default_link_id = links.json()[0]["id"]

        updated_link = await client.patch(
            f"/forms/intake-links/{default_link_id}",
            json={"campaign_name": "Donor recruitment"},
        )
        assert updated_link.status_code == 200, updated_link.text
        rotated = await client.post(f"/forms/intake-links/{default_link_id}/rotate")
        assert rotated.status_code == 200, rotated.text
        assert rotated.json()["slug"] != updated_link.json()["slug"]

        extra_link = await client.post(
            f"/forms/{form_id}/intake-links",
            json={"campaign_name": "Second donor source"},
        )
        assert extra_link.status_code == 200, extra_link.text

        disposable = await client.post(
            "/forms",
            json={
                "name": "Disposable donor form",
                "purpose": "other",
                "lead_kind": "sperm_donor",
            },
        )
        assert disposable.status_code == 200, disposable.text
        deleted = await client.delete(f"/forms/{disposable.json()['id']}")
        assert deleted.status_code == 200, deleted.text

        surrogate = await client.post("/forms", json={"name": "Reclassify me"})
        assert surrogate.status_code == 200, surrogate.text
        reclassified = await client.patch(
            f"/forms/{surrogate.json()['id']}",
            json={"lead_kind": "egg_donor", "purpose": "other"},
        )
        assert reclassified.status_code == 200, reclassified.text
        assert reclassified.json()["lead_kind"] == "egg_donor"

    workflow = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == test_org.id,
            AutomationWorkflow.system_key == f"shared_intake_routing:{form_id}",
        )
        .one()
    )
    assert workflow.actions == [{"action_type": "create_intake_lead", "requires_approval": True}]
