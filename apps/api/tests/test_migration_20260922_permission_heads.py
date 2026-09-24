"""The permission and operational schemas join without activating an organization."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command


@pytest.mark.parametrize(
    "previous",
    ["20260920_0310_permission_heads", "20260921_0100_google_appointment_sync"],
)
def test_permission_join_preserves_existing_data_and_policy_versions(db_engine, previous):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, previous)
            had_policy = inspect(connection).has_table("organization_permission_policies")
            org_ids = [uuid4(), uuid4()]
            for version, org_id in enumerate(org_ids, start=1):
                connection.execute(
                    text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": org_id, "name": "Existing organization", "slug": f"join-{org_id}"},
                )
                if had_policy:
                    connection.execute(
                        text(
                            "INSERT INTO organization_permission_policies "
                            "(organization_id, version, configuration_revision) "
                            "VALUES (:id, :version, 7)"
                        ),
                        {"id": org_id, "version": version},
                    )
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
                "20260922_1600_permission_heads"
            )
            for version, org_id in enumerate(org_ids, start=1):
                assert connection.execute(
                    text("SELECT name FROM organizations WHERE id = :id"), {"id": org_id}
                ).scalar_one() == "Existing organization"
                policy = connection.execute(
                    text(
                        "SELECT version, configuration_revision FROM organization_permission_policies "
                        "WHERE organization_id = :id"
                    ),
                    {"id": org_id},
                ).one_or_none()
                if had_policy:
                    assert tuple(policy) == (version, 7)
                else:
                    assert policy is None or policy.version == 1
            assert "google_sync_revision" in {
                column["name"] for column in inspect(connection).get_columns("appointments")
            }
        finally:
            transaction.rollback()
