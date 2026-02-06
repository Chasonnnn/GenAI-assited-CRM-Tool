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


def test_render_template_supports_whitespace_in_tokens():
    subject, body = email_service.render_template(
        subject="Hi {{ full_name }}",
        body="<p>{{ full_name }}</p>",
        variables={"full_name": "Alice"},
    )

    assert subject == "Hi Alice"
    assert "<p>Alice</p>" in body


def test_render_template_preserves_emojis_in_static_and_variable_content():
    subject, body = email_service.render_template(
        subject="Hi 👋 {{ full_name }}",
        body="<p>Welcome 😊 {{ full_name }}</p>",
        variables={"full_name": "Alice 😊"},
    )

    assert subject == "Hi 👋 Alice 😊"
    assert "<p>Welcome 😊 Alice 😊</p>" in body
