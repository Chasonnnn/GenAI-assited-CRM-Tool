import uuid

import pytest

from app.core.encryption import hash_email, hash_phone
from app.db.enums import Role
from app.db.models import Attachment, Donor, EntityNote, Organization
from app.services import search_service
from app.utils.normalization import normalize_email, normalize_phone


def _donor(
    *,
    org_id,
    stage_id,
    donor_number: str,
    donor_type: str,
    full_name: str,
    email: str,
    phone: str,
) -> Donor:
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)
    return Donor(
        id=uuid.uuid4(),
        organization_id=org_id,
        donor_number=donor_number,
        donor_type=donor_type,
        full_name=full_name,
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        phone=normalized_phone,
        phone_hash=hash_phone(normalized_phone),
        stage_id=stage_id,
    )


@pytest.mark.asyncio
async def test_default_global_search_finds_egg_and_sperm_donors(
    authed_client, db, test_org, default_stage
):
    egg = _donor(
        org_id=test_org.id,
        stage_id=default_stage.id,
        donor_number="D12001",
        donor_type="egg",
        full_name="Avery Searchable",
        email="avery.egg@example.com",
        phone="+1 607 555 1201",
    )
    sperm = _donor(
        org_id=test_org.id,
        stage_id=default_stage.id,
        donor_number="D12002",
        donor_type="sperm",
        full_name="Jordan Searchable",
        email="jordan.sperm@example.com",
        phone="+1 607 555 1202",
    )
    db.add_all([egg, sperm])
    db.flush()

    searches = (
        ("Avery", egg),
        ("D12002", sperm),
        ("avery.egg@example.com", egg),
        ("+1 607 555 1202", sperm),
    )
    for query, expected in searches:
        response = await authed_client.get("/search", params={"q": query})
        assert response.status_code == 200, response.text
        result = next(
            result
            for result in response.json()["results"]
            if result["entity_type"] == "donor" and result["entity_id"] == str(expected.id)
        )
        assert result["donor_id"] == str(expected.id)


@pytest.mark.asyncio
async def test_global_search_links_donor_notes_and_files_to_the_donor(
    authed_client, db, test_org, test_user, default_stage
):
    donor = _donor(
        org_id=test_org.id,
        stage_id=default_stage.id,
        donor_number="D12005",
        donor_type="egg",
        full_name="Donor With Records",
        email="donor-records@example.com",
        phone="+1 607 555 1205",
    )
    db.add(donor)
    db.flush()
    note = EntityNote(
        organization_id=test_org.id,
        entity_type="donor",
        entity_id=donor.id,
        author_id=test_user.id,
        content="Education verification follow-up completed",
    )
    attachment = Attachment(
        organization_id=test_org.id,
        donor_id=donor.id,
        uploaded_by_user_id=test_user.id,
        filename="genetic-screening-report.pdf",
        storage_key=f"test/{donor.id}/genetic-screening-report.pdf",
        content_type="application/pdf",
        file_size=128,
        checksum_sha256="a" * 64,
        scan_status="clean",
        quarantined=False,
    )
    db.add_all([note, attachment])
    db.commit()

    note_response = await authed_client.get(
        "/search",
        params={"q": "education verification", "types": "note"},
    )
    assert note_response.status_code == 200, note_response.text
    note_result = next(
        result
        for result in note_response.json()["results"]
        if result["entity_type"] == "note" and result["entity_id"] == str(note.id)
    )
    assert note_result["donor_id"] == str(donor.id)

    file_response = await authed_client.get(
        "/search",
        params={"q": "genetic-screening-report.pdf", "types": "attachment"},
    )
    assert file_response.status_code == 200, file_response.text
    matching_files = [
        result
        for result in file_response.json()["results"]
        if result["entity_type"] == "attachment" and result["entity_id"] == str(attachment.id)
    ]
    assert matching_files, file_response.json()
    file_result = matching_files[0]
    assert file_result["donor_id"] == str(donor.id)


def test_donor_search_requires_permission_and_is_organization_scoped(
    db, test_org, test_user, default_stage
):
    local = _donor(
        org_id=test_org.id,
        stage_id=default_stage.id,
        donor_number="D12003",
        donor_type="egg",
        full_name="Local Donor",
        email="local.donor@example.com",
        phone="+1 607 555 1203",
    )
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Donor Organization",
        slug=f"other-donor-org-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add_all([local, other_org])
    db.flush()
    foreign = _donor(
        org_id=other_org.id,
        stage_id=default_stage.id,
        donor_number="D12004",
        donor_type="sperm",
        full_name="Foreign Donor",
        email="foreign.donor@example.com",
        phone="+1 607 555 1204",
    )
    db.add(foreign)
    db.flush()

    without_permission = search_service.global_search(
        db=db,
        org_id=test_org.id,
        query="Local Donor",
        user_id=test_user.id,
        role=Role.CASE_MANAGER.value,
        permissions=set(),
        entity_types=["donor"],
    )
    assert without_permission["results"] == []

    cross_org = search_service.global_search(
        db=db,
        org_id=test_org.id,
        query="Foreign Donor",
        user_id=test_user.id,
        role=Role.CASE_MANAGER.value,
        permissions={"view_donors"},
        entity_types=["donor"],
    )
    assert cross_org["results"] == []
