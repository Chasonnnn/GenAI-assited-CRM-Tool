"""Dated medical records: corrections, history, archive/restore and access boundaries."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select, text

from app.db.enums import Role
from app.db.models import (
    AuditLog,
    MedicalRecord,
    Organization,
    SurrogateActivityLog,
)
from app.services import medical_record_service
from tests.test_donors import _client_for_org, _create_donor
from tests.test_tasks_match_scope import _create_surrogate


@pytest.fixture
def other_org(db):
    org = Organization(
        id=uuid.uuid4(), name="Other tenant", slug=f"medical-other-{uuid.uuid4().hex[:8]}"
    )
    db.add(org)
    db.flush()
    return org


@pytest.fixture
def surrogate(db, test_org, test_user, default_stage):
    return _create_surrogate(db, test_org.id, test_user.id, default_stage)


def _today(db, org) -> date:
    return medical_record_service.org_today(db, org.id)


def _section(body: dict, section: str) -> list[dict]:
    return [record for record in body["records"] if record["section"] == section]


def _current(body: dict, section: str) -> dict | None:
    return next((r for r in _section(body, section) if r["status"] == "current"), None)


async def _create(client, base: str, **payload) -> dict:
    response = await client.post(f"{base}/medical-records", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_new_record_becomes_current_and_keeps_previous_history(db, test_org, surrogate):
    base = f"/surrogates/{surrogate.id}"
    today = _today(db, test_org)
    async with _client_for_org(db, test_org) as client:
        await _create(
            client,
            base,
            section="clinic",
            effective_date=(today - timedelta(days=200)).isoformat(),
            name="Cedar Ridge Fertility",
            phone="(555) 201-4400",
            state="ca",
        )
        body = await _create(
            client,
            base,
            section="clinic",
            effective_date=today.isoformat(),
            name="Willow Bay IVF",
        )
        current = _current(body, "clinic")
        assert current["name"] == "Willow Bay IVF"
        past = [r for r in _section(body, "clinic") if r["status"] == "past"]
        assert [r["name"] for r in past] == ["Cedar Ridge Fertility"]
        assert past[0]["end_date"] == (today - timedelta(days=1)).isoformat()
        assert past[0]["state"] == "CA" and past[0]["phone"].startswith("+1")

        # Backdated records stay in the past; future records are scheduled.
        body = await _create(
            client,
            base,
            section="clinic",
            effective_date=(today - timedelta(days=400)).isoformat(),
            name="Lakeside IVF",
        )
        assert _current(body, "clinic")["name"] == "Willow Bay IVF"
        body = await _create(
            client,
            base,
            section="clinic",
            effective_date=(today + timedelta(days=30)).isoformat(),
            name="Summit Fertility",
        )
        assert _current(body, "clinic")["name"] == "Willow Bay IVF"
        scheduled = [r for r in _section(body, "clinic") if r["status"] == "scheduled"]
        assert [r["name"] for r in scheduled] == ["Summit Fertility"]

    activity = db.scalars(
        select(SurrogateActivityLog.activity_type).where(
            SurrogateActivityLog.surrogate_id == surrogate.id
        )
    ).all()
    assert "medical_info_updated" in activity
    audit = db.scalars(
        select(AuditLog).where(
            AuditLog.target_id == surrogate.id, AuditLog.event_type == "medical_record_created"
        )
    ).all()
    assert len(audit) == 4
    assert "Willow" not in str([event.details for event in audit])


@pytest.mark.asyncio
async def test_correction_increments_revision_and_records_values(db, test_org, surrogate):
    base = f"/surrogates/{surrogate.id}"
    today = _today(db, test_org)
    async with _client_for_org(db, test_org) as client:
        body = await _create(
            client,
            base,
            section="insurance",
            effective_date=today.isoformat(),
            name="Blue Harbor Health",
            member_id="M8821-04",
            policy_number="BH-61743",
        )
        record = _current(body, "insurance")
        response = await client.patch(
            f"{base}/medical-records/{record['id']}",
            json={
                "expected_revision": 1,
                "policy_number": "BH-61734",
                "phone": "(555) 310-2200",
            },
        )
        assert response.status_code == 200, response.text
        corrected = _current(response.json(), "insurance")
        assert corrected["revision"] == 2
        assert len(_section(response.json(), "insurance")) == 1
        by_field = {c["field"]: c for c in corrected["corrections"]}
        assert by_field["policy_number"]["redacted"] is True
        assert by_field["policy_number"]["old_value"] is None
        assert by_field["phone"]["old_value"] is None
        assert by_field["phone"]["new_value"] == corrected["phone"]

        stale = await client.patch(
            f"{base}/medical-records/{record['id']}",
            json={"expected_revision": 1, "plan_name": "Gold"},
        )
        assert stale.status_code == 409

        wrong_field = await client.patch(
            f"{base}/medical-records/{record['id']}",
            json={"expected_revision": 2, "provider_name": "Dr. Nobody"},
        )
        assert wrong_field.status_code == 422

        no_name = await client.patch(
            f"{base}/medical-records/{record['id']}",
            json={"expected_revision": 2, "name": ""},
        )
        assert no_name.status_code == 422

    raw = db.execute(
        text("SELECT member_id, phone FROM medical_records WHERE id = :id"), {"id": record["id"]}
    ).one()
    assert "M8821" not in raw.member_id and "555" not in raw.phone
    raw_correction = db.execute(
        text("SELECT new_value FROM medical_record_corrections WHERE field = 'phone'")
    ).scalar()
    assert raw_correction and "310" not in raw_correction


@pytest.mark.asyncio
async def test_create_rejects_fields_from_other_sections_and_missing_name(db, test_org, surrogate):
    base = f"/surrogates/{surrogate.id}"
    today = _today(db, test_org).isoformat()
    async with _client_for_org(db, test_org) as client:
        wrong = await client.post(
            f"{base}/medical-records",
            json={"section": "clinic", "effective_date": today, "name": "X", "member_id": "1"},
        )
        assert wrong.status_code == 422
        unnamed = await client.post(
            f"{base}/medical-records",
            json={"section": "ob", "effective_date": today, "phone": "5552014400"},
        )
        assert unnamed.status_code == 422
        provider_only = await client.post(
            f"{base}/medical-records",
            json={"section": "ob", "effective_date": today, "provider_name": "Dr. Priya Raman"},
        )
        assert provider_only.status_code == 200


@pytest.mark.asyncio
async def test_retried_create_with_same_key_creates_one_record(db, test_org, surrogate):
    base = f"/surrogates/{surrogate.id}"
    payload = {
        "section": "pcp",
        "effective_date": _today(db, test_org).isoformat(),
        "provider_name": "Dr. Alicia Romero",
        "idempotency_key": "create-pcp-0001",
    }
    async with _client_for_org(db, test_org) as client:
        first = await _create(client, base, **payload)
        second = await _create(client, base, **payload)
        assert len(_section(first, "pcp")) == len(_section(second, "pcp")) == 1
        reused = await client.post(
            f"{base}/medical-records",
            json={
                "section": "lab_clinic",
                "effective_date": payload["effective_date"],
                "name": "Meridian Lab",
                "idempotency_key": payload["idempotency_key"],
            },
        )
        assert reused.status_code == 409


@pytest.mark.asyncio
async def test_archive_ends_current_and_restore_starts_new_record_today(db, test_org, surrogate):
    base = f"/surrogates/{surrogate.id}"
    today = _today(db, test_org)
    async with _client_for_org(db, test_org) as client:
        body = await _create(
            client,
            base,
            section="monitoring_clinic",
            effective_date=(today - timedelta(days=90)).isoformat(),
            name="Summit Lane Monitoring",
            city="Corona",
        )
        record = _current(body, "monitoring_clinic")

        archived = await client.post(
            f"{base}/medical-records/{record['id']}/archive", json={"expected_revision": 1}
        )
        assert archived.status_code == 200, archived.text
        body = archived.json()
        assert _current(body, "monitoring_clinic") is None
        (old,) = _section(body, "monitoring_clinic")
        assert old["archived_on"] == today.isoformat() and old["end_date"] == today.isoformat()

        again = await client.post(
            f"{base}/medical-records/{record['id']}/archive", json={"expected_revision": 2}
        )
        assert again.status_code == 409

        restored = await client.post(
            f"{base}/medical-records/sections/monitoring_clinic/restore",
            json={"idempotency_key": "restore-monitoring-1"},
        )
        assert restored.status_code == 200, restored.text
        body = restored.json()
        current = _current(body, "monitoring_clinic")
        assert current["id"] != record["id"]
        assert current["effective_date"] == today.isoformat()
        assert current["source"] == "restore"
        assert (current["name"], current["city"]) == ("Summit Lane Monitoring", "Corona")
        assert len(_section(body, "monitoring_clinic")) == 2

        not_archived = await client.post(
            f"{base}/medical-records/sections/monitoring_clinic/restore", json={}
        )
        assert not_archived.status_code == 409


@pytest.mark.asyncio
async def test_only_current_record_can_be_archived(db, test_org, surrogate):
    base = f"/surrogates/{surrogate.id}"
    today = _today(db, test_org)
    async with _client_for_org(db, test_org) as client:
        await _create(
            client,
            base,
            section="ob",
            effective_date=(today - timedelta(days=60)).isoformat(),
            provider_name="Dr. Kevin Osei",
        )
        body = await _create(
            client, base, section="ob", effective_date=today.isoformat(), provider_name="Dr. Raman"
        )
        past = next(r for r in _section(body, "ob") if r["status"] == "past")
        response = await client.post(
            f"{base}/medical-records/{past['id']}/archive", json={"expected_revision": 1}
        )
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_donor_records_and_archived_donor_is_read_only(db, test_org):
    async with _client_for_org(db, test_org) as client:
        donor = await _create_donor(client)
        base = f"/donors/{donor['id']}"
        body = await _create(
            client,
            base,
            section="clinic",
            effective_date=_today(db, test_org).isoformat(),
            name="Cedar Ridge Fertility",
        )
        assert _current(body, "clinic")["name"] == "Cedar Ridge Fertility"
        listed = await client.get(f"{base}/medical-records")
        assert listed.status_code == 200
        assert listed.headers["cache-control"] == "no-store"

        archive = await client.post(f"{base}/archive")
        assert archive.status_code == 200, archive.text
        blocked = await client.post(
            f"{base}/medical-records",
            json={
                "section": "lab_clinic",
                "effective_date": _today(db, test_org).isoformat(),
                "name": "Meridian Lab",
            },
        )
        assert blocked.status_code in (400, 403)


@pytest.mark.asyncio
async def test_records_are_invisible_and_immutable_across_organizations(
    db, test_org, other_org, surrogate
):
    async with _client_for_org(db, test_org) as client:
        donor = await _create_donor(client)
        body = await _create(
            client,
            f"/surrogates/{surrogate.id}",
            section="clinic",
            effective_date=_today(db, test_org).isoformat(),
            name="Cedar Ridge Fertility",
        )
        record_id = _current(body, "clinic")["id"]
        donor_body = await _create(
            client,
            f"/donors/{donor['id']}",
            section="clinic",
            effective_date=_today(db, test_org).isoformat(),
            name="Willow Bay IVF",
        )
        donor_record_id = _current(donor_body, "clinic")["id"]

        # A record cannot be reached through another owner in the same org.
        crossed = await client.patch(
            f"/donors/{donor['id']}/medical-records/{record_id}",
            json={"expected_revision": 1, "name": "Changed"},
        )
        assert crossed.status_code == 404

    async with _client_for_org(db, other_org) as outsider:
        for base, rid in (
            (f"/surrogates/{surrogate.id}", record_id),
            (f"/donors/{donor['id']}", donor_record_id),
        ):
            assert (await outsider.get(f"{base}/medical-records")).status_code == 404
            created = await outsider.post(
                f"{base}/medical-records",
                json={"section": "ob", "effective_date": "2026-01-01", "provider_name": "X"},
            )
            assert created.status_code == 404
            patched = await outsider.patch(
                f"{base}/medical-records/{rid}", json={"expected_revision": 1, "name": "X"}
            )
            assert patched.status_code == 404
            archived = await outsider.post(
                f"{base}/medical-records/{rid}/archive", json={"expected_revision": 1}
            )
            assert archived.status_code == 404

    names = db.scalars(select(MedicalRecord.name).where(MedicalRecord.section == "clinic")).all()
    assert sorted(names) == ["Cedar Ridge Fertility", "Willow Bay IVF"]


@pytest.mark.asyncio
async def test_writes_require_edit_permission_and_csrf(db, test_org, surrogate):
    async with _client_for_org(db, test_org) as client:
        donor = await _create_donor(client)
    payload = {"section": "clinic", "effective_date": "2026-01-01", "name": "Cedar Ridge"}
    async with _client_for_org(
        db, test_org, role=Role.ADMIN, revokes=("edit_surrogates", "edit_donors")
    ) as reader:
        assert (await reader.get(f"/donors/{donor['id']}/medical-records")).status_code == 200
        denied_donor = await reader.post(f"/donors/{donor['id']}/medical-records", json=payload)
        assert denied_donor.status_code == 403
        denied_surrogate = await reader.post(
            f"/surrogates/{surrogate.id}/medical-records", json=payload
        )
        assert denied_surrogate.status_code == 403
    async with _client_for_org(db, test_org) as client:
        no_csrf = await client.post(
            f"/surrogates/{surrogate.id}/medical-records",
            json=payload,
            headers={"X-CSRF-Token": ""},
        )
        assert no_csrf.status_code == 403


def test_form_values_correct_current_record_or_start_one(db, test_org, test_user, surrogate):
    owner = medical_record_service.RecordOwner.for_surrogate(surrogate)
    today = _today(db, test_org)
    db.add(
        MedicalRecord(
            organization_id=test_org.id,
            surrogate_id=surrogate.id,
            section="insurance",
            name="Blue Harbor Health",
            effective_date=today - timedelta(days=10),
        )
    )
    db.flush()

    changed = medical_record_service.apply_form_values(
        db,
        owner,
        test_user.id,
        {
            "insurance": {"name": "Blue Harbor Health", "member_id": "M-1", "plan_name": ""},
            "clinic": {"name": "Cedar Ridge Fertility", "phone": "(555) 201-4400"},
            "lab_clinic": {"name": ""},
        },
        today - timedelta(days=2),
    )
    assert changed == ["clinic", "insurance"]
    records = {r.section: r for r in db.scalars(select(MedicalRecord)).all()}
    insurance = records["insurance"]
    assert (insurance.member_id, insurance.revision) == ("M-1", 2)
    assert [(c.field, c.redacted, c.source) for c in insurance.corrections] == [
        ("member_id", True, "form")
    ]
    clinic = records["clinic"]
    assert clinic.source == "form" and clinic.effective_date == today - timedelta(days=2)
    assert clinic.phone == "+15552014400"
    assert "lab_clinic" not in records


def test_legacy_field_map_matches_imported_columns():
    from app.schemas.medical_record import LEGACY_MEDICAL_FIELDS
    from tests.test_migration_20261003_medical_records import _load_migration

    imported = {
        legacy: (section, field)
        for section, columns in _load_migration().SECTION_COLUMNS.items()
        for field, legacy in columns.items()
    }
    assert LEGACY_MEDICAL_FIELDS == imported
