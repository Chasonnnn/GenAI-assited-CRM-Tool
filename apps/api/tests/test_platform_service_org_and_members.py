from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import AlertSeverity, AlertStatus, AlertType, MatchStatus, Role
from app.db.models import (
    AdminActionLog,
    Match,
    Membership,
    Organization,
    SupportSession,
    SystemAlert,
    User,
)
from app.services import pipeline_service, platform_service
from tests.test_tasks_match_scope import _create_intended_parent, _create_surrogate


def test_organization_detail_counts_only_non_terminal_matches_in_organization(
    db, test_org, test_user, default_stage
):
    other_org = Organization(name="Other Organization", slug=f"other-org-{uuid4().hex}")
    other_user = User(email=f"other-{uuid4().hex}@example.com", display_name="Other User")
    db.add_all([other_org, other_user])
    db.flush()
    db.add(
        Membership(organization_id=other_org.id, user_id=other_user.id, role=Role.DEVELOPER.value)
    )
    other_pipeline = pipeline_service.get_or_create_default_pipeline(db, other_org.id)
    other_stage = pipeline_service.get_stage_by_slug(db, other_pipeline.id, "new_unread")
    assert other_stage is not None

    for org, user, stage, statuses in (
        (
            test_org,
            test_user,
            default_stage,
            (
                MatchStatus.PROPOSED,
                MatchStatus.REVIEWING,
                MatchStatus.ACCEPTED,
                MatchStatus.CANCEL_PENDING,
                MatchStatus.REJECTED,
                MatchStatus.CANCELLED,
                MatchStatus.COMPLETED,
            ),
        ),
        (other_org, other_user, other_stage, (MatchStatus.ACCEPTED,)),
    ):
        intended_parent = _create_intended_parent(db, org.id)
        for index, status in enumerate(statuses, start=1):
            surrogate = _create_surrogate(db, org.id, user.id, stage)
            db.add(
                Match(
                    organization_id=org.id,
                    match_number=f"M{10000 + index}",
                    surrogate_id=surrogate.id,
                    intended_parent_id=intended_parent.id,
                    proposed_by_user_id=user.id,
                    status=status.value,
                )
            )
    db.flush()

    detail = platform_service.get_organization_detail(db, test_org.id)
    assert detail is not None
    assert detail["active_match_count"] == 4
    other_detail = platform_service.get_organization_detail(db, other_org.id)
    assert other_detail is not None
    assert other_detail["active_match_count"] == 1


def test_platform_validation_and_hash_helpers(monkeypatch):
    value = platform_service.hmac_hash("abc123")
    assert isinstance(value, str)
    assert len(value) == 64

    request = SimpleNamespace(client=SimpleNamespace(host="10.0.0.1"), headers={})
    assert platform_service._get_ip_from_request(request) == "10.0.0.1"

    assert platform_service._validate_role(Role.DEVELOPER.value) == Role.DEVELOPER.value
    with pytest.raises(ValueError):
        platform_service._validate_role("invalid-role")

    monkeypatch.setattr(platform_service.settings, "SUPPORT_SESSION_ALLOW_READ_ONLY", True)
    assert platform_service._validate_support_mode("write") == "write"
    assert platform_service._validate_support_mode("read_only") == "read_only"
    with pytest.raises(ValueError):
        platform_service._validate_support_mode("invalid")

    assert platform_service._validate_reason_code("other") == "other"
    with pytest.raises(ValueError):
        platform_service._validate_reason_code("not-allowed")


def test_platform_support_session_create_and_revoke(monkeypatch, db, test_org, test_user):
    audit_calls: list[str] = []

    monkeypatch.setattr(
        platform_service, "create_support_session_token", lambda **kwargs: "support-token"
    )
    monkeypatch.setattr(platform_service.session_service, "create_session", lambda **kwargs: None)
    monkeypatch.setattr(
        platform_service,
        "log_admin_action",
        lambda **kwargs: audit_calls.append(kwargs["action"]),
    )

    session_data, token, ttl = platform_service.create_support_session(
        db=db,
        actor_id=test_user.id,
        org_id=test_org.id,
        role=Role.ADMIN.value,
        reason_code="other",
        reason_text="Investigating issue",
        mode="write",
        token_version=test_user.token_version,
        mfa_verified=True,
        mfa_required=True,
        request=None,
    )
    assert token == "support-token"
    assert ttl > 0
    assert session_data["org_id"] == str(test_org.id)
    assert "support_session.create" in audit_calls

    support_session = (
        db.query(SupportSession).filter(SupportSession.actor_user_id == test_user.id).first()
    )
    assert support_session is not None

    revoked = platform_service.revoke_support_session(
        db=db,
        session_id=support_session.id,
        actor_id=test_user.id,
        request=None,
    )
    assert revoked is not None
    assert revoked.revoked_at is not None
    assert "support_session.revoke" in audit_calls


def test_platform_member_list_update_and_mfa_reset(monkeypatch, db, test_org, test_user):
    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == test_user.id,
            Membership.organization_id == test_org.id,
        )
        .first()
    )
    assert membership is not None

    actions: list[str] = []
    monkeypatch.setattr(
        platform_service,
        "log_admin_action",
        lambda **kwargs: actions.append(kwargs["action"]),
    )
    monkeypatch.setattr(
        platform_service.duo_admin_service,
        "reset_user_enrollment",
        lambda **kwargs: SimpleNamespace(
            duo_user_id=None,
            actions=[],
            deleted_user=False,
        ),
    )
    monkeypatch.setattr(
        platform_service.mfa_service, "disable_mfa", lambda db, user, **kwargs: None
    )
    monkeypatch.setattr(
        platform_service.session_service, "revoke_all_user_sessions", lambda *args, **kwargs: None
    )

    members = platform_service.list_members(db, test_org.id)
    assert members
    assert members[0]["email"]

    updated = platform_service.update_member(
        db=db,
        org_id=test_org.id,
        member_id=membership.id,
        actor_id=test_user.id,
        role=Role.ADMIN.value,
        is_active=True,
        request=None,
    )
    assert updated["role"] == Role.ADMIN.value
    assert "member.update" in actions

    result = platform_service.reset_member_mfa(
        db=db,
        org_id=test_org.id,
        member_id=membership.id,
        actor_id=test_user.id,
        request=None,
    )
    assert result["message"] == "MFA reset successfully"
    assert "member.mfa.reset" in actions


def test_platform_update_member_not_found_raises(db, test_org, test_user):
    with pytest.raises(ValueError, match="Member not found"):
        platform_service.update_member(
            db=db,
            org_id=test_org.id,
            member_id=uuid4(),
            actor_id=test_user.id,
            role=Role.ADMIN.value,
            is_active=True,
        )


def test_platform_admin_action_log_pagination_keeps_exact_total(db, test_org, test_user):
    now = datetime.now(UTC)
    for index in range(3):
        db.add(
            AdminActionLog(
                actor_user_id=test_user.id,
                action=f"org.test.{index}",
                target_organization_id=test_org.id,
                metadata_={"index": index},
                created_at=now + timedelta(seconds=index),
            )
        )
    db.flush()

    items, total = platform_service.get_admin_action_logs(
        db=db,
        org_id=test_org.id,
        limit=2,
        offset=0,
    )

    assert len(items) == 2
    assert total == 3


def test_platform_alert_pagination_keeps_exact_total_on_full_page(db, test_org):
    now = datetime.now(UTC)
    for index in range(3):
        db.add(
            SystemAlert(
                organization_id=test_org.id,
                dedupe_key=f"platform-alert-{index}",
                alert_type=AlertType.API_ERROR.value,
                severity=AlertSeverity.ERROR.value,
                status=AlertStatus.OPEN.value,
                title=f"Platform alert {index}",
                message="Test alert",
                first_seen_at=now + timedelta(seconds=index),
                last_seen_at=now + timedelta(seconds=index),
            )
        )
    db.flush()

    items, total = platform_service.list_platform_alerts(
        db=db,
        status=AlertStatus.OPEN.value,
        severity=AlertSeverity.ERROR.value,
        org_id=test_org.id,
        limit=2,
        offset=0,
    )

    assert len(items) == 2
    assert total == 3
