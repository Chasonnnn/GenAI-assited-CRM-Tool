"""The medical records upgrade imports each nonempty flat section once and keeps encryption."""

import importlib.util
import uuid
from datetime import date
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select, text

from app.core.encryption import encrypt_value
from app.db.models import MedicalRecord
from app.schemas.donor import DonorCreate
from app.services import donor_service
from tests.test_tasks_match_scope import _create_surrogate


def _load_migration():
    path = Path(__file__).parents[1] / "alembic/versions/20261003_1200_medical_records.py"
    spec = importlib.util.spec_from_file_location("medical_records_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_medical_records_migration_imports_flat_sections(db, test_org, test_user, default_stage):
    migration = _load_migration()
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    empty_surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(donor_type="egg", full_name="Import Donor", email="import-donor@example.com"),
        emit_workflow_events=False,
    )
    connection = db.connection()
    connection.execute(
        text(
            "UPDATE surrogates SET clinic_name = 'Cedar Ridge Fertility', clinic_city = 'San Diego', "
            "clinic_phone = :phone, insurance_company = 'Blue Harbor Health', "
            "insurance_member_id = :member, insurance_subscriber_dob = :dob WHERE id = :id"
        ),
        {
            "phone": encrypt_value("+15552014400"),
            "member": encrypt_value("M8821-04"),
            "dob": encrypt_value("1994-05-17"),
            "id": surrogate.id,
        },
    )
    # Empty strings and NULLs do not create records.
    connection.execute(
        text("UPDATE surrogates SET ob_clinic_name = '', pcp_name = NULL WHERE id = :id"),
        {"id": empty_surrogate.id},
    )
    connection.execute(
        text(
            "UPDATE donors SET ob_provider_name = 'Dr. Priya Raman', ob_clinic_name = 'Ashford', "
            "ob_email = :email WHERE id = :id"
        ),
        {"email": encrypt_value("ob@example.com"), "id": donor.id},
    )

    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        assert "medical_records" not in inspect(connection).get_table_names()
        migration.upgrade()

    db.expire_all()
    records = db.scalars(
        select(MedicalRecord).where(MedicalRecord.organization_id == test_org.id)
    ).all()
    by_owner = {(r.surrogate_id or r.donor_id, r.section): r for r in records}
    assert set(by_owner) == {
        (surrogate.id, "clinic"),
        (surrogate.id, "insurance"),
        (donor.id, "ob"),
    }
    clinic = by_owner[(surrogate.id, "clinic")]
    assert (clinic.name, clinic.city, clinic.phone) == (
        "Cedar Ridge Fertility",
        "San Diego",
        "+15552014400",
    )
    assert clinic.source == "import" and clinic.effective_date is None
    assert clinic.revision == 1 and clinic.created_by_user_id is None
    insurance = by_owner[(surrogate.id, "insurance")]
    assert insurance.name == "Blue Harbor Health"
    assert insurance.member_id == "M8821-04"
    assert insurance.subscriber_dob == date(1994, 5, 17)
    ob = by_owner[(donor.id, "ob")]
    assert (ob.provider_name, ob.name, ob.email) == ("Dr. Priya Raman", "Ashford", "ob@example.com")

    # Ciphertext stays ciphertext in the new table.
    raw_member = connection.execute(
        text("SELECT member_id FROM medical_records WHERE id = :id"), {"id": insurance.id}
    ).scalar()
    assert raw_member and "M8821" not in raw_member


def test_medical_records_reject_rows_without_exactly_one_owner(db, test_org):
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(MedicalRecord(id=uuid.uuid4(), organization_id=test_org.id, section="clinic"))
        db.flush()
