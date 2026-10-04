"""Dropping the flat medical columns leaves imported records intact and downgrade restores the columns."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select

from app.db.models import MedicalRecord
from app.schemas.medical_record import LEGACY_MEDICAL_FIELDS
from tests.test_tasks_match_scope import _create_surrogate


def _load_migration():
    path = Path(__file__).parents[1] / "alembic/versions/20261004_1000_drop_flat_medical_columns.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _columns(connection, table: str) -> dict[str, object]:
    return {column["name"]: column["type"] for column in inspect(connection).get_columns(table)}


def test_drop_flat_medical_columns_round_trip(db, test_org, test_user, default_stage):
    migration = _load_migration()
    assert set(migration.FLAT_COLUMNS) == set(LEGACY_MEDICAL_FIELDS)
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    record = MedicalRecord(
        organization_id=test_org.id, surrogate_id=surrogate.id, section="clinic", name="Cedar Ridge"
    )
    db.add(record)
    db.flush()
    connection = db.connection()
    for table in migration._OWNER_TABLES:
        assert not set(migration.FLAT_COLUMNS) & set(_columns(connection, table))

    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        for table in migration._OWNER_TABLES:
            restored = _columns(connection, table)
            assert str(restored["clinic_city"]) == "VARCHAR(100)"
            assert str(restored["insurance_member_id"]) == "TEXT"
            assert set(migration.FLAT_COLUMNS) <= set(restored)
        migration.upgrade()

    for table in migration._OWNER_TABLES:
        assert not set(migration.FLAT_COLUMNS) & set(_columns(connection, table))
    assert (
        db.scalar(select(MedicalRecord.name).where(MedicalRecord.id == record.id)) == "Cedar Ridge"
    )
