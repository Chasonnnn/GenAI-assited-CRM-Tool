"""OIDC discovery endpoints for Workload Identity Federation."""

from fastapi import APIRouter, Request

from app.services import wif_oidc_service

router = APIRouter(tags=["OIDC"])


@router.get("/.well-known/openid-configuration")
def openid_configuration(request: Request) -> dict[str, object]:
    issuer = wif_oidc_service.get_oidc_issuer()
    base = issuer.rstrip("/")
    return {
        "issuer": issuer,
        "jwks_uri": f"{base}/.well-known/jwks.json",
        "response_types_supported": ["id_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }


@router.get("/.well-known/jwks.json")
def jwks() -> dict[str, object]:
    return wif_oidc_service.get_jwks()
