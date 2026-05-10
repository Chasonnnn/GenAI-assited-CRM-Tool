"""OIDC well-known endpoints for Workload Identity Federation."""

import pytest

from app.core.config import settings
from app.services import wif_oidc_service


def _clear_wif_key_cache() -> None:
    wif_oidc_service._load_private_key.cache_clear()
    wif_oidc_service._load_public_key.cache_clear()


@pytest.mark.asyncio
async def test_oidc_openid_configuration(client):
    response = await client.get("/.well-known/openid-configuration")
    assert response.status_code == 200

    payload = response.json()
    assert payload["issuer"] == "https://test"
    assert payload["jwks_uri"] == "https://test/.well-known/jwks.json"
    assert "RS256" in payload.get("id_token_signing_alg_values_supported", [])


@pytest.mark.asyncio
async def test_oidc_jwks_exposes_signing_key(client):
    response = await client.get("/.well-known/jwks.json")
    assert response.status_code == 200

    payload = response.json()
    keys = payload.get("keys")
    assert isinstance(keys, list)
    assert keys

    key = keys[0]
    assert key.get("kty") == "RSA"
    assert key.get("use") == "sig"
    assert key.get("kid")


@pytest.mark.asyncio
async def test_oidc_openid_configuration_returns_404_when_signing_key_is_unconfigured(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "WIF_OIDC_PRIVATE_KEY", "", raising=False)
    _clear_wif_key_cache()

    response = await client.get("/.well-known/openid-configuration")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_oidc_jwks_returns_404_when_signing_key_is_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "WIF_OIDC_PRIVATE_KEY", "", raising=False)
    _clear_wif_key_cache()

    response = await client.get("/.well-known/jwks.json")

    assert response.status_code == 404
