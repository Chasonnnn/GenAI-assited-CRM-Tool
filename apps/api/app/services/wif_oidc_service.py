"""OIDC helper utilities for Workload Identity Federation."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings


DEFAULT_TOKEN_TTL_SECONDS = 300  # 5 minutes


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _normalize_issuer(issuer: str) -> str:
    return issuer.rstrip("/")


@lru_cache(maxsize=1)
def _load_private_key() -> rsa.RSAPrivateKey:
    if not settings.WIF_OIDC_PRIVATE_KEY:
        raise ValueError("WIF_OIDC_PRIVATE_KEY not configured")
    return serialization.load_pem_private_key(settings.WIF_OIDC_PRIVATE_KEY.encode(), password=None)


@lru_cache(maxsize=1)
def _load_public_key() -> rsa.RSAPublicKey:
    return _load_private_key().public_key()


def _derive_kid(public_key: rsa.RSAPublicKey) -> str:
    data = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(data).hexdigest()[:16]


def get_oidc_issuer() -> str:
    issuer = settings.WIF_OIDC_ISSUER or settings.API_BASE_URL
    if not issuer:
        raise ValueError("WIF_OIDC_ISSUER or API_BASE_URL must be configured")
    return _normalize_issuer(issuer)


def get_jwks() -> dict[str, Any]:
    public_key = _load_public_key()
    numbers = public_key.public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": settings.WIF_OIDC_KEY_ID or _derive_kid(public_key),
        "n": _base64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": _base64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }
    return {"keys": [jwk]}


def create_subject_token(
    *,
    audience: str,
    subject: str,
    claims: dict[str, Any] | None = None,
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "iss": get_oidc_issuer(),
        "sub": subject,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    if claims:
        payload.update(claims)

    private_key = _load_private_key()
    headers = {"kid": settings.WIF_OIDC_KEY_ID or _derive_kid(private_key.public_key())}
    return jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
