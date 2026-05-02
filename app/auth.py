from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import Header, HTTPException, status
import jwt
from jwt import PyJWKClient

from app.config import Settings, get_settings


CallerRole = Literal["user", "worker", "admin"]


@dataclass(frozen=True)
class Caller:
    subject_id: str
    role: CallerRole


def worker_caller(worker_id: str = "worker") -> Caller:
    return Caller(subject_id=worker_id, role="worker")


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    return token


def _verify_supabase_token(token: str, settings: Settings) -> Caller:
    if not settings.supabase_project_url:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Supabase auth is not configured")

    issuer = settings.supabase_project_url.rstrip("/") + "/auth/v1"
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm == "HS256":
            if not settings.supabase_jwt_secret:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Supabase JWT secret is not configured")
            claims = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                issuer=issuer,
                audience=settings.supabase_jwt_audience,
                options={"require": ["exp", "sub"]},
            )
        elif algorithm in {"ES256", "RS256"}:
            jwks_url = issuer + "/.well-known/jwks.json"
            signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                issuer=issuer,
                audience=settings.supabase_jwt_audience,
                options={"require": ["exp", "sub"]},
            )
        else:
            raise jwt.InvalidAlgorithmError("Unsupported Supabase JWT algorithm")
    except HTTPException:
        raise
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    return Caller(subject_id=subject, role="user")


def get_current_caller(authorization: str | None = Header(default=None)) -> Caller:
    settings = get_settings()
    if settings.auth_mode == "dev":
        if authorization is None:
            return Caller(subject_id=settings.dev_user_id, role="user")
        token = _bearer_token(authorization)
        if token.startswith("dev:"):
            return Caller(subject_id=token.removeprefix("dev:"), role="user")
        return Caller(subject_id=settings.dev_user_id, role="user")
    if settings.auth_mode != "supabase":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unsupported auth mode")
    return _verify_supabase_token(_bearer_token(authorization), settings)
