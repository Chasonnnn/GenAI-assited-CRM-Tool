"""Tests for HTML sanitization helpers used by email templates."""

from app.services import email_service


def test_sanitize_template_html_preserves_blank_paragraphs():
    html = "<p>Hello</p><p></p><p><br></p><p>World</p>"

    sanitized = email_service.sanitize_template_html(html)

    # Empty paragraphs should be normalized to a visible blank line.
    assert "<p>&nbsp;</p>" in sanitized
    assert "<p></p>" not in sanitized
