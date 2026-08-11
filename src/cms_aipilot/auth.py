"""Admin login credentials/JWT helpers for SDLCAIP1-10.

Exposes `decode_access_token` for downstream consumers (e.g. SDLCAIP1-11's
FastAPI dependency) to validate a bearer token without needing to know about
the `jwt` package's exception hierarchy.

SSM parameter values (JWT secret, admin username, admin password hash) are
fetched once per process and cached via `functools.lru_cache` — Lambda
cold-start caching, not a per-request SSM call.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import boto3
import jwt

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(hours=8)


def _get_ssm_parameter(env_var_name: str) -> str:
    """Fetch a SecureString SSM parameter, given the env var holding its name."""
    parameter_name = os.environ[env_var_name]
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
    return response["Parameter"]["Value"]


@lru_cache
def get_jwt_secret() -> str:
    return _get_ssm_parameter("JWT_SECRET_SSM_PARAM")


@lru_cache
def get_admin_username() -> str:
    return _get_ssm_parameter("ADMIN_USERNAME_SSM_PARAM")


@lru_cache
def get_admin_password_hash() -> str:
    return _get_ssm_parameter("ADMIN_PASSWORD_HASH_SSM_PARAM")


def create_access_token(subject: str) -> str:
    """Create an HS256-signed JWT for `subject`, valid for 8 hours."""
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRE,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Validate JWT signature and expiry.

    Returns the decoded payload (dict, at least containing sub/iat/exp) on
    success. Returns None on any failure (bad signature, malformed token,
    expired) — never raises, so callers can convert None into a 401 without
    needing to catch specific jwt exception types.
    """
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
