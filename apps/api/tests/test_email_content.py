"""Tests for provider-neutral email content rendering helpers."""

from app.services.email_content import html_to_text


def test_html_to_text_removes_script_and_style_content():
    result = html_to_text(
        "<style>.hidden { display: none }</style>"
        "<p>Hello <strong>world</strong></p>"
        "<script>alert('secret')</script>"
    )

    assert result == "Hello world"


def test_html_to_text_collapses_whitespace_and_decodes_entities():
    result = html_to_text("<p>Hello&nbsp;   world</p>\n<p>Next &amp; final</p>")

    assert result == "Hello world Next & final"
