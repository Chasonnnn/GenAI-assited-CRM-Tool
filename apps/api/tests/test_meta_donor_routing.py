"""Public-interface coverage for Meta lead-kind routing."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient

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
    {
        "csv_column": "phone_number",
        "surrogate_field": "phone",
        "transformation": "phone_normalize",
        "action": "map",
        "custom_field_key": None,
    },
    {
        "csv_column": "education",
        "surrogate_field": "education",
        "transformation": None,
        "action": "map",
        "custom_field_key": None,
    },
]


def _mapped_form(db, org_id, *, external_id: str, lead_kind: str | None = None):
    from app.db.models import MetaForm, MetaFormVersion

    values = {
        "organization_id": org_id,
        "page_id": f"page-{external_id}",
        "form_external_id": external_id,
        "form_name": f"Form {external_id}",
        "mapping_status": "mapped",
    }
    if lead_kind is not None:
        values["lead_kind"] = lead_kind
    form = MetaForm(**values)
    db.add(form)
    db.flush()
    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=[
            {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
            {"key": "email", "type": "EMAIL", "label": "Email"},
            {"key": "phone_number", "type": "PHONE", "label": "Phone"},
            {"key": "education", "type": "TEXT", "label": "Education"},
        ],
        schema_hash=f"hash-{external_id}",
    )
    db.add(version)
    db.flush()
    form.current_version_id = version.id
    form.mapping_version_id = version.id
    form.mapping_rules = MAPPINGS
    db.commit()
    return form


def _lead(db, org_id, *, external_id: str, form_external_id: str, email: str):
    from app.db.models import MetaLead

    lead = MetaLead(
        organization_id=org_id,
        meta_lead_id=external_id,
        meta_form_id=form_external_id,
        meta_page_id=f"page-{form_external_id}",
        field_data={"full_name": "Meta Applicant", "email": email},
        field_data_raw={
            "full_name": "Meta Applicant",
            "email": email,
            "phone_number": "+1 (607) 555-0198",
            "education": "Bachelor's degree",
        },
        meta_created_time=datetime.now(UTC),
    )
    db.add(lead)
    db.commit()
    return lead


@pytest.mark.asyncio
async def test_meta_mapping_api_exposes_and_updates_exact_lead_kind_values(
    authed_client: AsyncClient, db, test_org
):
    form = _mapped_form(db, test_org.id, external_id="mapping-kind")

    preview = await authed_client.get(f"/integrations/meta/forms/{form.id}/mapping")
    assert preview.status_code == 200
    assert preview.json()["form"]["lead_kind"] == "surrogate"

    payload = {
        "lead_kind": "egg_donor",
        "column_mappings": MAPPINGS[:2],
        "unknown_column_behavior": "metadata",
    }
    updated = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json=payload,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["lead_kind"] == "egg_donor"
    db.refresh(form)
    assert form.lead_kind == "egg_donor"

    legacy_client_update = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json={
            "column_mappings": MAPPINGS[:2],
            "unknown_column_behavior": "metadata",
        },
    )
    assert legacy_client_update.status_code == 200
    db.refresh(form)
    assert form.lead_kind == "egg_donor"

    donor_preview = await authed_client.get(f"/integrations/meta/forms/{form.id}/mapping")
    assert donor_preview.status_code == 200
    assert "education" in donor_preview.json()["available_fields"]
    assert "journey_timing_preference" not in donor_preview.json()["available_fields"]
    listed = await authed_client.get("/integrations/meta/forms")
    assert listed.status_code == 200
    listed_form = next(item for item in listed.json() if item["id"] == str(form.id))
    assert listed_form["lead_kind"] == "egg_donor"

    invalid = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json={**payload, "lead_kind": "donor"},
    )
    assert invalid.status_code == 422


@pytest.mark.parametrize(
    ("lead_kind", "donor_type"),
    [("egg_donor", "egg"), ("sperm_donor", "sperm")],
)
def test_process_stored_meta_lead_routes_each_donor_subtype_to_its_entry_stage(
    db, test_org, lead_kind, donor_type
):
    from app.db.models import Donor, Pipeline, PipelineStage
    from app.services import meta_lead_service

    external_id = f"{donor_type}-routing"
    _mapped_form(
        db,
        test_org.id,
        external_id=external_id,
        lead_kind=lead_kind,
    )
    lead = _lead(
        db,
        test_org.id,
        external_id=f"lead-{external_id}",
        form_external_id=external_id,
        email=f"{external_id}@example.com",
    )

    status, subject = meta_lead_service.process_stored_meta_lead(db, lead)

    assert status == "converted"
    assert isinstance(subject, Donor)
    assert subject.donor_type == donor_type
    assert subject.education == "Bachelor's degree"
    assert subject.source == "Meta"
    assert subject.stage.system_role == "intake_entry"
    pipeline = db.get(Pipeline, db.get(PipelineStage, subject.stage_id).pipeline_id)
    assert pipeline is not None
    assert pipeline.organization_id == test_org.id
    assert pipeline.entity_type == lead_kind
    db.refresh(lead)
    assert lead.converted_donor_id == subject.id
    assert lead.converted_surrogate_id is None


def test_process_stored_meta_lead_keeps_default_surrogate_routing(db, test_org):
    from app.db.models import Surrogate
    from app.services import meta_lead_service

    form = _mapped_form(db, test_org.id, external_id="default-surrogate")
    assert form.lead_kind == "surrogate"
    lead = _lead(
        db,
        test_org.id,
        external_id="lead-default-surrogate",
        form_external_id=form.form_external_id,
        email="default-surrogate@example.com",
    )

    status, subject = meta_lead_service.process_stored_meta_lead(db, lead)

    assert status == "converted"
    assert isinstance(subject, Surrogate)
    db.refresh(lead)
    assert lead.converted_surrogate_id == subject.id
    assert lead.converted_donor_id is None


def test_meta_donor_conversion_is_idempotent_on_replay(db, test_org):
    from app.db.models import Donor
    from app.services import meta_lead_service

    form = _mapped_form(
        db,
        test_org.id,
        external_id="idempotent-donor",
        lead_kind="egg_donor",
    )
    lead = _lead(
        db,
        test_org.id,
        external_id="lead-idempotent-donor",
        form_external_id=form.form_external_id,
        email="idempotent-donor@example.com",
    )

    first_status, first = meta_lead_service.process_stored_meta_lead(db, lead)
    second_status, second = meta_lead_service.process_stored_meta_lead(db, lead)

    assert first_status == second_status == "converted"
    assert first is not None and second is not None
    assert first.id == second.id
    assert db.query(Donor).filter(Donor.organization_id == test_org.id).count() == 1


def test_meta_donor_conversion_rolls_back_donor_and_link_together(
    db, test_org, monkeypatch
):
    from app.db.models import Donor, MetaLead
    from app.services import donor_service, meta_lead_service, workflow_triggers

    form = _mapped_form(
        db,
        test_org.id,
        external_id="atomic-donor",
        lead_kind="egg_donor",
    )
    lead = _lead(
        db,
        test_org.id,
        external_id="lead-atomic-donor",
        form_external_id=form.form_external_id,
        email="atomic-donor@example.com",
    )
    triggered: list[object] = []
    monkeypatch.setattr(
        workflow_triggers,
        "trigger_donor_created",
        lambda _db, donor: triggered.append(donor.id),
    )

    create_calls: list[dict] = []
    original_create_donor = donor_service.create_donor
    savepoint = db.begin_nested()

    with monkeypatch.context() as failure_patch:
        def record_create(*args, **kwargs):
            create_calls.append(kwargs)
            return original_create_donor(*args, **kwargs)

        def rollback_savepoint():
            if savepoint.is_active:
                savepoint.rollback()

        failure_patch.setattr(donor_service, "create_donor", record_create)
        failure_patch.setattr(
            db,
            "commit",
            lambda: (_ for _ in ()).throw(RuntimeError("injected transaction failure")),
        )
        failure_patch.setattr(db, "rollback", rollback_savepoint)
        failure_patch.setattr(
            meta_lead_service,
            "_mark_conversion_failed",
            lambda failure_db, *_args, **_kwargs: failure_db.rollback(),
        )
        failure_patch.setattr(
            meta_lead_service,
            "_ensure_review_task_for_mapping_conversion_failure",
            lambda *_args, **_kwargs: None,
        )
        donor, error = meta_lead_service.convert_to_donor_with_mapping(
            db,
            lead,
            form.mapping_rules,
            donor_type="egg",
        )

    assert donor is None
    assert error == "Conversion failed: RuntimeError"
    assert create_calls[0]["commit"] is False
    assert create_calls[0]["emit_workflow_events"] is False
    assert db.query(Donor).filter(Donor.organization_id == test_org.id).count() == 0
    failed_lead = db.get(MetaLead, lead.id)
    assert failed_lead is not None
    assert failed_lead.is_converted is False
    assert failed_lead.converted_donor_id is None
    assert triggered == []

    donor, error = meta_lead_service.convert_to_donor_with_mapping(
        db,
        failed_lead,
        form.mapping_rules,
        donor_type="egg",
    )

    assert error is None
    assert donor is not None
    db.refresh(failed_lead)
    assert failed_lead.converted_donor_id == donor.id
    assert db.query(Donor).filter(Donor.organization_id == test_org.id).count() == 1
    assert triggered == [donor.id]


def test_unmapped_donor_form_waits_without_creating_a_donor(db, test_org):
    from app.db.models import Donor
    from app.services import meta_lead_service

    form = _mapped_form(
        db,
        test_org.id,
        external_id="unmapped-donor",
        lead_kind="egg_donor",
    )
    form.mapping_status = "unmapped"
    form.mapping_version_id = None
    db.commit()
    lead = _lead(
        db,
        test_org.id,
        external_id="lead-unmapped-donor",
        form_external_id=form.form_external_id,
        email="unmapped-donor@example.com",
    )

    status, subject = meta_lead_service.process_stored_meta_lead(db, lead)

    assert status == "awaiting_mapping"
    assert subject is None
    assert db.query(Donor).filter(Donor.organization_id == test_org.id).count() == 0


@pytest.mark.asyncio
async def test_reprocess_job_uses_configured_donor_routing(db, test_org):
    from app.db.models import Donor
    from app.jobs.handlers.meta import process_meta_lead_reprocess_form

    form = _mapped_form(
        db,
        test_org.id,
        external_id="reprocess-sperm-donor",
        lead_kind="sperm_donor",
    )
    lead = _lead(
        db,
        test_org.id,
        external_id="lead-reprocess-sperm-donor",
        form_external_id=form.form_external_id,
        email="reprocess-sperm-donor@example.com",
    )
    lead.status = "convert_failed"
    lead.conversion_error = "old mapping error"
    db.commit()

    await process_meta_lead_reprocess_form(
        db,
        SimpleNamespace(
            organization_id=test_org.id,
            payload={"form_id": str(form.id), "lead_ids": [str(lead.id)]},
        ),
    )

    db.refresh(lead)
    donor = db.get(Donor, lead.converted_donor_id)
    assert lead.status == "converted"
    assert donor is not None
    assert donor.donor_type == "sperm"


@pytest.mark.asyncio
async def test_zapier_meta_webhook_returns_donor_contract_for_donor_form(
    client: AsyncClient, db, test_org
):
    from app.db.models import Donor
    from app.services import zapier_settings_service

    form = _mapped_form(
        db,
        test_org.id,
        external_id="zapier-egg-donor",
        lead_kind="egg_donor",
    )
    settings = zapier_settings_service.get_or_create_settings(db, test_org.id)
    secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)

    response = await client.post(
        f"/webhooks/zapier/{settings.webhook_id}",
        json={
            "lead_id": "zapier-egg-donor-lead",
            "form_id": form.form_external_id,
            "field_data": [
                {"name": "full_name", "values": ["Zapier Egg Donor"]},
                {"name": "email", "values": ["zapier-egg-donor@example.com"]},
                {"name": "education", "values": ["Master's degree"]},
            ],
        },
        headers={"X-Webhook-Token": secret},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "converted"
    assert body["surrogate_id"] is None
    assert body["donor_id"] is not None
    assert "converted into a donor" in body["message"]
    donor = db.get(Donor, body["donor_id"])
    assert donor is not None
    assert donor.donor_type == "egg"


def test_meta_donor_duplicate_email_fails_without_creating_another_donor(
    db, test_org, test_user
):
    from app.db.models import Donor
    from app.schemas.donor import DonorCreate
    from app.services import donor_service, meta_lead_service

    existing = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="sperm",
            full_name="Existing Donor",
            email="same-donor@example.com",
        ),
    )
    form = _mapped_form(
        db,
        test_org.id,
        external_id="duplicate-donor",
        lead_kind="egg_donor",
    )
    lead = _lead(
        db,
        test_org.id,
        external_id="lead-duplicate-donor",
        form_external_id=form.form_external_id,
        email="SAME-DONOR@example.com",
    )

    status, subject = meta_lead_service.process_stored_meta_lead(db, lead)

    assert status == "convert_failed"
    assert subject is None
    assert db.query(Donor).filter(Donor.organization_id == test_org.id).count() == 1
    assert db.get(Donor, existing.id) is not None
    db.refresh(lead)
    assert lead.converted_donor_id is None


def test_meta_form_lookup_fails_closed_across_organizations(db, test_org):
    from app.db.models import Donor, Organization
    from app.services import meta_lead_service

    other_org = Organization(
        id=uuid4(),
        name="Other Meta Organization",
        slug=f"other-meta-{uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    _mapped_form(
        db,
        other_org.id,
        external_id="shared-external-id",
        lead_kind="egg_donor",
    )
    lead = _lead(
        db,
        test_org.id,
        external_id="local-lead-with-foreign-form",
        form_external_id="shared-external-id",
        email="foreign-form@example.com",
    )

    status, subject = meta_lead_service.process_stored_meta_lead(db, lead)

    assert status == "awaiting_mapping"
    assert subject is None
    assert db.query(Donor).filter(Donor.organization_id == test_org.id).count() == 0


@pytest.mark.asyncio
async def test_meta_mapping_api_hides_cross_org_form(
    authed_client: AsyncClient, db, test_org
):
    from app.db.models import Organization

    other_org = Organization(
        id=uuid4(),
        name="Foreign Form Organization",
        slug=f"foreign-form-{uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    form = _mapped_form(
        db,
        other_org.id,
        external_id="foreign-form-api",
        lead_kind="sperm_donor",
    )

    response = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json={
            "lead_kind": "egg_donor",
            "column_mappings": MAPPINGS[:2],
            "unknown_column_behavior": "metadata",
        },
    )

    assert response.status_code == 404
