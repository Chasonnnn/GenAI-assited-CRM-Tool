"""URL validation helpers for outbound HTTP requests (SSRF defense)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


def _is_ip_global(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # `is_global` is the closest thing to "publicly routable" we get in stdlib.
    # It rejects loopback, link-local, private RFC1918, multicast, etc.
    return ip.is_global


def validate_outbound_webhook_url(url: str) -> str:
    """
    Validate a user-configurable outbound webhook URL.

    Security goals:
    - Prevent SSRF to localhost, RFC1918, link-local, etc.
    - Allow only https:// URLs.
    - Disallow credentials in the URL.

    Returns a normalized URL (lowercased scheme, no fragment) or raises ValueError.
    """
    candidate = (url or "").strip()
    if not candidate:
        raise ValueError("Webhook URL is required")

    parts = urlsplit(candidate)
    scheme = (parts.scheme or "").lower()
    if scheme != "https":
        raise ValueError("Webhook URL must start with https://")

    if not parts.netloc:
        raise ValueError("Webhook URL must include a host")

    if parts.username or parts.password:
        raise ValueError("Webhook URL must not include credentials")

    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise ValueError("Webhook URL must include a host")

    if parts.fragment:
        raise ValueError("Webhook URL must not include a fragment")

    # Validate IP literals directly.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if not _is_ip_global(ip):
            raise ValueError("Webhook URL host is not allowed")
        normalized = urlunsplit((scheme, parts.netloc, parts.path, parts.query, ""))
        return normalized

    # Resolve DNS to defend against internal hostnames and tricky IP representations.
    port = parts.port or 443
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except Exception as exc:
        raise ValueError("Webhook URL host could not be resolved") from exc

    resolved_ips: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_str = sockaddr[0]
        try:
            resolved_ips.add(ipaddress.ip_address(ip_str))
        except ValueError:
            continue

    if not resolved_ips:
        raise ValueError("Webhook URL host could not be resolved")

    for resolved in resolved_ips:
        if not _is_ip_global(resolved):
            raise ValueError("Webhook URL host is not allowed")

    normalized = urlunsplit((scheme, parts.netloc, parts.path, parts.query, ""))
    return normalized
