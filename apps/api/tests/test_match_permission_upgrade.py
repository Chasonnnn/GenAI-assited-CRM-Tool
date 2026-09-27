"""Reviewed activation preserves match authority and labels historical action gains."""

import pytest

from app.db.models import RolePermission, UserPermissionOverride
from app.schemas.permission_policy import PermissionPolicyChanges
from app.services import permission_policy_service as policy_service
from app.services import permission_service
from tests.test_permission_policy import add_member
from tests.test_permission_policy import ready_review as ready_review


@pytest.mark.parametrize(
    "role,granted", [("case_manager", False), ("case_manager", True), ("operations", True)]
)
def test_upgrade_maps_legacy_role_match_authority(
    db, test_org, test_user, ready_review, role, granted
):
    user, _ = add_member(db, test_org.id, role)
    db.add(
        RolePermission(
            organization_id=test_org.id, role=role, permission="propose_matches", is_granted=granted
        )
    )
    db.flush()
    changes = PermissionPolicyChanges()
    preview = policy_service.preview(db, test_org.id, changes)
    member = next(item for item in preview.members if item.user_id == user.id)
    for key in ("decide_matches", "close_matches"):
        assert (key in member.proposed) is granted
        assert preview.role_permissions[role][key] is granted
    policy_service.activate(db, test_org.id, test_user.id, changes, preview.digest)
    effective = permission_service.get_effective_permissions(db, test_org.id, user.id, role)
    for key in ("decide_matches", "close_matches"):
        assert (key in effective) is granted


def test_upgrade_maps_individual_legacy_match_grant(db, test_org, test_user, ready_review):
    user, _ = add_member(db, test_org.id)
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=user.id,
            permission="propose_matches",
            override_type="grant",
        )
    )
    db.flush()
    changes = PermissionPolicyChanges()
    preview = policy_service.preview(db, test_org.id, changes)
    member = next(item for item in preview.members if item.user_id == user.id)
    assert {"decide_matches", "close_matches"} <= set(member.proposed)
    policy_service.activate(db, test_org.id, test_user.id, changes, preview.digest)
    assert {"decide_matches", "close_matches"} <= permission_service.get_effective_permissions(
        db, test_org.id, user.id, "intake_specialist"
    )
    assert {
        row.permission for row in db.query(UserPermissionOverride).filter_by(user_id=user.id)
    } == {"propose_matches", "decide_matches", "close_matches"}


def test_preview_labels_proposing_gain_without_granting_legacy_edit_permission(
    db, test_org, test_user, ready_review
):
    user, _ = add_member(db, test_org.id, "case_manager")
    db.add(
        RolePermission(
            organization_id=test_org.id,
            role="case_manager",
            permission="propose_matches",
            is_granted=False,
        )
    )
    db.flush()
    changes = PermissionPolicyChanges()
    preview = policy_service.preview(db, test_org.id, changes)
    member = next(item for item in preview.members if item.user_id == user.id)
    assert preview.match_action_baseline == "pre_step_7"
    assert member.previous_match_actions == []
    assert member.proposed_match_actions == ["propose"]
    assert member.gained_match_actions == ["propose"]
    assert member.lost_match_actions == []
    assert "propose_matches" not in member.current
    assert "propose_matches" not in member.proposed
    assert "propose_matches" not in member.gained
    policy_service.activate(db, test_org.id, test_user.id, changes, preview.digest)
    current = policy_service.preview(db, test_org.id, changes)
    member = next(item for item in current.members if item.user_id == user.id)
    assert current.match_action_baseline == "current"
    assert member.previous_match_actions == ["propose"]
    assert member.gained_match_actions == []


def test_reviewed_action_changes_override_legacy_mapping(db, test_org, ready_review):
    user, _ = add_member(db, test_org.id, "case_manager")
    preview = policy_service.preview(
        db,
        test_org.id,
        PermissionPolicyChanges(
            role_permissions={"case_manager": {"decide_matches": False, "close_matches": True}}
        ),
    )
    member = next(item for item in preview.members if item.user_id == user.id)
    assert "decide_matches" not in member.proposed
    assert "close_matches" in member.proposed
    assert member.lost_match_actions == ["accept", "decline"]


@pytest.mark.parametrize("resolution", ["remove", "deny_for_role"])
def test_legacy_match_revoke_resolution_updates_both_action_keys(
    db, test_org, test_user, ready_review, resolution
):
    from app.schemas.permission_policy import RevokeResolution

    user, _ = add_member(db, test_org.id, "case_manager")
    revoke = UserPermissionOverride(
        organization_id=test_org.id,
        user_id=user.id,
        permission="propose_matches",
        override_type="revoke",
    )
    db.add(revoke)
    db.flush()
    changes = PermissionPolicyChanges(
        revoke_resolutions=[RevokeResolution(override_id=revoke.id, action=resolution)]
    )
    preview = policy_service.preview(db, test_org.id, changes)
    member = next(item for item in preview.members if item.user_id == user.id)
    assert member.previous_match_actions == []
    assert "propose" in member.gained_match_actions
    for permission in ("decide_matches", "close_matches"):
        assert (permission in member.proposed) is (resolution == "remove")
    policy_service.activate(db, test_org.id, test_user.id, changes, preview.digest)
    effective = permission_service.get_effective_permissions(
        db, test_org.id, user.id, "case_manager"
    )
    for permission in ("decide_matches", "close_matches"):
        assert (permission in effective) is (resolution == "remove")
