"""Tests for HTML sanitization helpers used by email templates."""

from app.services import email_service


def test_sanitize_template_html_preserves_blank_paragraphs():
    html = "<p>Hello</p><p></p><p><br></p><p>World</p>"

    sanitized = email_service.sanitize_template_html(html)

    # Empty paragraphs should be normalized to a visible blank line.
    assert "<p>&nbsp;</p>" in sanitized
    assert "<p></p>" not in sanitized


def test_sanitize_template_html_preserves_attributed_blank_paragraphs():
    html = (
        '<p style="text-align:center"></p>'
        '<p class="legacy"><br class="ProseMirror-trailingBreak"></p>'
    )

    sanitized = email_service.sanitize_template_html(html)

    assert sanitized == (
        '<p style="text-align:center">&nbsp;</p>'
        '<p class="legacy">&nbsp;</p>'
    )
