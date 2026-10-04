"""The profile upgrade preserves existing donors and keeps sensitive columns encrypted."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.db.models import Donor
from app.db.types import EncryptedDate, EncryptedString


def _load_migration(filename: str):
    path = Path(__file__).parents[1] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_profile_migration_upgrade_and_downgrade(db):
    migration = _load_migration("20260914_1200_donor_profile.py")
    # The profile downgrade drops flat medical columns that a later migration removes.
    drop_flat_medical = _load_migration("20261004_1000_drop_flat_medical_columns.py")
    connection = db.connection()
    original_columns = {column["name"] for column in inspect(connection).get_columns("donors")}
    with Operations.context(MigrationContext.configure(connection)):
        drop_flat_medical.downgrade()
        migration.downgrade()
        basic_columns = {column["name"] for column in inspect(connection).get_columns("donors")}
        assert "email" in basic_columns and "education" in basic_columns
        assert "ssn" not in basic_columns and "nicotine" not in basic_columns
        migration.upgrade()
        drop_flat_medical.upgrade()
    assert {
        column["name"] for column in inspect(connection).get_columns("donors")
    } == original_columns
    for field in (
        "ssn",
        "partner_ssn",
        "college",
        "nicotine",
        "infectious_disease",
        "date_of_birth",
    ):
        assert isinstance(Donor.__table__.c[field].type, EncryptedString | EncryptedDate)
    assert (
        connection.execute(
            text(
                "SELECT column_default FROM information_schema.columns WHERE table_name='donors' AND column_name='profile_updated_fields'"
            )
        ).scalar()
        == "'[]'::jsonb"
    )
