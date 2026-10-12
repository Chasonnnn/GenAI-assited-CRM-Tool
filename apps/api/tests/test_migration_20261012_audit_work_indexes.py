"""Audit index upgrades preserve immutable history and organization-scoped tails."""

import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from alembic import command
from app.services import version_service


def test_audit_indexes_upgrade_existing_history_and_downgrade_without_data_changes(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        org_id, other_org_id = uuid.uuid4(), uuid.uuid4()
        indexes = {"idx_audit_chain_tail", "idx_audit_match_work"}

        def rows():
            return connection.execute(text("SELECT * FROM audit_logs ORDER BY id")).all()

        def index_names():
            return {index["name"] for index in inspect(connection).get_indexes("audit_logs")}

        try:
            command.downgrade(config, "20261010_2100_email_template_layout")
            assert indexes.isdisjoint(index_names())
            for org in (org_id, other_org_id):
                connection.execute(
                    text(
                        "INSERT INTO organizations (id, name, slug) VALUES (:id, 'Audit migration', :slug)"
                    ),
                    {"id": org, "slug": f"audit-migration-{org}"},
                )
            connection.execute(
                text("""
                INSERT INTO audit_logs (organization_id, event_type, target_type, details)
                SELECT :org, 'phi_viewed', 'match', '{}'::jsonb FROM generate_series(1, 1000)
            """),
                {"org": org_id},
            )
            ids = sorted([uuid.uuid4(), uuid.uuid4()])
            for entry_id, org, entry_hash in (
                (ids[0], org_id, "a" * 64),
                (ids[1], org_id, "b" * 64),
                (uuid.uuid4(), other_org_id, "c" * 64),
            ):
                connection.execute(
                    text("""
                    INSERT INTO audit_logs (id, organization_id, event_type, entry_hash, created_at)
                    VALUES (:id, :org, 'auth_login_failed', :hash, now() - interval '1 day')
                """),
                    {"id": entry_id, "org": org, "hash": entry_hash},
                )
            before = rows()
            command.upgrade(config, "head")
            assert indexes <= index_names()
            assert rows() == before
            with Session(bind=connection) as db:
                assert version_service.get_last_audit_hash(db, org_id) == "b" * 64
                assert version_service.get_last_audit_hash(db, other_org_id) == "c" * 64
                assert (
                    version_service.get_last_audit_hash(db, uuid.uuid4())
                    == version_service.GENESIS_HASH
                )
            for statement in (
                "UPDATE audit_logs SET details = '{}'::jsonb WHERE id = :id",
                "DELETE FROM audit_logs WHERE id = :id",
            ):
                savepoint = connection.begin_nested()
                with pytest.raises(DBAPIError, match="append-only"):
                    connection.execute(text(statement), {"id": ids[0]})
                savepoint.rollback()
            command.downgrade(config, "20261010_2100_email_template_layout")
            assert indexes.isdisjoint(index_names())
            assert rows() == before
        finally:
            transaction.rollback()
