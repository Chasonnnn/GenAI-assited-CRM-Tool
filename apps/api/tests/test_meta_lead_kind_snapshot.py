from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.db.models import Donor, MetaForm, MetaFormVersion, Surrogate
from app.services import meta_lead_service

BASE_MAPPINGS = [
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


def _form(
    db,
    org_id,
    *,
    suffix: str,
    lead_kind: str = "surrogate",
    mapped: bool = True,
) -> MetaForm:
    form = MetaForm(
        id=uuid4(),
        organization_id=org_id,
        page_id=f"page-{suffix}",
        form_external_id=f"form-{suffix}",
        form_name=f"Form {suffix}",
        lead_kind=lead_kind,
        mapping_status="mapped" if mapped else "unmapped",
        mapping_rules=BASE_MAPPINGS if mapped else None,
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
    if mapped:
        form.mapping_version_id = version.id
    db.commit()
    return form


def _store_lead(db, org_id, form: MetaForm, *, suffix: str):
    lead, error = meta_lead_service.store_meta_lead(
        db,
        org_id,
        f"lead-{suffix}",
        {
            "full_name": f"Applicant {suffix}",
            "email": f"{suffix}@example.com",
        },
        field_data_raw={
            "full_name": f"Applicant {suffix}",
            "email": f"{suffix}@example.com",
        },
        meta_form_id=form.form_external_id,
        meta_page_id=form.page_id,
    )
    assert error is None
    assert lead is not None
    return lead


@pytest.mark.asyncio
async def test_meta_lead_kind_snapshot_prevents_historical_reprocess_rerouting(
    db,
    test_org,
    test_user,
):
    from app.jobs.handlers.meta import process_meta_lead_reprocess_form
    from app.services import meta_form_mapping_service

    form = _form(db, test_org.id, suffix="historical-surrogate")
    historical = _store_lead(
        db,
        test_org.id,
        form,
        suffix="historical-surrogate",
    )
    historical.status = "convert_failed"
    db.commit()
    assert historical.lead_kind == "surrogate"

    meta_form_mapping_service.save_mapping(
        db,
        form,
        column_mappings=BASE_MAPPINGS,
        unknown_column_behavior="metadata",
        lead_kind="egg_donor",
        user_id=test_user.id,
    )
    replayed = _store_lead(
        db,
        test_org.id,
        form,
        suffix="historical-surrogate",
    )
    assert replayed.id == historical.id
    assert replayed.lead_kind == "surrogate"

    await process_meta_lead_reprocess_form(
        db,
        SimpleNamespace(
            organization_id=test_org.id,
            payload={
                "form_id": str(form.id),
                "lead_ids": [str(historical.id)],
            },
        ),
    )
    db.refresh(historical)

    assert historical.status == "converted"
    assert isinstance(db.get(Surrogate, historical.converted_surrogate_id), Surrogate)
    assert historical.converted_donor_id is None

    current = _store_lead(db, test_org.id, form, suffix="current-egg")
    assert current.lead_kind == "egg_donor"
    status, subject = meta_lead_service.process_stored_meta_lead(db, current)
    assert status == "converted"
    assert isinstance(subject, Donor)
    assert subject.donor_type == "egg"


def test_unmapped_meta_lead_snapshots_first_approved_kind(db, test_org, test_user):
    from app.services import meta_form_mapping_service

    form = _form(
        db,
        test_org.id,
        suffix="unmapped-donor",
        mapped=False,
    )
    lead = _store_lead(db, test_org.id, form, suffix="unmapped-donor")
    assert lead.lead_kind is None

    meta_form_mapping_service.save_mapping(
        db,
        form,
        column_mappings=BASE_MAPPINGS,
        unknown_column_behavior="metadata",
        lead_kind="sperm_donor",
        user_id=test_user.id,
    )
    status, subject = meta_lead_service.process_stored_meta_lead(db, lead)

    assert status == "converted"
    assert lead.lead_kind == "sperm_donor"
    assert isinstance(subject, Donor)
    assert subject.donor_type == "sperm"


@pytest.mark.asyncio
async def test_donor_meta_mapping_rejects_surrogate_only_target_fields(
    authed_client: AsyncClient,
    db,
    test_org,
):
    form = _form(
        db,
        test_org.id,
        suffix="invalid-donor-field",
        lead_kind="egg_donor",
    )
    original_rules = list(form.mapping_rules)
    response = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json={
            "lead_kind": "egg_donor",
            "unknown_column_behavior": "metadata",
            "column_mappings": [
                *BASE_MAPPINGS,
                {
                    "csv_column": "date_of_birth",
                    "surrogate_field": "date_of_birth",
                    "transformation": "date_flexible",
                    "action": "map",
                    "custom_field_key": None,
                },
            ],
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == (
        "Unsupported donor mapping field(s): date_of_birth"
    )
    db.refresh(form)
    assert form.mapping_rules == original_rules
    assert form.lead_kind == "egg_donor"
