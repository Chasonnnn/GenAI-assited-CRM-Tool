"""The intended parent stage-change permission keeps each member's stored access."""

from uuid import uuid4

from sqlalchemy import text

from alembic import command
from app.core.permission_resolution import resolve_effective_permissions
from tests.test_migration_20260829_donor_module import _alembic_config

REVISION = "20260928_1200_ip_stage_permission"
PREVIOUS = "20260926_1200_donor_match_stages"
EDIT = "edit_intended_parents"
CHANGE = "change_intended_parent_status"


def _insert_user(connection) -> object:
    user_id = uuid4()
    connection.execute(
        text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, 'Member')"),
        {"id": user_id, "email": f"ip-permission-{user_id.hex}@example.com"},
    )
    return user_id


def _role_rows(connection, org_id) -> dict[tuple[str, str], bool]:
    rows = connection.execute(
        text(
            "SELECT role, permission, is_granted FROM role_permissions "
            "WHERE organization_id = :org AND permission IN (:edit, :change)"
        ),
        {"org": org_id, "edit": EDIT, "change": CHANGE},
    ).all()
    return {(row.role, row.permission): row.is_granted for row in rows}


def _user_rows(connection, org_id) -> dict[tuple[object, str], str]:
    rows = connection.execute(
        text(
            "SELECT user_id, permission, override_type FROM user_permission_overrides "
            "WHERE organization_id = :org AND permission IN (:edit, :change)"
        ),
        {"org": org_id, "edit": EDIT, "change": CHANGE},
    ).all()
    return {(row.user_id, row.permission): row.override_type for row in rows}


def test_upgrade_copies_edit_overrides_to_stage_change_permission(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            org_id, other_org_id = uuid4(), uuid4()
            for org in (org_id, other_org_id):
                connection.execute(
                    text(
                        "INSERT INTO organizations (id, name, slug) VALUES (:id, 'Agency', :slug)"
                    ),
                    {"id": org, "slug": f"ip-permission-{org.hex}"},
                )
            granted_user, revoked_user, untouched_user = (
                _insert_user(connection),
                _insert_user(connection),
                _insert_user(connection),
            )
            role_rows = [
                (org_id, "intake_specialist", EDIT, True),
                (org_id, "case_manager", EDIT, False),
                # An existing row for the new key is kept as configured.
                (org_id, "admin", EDIT, False),
                (org_id, "admin", CHANGE, True),
                (other_org_id, "case_manager", "edit_surrogates", False),
            ]
            for org, role, permission, granted in role_rows:
                connection.execute(
                    text(
                        "INSERT INTO role_permissions (organization_id, role, permission, is_granted) "
                        "VALUES (:org, :role, :permission, :granted)"
                    ),
                    {"org": org, "role": role, "permission": permission, "granted": granted},
                )
            for user_id, override_type in (
                (granted_user, "grant"),
                (revoked_user, "revoke"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO user_permission_overrides "
                        "(organization_id, user_id, permission, override_type) "
                        "VALUES (:org, :user, :permission, :type)"
                    ),
                    {"org": org_id, "user": user_id, "permission": EDIT, "type": override_type},
                )
            connection.execute(
                text(
                    "INSERT INTO user_permission_overrides "
                    "(organization_id, user_id, permission, override_type) "
                    "VALUES (:org, :user, :permission, 'revoke')"
                ),
                {"org": org_id, "user": untouched_user, "permission": CHANGE},
            )

            command.upgrade(config, REVISION)
            command.upgrade(config, REVISION)

            assert _role_rows(connection, org_id) == {
                ("intake_specialist", EDIT): True,
                ("intake_specialist", CHANGE): True,
                ("case_manager", EDIT): False,
                ("case_manager", CHANGE): False,
                ("admin", EDIT): False,
                ("admin", CHANGE): True,
            }
            assert _role_rows(connection, other_org_id) == {}
            assert _user_rows(connection, org_id) == {
                (granted_user, EDIT): "grant",
                (granted_user, CHANGE): "grant",
                (revoked_user, EDIT): "revoke",
                (revoked_user, CHANGE): "revoke",
                (untouched_user, CHANGE): "revoke",
            }
            roles = _role_rows(connection, org_id)
            for role in ("intake_specialist", "case_manager"):
                effective = resolve_effective_permissions(
                    role,
                    role_overrides=[
                        (permission, granted)
                        for (row_role, permission), granted in roles.items()
                        if row_role == role
                    ],
                )
                assert (EDIT in effective) == (CHANGE in effective)

            command.downgrade(config, PREVIOUS)
            assert set(_role_rows(connection, org_id)) == {
                ("intake_specialist", EDIT),
                ("case_manager", EDIT),
                ("admin", EDIT),
            }
            assert set(_user_rows(connection, org_id)) == {
                (granted_user, EDIT),
                (revoked_user, EDIT),
            }
        finally:
            transaction.rollback()
