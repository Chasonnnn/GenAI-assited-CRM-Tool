"""The profile upgrade preserves existing donors and keeps sensitive columns encrypted."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.db.models import Donor
from app.db.types import EncryptedDate, EncryptedString


def test_profile_migration_upgrade_and_downgrade(db):
    path = Path(__file__).parents[1] / "alembic/versions/20260914_1200_donor_profile.py"
    spec = importlib.util.spec_from_file_location("donor_profile_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = db.connection()
    original_columns = {column["name"] for column in inspect(connection).get_columns("donors")}
    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        basic_columns = {column["name"] for column in inspect(connection).get_columns("donors")}
        assert "email" in basic_columns and "education" in basic_columns
        assert "ssn" not in basic_columns and "nicotine" not in basic_columns
        migration.upgrade()
    assert {
        column["name"] for column in inspect(connection).get_columns("donors")
    } == original_columns
    for field in (
        "ssn",
        "partner_ssn",
        "college",
        "nicotine",
        "infectious_disease",
        "insurance_policy_number",
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
