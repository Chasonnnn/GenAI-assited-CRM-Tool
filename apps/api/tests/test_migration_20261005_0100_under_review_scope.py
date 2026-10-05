"""Under Review scope storage preserves custom rules and requires a reviewed rollback."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from tests.test_migration_20260928_1300_workflow_fixed_trigger_subjects import _alembic_config

REVISION = "20261005_0100_under_review_scope"
PREVIOUS = "20261004_1300_organization_logo"


def test_under_review_scope_upgrade_preserves_rules_and_guards_downgrade(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            ids = {key: uuid4() for key in ("org", "user", "member", "role", "addition")}
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) VALUES (:org, 'Scope org', :slug)"
                ),
                {**ids, "slug": f"scope-{ids['org']}"},
            )
            connection.execute(
                text("INSERT INTO users (id, email, display_name) VALUES (:user, :email, 'Staff')"),
                {**ids, "email": f"scope-{ids['user']}@example.test"},
            )
            connection.execute(
                text(
                    "INSERT INTO memberships (id, organization_id, user_id, role) VALUES (:member, :org, :user, 'case_manager')"
                ),
                ids,
            )
            connection.execute(
                text(
                    "INSERT INTO role_record_scopes (id, organization_id, role, module, assignment, phase) VALUES (:role, :org, 'case_manager', 'surrogates', 'assigned', 'post_approval')"
                ),
                ids,
            )
            connection.execute(
                text(
                    "INSERT INTO user_record_scope_additions (id, organization_id, membership_id, user_id, module, assignment, phase) VALUES (:addition, :org, :member, :user, 'surrogates', 'assigned', 'pre_approval')"
                ),
                ids,
            )
            command.upgrade(config, REVISION)
            for table, key, phase in (
                ("role_record_scopes", "role", "post_approval"),
                ("user_record_scope_additions", "addition", "pre_approval"),
            ):
                assert connection.execute(
                    text(f"SELECT assignment, phase FROM {table} WHERE id = :id"),
                    {"id": ids[key]},
                ).one() == ("assigned", phase)
                connection.execute(
                    text(f"UPDATE {table} SET phase = 'under_review_onward' WHERE id = :id"),
                    {"id": ids[key]},
                )
                for module in ("donors", "intended_parents"):
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(
                                text(f"UPDATE {table} SET module = :module WHERE id = :id"),
                                {"id": ids[key], "module": module},
                            )
            with pytest.raises(RuntimeError, match="reviewed rollback"):
                command.downgrade(config, PREVIOUS)
            for table, key in (
                ("role_record_scopes", "role"),
                ("user_record_scope_additions", "addition"),
            ):
                connection.execute(
                    text(f"UPDATE {table} SET phase = 'post_approval' WHERE id = :id"),
                    {"id": ids[key]},
                )
            command.downgrade(config, PREVIOUS)
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "UPDATE role_record_scopes SET phase = 'under_review_onward' WHERE id = :role"
                        ),
                        ids,
                    )
            command.upgrade(config, REVISION)
        finally:
            transaction.rollback()
