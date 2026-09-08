"""Pure tests for the existing role and override resolution contract."""

import pytest

from app.core.permission_resolution import resolve_effective_permissions
from app.core.permissions import PERMISSION_REGISTRY, ROLE_DEFAULTS


@pytest.mark.parametrize(
    ("role", "org_override", "user_override", "expected"),
    [
        ("intake_specialist", None, None, False),
        ("intake_specialist", None, "grant", True),
        ("intake_specialist", None, "revoke", False),
        ("intake_specialist", True, None, True),
        ("intake_specialist", True, "grant", True),
        ("intake_specialist", True, "revoke", False),
        ("intake_specialist", False, None, False),
        ("intake_specialist", False, "grant", True),
        ("intake_specialist", False, "revoke", False),
        ("case_manager", None, None, True),
        ("case_manager", None, "grant", True),
        ("case_manager", None, "revoke", False),
        ("case_manager", True, None, True),
        ("case_manager", True, "grant", True),
        ("case_manager", True, "revoke", False),
        ("case_manager", False, None, False),
        ("case_manager", False, "grant", True),
        ("case_manager", False, "revoke", False),
    ],
)
def test_user_override_takes_precedence_over_org_override_and_role_default(
    role, org_override, user_override, expected
):
    permission = "view_reports"
    result = resolve_effective_permissions(
        role,
        role_overrides=[] if org_override is None else [(permission, org_override)],
        user_overrides=[] if user_override is None else [(permission, user_override)],
    )

    assert (permission in result) is expected
    assert result - {permission} == ROLE_DEFAULTS[role] - {permission}


@pytest.mark.parametrize("role", ["intake_specialist", "case_manager", "admin"])
def test_no_overrides_preserves_all_role_defaults(role):
    assert resolve_effective_permissions(role) == ROLE_DEFAULTS[role]


def test_developer_ignores_overrides_without_consuming_them():
    def unused_overrides():
        raise AssertionError("Developer resolution must bypass overrides")
        yield  # Make this a lazy iterable so accessing it fails inside resolution.

    result = resolve_effective_permissions(
        "developer",
        role_overrides=unused_overrides(),
        user_overrides=unused_overrides(),
    )

    assert result == set(PERMISSION_REGISTRY)


@pytest.mark.parametrize("source", ["defaults", "organization", "user"])
def test_developer_only_permissions_are_filtered_after_every_source(source, monkeypatch):
    developer_permissions = {
        key for key, definition in PERMISSION_REGISTRY.items() if definition.developer_only
    }
    assert developer_permissions
    defaults = {"view_reports"}
    if source == "defaults":
        defaults |= developer_permissions
    monkeypatch.setitem(ROLE_DEFAULTS, "test_role", defaults)

    result = resolve_effective_permissions(
        "test_role",
        role_overrides=(
            [(permission, True) for permission in developer_permissions]
            if source == "organization"
            else []
        ),
        user_overrides=(
            [(permission, "grant") for permission in developer_permissions]
            if source == "user"
            else []
        ),
    )

    assert result == {"view_reports"}


@pytest.mark.parametrize(
    ("role_overrides", "user_overrides", "expected"),
    [
        ([], [], set()),
        ([("view_reports", True)], [], {"view_reports"}),
        ([], [("view_reports", "grant")], {"view_reports"}),
        ([("view_reports", False)], [], set()),
        ([], [("view_reports", "revoke")], set()),
        ([("legacy_permission", True)], [], {"legacy_permission"}),
        ([], [("legacy_permission", "grant")], {"legacy_permission"}),
        ([("legacy_permission", True)], [("legacy_permission", "revoke")], set()),
        ([], [("view_reports", "invalid")], set()),
        ([("view_reports", True)], [("view_reports", "invalid")], {"view_reports"}),
    ],
)
def test_unknown_role_has_no_defaults_but_preserves_explicit_override_behavior(
    role_overrides, user_overrides, expected
):
    assert (
        resolve_effective_permissions(
            "unknown_role",
            role_overrides=role_overrides,
            user_overrides=user_overrides,
        )
        == expected
    )


def test_resolution_does_not_mutate_defaults_inputs_or_subsequent_results():
    original_defaults = {role: permissions.copy() for role, permissions in ROLE_DEFAULTS.items()}
    role_overrides = [("view_reports", True), ("view_surrogates", False)]
    user_overrides = [("view_reports", "revoke"), ("export_data", "grant")]

    result = resolve_effective_permissions(
        "intake_specialist",
        role_overrides=role_overrides,
        user_overrides=user_overrides,
    )

    assert "view_reports" not in result
    assert "view_surrogates" not in result
    assert "export_data" in result
    result.clear()
    developer_result = resolve_effective_permissions("developer")
    developer_result.clear()

    assert ROLE_DEFAULTS == original_defaults
    assert role_overrides == [("view_reports", True), ("view_surrogates", False)]
    assert user_overrides == [("view_reports", "revoke"), ("export_data", "grant")]
    assert (
        resolve_effective_permissions("intake_specialist") == original_defaults["intake_specialist"]
    )
    assert resolve_effective_permissions("developer") == set(PERMISSION_REGISTRY)
