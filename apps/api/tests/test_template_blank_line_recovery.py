"""Fail-closed recovery contracts for the Template Studio blank-line regression."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.enums import AuditEventType
from app.db.models import AuditLog
from app.services import (
    email_service,
    email_template_draft_service,
    template_blank_line_recovery_service,
    version_service,
)


def _create_regressed_template(db, test_org, test_user):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Welcome",
        subject="Original subject",
        body="Hi {{first_name}},\n\nThanks for reaching out.",
        scope="org",
    )
    return email_service.update_template(
        db,
        template=template,
        user_id=test_user.id,
        subject="Current subject",
        body="<p>Hi {{first_name}},</p><p>Thanks for reaching out.</p>",
        expected_version=1,
        comment="Published from Template Studio",
    )


def test_blank_line_recovery_plan_requires_identical_content_and_more_spacing(
    db,
    test_org,
    test_user,
):
    template = _create_regressed_template(db, test_org, test_user)

    plan = template_blank_line_recovery_service.build_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
    )

    assert plan.current_version == 2
    assert plan.target_version == 1
    assert plan.visible_text_equal is True
    assert plan.variable_tokens_equal is True
    assert plan.structural_content_equal is True
    assert plan.current_blank_line_count == 0
    assert plan.target_blank_line_count == 1
    assert plan.eligible is True
    assert plan.current_body_sha256 != plan.target_body_sha256


def test_blank_line_recovery_is_body_only_and_appends_history(
    db,
    test_org,
    test_user,
):
    template = _create_regressed_template(db, test_org, test_user)
    plan = template_blank_line_recovery_service.build_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
    )

    recovered = template_blank_line_recovery_service.apply_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
        expected_current_version=plan.current_version,
        expected_current_body_sha256=plan.current_body_sha256,
        expected_target_body_sha256=plan.target_body_sha256,
        review_reason="Recover spacing lost during Template Studio publish",
    )

    assert recovered.current_version == 3
    assert recovered.subject == "Current subject"
    assert recovered.body == "Hi {{first_name}},\n\nThanks for reaching out."
    assert recovered.name == "Welcome"

    versions = email_service.get_template_versions(
        db,
        test_org.id,
        template.id,
    )
    assert [version.version for version in versions[:3]] == [3, 2, 1]
    assert versions[0].comment == "Recovered blank-line formatting"

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == AuditEventType.CONFIG_TEMPLATE_UPDATED.value,
            AuditLog.target_id == template.id,
        )
        .one()
    )
    assert audit.actor_user_id is None
    assert audit.target_type == "email_template"
    assert audit.before_version_id == versions[1].id
    assert audit.after_version_id == versions[0].id
    assert audit.prev_hash
    assert audit.entry_hash
    assert audit.details == {
        "action": "blank_line_recovery",
        "review_reason": "Recover spacing lost during Template Studio publish",
        "from_version": 2,
        "to_version": 3,
        "source_version": 1,
        "current_body_sha256": plan.current_body_sha256,
        "recovered_body_sha256": plan.target_body_sha256,
        "blank_lines_before": 0,
        "blank_lines_after": 1,
    }
    assert "Hi {{first_name}}" not in str(audit.details)


@pytest.mark.parametrize(
    "changed_body",
    [
        "<p>Hi {{first_name}},</p><p>Different wording.</p>",
        "<p>Hi {{full_name}},</p><p>Thanks for reaching out.</p>",
    ],
)
def test_blank_line_recovery_refuses_content_or_variable_changes(
    db,
    test_org,
    test_user,
    changed_body,
):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Unsafe recovery",
        subject="Subject",
        body="Hi {{first_name}},\n\nThanks for reaching out.",
        scope="org",
    )
    template = email_service.update_template(
        db,
        template=template,
        user_id=test_user.id,
        body=changed_body,
        expected_version=1,
    )

    plan = template_blank_line_recovery_service.build_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
    )

    assert plan.eligible is False
    with pytest.raises(
        template_blank_line_recovery_service.TemplateBlankLineRecoveryConflict,
        match="not a spacing-only change",
    ):
        template_blank_line_recovery_service.apply_recovery_plan(
            db,
            organization_id=test_org.id,
            template_id=template.id,
            target_version=1,
            expected_current_version=plan.current_version,
            expected_current_body_sha256=plan.current_body_sha256,
            expected_target_body_sha256=plan.target_body_sha256,
            review_reason="Must not restore changed content",
        )

    db.refresh(template)
    assert template.current_version == 2
    assert template.body == changed_body


def test_blank_line_recovery_refuses_a_stale_review_fingerprint(
    db,
    test_org,
    test_user,
):
    template = _create_regressed_template(db, test_org, test_user)
    plan = template_blank_line_recovery_service.build_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
    )

    with pytest.raises(
        template_blank_line_recovery_service.TemplateBlankLineRecoveryConflict,
        match="review no longer matches",
    ):
        template_blank_line_recovery_service.apply_recovery_plan(
            db,
            organization_id=test_org.id,
            template_id=template.id,
            target_version=1,
            expected_current_version=plan.current_version,
            expected_current_body_sha256="0" * 64,
            expected_target_body_sha256=plan.target_body_sha256,
            review_reason="Stale review",
        )

    db.refresh(template)
    assert template.current_version == 2


def test_blank_line_recovery_refuses_cross_organization_lookup(
    db,
    test_org,
    test_user,
):
    template = _create_regressed_template(db, test_org, test_user)

    with pytest.raises(
        template_blank_line_recovery_service.TemplateBlankLineRecoveryConflict,
        match="Template was not found",
    ):
        template_blank_line_recovery_service.build_recovery_plan(
            db,
            organization_id=uuid4(),
            template_id=template.id,
            target_version=1,
        )


@pytest.mark.parametrize(
    ("target_body", "changed_body"),
    [
        (
            '<p>Hello</p><p><br></p><p><a href="https://safe.example">Visit</a></p>',
            '<p>Hello</p><p><a href="https://evil.example">Visit</a></p>',
        ),
        (
            '<p>Hello</p><p><br></p><img src="https://safe.example/a.png" alt="A">',
            '<p>Hello</p><img src="https://safe.example/b.png" alt="B">',
        ),
        (
            '<p style="color:red">Hello</p><p><br></p>',
            '<p style="color:blue">Hello</p>',
        ),
        (
            "<table><tr><td>Hello</td></tr></table><p><br></p>",
            "<div>Hello</div>",
        ),
    ],
)
def test_blank_line_recovery_refuses_non_spacing_markup_changes(
    db,
    test_org,
    test_user,
    target_body,
    changed_body,
):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"Unsafe markup {uuid4()}",
        subject="Subject",
        body=target_body,
        scope="org",
    )
    template = email_service.update_template(
        db,
        template=template,
        user_id=test_user.id,
        body=changed_body,
        expected_version=1,
    )

    plan = template_blank_line_recovery_service.build_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
    )

    assert plan.visible_text_equal is True
    assert plan.variable_tokens_equal is True
    assert plan.target_blank_line_count > plan.current_blank_line_count
    assert plan.structural_content_equal is False
    assert plan.eligible is False


def test_blank_line_recovery_reviews_the_exact_sanitized_body_that_is_committed(
    db,
    test_org,
    test_user,
):
    template = _create_regressed_template(db, test_org, test_user)
    historical = version_service.get_version(
        db,
        test_org.id,
        email_service.ENTITY_TYPE,
        template.id,
        1,
    )
    payload = version_service.decrypt_payload(historical.payload_encrypted)
    payload["body"] = "<p>Hi {{first_name}},</p><p><br></p><p>Thanks for reaching out.</p>"
    historical.payload_encrypted = version_service.encrypt_payload(payload)
    historical.checksum = version_service.compute_checksum(payload)
    db.commit()

    plan = template_blank_line_recovery_service.build_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
    )
    expected_body = "<p>Hi {{first_name}},</p><p>&nbsp;</p><p>Thanks for reaching out.</p>"

    recovered = template_blank_line_recovery_service.apply_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
        expected_current_version=plan.current_version,
        expected_current_body_sha256=plan.current_body_sha256,
        expected_target_body_sha256=plan.target_body_sha256,
        review_reason="Recover reviewed spacing",
    )

    assert recovered.body == expected_body
    assert template_blank_line_recovery_service.body_sha256(recovered.body) == (
        plan.target_body_sha256
    )


def test_blank_line_recovery_refuses_non_body_current_history_drift(
    db,
    test_org,
    test_user,
):
    template = _create_regressed_template(db, test_org, test_user)
    current = version_service.get_version(
        db,
        test_org.id,
        email_service.ENTITY_TYPE,
        template.id,
        template.current_version,
    )
    payload = version_service.decrypt_payload(current.payload_encrypted)
    payload["subject"] = "Different recorded subject"
    current.payload_encrypted = version_service.encrypt_payload(payload)
    current.checksum = version_service.compute_checksum(payload)
    db.commit()

    with pytest.raises(
        template_blank_line_recovery_service.TemplateBlankLineRecoveryConflict,
        match="Published template does not match its version history",
    ):
        template_blank_line_recovery_service.build_recovery_plan(
            db,
            organization_id=test_org.id,
            template_id=template.id,
            target_version=1,
        )


def test_blank_line_recovery_refuses_to_stale_an_open_studio_draft(
    db,
    test_org,
    test_user,
):
    template = _create_regressed_template(db, test_org, test_user)
    plan = template_blank_line_recovery_service.build_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
    )
    email_template_draft_service.create_draft_from_template(
        db,
        template=template,
        user_id=test_user.id,
    )

    with pytest.raises(
        template_blank_line_recovery_service.TemplateBlankLineRecoveryConflict,
        match="open Studio draft",
    ):
        template_blank_line_recovery_service.apply_recovery_plan(
            db,
            organization_id=test_org.id,
            template_id=template.id,
            target_version=1,
            expected_current_version=plan.current_version,
            expected_current_body_sha256=plan.current_body_sha256,
            expected_target_body_sha256=plan.target_body_sha256,
            review_reason="Must not stale a user draft",
        )

    db.refresh(template)
    assert template.current_version == 2


def test_blank_line_recovery_rolls_back_if_audit_append_fails(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    template = _create_regressed_template(db, test_org, test_user)
    plan = template_blank_line_recovery_service.build_recovery_plan(
        db,
        organization_id=test_org.id,
        template_id=template.id,
        target_version=1,
    )

    def _fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(
        template_blank_line_recovery_service.audit_service,
        "log_event",
        _fail_audit,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        template_blank_line_recovery_service.apply_recovery_plan(
            db,
            organization_id=test_org.id,
            template_id=template.id,
            target_version=1,
            expected_current_version=plan.current_version,
            expected_current_body_sha256=plan.current_body_sha256,
            expected_target_body_sha256=plan.target_body_sha256,
            review_reason="Audit append must be atomic",
        )

    db.refresh(template)
    assert template.current_version == 2
    versions = email_service.get_template_versions(db, test_org.id, template.id)
    assert [version.version for version in versions] == [2, 1]
