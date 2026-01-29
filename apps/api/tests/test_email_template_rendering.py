"""Tests for template rendering and variable escaping."""

from app.services import email_service


def test_render_template_escapes_html_in_body():
    subject, body = email_service.render_template(
        subject="Hi {{full_name}}",
        body="<p>{{full_name}}</p>",
        variables={"full_name": "<b>Alice</b>"},
    )

    assert subject == "Hi <b>Alice</b>"
    assert "<b>" not in body
    assert "&lt;b&gt;Alice&lt;/b&gt;" in body


def test_render_template_strips_newlines_from_subject():
    subject, _ = email_service.render_template(
        subject="Hello {{full_name}}",
        body="<p>{{full_name}}</p>",
        variables={"full_name": "Bob\\r\\nBcc: evil@example.com"},
    )

    assert "\\n" not in subject
    assert "\\r" not in subject
