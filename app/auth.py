"""ZITADEL OIDC helpers using Authlib + PKCE."""

import base64
import hashlib
import secrets
from typing import Any, Optional

import httpx
from authlib.integrations.starlette_client import OAuth
from authlib.oidc.core import CodeIDToken
from jose import jwt
from jose.exceptions import JWTError
from starlette.config import Config
from starlette.requests import Request

from app import config

oauth = OAuth(Config(environ={
    "ZITADEL_CLIENT_ID": config.OIDC_CLIENT_ID,
    "ZITADEL_SERVER_METADATA_URL": config.OIDC_DISCOVERY_URL,
}))

oauth.register(
    name="zitadel",
    client_id=config.OIDC_CLIENT_ID,
    server_metadata_url=config.OIDC_DISCOVERY_URL,
    client_kwargs={
        "scope": " ".join(config.OIDC_SCOPES),
        "code_challenge_method": "S256",
    },
)


def generate_pkce() -> dict[str, str]:
    """Generate PKCE verifier and challenge."""
    verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(48)
    ).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return {"verifier": verifier, "challenge": challenge}


def generate_state_nonce() -> str:
    return secrets.token_urlsafe(32)


async def fetch_jwks() -> dict[str, Any]:
    async with httpx.AsyncClient(verify=True) as client:
        meta_resp = await client.get(config.OIDC_DISCOVERY_URL)
        meta_resp.raise_for_status()
        metadata = meta_resp.json()
        jwks_uri = metadata["jwks_uri"]
        jwks_resp = await client.get(jwks_uri)
        jwks_resp.raise_for_status()
        return jwks_resp.json()


def decode_id_token(
    token: str,
    jwks: dict[str, Any],
    nonce: Optional[str] = None,
    access_token: Optional[str] = None,
) -> dict[str, Any]:
    """Validate and decode the ZITADEL ID token."""
    claims = jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        issuer=config.OIDC_ISSUER,
        audience=config.OIDC_CLIENT_ID,
        access_token=access_token,
        options={
            "verify_exp": True,
            "verify_iss": True,
            "verify_aud": True,
            "verify_sub": True,
            "require_exp": True,
        },
    )
    if nonce and claims.get("nonce") != nonce:
        raise JWTError("Invalid nonce in ID token")
    return claims


def get_roles_from_claims(claims: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract project roles from ZITADEL role claim.

    ZITADEL returns roles under a single-project claim keyed by role name, e.g.:
    {
      "urn:zitadel:iam:org:project:roles": {
        "role-name": {
          "org-id": "org-domain"
        }
      }
    }
    """
    roles_claim = claims.get("urn:zitadel:iam:org:project:roles")
    if not roles_claim or not isinstance(roles_claim, dict):
        return []

    roles: list[dict[str, Any]] = []
    for role_key, org_map in roles_claim.items():
        if not isinstance(org_map, dict):
            continue
        for org_id, org_domain in org_map.items():
            roles.append({"role": role_key, "org_id": org_id, "org_domain": org_domain})
    return roles


def get_user_info(claims: dict[str, Any]) -> dict[str, Any]:
    # ZITADEL returns resourceowner as flat, suffixed claim keys rather than
    # a nested object, e.g. "urn:zitadel:iam:user:resourceowner:name".
    return {
        "sub": claims.get("sub"),
        "email": claims.get("email"),
        "email_verified": claims.get("email_verified"),
        "name": claims.get("name"),
        "given_name": claims.get("given_name"),
        "family_name": claims.get("family_name"),
        "preferred_username": claims.get("preferred_username"),
        "picture": claims.get("picture"),
        "organization": claims.get("urn:zitadel:iam:user:resourceowner:name")
        or claims.get("urn:zitadel:iam:user:resourceowner:primary_domain"),
        "organization_id": claims.get("urn:zitadel:iam:user:resourceowner:id"),
    }


def store_oidc_session(request: Request, token: dict[str, Any], claims: dict[str, Any]) -> None:
    request.session["user"] = get_user_info(claims)
    request.session["roles"] = get_roles_from_claims(claims)
    request.session["access_token"] = token.get("access_token")
    request.session["id_token"] = token.get("id_token")
    request.session["refresh_token"] = token.get("refresh_token")


def clear_oidc_session(request: Request) -> None:
    request.session.clear()
