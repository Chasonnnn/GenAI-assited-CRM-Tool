"""Immutable messaging-template and media-policy service contracts."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest

from app.db.models import MessageTemplate, TwilioSettings
from app.services import message_content_service


def _valid_enrollment_body(*, purpose: str = "operational") -> str:
    return (
        f"EWI Surrogacy {purpose} program. Message frequency varies. "
        "Message and data rates may apply. Reply HELP for help and STOP to opt out."
    )


def _configure_twilio_policy(db, organization_id, *, phi_enabled: bool = False) -> TwilioSettings:
    configured_at = datetime(2026, 7, 31, 20, 0, tzinfo=UTC)
    settings = TwilioSettings(
        organization_id=organization_id,
        legal_messaging_brand="EWI Surrogacy",
        expected_frequency="Message frequency varies",
        twilio_edition="hipaa_eligible" if phi_enabled else None,
        baa_verified_at=configured_at if phi_enabled else None,
        compliance_approved_at=configured_at if phi_enabled else None,
        phi_enabled=phi_enabled,
    )
    db.add(settings)
    db.commit()
    return settings


def test_template_versions_are_immutable_and_publish_is_exact_and_idempotent(
    db,
    test_org,
    test_user,
):
    _configure_twilio_policy(db, test_org.id)
    first = message_content_service.create_template_draft(
        db,
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Enrollment",
        purpose="operational",
        body=_valid_enrollment_body(),
        is_enrollment_confirmation=True,
        content_classification="no_phi",
    )
    original_body = first.body
    assert first.version == 1
    assert first.status == "draft"
    assert first.content_hash == hashlib.sha256(original_body.encode()).hexdigest()

    second = message_content_service.create_next_template_version(
        db,
        organization_id=test_org.id,
        template_key=first.template_key,
        created_by_user_id=test_user.id,
        body=original_body.replace("Reply HELP", "Text HELP"),
    )

    assert second.version == 2
    assert second.id != first.id
    assert db.get(MessageTemplate, first.id).body == original_body

    published_first = message_content_service.publish_template(
        db,
        organization_id=test_org.id,
        template_id=first.id,
    )
    published_at = published_first.published_at
    assert published_first.status == "published"
    assert published_at is not None

    published_again = message_content_service.publish_template(
        db,
        organization_id=test_org.id,
        template_id=first.id,
    )
    assert published_again.published_at == published_at

    published_second = message_content_service.publish_template(
        db,
        organization_id=test_org.id,
        template_id=second.id,
    )
    assert published_second.status == "published"
    assert db.get(MessageTemplate, first.id).status == "retired"


@pytest.mark.parametrize(
    ("body", "missing_fragment"),
    [
        (
            "operational program. Message frequency varies. Message and data rates may apply. "
            "HELP STOP",
            "legal brand",
        ),
        (
            "EWI Surrogacy operational program. Message frequency varies. HELP STOP",
            "message/data rate language",
        ),
        (
            "EWI Surrogacy operational program. Message frequency varies. "
            "Message and data rates may apply. HELP",
            "STOP",
        ),
    ],
)
def test_enrollment_confirmation_publish_requires_complete_disclosure(
    db,
    test_org,
    test_user,
    body,
    missing_fragment,
):
    _configure_twilio_policy(db, test_org.id)
    template = message_content_service.create_template_draft(
        db,
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Incomplete enrollment",
        purpose="operational",
        body=body,
        is_enrollment_confirmation=True,
        content_classification="no_phi",
    )

    with pytest.raises(message_content_service.TemplateDisclosureError) as exc_info:
        message_content_service.publish_template(
            db,
            organization_id=test_org.id,
            template_id=template.id,
        )

    assert missing_fragment in str(exc_info.value)
    assert db.get(MessageTemplate, template.id).status == "draft"


def test_phi_templates_require_a_current_valid_twilio_phi_gate(db, test_org, test_user):
    _configure_twilio_policy(db, test_org.id, phi_enabled=False)

    with pytest.raises(message_content_service.PhiMessagingBlocked):
        message_content_service.create_template_draft(
            db,
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            name="Protected update",
            purpose="operational",
            body="Protected case update",
            is_enrollment_confirmation=False,
            content_classification="phi",
        )

    settings = db.query(TwilioSettings).filter_by(organization_id=test_org.id).one()
    approved_at = datetime(2026, 7, 31, 20, 0, tzinfo=UTC)
    settings.phi_enabled = True
    settings.twilio_edition = "hipaa_eligible"
    settings.baa_verified_at = approved_at
    settings.compliance_approved_at = approved_at
    db.commit()

    allowed = message_content_service.create_template_draft(
        db,
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Protected update",
        purpose="operational",
        body="Protected case update",
        is_enrollment_confirmation=False,
        content_classification="phi",
    )
    assert allowed.content_classification == "phi"


def test_template_reads_are_organization_scoped(db, test_org, test_user):
    first = message_content_service.create_template_draft(
        db,
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Scoped",
        purpose="promotional",
        body="Surrogacy event invitation",
        is_enrollment_confirmation=False,
        content_classification="no_phi",
    )

    assert message_content_service.get_template(db, test_org.id, first.id) == first
    assert message_content_service.get_template(db, uuid.uuid4(), first.id) is None
    assert message_content_service.list_templates(db, uuid.uuid4()) == []
