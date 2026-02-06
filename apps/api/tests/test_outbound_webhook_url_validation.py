from __future__ import annotations

import pytest

from app.core.url_validation import validate_outbound_webhook_url


def test_validate_outbound_webhook_url_rejects_non_https():
    with pytest.raises(ValueError):
        validate_outbound_webhook_url("http://example.com/hook")


def test_validate_outbound_webhook_url_rejects_credentials():
    with pytest.raises(ValueError):
        validate_outbound_webhook_url("https://user:pass@example.com/hook")


def test_validate_outbound_webhook_url_rejects_fragment():
    with pytest.raises(ValueError):
        validate_outbound_webhook_url("https://example.com/hook#frag")


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/hook",
        "https://[::1]/hook",
        "https://169.254.169.254/latest/meta-data/",
        "https://10.0.0.1/hook",
        "https://192.168.1.2/hook",
    ],
)
def test_validate_outbound_webhook_url_rejects_private_or_local_ips(url: str):
    with pytest.raises(ValueError):
        validate_outbound_webhook_url(url)


def test_validate_outbound_webhook_url_allows_public_hostname(monkeypatch: pytest.MonkeyPatch):
    def fake_getaddrinfo(host: str, port: int, type=None):  # noqa: A002 - match socket API
        assert host == "example.com"
        assert port == 443
        return [
            # (family, socktype, proto, canonname, sockaddr)
            (2, 1, 6, "", ("93.184.216.34", port)),
        ]

    monkeypatch.setattr("app.core.url_validation.socket.getaddrinfo", fake_getaddrinfo)

    normalized = validate_outbound_webhook_url("HTTPS://example.com/hook?x=1")
    assert normalized == "https://example.com/hook?x=1"


def test_validate_outbound_webhook_url_rejects_hostname_resolving_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_getaddrinfo(host: str, port: int, type=None):  # noqa: A002 - match socket API
        assert host == "evil.example"
        return [
            (2, 1, 6, "", ("127.0.0.1", port)),
        ]

    monkeypatch.setattr("app.core.url_validation.socket.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError):
        validate_outbound_webhook_url("https://evil.example/hook")
