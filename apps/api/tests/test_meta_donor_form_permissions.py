from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import JobType, Role
from app.db.models import (
    Job,
    Membership,
    MetaForm,
    MetaFormVersion,
    MetaLead,
    User,
    UserPermissionOverride,
)
from app.main import app
from app.services import session_service

MAPPINGS = [
    {
        "csv_column": "full_name",
        "surrogate_field": "full_name",
        "transformation": None,
        "action": "map",
        "custom_field_key": None,
    },
    {
        "csv_column": "email",
        "surrogate_field": "email",
        "transformation": None,
        "action": "map",
        "custom_field_key": None,
    },
]


def _admin_with_revokes(db, org_id: UUID, *permissions: str) -> User:
    user = User(
        id=uuid4(),
        email=f"meta-donor-scope-{uuid4().hex[:8]}@test.com",
        display_name="Meta Donor Scope Tester",
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


def _mapped_form(db, org_id: UUID, *, suffix: str, lead_kind: str) -> MetaForm:
    form = MetaForm(
        id=uuid4(),
        organization_id=org_id,
        page_id=f"page-{suffix}",
        form_external_id=f"form-{suffix}",
        form_name=f"{lead_kind} form {suffix}",
        lead_kind=lead_kind,
        mapping_status="mapped",
        mapping_rules=MAPPINGS,
    )
    db.add(form)
    db.flush()
    version = MetaFormVersion(
        id=uuid4(),
        form_id=form.id,
        version_number=1,
        field_schema=[
            {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
            {"key": "email", "type": "EMAIL", "label": "Email"},
        ],
        schema_hash=f"hash-{suffix}",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id
    form.mapping_version_id = version.id
    db.flush()
    return form


def _unconverted_lead(
    db,
    org_id: UUID,
    form: MetaForm,
    *,
    lead_kind: str | None = None,
) -> MetaLead:
    lead = MetaLead(
        id=uuid4(),
        organization_id=org_id,
        meta_lead_id=f"lead-{form.form_external_id}",
        meta_form_id=form.form_external_id,
        meta_page_id=form.page_id,
        lead_kind=lead_kind or form.lead_kind,
        field_data={"full_name": "Private Donor", "email": "private@example.com"},
        field_data_raw={
            "full_name": "Private Donor",
            "email": "private@example.com",
            "phone_number": "+1 607 555 0101",
        },
        status="convert_failed",
        conversion_error="Review required",
    )
    db.add(lead)
    db.flush()
    return lead


@pytest.mark.asyncio
async def test_meta_donor_form_reads_require_view_and_list_filters_donor_forms(
    db,
    test_org,
):
    donor_form = _mapped_form(
        db,
        test_org.id,
        suffix="private-egg",
        lead_kind="egg_donor",
    )
    surrogate_form = _mapped_form(
        db,
        test_org.id,
        suffix="visible-surrogate",
        lead_kind="surrogate",
    )
    mixed_history_form = _mapped_form(
        db,
        test_org.id,
        suffix="historical-donor-now-surrogate",
        lead_kind="surrogate",
    )
    donor_lead = _unconverted_lead(db, test_org.id, donor_form)
    _unconverted_lead(
        db,
        test_org.id,
        mixed_history_form,
        lead_kind="egg_donor",
    )
    no_donor_access = _admin_with_revokes(
        db,
        test_org.id,
        "view_donors",
        "edit_donors",
    )
    donor_reader = _admin_with_revokes(db, test_org.id, "edit_donors")
    db.commit()

    async with _client_for(db, test_org.id, no_donor_access) as client:
        listed = await client.get("/integrations/meta/forms")
        donor_preview = await client.get(
            f"/integrations/meta/forms/{donor_form.id}/mapping"
        )
        donor_leads = await client.get(
            f"/integrations/meta/forms/{donor_form.id}/unconverted-leads"
        )
        surrogate_preview = await client.get(
            f"/integrations/meta/forms/{surrogate_form.id}/mapping"
        )
        mixed_history_preview = await client.get(
            f"/integrations/meta/forms/{mixed_history_form.id}/mapping"
        )

    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [str(surrogate_form.id)]
    assert donor_preview.status_code == 403, donor_preview.text
    assert donor_leads.status_code == 403, donor_leads.text
    assert surrogate_preview.status_code == 200, surrogate_preview.text
    assert mixed_history_preview.status_code == 403, mixed_history_preview.text

    async with _client_for(db, test_org.id, donor_reader) as client:
        listed = await client.get("/integrations/meta/forms")
        donor_preview = await client.get(
            f"/integrations/meta/forms/{donor_form.id}/mapping"
        )
        donor_leads = await client.get(
            f"/integrations/meta/forms/{donor_form.id}/unconverted-leads"
        )

    assert {item["id"] for item in listed.json()} == {
        str(donor_form.id),
        str(surrogate_form.id),
        str(mixed_history_form.id),
    }
    assert donor_preview.status_code == 200, donor_preview.text
    assert donor_leads.status_code == 200, donor_leads.text
    assert donor_leads.json()["items"][0]["id"] == str(donor_lead.id)
    assert donor_leads.json()["items"][0]["email"] == "private@example.com"


@pytest.mark.asyncio
async def test_meta_donor_form_mutations_require_edit_for_current_and_target_kind(
    db,
    test_org,
    monkeypatch,
):
    donor_form = _mapped_form(
        db,
        test_org.id,
        suffix="mutate-egg",
        lead_kind="egg_donor",
    )
    surrogate_form = _mapped_form(
        db,
        test_org.id,
        suffix="mutate-surrogate",
        lead_kind="surrogate",
    )
    mixed_history_form = _mapped_form(
        db,
        test_org.id,
        suffix="mutate-historical-donor",
        lead_kind="surrogate",
    )
    _unconverted_lead(db, test_org.id, donor_form)
    _unconverted_lead(
        db,
        test_org.id,
        mixed_history_form,
        lead_kind="sperm_donor",
    )
    donor_reader = _admin_with_revokes(db, test_org.id, "edit_donors")
    db.commit()

    sync_calls: list[tuple[UUID, str | None]] = []

    async def fake_sync_forms(_db, org_id, page_id):
        sync_calls.append((org_id, page_id))
        return {"forms_synced": 0, "error": None}

    from app.routers import meta_forms as meta_forms_router

    monkeypatch.setattr(meta_forms_router.meta_sync_service, "sync_forms", fake_sync_forms)
    jobs_before = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_LEAD_REPROCESS_FORM.value,
        )
        .count()
    )

    async with _client_for(db, test_org.id, donor_reader) as client:
        donor_reclassified = await client.put(
            f"/integrations/meta/forms/{donor_form.id}/mapping",
            json={"lead_kind": "surrogate", "column_mappings": MAPPINGS},
        )
        surrogate_reclassified = await client.put(
            f"/integrations/meta/forms/{surrogate_form.id}/mapping",
            json={"lead_kind": "sperm_donor", "column_mappings": MAPPINGS},
        )
        mixed_history_updated = await client.put(
            f"/integrations/meta/forms/{mixed_history_form.id}/mapping",
            json={"lead_kind": "surrogate", "column_mappings": MAPPINGS},
        )
        reconverted = await client.post(
            f"/integrations/meta/forms/{donor_form.id}/reconvert",
            json={},
        )
        synced = await client.post(
            "/integrations/meta/forms/sync",
            json={"page_id": mixed_history_form.page_id},
        )
        deleted = await client.delete(f"/integrations/meta/forms/{donor_form.id}")

    for response in (
        donor_reclassified,
        surrogate_reclassified,
        mixed_history_updated,
        reconverted,
        synced,
        deleted,
    ):
        assert response.status_code == 403, response.text

    db.expire_all()
    assert db.get(MetaForm, donor_form.id).lead_kind == "egg_donor"
    assert db.get(MetaForm, surrogate_form.id).lead_kind == "surrogate"
    assert sync_calls == []
    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_LEAD_REPROCESS_FORM.value,
        )
        .count()
        == jobs_before
    )
