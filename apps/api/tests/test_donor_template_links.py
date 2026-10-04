"""Donor templates resolve form and booking links like surrogate templates."""

import uuid

import pytest

from app.core.config import settings
from app.core.security import decode_booking_record_token
from app.db.models import BookingLink, Organization
from app.schemas.donor import DonorCreate
from app.services import (
    campaign_content,
    donor_service,
    form_intake_service,
    org_service,
    workflow_communication_actions,
)
from tests.test_hosted_donor_forms import _create_donor_form


@pytest.fixture(autouse=True)
def _no_attachment_scan(monkeypatch):
    monkeypatch.setattr(settings, "ATTACHMENT_SCAN_ENABLED", False)


def _donor(db, org_id, user_id, *, donor_type="egg", owner_id=None):
    return donor_service.create_donor(
        db,
        org_id,
        user_id,
        DonorCreate(
            donor_type=donor_type,
            full_name="Template Link Donor",
            email=f"template-link-{uuid.uuid4().hex[:8]}@example.com",
            owner_type="user" if owner_id else None,
            owner_id=owner_id,
        ),
        emit_workflow_events=False,
    )


def _surrogate_form(db, org_id, user_id):
    from app.db.models import Form

    form = Form(
        organization_id=org_id,
        name=f"Surrogate application {uuid.uuid4().hex[:6]}",
        status="published",
        purpose="surrogate_application",
        lead_kind="surrogate",
        schema_json={"pages": []},
        published_schema_json={"pages": []},
        created_by_user_id=user_id,
    )
    db.add(form)
    db.flush()
    return form


def _variable_paths(db, donor):
    return {
        "workflow": workflow_communication_actions.resolve_email_variables(db, donor),
        "campaign": campaign_content.build_recipient_template_variables(
            db, donor.pipeline_entity_type, donor
        ),
    }


def _expected_form_link(org, slug: str) -> str:
    return form_intake_service.build_shared_application_link(
        org_service.get_org_portal_base_url(org), slug
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("donor_type", "lead_kind"), [("egg", "egg_donor"), ("sperm", "sperm_donor")]
)
async def test_donor_template_links_use_donor_form_and_owner_booking_link(
    authed_client, db, test_org, test_user, donor_type, lead_kind
):
    _surrogate_form(db, test_org.id, test_user.id)
    other_kind = "sperm_donor" if lead_kind == "egg_donor" else "egg_donor"
    await _create_donor_form(authed_client, lead_kind=other_kind)
    _, slug = await _create_donor_form(authed_client, lead_kind=lead_kind)
    donor = _donor(db, test_org.id, test_user.id, donor_type=donor_type, owner_id=test_user.id)
    org = db.get(Organization, test_org.id)

    for path, variables in _variable_paths(db, donor).items():
        booking_link = (
            db.query(BookingLink)
            .filter(
                BookingLink.organization_id == test_org.id,
                BookingLink.user_id == test_user.id,
            )
            .one()
        )
        assert variables["form_link"] == _expected_form_link(org, slug), path
        booking_url, record_token = variables["appointment_link"].split("?record=")
        assert booking_url.endswith(f"/book/{booking_link.public_slug}"), path
        token = decode_booking_record_token(record_token)
        assert (token["record_type"], token["record_id"]) == ("donor", str(donor.id)), path


def test_donor_booking_link_omits_record_while_match_expansion_is_off(
    db, test_org, test_user, monkeypatch
):
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    donor = _donor(db, test_org.id, test_user.id, donor_type="egg", owner_id=test_user.id)

    for path, variables in _variable_paths(db, donor).items():
        assert "/book/" in variables["appointment_link"], path
        assert "?record=" not in variables["appointment_link"], path


@pytest.mark.asyncio
async def test_sperm_donor_form_link_falls_back_to_shared_donor_form(
    authed_client, db, test_org, test_user
):
    _, slug = await _create_donor_form(authed_client, lead_kind="egg_donor", shared_donor=True)
    donor = _donor(db, test_org.id, test_user.id, donor_type="sperm")
    org = db.get(Organization, test_org.id)

    for path, variables in _variable_paths(db, donor).items():
        assert variables["form_link"] == _expected_form_link(org, slug), path
        assert variables["appointment_link"] == "", path


@pytest.mark.asyncio
async def test_donor_form_link_ignores_surrogate_and_other_org_forms(
    authed_client, db, test_org, test_user
):
    from app.db.models import Form

    _surrogate_form(db, test_org.id, test_user.id)
    other_form_id, _ = await _create_donor_form(authed_client, lead_kind="egg_donor")
    other_org = Organization(
        id=uuid.uuid4(), name="Other Link Org", slug=f"other-link-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    db.query(Form).filter(Form.id == uuid.UUID(other_form_id)).one().organization_id = other_org.id
    db.flush()
    donor = _donor(db, test_org.id, test_user.id, donor_type="egg")

    for path, variables in _variable_paths(db, donor).items():
        assert variables["form_link"] == "", path
