from starlette.requests import Request

from app.core.config import settings
from app.services import session_service


def _make_request(headers: dict[str, str] | None = None, client_host: str = "10.0.0.1") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": (client_host, 12345),
    }
    if headers:
        scope["headers"] = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request(scope)


def test_get_client_ip_ignores_forwarded_when_not_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    request = _make_request({"X-Forwarded-For": "203.0.113.10"}, client_host="198.51.100.5")
    assert session_service.get_client_ip(request) == "198.51.100.5"


def test_get_client_ip_uses_forwarded_when_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    request = _make_request({"X-Forwarded-For": "203.0.113.10, 10.0.0.2"}, client_host="198.51.100.5")
    assert session_service.get_client_ip(request) == "203.0.113.10"


def test_get_client_ip_falls_back_to_client(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    request = _make_request(client_host="198.51.100.5")
    assert session_service.get_client_ip(request) == "198.51.100.5"
