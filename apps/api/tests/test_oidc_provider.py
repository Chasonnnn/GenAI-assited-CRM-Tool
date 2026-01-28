"""OIDC well-known endpoints for Workload Identity Federation."""

import pytest


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
