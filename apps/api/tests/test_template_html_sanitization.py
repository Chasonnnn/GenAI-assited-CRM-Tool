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

    assert sanitized == ('<p style="text-align:center">&nbsp;</p><p class="legacy">&nbsp;</p>')


def test_sanitize_template_html_keeps_color_only_background_shorthand():
    html = (
        '<a href="https://example.com" style="background: #4F46E5; color: #ffffff">Open</a>'
        "<table><tr><td style='color:#111;background:rgb(17, 24, 39) !important'>Cell</td></tr></table>"
        '<div style="BACKGROUND:white">Box</div>'
    )

    sanitized = email_service.sanitize_template_html(html)

    assert "background-color:#4F46E5" in sanitized
    assert "background-color:rgb(17, 24, 39)" in sanitized
    assert "background-color:white" in sanitized


def test_sanitize_template_html_drops_background_images():
    html = (
        '<div style="background: url(https://tracker.example/p.gif) #fff; color: red">A</div>'
        '<div style="background: linear-gradient(red, blue)">B</div>'
    )

    sanitized = email_service.sanitize_template_html(html)

    assert "url(" not in sanitized
    assert "gradient" not in sanitized
    assert "color:red" in sanitized
