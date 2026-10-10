"""Emails must link the organization logo by a URL that does not expire."""

from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services import (
    attachment_service,
    email_service,
    email_test_send_service,
    media_service,
    signature_template_service,
)

S3_LOGO = "https://crm-attachments.s3.amazonaws.com/logos/org/logo.png"


@pytest.fixture
def s3_logo(db, test_org, monkeypatch):
    monkeypatch.setattr(settings, "S3_BUCKET", "crm-attachments", raising=False)

    def fail_if_signed(*_args, **_kwargs):
        raise AssertionError("Email HTML must not embed a presigned logo URL")

    monkeypatch.setattr(attachment_service, "generate_signed_url", fail_if_signed)
    test_org.signature_logo_url = S3_LOGO
    db.commit()
    return test_org


def _stable_url(org) -> str:
    return f"{settings.API_BASE_URL.rstrip('/')}/forms/public/{org.id}/signature-logo?v="


def test_email_logo_url_is_stable_and_versioned(s3_logo):
    url = media_service.email_logo_url(s3_logo)

    assert url.startswith(_stable_url(s3_logo))
    assert "X-Amz" not in url and "logos/org" not in url
    assert url == media_service.email_logo_url(s3_logo)

    s3_logo.signature_logo_url = S3_LOGO.replace("logo.png", "new.png")
    assert media_service.email_logo_url(s3_logo) != url


def test_email_logo_url_is_empty_without_a_logo(test_org):
    test_org.signature_logo_url = None
    assert media_service.email_logo_url(test_org) == ""
    assert media_service.email_logo_url(None) == ""


def test_record_and_test_send_variables_use_the_stable_logo_url(db, s3_logo):
    record = SimpleNamespace(
        owner_type=None,
        owner_id=None,
        organization_id=s3_logo.id,
        full_name="Avery Lee",
        email="",
        phone="",
        state="",
    )

    record_variables = email_service._build_record_contact_template_variables(db, record, s3_logo)
    sample_variables = email_test_send_service.build_sample_variables(
        db, org_id=s3_logo.id, to_email="qa@example.com", actor_display_name="QA"
    )

    assert record_variables["org_logo_url"].startswith(_stable_url(s3_logo))
    assert sample_variables["org_logo_url"].startswith(_stable_url(s3_logo))


def test_signature_html_uses_the_stable_logo_url(db, s3_logo, test_user):
    html = signature_template_service.render_signature_html(db, s3_logo.id, test_user.id)

    assert f'src="{_stable_url(s3_logo)}' in html
