"""An unconverted Meta lead can be converted as a different lead kind."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import JobType
from app.db.models import Donor, Job, MetaLead, Organization
from app.jobs.handlers.meta import process_meta_lead_reprocess_form
from tests.test_meta_donor_form_permissions import (
    _admin_with_revokes,
    _client_for,
    _mapped_form,
    _unconverted_lead,
)


def _reroute_url(form, lead) -> str:
    return f"/integrations/meta/forms/{form.id}/leads/{lead.id}/reroute"


def _reprocess_jobs(db, org_id) -> list[Job]:
    return (
        db.query(Job)
        .filter(
            Job.organization_id == org_id, Job.job_type == JobType.META_LEAD_REPROCESS_FORM.value
        )
        .all()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lead_kind", "donor_type"), [("egg_donor", "egg"), ("sperm_donor", "sperm")]
)
async def test_reroute_surrogate_lead_to_donor_queues_and_converts(
    authed_client, db, test_org, lead_kind, donor_type
):
    form = _mapped_form(db, test_org.id, suffix=f"reroute-{donor_type}", lead_kind="surrogate")
    lead = _unconverted_lead(db, test_org.id, form)
    db.commit()

    response = await authed_client.post(_reroute_url(form, lead), json={"lead_kind": lead_kind})

    assert response.status_code == 200, response.text
    assert response.json()["queued"] is True
    assert response.json()["lead_kind"] == lead_kind
    db.refresh(lead)
    assert lead.lead_kind == lead_kind
    jobs = _reprocess_jobs(db, test_org.id)
    assert [job.payload for job in jobs] == [{"form_id": str(form.id), "lead_ids": [str(lead.id)]}]

    await process_meta_lead_reprocess_form(
        db, SimpleNamespace(organization_id=test_org.id, payload=jobs[0].payload)
    )

    db.refresh(lead)
    donor = db.get(Donor, lead.converted_donor_id)
    assert lead.status == "converted"
    assert donor is not None and donor.donor_type == donor_type


@pytest.mark.asyncio
async def test_reroute_is_listed_on_unconverted_leads(authed_client, db, test_org):
    form = _mapped_form(db, test_org.id, suffix="reroute-list", lead_kind="surrogate")
    _unconverted_lead(db, test_org.id, form)
    db.commit()

    listed = await authed_client.get(f"/integrations/meta/forms/{form.id}/unconverted-leads")

    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["lead_kind"] == "surrogate"


@pytest.mark.asyncio
async def test_reroute_reports_unready_mapping_without_queueing(authed_client, db, test_org):
    form = _mapped_form(db, test_org.id, suffix="reroute-outdated", lead_kind="surrogate")
    form.mapping_status = "outdated"
    lead = _unconverted_lead(db, test_org.id, form)
    db.commit()

    response = await authed_client.post(_reroute_url(form, lead), json={"lead_kind": "egg_donor"})

    assert response.status_code == 200, response.text
    assert response.json()["queued"] is False
    assert response.json()["reprocess_block_reason"] == "mapping_not_ready"
    assert _reprocess_jobs(db, test_org.id) == []


@pytest.mark.asyncio
async def test_reroute_rejects_converted_lead(authed_client, db, test_org):
    form = _mapped_form(db, test_org.id, suffix="reroute-converted", lead_kind="surrogate")
    lead = _unconverted_lead(db, test_org.id, form)
    lead.is_converted = True
    db.commit()

    response = await authed_client.post(_reroute_url(form, lead), json={"lead_kind": "egg_donor"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Converted leads cannot be rerouted"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current_kind", "target_kind"),
    [("surrogate", "egg_donor"), ("sperm_donor", "surrogate")],
)
async def test_reroute_touching_a_donor_kind_requires_donor_edit(
    db, test_org, current_kind, target_kind
):
    form = _mapped_form(
        db, test_org.id, suffix=f"reroute-denied-{current_kind}", lead_kind="surrogate"
    )
    lead = _unconverted_lead(db, test_org.id, form, lead_kind=current_kind)
    user = _admin_with_revokes(db, test_org.id, "edit_donors")
    db.commit()

    async with _client_for(db, test_org.id, user) as client:
        response = await client.post(_reroute_url(form, lead), json={"lead_kind": target_kind})

    assert response.status_code == 403
    db.refresh(lead)
    assert lead.lead_kind == current_kind


@pytest.mark.asyncio
async def test_reroute_hides_other_org_and_other_form_leads(authed_client, db, test_org):
    other_org = Organization(id=uuid4(), name="Other Org", slug=f"other-{uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    foreign_form = _mapped_form(db, other_org.id, suffix="reroute-foreign", lead_kind="surrogate")
    foreign_lead = _unconverted_lead(db, other_org.id, foreign_form)
    own_form = _mapped_form(db, test_org.id, suffix="reroute-own", lead_kind="surrogate")
    other_form = _mapped_form(db, test_org.id, suffix="reroute-other", lead_kind="surrogate")
    other_form_lead = _unconverted_lead(db, test_org.id, other_form)
    db.commit()

    foreign = await authed_client.post(
        _reroute_url(foreign_form, foreign_lead), json={"lead_kind": "egg_donor"}
    )
    mismatched = await authed_client.post(
        _reroute_url(own_form, other_form_lead), json={"lead_kind": "egg_donor"}
    )

    assert foreign.status_code == 404
    assert mismatched.status_code == 404
    assert db.get(MetaLead, foreign_lead.id).lead_kind == "surrogate"
    assert db.get(MetaLead, other_form_lead.id).lead_kind == "surrogate"
