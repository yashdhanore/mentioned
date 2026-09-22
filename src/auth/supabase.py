from __future__ import annotations

from functools import lru_cache

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from src.auth.schemas import Caller
from src.config import AuthConfig

JWKS_CACHE_LIFESPAN_SECONDS = 300


@lru_cache
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=JWKS_CACHE_LIFESPAN_SECONDS)


def verify_supabase_token(token: str, config: AuthConfig) -> Caller:
    if not config.supabase_project_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase auth is not configured",
        )

    issuer = config.supabase_project_url.rstrip("/") + "/auth/v1"
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm == "HS256":
            if not config.supabase_jwt_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Supabase JWT secret is not configured",
                )
            claims = jwt.decode(
                token,
                config.supabase_jwt_secret,
                algorithms=["HS256"],
                issuer=issuer,
                audience=config.supabase_jwt_audience,
                options={"require": ["exp", "sub"]},
            )
        elif algorithm in {"ES256", "RS256"}:
            jwks_url = issuer + "/.well-known/jwks.json"
            signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                issuer=issuer,
                audience=config.supabase_jwt_audience,
                options={"require": ["exp", "sub"]},
            )
        else:
            raise jwt.InvalidAlgorithmError("Unsupported Supabase JWT algorithm")
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        ) from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )
    role = claims.get("role")
    if role is not None and role != "authenticated":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )
    return Caller(subject_id=subject, role="user")
