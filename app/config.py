"""Application configuration loaded from environment variables."""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


# OIDC / ZITADEL
OIDC_ISSUER = _require_env("OIDC_ISSUER").rstrip("/")
OIDC_CLIENT_ID = _require_env("OIDC_CLIENT_ID")
OIDC_REDIRECT_URI = _require_env("OIDC_REDIRECT_URI")
OIDC_POST_LOGOUT_URI = _require_env("OIDC_POST_LOGOUT_URI")

# Sessions
SESSION_SECRET = _require_env("SESSION_SECRET")
if len(SESSION_SECRET) < 32:
    raise RuntimeError("SESSION_SECRET must be at least 32 characters")

# Application
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8088"))
APP_ROOT_PATH = os.getenv("APP_ROOT_PATH", "").rstrip("/")

# Session cookie security. Disable only for local HTTP testing.
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "true").lower() in ("true", "1", "yes")

# OIDC discovery endpoint
OIDC_DISCOVERY_URL = f"{OIDC_ISSUER}/.well-known/openid-configuration"

# Scopes requested during authentication
OIDC_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "urn:zitadel:iam:org:projects:roles",
    "urn:zitadel:iam:user:resourceowner",
]
