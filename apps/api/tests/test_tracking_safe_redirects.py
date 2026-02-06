from __future__ import annotations

from app.services import tracking_service


def test_wrap_links_in_email_skips_javascript_links():
    html = '<a href="javascript:alert(1)">bad</a> <a href="https://example.com">ok</a>'
    token = tracking_service.generate_tracking_token()

    result = tracking_service.wrap_links_in_email(html, token)

    assert 'href="javascript:alert(1)"' in result
    assert "/tracking/click/" in result


def test_wrap_links_in_email_skips_relative_links():
    html = '<a href="/app">relative</a>'
    token = tracking_service.generate_tracking_token()

    result = tracking_service.wrap_links_in_email(html, token)

    assert result == html
